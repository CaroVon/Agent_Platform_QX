"""
============================================================
AI Product Studio API
—— POST /api/v1/product/create 等多 Agent 产品资产包端点
============================================================

流水线（agent-platform LangGraph 工作流）:
  Requirement Parser → Research → Competitor Analysis → Strategy → Design → Presentation

创建后异步执行（Celery），前端轮询 GET /api/v1/product/{id} 获取
结构化资产包（research / strategy / design / presentation ...）。
"""

from __future__ import annotations

import json
import hashlib
import logging
import os
import uuid
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, Response, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.studio_product import StudioProduct, StudioProductStatus
from app.models.user import User
from app.schemas import (
    ExportPdfResponse,
    PresentationUpdateRequest,
    ProductAssetResponse,
    ProductCreateRequest,
    ProductCreateResponse,
    ProductImageSearchRequest,
    ProductImageSearchResponse,
    ProductImageResult,
    ProductKeywordsUpdateRequest,
    ProductKeywordsUpdateResponse,
    ProductListResponse,
)
from app.llm.prompts import PRODUCT_CLARIFY_SYSTEM as _CLARIFY_SYSTEM
from app.services.ppt_asset_recovery import (
    build_ppt_asset_index,
    build_svg_preview_urls,
    latest_pptx,
    match_asset_for_product,
)
from app.tasks.product_studio_tasks import run_product_studio_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/product", tags=["product-studio"])

_ASSET_KEYS = (
    "requirement",
    "research",
    "competitor_matrix",
    "competitor_analysis",
    "strategy",
    "design",
    "presentation",
    "ppt_design",
)


def _parse_keywords(raw: str | None) -> dict[str, list[str]] | None:
    """解析 keywords 列 JSON（方面 → 关键词列表）；非法/空返回 None。"""
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return {
        str(k): [str(w) for w in v if isinstance(w, str)]
        for k, v in data.items()
        if isinstance(v, list)
    }


def _to_asset_response(product: StudioProduct) -> ProductAssetResponse:
    """ORM → 资产包响应（解析 asset_package JSON，按节点拆出结构化资产）。"""
    package: dict = {}
    if product.asset_package:
        try:
            package = json.loads(product.asset_package)
        except json.JSONDecodeError:
            package = {}

    meta = package.get("meta") or {}
    base = {
        "product_id": str(product.id),
        "idea": product.idea,
        "status": product.status.value,
        "error_message": product.error_message,
        "created_at": product.created_at.isoformat() if product.created_at else None,
        "updated_at": product.updated_at.isoformat() if product.updated_at else None,
        "node_status": {
            **(meta.get("node_status") or {}),
            **(json.loads(product.node_status or "{}") or {}),
        },
        "node_models": meta.get("node_models") or {},
        "errors": meta.get("errors") or {},
        "critic_score": package.get("critic_score"),
        "gate_report": package.get("gate_report"),
        # C5: 各节点模型 token 用量（成本可观测）
        "usage": package.get("usage"),
        # Key Words：独立列优先（用户编辑后的最新值），缺失时回退资产包内记录
        "keywords": _parse_keywords(product.keywords) or package.get("keywords"),
    }
    for key in _ASSET_KEYS:
        base[key] = package.get(key)
    # 后端 SVG 是最终 PPT 的真实视觉产物。即使 asset_package 已记录 ppt_design，
    # 也重新从其 pptx_relative 定位 svg_final，避免前端展示另一套 DSL 缩略图。
    ppt_design = base.get("ppt_design")
    if ppt_design and ppt_design.get("pptx_relative"):
        pptx_relative = Path(ppt_design["pptx_relative"])
        if not pptx_relative.is_absolute():
            output_dir = Path(get_settings().OUTPUT_DIR).resolve()
            project_dir = output_dir / pptx_relative.parent.parent
            latest = latest_pptx(project_dir)
            previews = build_svg_preview_urls(project_dir)
            corrected = dict(ppt_design)
            if latest:
                corrected["pptx_path"] = str(latest)
                corrected["pptx_relative"] = str(latest.relative_to(output_dir))
            if previews:
                corrected["svg_previews"] = previews
            base["ppt_design"] = corrected
    # P7: disk 资产对账 —— 当资产包没有 ppt_design（早期 bug / 超时重投递丢失）但磁盘仍有
    # 有效 PPTX 时，恢复合并进响应（只读，不改 asset_package / node_status）。
    # 匹配服务内部按「强信号（UUID/title）+ 弱信号（idea 前缀 + 时间窗）」
    # 严格判定归属，同名产品跨天不会误配，因此不再要求 presentation 已存在。
    if not base.get("ppt_design") or not base["ppt_design"].get("pptx_relative"):
        recovered = match_asset_for_product(
            str(product.id),
            idea=product.idea,
            presentation_title=(package.get("presentation") or {}).get("title") or "",
            created_at_utc=(product.created_at.isoformat() if product.created_at else None),
            updated_at_utc=(product.updated_at.isoformat() if product.updated_at else None),
        )
        if recovered:
            base["ppt_design"] = recovered
    # P8: 状态归一化 —— 资产最终可用（原生或恢复）时，节点不应显示为「失败/进行中」。
    # 已恢复资产 → recovered（前端按成功/绿色呈现）；纯节点失败仅当无可交付资产时保留。
    # 产品已 completed 时，残留 running（进度快照滞后于实际）也一并收敛为最终态。
    product_done = product.status.value == StudioProductStatus.COMPLETED.value
    ppt_ready = bool((base.get("ppt_design") or {}).get("pptx_relative"))
    for node, asset_ready in (
        ("ppt_design", ppt_ready),
        ("presentation", bool(base.get("presentation"))),
    ):
        node_status = base.setdefault("node_status", {})
        current = node_status.get(node)
        if current is None:
            continue
        target = "recovered" if node == "ppt_design" else "completed"
        if asset_ready and (current == "failed" or (product_done and current == "running")):
            node_status[node] = target
            base.setdefault("errors", {}).pop(node, None)
        elif not asset_ready and product_done and current == "running":
            # 产品已收尾但该节点未产出资产：running 快照已无意义，收敛为 failed
            node_status[node] = "failed"
    # 顺带清理：最终 completed 节点不应残留错误条目（避免前端错误清单误报）
    errors_map = base.setdefault("errors", {})
    for node, state in base["node_status"].items():
        if state in ("completed", "recovered") and node in errors_map:
            errors_map.pop(node, None)
    base["document"] = package.get("document")
    return ProductAssetResponse(**base)


@router.post("/create", response_model=ProductCreateResponse, status_code=201)
async def create_product(
    body: ProductCreateRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: User = Depends(get_current_user),
):
    """
    创建产品并触发多 Agent 流水线（异步）。

    请求示例: {"idea": "Build an AI fitness application"}
    可通过 Idempotency-Key 复用同一次请求；未提供时服务端按规范化 idea 自动生成。
    完成后通过 GET /api/v1/product/{product_id} 获取
    {research, strategy, design, presentation} 结构化资产包。
    """
    idea = " ".join(body.idea.split())
    if not idea:
        raise HTTPException(status_code=422, detail="产品想法不能为空")
    normalized_idea = idea.casefold()
    idea_hash = hashlib.sha256(normalized_idea.encode("utf-8")).hexdigest()
    request_key = (idempotency_key or idea_hash).strip()
    if not request_key or len(request_key) > 128:
        raise HTTPException(status_code=400, detail="Idempotency-Key 无效")

    async def _find_existing() -> StudioProduct | None:
        result = await db.execute(
            select(StudioProduct).where(
                or_(
                    StudioProduct.idea_hash == idea_hash,
                    StudioProduct.idempotency_key == request_key,
                    StudioProduct.idea == idea,
                )
            ).order_by(StudioProduct.created_at.asc())
        )
        candidates = result.scalars().all()
        # 兼容幂等字段加入前创建的旧记录，并避免把 key 错配到另一想法。
        for candidate in candidates:
            if candidate.idempotency_key == request_key:
                candidate_idea = " ".join(candidate.idea.split()).casefold()
                if candidate.idea_hash not in (None, idea_hash) or candidate_idea != normalized_idea:
                    raise HTTPException(
                        status_code=409,
                        detail="Idempotency-Key 已用于其他产品想法",
                    )
                return candidate
            if candidate.idea_hash == idea_hash:
                return candidate
            if " ".join(candidate.idea.split()).casefold() == normalized_idea:
                return candidate
        return None

    product = await _find_existing()
    duplicate = product is not None
    if not duplicate:
        product = StudioProduct(
            idea=idea,
            idempotency_key=request_key,
            idea_hash=idea_hash,
            status=StudioProductStatus.QUEUED,
            owner_id=user.id,
            theme_id=(body.theme_id or None) or None,
            style_id=(body.style_id or None) or None,
        )
        db.add(product)
        try:
            await db.commit()
        except IntegrityError:
            # 两个请求可能同时通过预查询；唯一索引负责最终仲裁。
            await db.rollback()
            product = await _find_existing()
            if product is None:
                raise
            duplicate = True
        if not duplicate:
            await db.refresh(product)

    if duplicate:
        response.status_code = 200
    else:
        celery_task = run_product_studio_pipeline.delay(str(product.id))
        # 持久化任务 ID（供取消/追踪）；失败不阻断创建
        product.celery_task_id = celery_task.id
        await db.commit()
        logger.info(
            "[Product Studio] product=%s | idea=%s | celery=%s",
            product.id, product.idea, celery_task.id,
        )
    return ProductCreateResponse(
        product_id=str(product.id),
        idea=product.idea,
        status=product.status.value,
    )


@router.get("/ppt-options", response_model=dict)
async def get_ppt_options(user: User = Depends(get_current_user)):
    """模板选择器数据源：设计主题（9 套，含预览图路径）+ 风格方法论（13 套）。"""
    from app.services.ppt_options import ppt_options

    return ppt_options()


@router.get("/ppt-assets", response_model=list[dict])
async def list_ppt_assets_index():
    """PPT 资产库：扫描 outputs/studio_assets/ppt_projects 全部磁盘资产。

    返回：{folder_name, title, pptx_url, size, svg_count, created_at, svg_previews}
    供前端「PPT 资产库」浏览 / 审计用途（只读）。
    """
    return build_ppt_asset_index()


@router.get("/{product_id}/ppt-recovery")
async def get_product_ppt_recovery(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """恢复视角：该产品在磁盘上的 PPT 资产（即使 asset_package 未记录）。"""
    product = await db.get(StudioProduct, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="产品不存在")
    try:
        package = json.loads(product.asset_package or "{}")
    except json.JSONDecodeError:
        package = {}
    recovered = match_asset_for_product(
        str(product.id),
        idea=product.idea,
        presentation_title=(package.get("presentation") or {}).get("title") or "",
        created_at_utc=(product.created_at.isoformat() if product.created_at else None),
        updated_at_utc=(product.updated_at.isoformat() if product.updated_at else None),
    )
    return {
        "product_id": str(product.id),
        "idea": product.idea,
        "recovered": recovered or None,
        "native": (package.get("ppt_design") or {}).get("pptx_relative"),
    }


@router.get("", response_model=list[ProductListResponse])
async def list_products(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """产品列表（按创建时间倒序，仅当前用户；兼容旧记录 owner 为空）。"""
    result = await db.execute(
        select(StudioProduct)
        .where(or_(
            StudioProduct.owner_id == user.id,
            StudioProduct.owner_id.is_(None),
        ))
        .order_by(StudioProduct.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    products = result.scalars().all()
    return [
        ProductListResponse(
            product_id=str(p.id),
            idea=p.idea,
            status=p.status.value,
            created_at=p.created_at.isoformat() if p.created_at else None,
            keywords=_parse_keywords(p.keywords),
        )
        for p in products
    ]


@router.get("/{product_id}", response_model=ProductAssetResponse)
async def get_product(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """获取产品资产包（前端轮询此端点直至 status=completed/failed）。"""
    product = await db.get(StudioProduct, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="产品不存在")
    # 兼容旧记录 owner 为空（视为当前用户所有）
    if product.owner_id is not None and product.owner_id != user.id:
        raise HTTPException(status_code=403, detail="无权访问该产品")
    return _to_asset_response(product)


async def _export_via_node(product_id: str, fmt: str, out_path: Path) -> dict:
    """P4: 调用 Node 导出脚本（Playwright PDF / PptxGenJS PPTX）。

    与 Web 预览共用同一 React 渲染源（WYSIWYG）；
    脚本 stdout 最后一行输出浏览器侧质量门 JSON 报告。

    注意：subprocess 必须在独立线程执行（run_in_executor）——
    Node 脚本会反向请求本后端（/export 路由 / 产品 API），
    若阻塞事件循环会形成死锁。
    """
    import asyncio
    import functools
    import shutil
    import subprocess

    # backend/app/api/v1/endpoints/product.py → parents[5] = QX_project_root
    frontend_dir = Path(__file__).resolve().parents[5] / "frontend"
    script = frontend_dir / "scripts" / "export-pdf.mjs"
    if not script.is_file():
        raise HTTPException(status_code=500, detail="导出脚本缺失（frontend/scripts/export-pdf.mjs）")

    node = shutil.which("node") or "node"
    settings = get_settings()
    base_url = settings.EXPORT_BASE_URL or "http://127.0.0.1:8000"

    cmd = [
        node, str(script), product_id,
        "--base-url", base_url,
        "--out", str(out_path),
        "--format", fmt,
    ]
    runner = functools.partial(
        subprocess.run,
        cmd,
        cwd=str(frontend_dir),
        capture_output=True,
        text=True,
        timeout=settings.EXPORT_TIMEOUT,
    )
    try:
        loop = asyncio.get_running_loop()
        proc = await loop.run_in_executor(None, runner)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="导出超时")

    if proc.returncode != 0 or not out_path.is_file():
        logger.error("导出失败 returncode=%s stdout=%s stderr=%s",
                     proc.returncode, proc.stdout[-400:], proc.stderr[-400:])
        detail = proc.stderr[-300:] or proc.stdout[-300:] or "未知错误"
        raise HTTPException(status_code=500, detail=f"导出失败: {detail}")

    # stdout 最后一行非空 JSON = 质量门报告
    gate: dict = {}
    for line in reversed(proc.stdout.strip().splitlines()):
        try:
            gate = json.loads(line.strip())
            break
        except json.JSONDecodeError:
            continue
    return gate


def _export_weasyprint_fallback(package: dict, pdf_path: Path) -> dict:
    """旧版资产包（slides 格式）兜底：WeasyPrint 渲染（P0 已修复完整度）。"""
    from app.services.studio_render import slides_to_pdf

    slides_to_pdf(package, str(pdf_path))
    return {}


@router.post("/{product_id}/export-pdf", response_model=ExportPdfResponse)
async def export_product_pdf(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    将演示资产渲染为 16:9 PDF。

    - 新版 Presentation DSL（pages）→ Playwright 打印 /export/{id}
      （与 Web 预览同一 React 渲染源 + 浏览器侧溢出质量门）
    - 旧版 SlideDeck（slides）→ WeasyPrint 兜底
    """
    product = await db.get(StudioProduct, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="产品不存在")
    if product.status != StudioProductStatus.COMPLETED or not product.asset_package:
        raise HTTPException(status_code=409, detail="产品资产包尚未生成完成")

    package = json.loads(product.asset_package)
    presentation = package.get("presentation") or {}
    if not presentation.get("pages") and not presentation.get("slides"):
        raise HTTPException(status_code=422, detail="资产包中无演示内容")

    settings = get_settings()
    out_dir = Path(settings.OUTPUT_DIR).resolve() / "studio_assets"
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / f"{product_id}.pdf"

    if presentation.get("pages"):
        gate = await _export_via_node(str(product_id), "pdf", pdf_path)
        overflow = len(gate.get("overflow_pages") or [])
        message = f"PDF 导出成功（Playwright）| 页数 {gate.get('pages')} | 溢出页 {overflow}"
    else:
        gate = _export_weasyprint_fallback(package, pdf_path)
        message = "PDF 导出成功（WeasyPrint 兜底）"

    # 质量门报告落盘（供审计）
    with (out_dir / f"{product_id}_gate.json").open("w", encoding="utf-8") as f:
        json.dump(gate, f, ensure_ascii=False)

    return ExportPdfResponse(
        product_id=str(product_id),
        pdf_url=f"/api/v1/files/studio_assets/{product_id}.pdf",
        message=message,
    )


@router.post("/{product_id}/export-html", response_model=ExportPdfResponse)
async def export_product_html(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """导出单文件 HTML 快照（与网页预览 100% 一致的独立展示文件）。"""
    product = await db.get(StudioProduct, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="产品不存在")
    if product.status != StudioProductStatus.COMPLETED or not product.asset_package:
        raise HTTPException(status_code=409, detail="产品资产包尚未生成完成")

    package = json.loads(product.asset_package)
    presentation = package.get("presentation") or {}
    if not presentation.get("pages"):
        raise HTTPException(status_code=422, detail="HTML 导出仅支持新版 Presentation DSL")

    settings = get_settings()
    out_dir = Path(settings.OUTPUT_DIR).resolve() / "studio_assets"
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / f"{product_id}.html"

    gate = await _export_via_node(str(product_id), "html", html_path)

    return ExportPdfResponse(
        product_id=str(product_id),
        pdf_url=f"/api/v1/files/studio_assets/{product_id}.html",
        message=f"HTML 导出成功 | 页数 {gate.get('pages', len(presentation['pages']))}",
    )


@router.patch("/{product_id}/presentation")
async def update_presentation(
    product_id: uuid.UUID,
    body: PresentationUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """演示编辑器保存：回写 Presentation DSL 到资产包。"""
    product = await db.get(StudioProduct, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="产品不存在")
    if not product.asset_package:
        raise HTTPException(status_code=409, detail="产品资产包尚未生成")

    package = json.loads(product.asset_package)
    package["presentation"] = body.presentation
    product.asset_package = json.dumps(package, ensure_ascii=False)
    await db.commit()
    return {"detail": "演示已更新"}


# ================================================================
# Key Words —— 产品关键词组（任务完成后 AI 总结，用户可编辑）
# ================================================================

@router.put("/{product_id}/keywords", response_model=ProductKeywordsUpdateResponse)
async def update_product_keywords(
    product_id: uuid.UUID,
    body: ProductKeywordsUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """整体替换产品的关键词组（用户编辑入口）。

    keywords 同时写入独立列（studio_products.keywords）与资产包
    （asset_package.keywords），作为产品资产的一部分随详情接口返回。
    """
    product = await db.get(StudioProduct, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="产品不存在")
    if product.owner_id is not None and product.owner_id != user.id:
        raise HTTPException(status_code=403, detail="无权访问该产品")

    from app.services.product_keywords import _normalize_keywords

    groups = _normalize_keywords(body.keywords)
    # 未知分组键不丢弃：保留原样（防御前端扩展），但统一为字符串列表
    for key, values in body.keywords.items():
        if key not in groups and isinstance(values, list):
            groups[key] = [str(v).strip() for v in values if str(v).strip()]

    product.keywords = json.dumps(groups, ensure_ascii=False)
    # 手动编辑标记：后续 regenerate 不再自动重算 keywords
    product.keywords_edited = True
    if product.asset_package:
        try:
            package = json.loads(product.asset_package)
        except json.JSONDecodeError:
            package = {}
        package["keywords"] = groups
        product.asset_package = json.dumps(package, ensure_ascii=False, default=str)
    await db.commit()
    logger.info("[Product Keywords] 用户编辑保存 | product=%s | 组数=%d",
                product_id, len(groups))
    return ProductKeywordsUpdateResponse(
        product_id=str(product.id),
        keywords=groups,
    )


@router.get("/{product_id}/assets")
async def list_product_assets(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """DesignStudio 资产库：列出产品图片资产（生图/上传共用目录）。"""
    product = await db.get(StudioProduct, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="产品不存在")
    settings = get_settings()
    asset_dir = Path(settings.OUTPUT_DIR).resolve() / "assets" / str(product_id)
    items = []
    if asset_dir.is_dir():
        for f in sorted(asset_dir.iterdir()):
            if f.is_file() and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
                items.append({
                    "name": f.name,
                    "url": f"/api/v1/files/assets/{product_id}/{f.name}",
                    "size": f.stat().st_size,
                })
    return {"assets": items}


@router.post("/{product_id}/search-images", response_model=ProductImageSearchResponse)
async def search_product_images(
    product_id: uuid.UUID,
    body: ProductImageSearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """编辑器素材搜索（无状态）：DuckDuckGo 搜索，结果不持久化。"""
    product = await db.get(StudioProduct, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="产品不存在")

    try:
        from app.search.image_search import search_images
        results = search_images(body.query, max_results=body.max_results)
    except Exception as e:
        logger.error("素材搜索失败 | product=%s | query=%s | error=%s", product_id, body.query, str(e))
        raise HTTPException(status_code=500, detail=f"图片搜索失败: {str(e)}")

    images = [
        ProductImageResult(
            id=f"img-{idx}",
            query=body.query,
            title=r.get("title", ""),
            image_url=r.get("image", ""),
            source_url=r.get("url") or None,
        )
        for idx, r in enumerate(results)
        if r.get("image")
    ]
    return ProductImageSearchResponse(images=images, total_count=len(images))


@router.post("/{product_id}/assets")
async def upload_product_asset(
    product_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """编辑器本地上传：保存图片至静态目录，返回公开访问 URL。"""
    product = await db.get(StudioProduct, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="产品不存在")

    settings = get_settings()
    asset_dir = Path(settings.OUTPUT_DIR) / "assets" / str(product_id)
    asset_dir.mkdir(parents=True, exist_ok=True)

    file_ext = os.path.splitext(file.filename or "image.png")[1] or ".png"
    safe_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = asset_dir / safe_filename
    content = await file.read()
    file_path.write_bytes(content)

    logger.info("编辑器素材已保存 | product=%s | filename=%s | size=%d",
                product_id, safe_filename, len(content))
    return {"url": f"/api/v1/files/assets/{product_id}/{safe_filename}"}


@router.post("/{product_id}/export-pptx", response_model=ExportPdfResponse)
async def export_product_pptx(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """导出 PPTX（PptxGenJS，可继续编辑的交付物；仅支持新版 DSL）。"""
    product = await db.get(StudioProduct, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="产品不存在")
    if product.status != StudioProductStatus.COMPLETED or not product.asset_package:
        raise HTTPException(status_code=409, detail="产品资产包尚未生成完成")

    package = json.loads(product.asset_package)
    presentation = package.get("presentation") or {}
    if not presentation.get("pages"):
        raise HTTPException(status_code=422, detail="PPTX 导出仅支持新版 Presentation DSL")

    settings = get_settings()
    out_dir = Path(settings.OUTPUT_DIR).resolve() / "studio_assets"
    out_dir.mkdir(parents=True, exist_ok=True)
    pptx_path = out_dir / f"{product_id}.pptx"

    # P6: 优先返回 ppt-master（PptDesignAgent）产出的原生可编辑 PPTX
    # 始终取项目 exports/ 目录最新 mtime 的导出（DB 里的 pptx_relative 可能
    # 指向被外科修复/重导出取代的旧文件），DB 记录仅作目录定位线索
    import re as _re_mod

    ppt_design = package.get("ppt_design") or {}
    pptx_relative = ppt_design.get("pptx_relative")
    candidates: list[Path] = []
    if pptx_relative:
        rel_dir = Path(settings.OUTPUT_DIR).resolve().joinpath(pptx_relative).parent
        if rel_dir.is_dir():
            candidates += [p for p in rel_dir.glob("*.pptx") if p.is_file()]
            candidates += [p for p in rel_dir.parent.glob("*.pptx") if p.is_file()]
    # 兜底：按产品定位项目目录扫 exports/
    if not candidates:
        key = _re_mod.sub(r"[^A-Za-z0-9._-]+", "_", str(product_id)).strip("._")[:80]
        base = Path(settings.OUTPUT_DIR).resolve() / "studio_assets" / "ppt_projects"
        for d in filter(lambda x: x.is_dir(), [base / key, *base.glob(f"{key}*")]):
            candidates += [p for p in d.glob("exports/*.pptx") if p.is_file()]
            candidates += [p for p in d.glob("*.pptx") if p.is_file()]
    latest = max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None
    if latest is not None:
        rel_latest = str(latest.relative_to(Path(settings.OUTPUT_DIR).resolve()))
        return ExportPdfResponse(
            product_id=str(product_id),
            pdf_url=f"/api/v1/files/{rel_latest.replace(os.sep, '/')}",
            message=(
                f"PPTX 导出成功（ppt-master 原生）| 页数 {ppt_design.get('pages', len(presentation['pages']))}"
                f" | 模型 {ppt_design.get('model', '')}"
            ),
        )

    gate = await _export_via_node(str(product_id), "pptx", pptx_path)

    # CyberPPT QA 门禁：validate_pptx.py（MIT，见 scripts/pptx_qa/LICENSE）
    # 结果写入响应 message（不阻断导出；错误级别条目记日志）
    qa_text = ""
    try:
        import asyncio
        import functools
        import subprocess
        import tempfile

        qa_script = Path(__file__).resolve().parents[4] / "scripts" / "pptx_qa" / "validate_pptx.py"
        manifest = pptx_path.with_suffix(".pptx.manifest.json")
        qa_out = Path(tempfile.gettempdir()) / f"pptx_qa_{product_id}.json"
        import sys
        qa_cmd = [sys.executable, str(qa_script), str(pptx_path), "--json-out", str(qa_out)]
        if manifest.is_file():
            qa_cmd += ["--manifest", str(manifest)]
        loop = asyncio.get_running_loop()
        qa_proc = await loop.run_in_executor(
            None,
            functools.partial(subprocess.run, qa_cmd, capture_output=True, text=True, timeout=60),
        )
        if qa_proc.returncode == 0 and qa_out.is_file():
            qa = json.loads(qa_out.read_text())
            qa_errors = len(qa.get("errors") or [])
            qa_warnings = len(qa.get("warnings") or [])
            qa_text = f" | QA:{qa.get('summary', {}).get('slide_count', '?')}页/errors {qa_errors}/warnings {qa_warnings}"
            if qa_errors:
                logger.warning("PPTX QA errors | product=%s | %s", product_id, qa["errors"][:2])
    except Exception as exc:  # noqa: BLE001 —— QA 门禁不阻断导出
        logger.warning("PPTX QA 门禁执行失败: %s", exc)

    return ExportPdfResponse(
        product_id=str(product_id),
        pdf_url=f"/api/v1/files/studio_assets/{product_id}.pptx",
        message=(
            f"PPTX 导出成功 | 页数 {gate.get('pages', len(presentation['pages']))}"
            f" | 图表嵌入 {gate.get('charts_embedded', 0)}{qa_text}"
        ),
    )


# ================================================================
# POST /api/v1/product/{product_id}/cancel —— 取消流水线
# ================================================================

@router.post("/{product_id}/cancel")
async def cancel_product(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """取消进行中的产品流水线：撤销 Celery 任务并置为 failed（原因=用户取消）。"""
    from app.core.celery_ops import revoke_active_tasks_for, revoke_task

    product = await db.get(StudioProduct, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="产品不存在")
    if product.owner_id is not None and product.owner_id != user.id:
        raise HTTPException(status_code=403, detail="无权访问该产品")
    if product.status in (StudioProductStatus.COMPLETED, StudioProductStatus.FAILED):
        raise HTTPException(
            status_code=409,
            detail=f"产品已处于 {product.status.value} 状态，无法取消",
        )

    revoke_task(product.celery_task_id)
    revoke_active_tasks_for(str(product.id))

    product.status = StudioProductStatus.FAILED
    product.error_message = "用户取消"
    await db.commit()
    return {"product_id": str(product.id), "status": "cancelled", "message": "产品流水线已取消"}


@router.post("/{product_id}/pause")
async def pause_product(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """暂停产品流水线，保留已有资产；当前外部调用结束后不再落库为 completed。"""
    from app.core.celery_ops import revoke_active_tasks_for, revoke_task

    product = await db.get(StudioProduct, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="产品不存在")
    if product.owner_id is not None and product.owner_id != user.id:
        raise HTTPException(status_code=403, detail="无权访问该产品")
    if product.status not in (StudioProductStatus.QUEUED, StudioProductStatus.RUNNING):
        raise HTTPException(status_code=409, detail=f"产品当前状态为 {product.status.value}，无法暂停")

    revoke_task(product.celery_task_id)
    revoke_active_tasks_for(str(product.id))
    product.status = StudioProductStatus.PAUSED
    product.error_message = "用户暂停"
    await db.commit()
    return {"product_id": str(product.id), "status": "paused", "message": "产品流水线已暂停"}


@router.post("/{product_id}/resume")
async def resume_product(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """恢复已暂停的产品流水线，从已保存的断点/资产状态继续。"""
    product = await db.get(StudioProduct, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="产品不存在")
    if product.owner_id is not None and product.owner_id != user.id:
        raise HTTPException(status_code=403, detail="无权访问该产品")
    if product.status != StudioProductStatus.PAUSED:
        raise HTTPException(status_code=409, detail=f"产品当前状态为 {product.status.value}，无法恢复")

    product.status = StudioProductStatus.QUEUED
    product.error_message = None
    await db.commit()
    from app.tasks.product_studio_tasks import run_product_studio_pipeline
    task = run_product_studio_pipeline.delay(str(product.id))
    product.celery_task_id = task.id
    await db.commit()
    return {"product_id": str(product.id), "status": "queued", "message": "产品流水线已恢复"}


# ================================================================
# GET /api/v1/product/{product_id}/logs —— 真实执行事件日志
# ================================================================

@router.get("/{product_id}/logs")
async def get_product_logs(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """返回产品流水线的真实执行事件日志（节点/状态/明细/时间）。"""
    product = await db.get(StudioProduct, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="产品不存在")
    if product.owner_id is not None and product.owner_id != user.id:
        raise HTTPException(status_code=403, detail="无权访问该产品")
    logs: list[dict] = []
    for line in (product.progress_log or "").splitlines():
        if not line.strip():
            continue
        try:
            logs.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return {"product_id": str(product.id), "logs": logs}


# ================================================================
# 资产局部重生成 + 版本历史（Phase B：资产可编辑闭环）
# ================================================================

@router.post("/{product_id}/regenerate")
async def regenerate_product_asset(
    product_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """用附加指令局部重生成单个资产（research/strategy/design/presentation…），
    旧版本自动进入版本历史。"""
    from app.services.product_regenerate import regenerate_asset, snapshot_version

    asset = (body.get("asset") or "").strip()
    instruction = (body.get("instruction") or "").strip()

    product = await db.get(StudioProduct, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="产品不存在")
    if product.owner_id is not None and product.owner_id != user.id:
        raise HTTPException(status_code=403, detail="无权访问该产品")
    if product.status != StudioProductStatus.COMPLETED:
        raise HTTPException(status_code=409, detail="仅已完成的产品支持局部重生成")

    try:
        package = json.loads(product.asset_package or "{}")
    except json.JSONDecodeError:
        package = {}

    old_data = package.get(asset)
    import asyncio  # 局部导入：模块级未引入（to_thread 需要）

    ok, result = await asyncio.to_thread(regenerate_asset, product, asset, instruction)
    if not ok:
        raise HTTPException(status_code=422, detail=str(result))

    # 快照旧版本 → 更新资产包
    try:
        versions = json.loads(product.asset_versions or "{}")
    except json.JSONDecodeError:
        versions = {}
    versions = snapshot_version(versions, asset, old_data)
    product.asset_versions = json.dumps(versions, ensure_ascii=False)

    package[asset] = result
    product.asset_package = json.dumps(package, ensure_ascii=False)
    await db.commit()

    # MOD（竞品矩阵）重生成后：keywords 自动重算（用户手动编辑过则跳过）
    keywords_refreshed = None
    if asset == "competitor_matrix":
        try:
            from app.services.product_keywords import refresh_keywords_if_auto

            keywords_refreshed = await asyncio.to_thread(
                refresh_keywords_if_auto, str(product_id))
        except Exception as exc:  # noqa: BLE001 —— 重算失败不影响 regenerate 结果
            keywords_refreshed = {"refreshed": False, "reason": str(exc)[:120]}

    return {
        "product_id": str(product.id),
        "asset": asset,
        "updated": True,
        "versions": len(versions.get(asset) or []),
        "keywords_refreshed": keywords_refreshed,
    }


@router.get("/{product_id}/versions")
async def get_product_versions(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """资产版本历史（各资产最多 5 版）。"""
    product = await db.get(StudioProduct, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="产品不存在")
    if product.owner_id is not None and product.owner_id != user.id:
        raise HTTPException(status_code=403, detail="无权访问该产品")
    try:
        versions = json.loads(product.asset_versions or "{}")
    except json.JSONDecodeError:
        versions = {}
    return {
        "product_id": str(product.id),
        "versions": {
            k: [{"ts": v["ts"]} for v in vs if isinstance(v, dict)]
            for k, vs in versions.items()
        },
    }


@router.post("/{product_id}/restore")
async def restore_product_asset(
    product_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """从版本历史恢复资产（回滚）。body: {asset, index}"""
    asset = (body.get("asset") or "").strip()
    index = int(body.get("index", 0))

    product = await db.get(StudioProduct, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="产品不存在")
    if product.owner_id is not None and product.owner_id != user.id:
        raise HTTPException(status_code=403, detail="无权访问该产品")
    try:
        versions = json.loads(product.asset_versions or "{}")
    except json.JSONDecodeError:
        versions = {}
    history = versions.get(asset) or []
    if index < 0 or index >= len(history):
        raise HTTPException(status_code=404, detail="版本不存在")

    version = history[index]
    package = json.loads(product.asset_package or "{}")
    # 当前版本入历史尾部（保留可逆性），恢复目标版本
    from app.services.product_regenerate import snapshot_version

    versions = snapshot_version(versions, asset, package.get(asset))
    package[asset] = version["data"]
    product.asset_package = json.dumps(package, ensure_ascii=False)
    product.asset_versions = json.dumps(versions, ensure_ascii=False)
    await db.commit()
    return {"product_id": str(product.id), "asset": asset, "restored": True}


# ================================================================
# 节点级 Plan/Act 门 —— 人工批准 / 拒绝
# ================================================================

@router.post("/{product_id}/approve-node")
async def approve_product_node(
    product_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """批准暂停节点：接受该节点产物，继续执行后续流水线。"""
    product = await db.get(StudioProduct, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="产品不存在")
    if product.owner_id is not None and product.owner_id != user.id:
        raise HTTPException(status_code=403, detail="无权访问该产品")
    if product.status != StudioProductStatus.WAITING_APPROVAL:
        raise HTTPException(status_code=409, detail="产品不在等待批准状态")

    node = (body.get("node") or "").strip()
    try:
        package = json.loads(product.asset_package or "{}")
    except json.JSONDecodeError:
        package = {}
    if package.get("_paused_node") != node:
        raise HTTPException(status_code=409, detail=f"当前等待的节点是 {package.get('_paused_node')}，不是 {node}")

    # 资料审核门：应用用户勾选的资料（selected_urls）
    if node == "source_gathering":
        selected_urls = body.get("selected_urls")
        sources = package.get("_sources_review") or []
        if selected_urls is not None:
            selected_set = set(str(u) for u in selected_urls)
            for s in sources:
                s["selected"] = s.get("url") in selected_set
            if not any(s.get("selected") for s in sources):
                raise HTTPException(status_code=422, detail="至少保留一条资料（或上传本地资料）")
            package["_sources_review"] = sources
            package["source_gathering_meta"] = {
                "total": len(sources),
                "selected": sum(1 for s in sources if s.get("selected")),
            }

    gate_passed = set(package.get("_gate_passed") or [])
    gate_passed.add(node)
    package["_gate_passed"] = sorted(gate_passed)
    package["_paused_node"] = None
    product.asset_package = json.dumps(package, ensure_ascii=False)
    product.status = StudioProductStatus.QUEUED
    product.error_message = None
    await db.commit()

    from app.tasks.product_studio_tasks import run_product_studio_pipeline
    run_product_studio_pipeline.delay(str(product.id))
    return {"product_id": str(product.id), "node": node, "approved": True, "message": "已批准，流水线继续执行"}


@router.post("/{product_id}/reject-node")
async def reject_product_node(
    product_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """拒绝暂停节点：终止流水线（产物保留为部分资产）。"""
    product = await db.get(StudioProduct, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="产品不存在")
    if product.owner_id is not None and product.owner_id != user.id:
        raise HTTPException(status_code=403, detail="无权访问该产品")
    if product.status != StudioProductStatus.WAITING_APPROVAL:
        raise HTTPException(status_code=409, detail="产品不在等待批准状态")

    node = (body.get("node") or "").strip()
    product.status = StudioProductStatus.FAILED
    product.error_message = f"用户拒绝了节点 {node}"
    await db.commit()
    return {"product_id": str(product.id), "node": node, "rejected": True, "message": "已拒绝，流水线终止"}


# ================================================================
# 资料审核（source_gathering 门）—— 读取 / 提交 / 上传本地资料
# ================================================================

@router.get("/{product_id}/events")
async def product_events(
    product_id: uuid.UUID,
    user: User = Depends(get_current_user),
):
    """SSE 进度事件流（P0.3）：订阅 Redis qx:events:{id}。

    事件：{ts, node, status, detail}；每 20s 注释心跳保活。
    """
    import asyncio

    from sse_starlette.sse import EventSourceResponse

    async def gen():
        import redis.asyncio as aioredis

        from app.core.config import get_settings

        s = get_settings()
        r = aioredis.Redis(host=s.REDIS_HOST, port=s.REDIS_PORT, db=s.REDIS_DB,
                           socket_connect_timeout=3)
        pubsub = r.pubsub()
        channel = f"qx:events:{product_id}"
        await pubsub.subscribe(channel)
        try:
            yield {"event": "open", "data": channel}
            while True:
                try:
                    msg = await asyncio.wait_for(pubsub.get_message(
                        ignore_subscribe_messages=True), timeout=20)
                except asyncio.TimeoutError:
                    yield {"comment": "keep-alive"}
                    continue
                if msg and msg.get("type") == "message":
                    yield {"event": "progress", "data": msg["data"].decode()}
        finally:
            await pubsub.unsubscribe(channel)
            await r.aclose()

    return EventSourceResponse(gen())


# ================================================================
# P0.5：页级返工（👎）—— 运行中入队 / 完成态外科单页重做
# ================================================================

@router.post("/{product_id}/ppt-rework")
async def ppt_page_rework(
    product_id: uuid.UUID,
    body: dict = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """对指定 PPT 页发起返工（携带用户反馈）。

    - 运行中（ppt_design running）：写入项目 progress.json 的
      rework_requests，创作循环在批次间消费并带反馈重做该页。
    - 完成态：调用外科单页重做服务（LLM 重创作 + 双 PPTX 重导出）。
    """
    body = body or {}
    page_index = int(body.get("page_index", 0))
    feedback = str(body.get("feedback") or "用户标记此页需要改进").strip()[:200]

    product = await db.get(StudioProduct, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="产品不存在")
    if product.owner_id is not None and product.owner_id != user.id:
        raise HTTPException(status_code=403, detail="无权访问该产品")

    import re as _re
    from pathlib import Path as _Path
    from app.core.config import get_settings

    key = _re.sub(r"[^A-Za-z0-9._-]+", "_", str(product_id)).strip("._")[:80]
    project_dir = _Path(get_settings().OUTPUT_DIR).resolve() / "studio_assets" / "ppt_projects" / key
    if not project_dir.is_dir():
        raise HTTPException(status_code=404, detail="PPT 项目目录不存在")

    try:
        _ns = json.loads(product.node_status or "{}")
    except (TypeError, ValueError):
        _ns = {}
    running = _ns.get("ppt_design") == "running"
    progress_path = project_dir / "progress.json"
    prog = {}
    try:
        prog = json.loads(progress_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        prog = {}

    if running:
        from datetime import datetime as _dt

        reqs = prog.get("rework_requests") or []
        reqs.append({"page_index": page_index, "feedback": feedback,
                     "ts": _dt.utcnow().isoformat()})
        prog["rework_requests"] = reqs
        progress_path.write_text(json.dumps(prog, ensure_ascii=False), encoding="utf-8")
        return {"product_id": str(product_id), "queued": True, "page_index": page_index}

    # 完成态：外科单页重做（线程池执行，避免阻塞事件循环）
    import asyncio

    from app.services.ppt_rework import surgical_rework_page

    pkg = json.loads(product.asset_package or "{}")
    ok, detail = await asyncio.to_thread(
        surgical_rework_page, str(product_id), pkg, page_index, feedback)
    if not ok:
        raise HTTPException(status_code=422, detail=detail)
    return {"product_id": str(product_id), "queued": False, "reworked": True,
            "page_index": page_index, "detail": detail}


@router.get("/{product_id}/ppt-progress")
async def get_product_ppt_progress(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """PPT 制作过程可视化（P5）：progress.json + svg_output 实时页清单。

    返回 {stage, total, done_pages, per_page, critic_score, revision_round,
    pages: [{index, file, url, size}], pptx_url}；无项目目录时 active=False。
    """
    import re as _re
    from urllib.parse import quote as _quote

    product = await db.get(StudioProduct, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="产品不存在")
    if product.owner_id is not None and product.owner_id != user.id:
        raise HTTPException(status_code=403, detail="无权访问该产品")
    settings = get_settings()
    out_root = Path(settings.OUTPUT_DIR).resolve()

    def _files_url(relative: str) -> str:
        parts = [_quote(p, safe="") for p in relative.split("/") if p]
        return "/api/v1/files/" + "/".join(parts)

    # 定位项目目录（与 PptDesignAgent._get_reusable_project_dir 同规则）
    key = _re.sub(r"[^A-Za-z0-9._-]+", "_", str(product_id)).strip("._")[:80]
    base = out_root / "studio_assets" / "ppt_projects"
    project_dir = None
    if (base / key).is_dir():
        project_dir = base / key
    else:
        legacy = [p for p in base.glob(f"{key}_*") if p.is_dir()]
        if legacy:
            project_dir = max(legacy, key=lambda p: p.stat().st_mtime)
    if project_dir is None:
        return {"product_id": str(product.id), "active": False, "stage": None,
                "total": 0, "done_pages": 0, "per_page": {}, "pages": []}

    progress: dict = {}
    try:
        progress = json.loads((project_dir / "progress.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        progress = {}
    pages: list[dict] = []
    svg_dir = project_dir / "svg_output"
    if svg_dir.is_dir():
        for f in sorted(svg_dir.glob("slide_*.svg")):
            m = _re.search(r"slide_(\d+)", f.name)
            pages.append({
                "index": int(m.group(1)) if m else 0,
                "file": f.name,
                "url": _files_url(str(f.relative_to(out_root))),
                "size": f.stat().st_size,
            })
    pptx_url = progress.get("pptx_url")
    if pptx_url and Path(pptx_url).is_absolute():
        try:
            pptx_url = _files_url(str(Path(pptx_url).relative_to(out_root)))
        except ValueError:
            pptx_url = None
    return {
        "product_id": str(product.id),
        "active": progress.get("stage") not in (None, "done"),
        "stage": progress.get("stage"),
        "total": progress.get("total"),
        "done_pages": progress.get("done_pages"),
        "per_page": progress.get("per_page") or {},
        "critic_score": progress.get("critic_score"),
        "revision_round": progress.get("revision_round"),
        "pages": pages,
        "pptx_url": pptx_url,
        "updated_at": progress.get("updated_at"),
    }


@router.get("/{product_id}/sources")
async def get_product_sources(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """返回待审核/已审核的资料列表（含权重）。"""
    product = await db.get(StudioProduct, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="产品不存在")
    if product.owner_id is not None and product.owner_id != user.id:
        raise HTTPException(status_code=403, detail="无权访问该产品")
    try:
        package = json.loads(product.asset_package or "{}")
    except json.JSONDecodeError:
        package = {}
    sources = package.get("_sources_review") or []
    # 统一采集层：亚马逊只读摘要（gate 展示用，不参与勾选）
    amazon = package.get("source_gathering_meta", {}).get("amazon") or \
        package.get("amazon_collection") or None
    if isinstance(amazon, dict):
        amazon.pop("data_dir", None)
        amazon.pop("out_dir", None)
    return {
        "product_id": str(product.id),
        "status": product.status.value,
        "sources": sources,
        "amazon": amazon,
        "paused_node": package.get("_paused_node"),
    }


@router.post("/{product_id}/upload-source")
async def upload_product_source(
    product_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """上传本地资料文件（PDF/TXT/MD）作为高权重补充来源（用户资料，权重最高）。"""
    import os as _os
    from pathlib import Path as _Path

    from app.core.config import get_settings as _get_settings
    from app.rag.local_parser import parse_local_pdf

    product = await db.get(StudioProduct, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="产品不存在")
    if product.owner_id is not None and product.owner_id != user.id:
        raise HTTPException(status_code=403, detail="无权访问该产品")

    raw_name = (file.filename or "").strip()
    safe_name = _Path(raw_name).name
    ext = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else ""
    settings = _get_settings()
    allowed = {e.strip().lower() for e in settings.ALLOWED_UPLOAD_EXTS.split(",") if e.strip()}
    if ext not in allowed:
        raise HTTPException(status_code=415, detail=f"不支持的文件类型 '.{ext}'，仅允许: {', '.join(sorted(allowed))}")

    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    content = b""
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        content += chunk
        if len(content) > max_bytes:
            raise HTTPException(status_code=413, detail=f"文件超过大小上限 {settings.MAX_UPLOAD_MB}MB")

    upload_dir = _os.path.join(settings.OUTPUT_DIR, "private", "product_sources", str(product.id))
    _os.makedirs(upload_dir, exist_ok=True)
    file_path = _os.path.join(upload_dir, safe_name)
    with open(file_path, "wb") as f:
        f.write(content)

    try:
        chunks = await asyncio.to_thread(parse_local_pdf, file_path, safe_name)
    except Exception as exc:  # noqa: BLE001
        try:
            _os.remove(file_path)
        except OSError:
            pass
        raise HTTPException(status_code=422, detail=f"文件解析失败: {str(exc)}")

    source_entry = {
        "title": f"本地资料：{safe_name}",
        "url": f"local://{safe_name}",
        "content": (chunks[0]["content"][:300] if chunks else ""),
        "weight": 1.0,
        "weight_label": "最高（用户资料）",
        "weight_detail": "用户上传的本地资料",
        "selected": True,
        "local": True,
        "chunk_count": len(chunks),
    }

    try:
        package = json.loads(product.asset_package or "{}")
    except json.JSONDecodeError:
        package = {}
    sources = package.get("_sources_review") or []
    # 去重：同 URL 不重复添加
    if not any(s.get("url") == source_entry["url"] for s in sources):
        sources.append(source_entry)
        package["_sources_review"] = sources
        product.asset_package = json.dumps(package, ensure_ascii=False)
        await db.commit()
    return {"product_id": str(product.id), "source": source_entry, "total": len(sources)}


# ================================================================
# 需求澄清对话（Workspace 对话式输入）—— SSE 流式
# ================================================================

class ClarifyMessage(BaseModel):
    role: Literal["user", "assistant"] = "user"
    content: str


class ClarifyRequest(BaseModel):
    idea: str = Field(default="", max_length=500, description="初始产品想法（可空，从对话开始）")
    messages: list[ClarifyMessage] = Field(default_factory=list, description="历史对话")
    max_rounds: int = Field(default=4, ge=1, le=8, description="澄清轮数上限")


# 维度覆盖关键词（规则判断，供 event: meta 信号）
_DIM_KEYWORDS = {
    "target_users": ["用户", "人群", "老人", "老年", "青年", "z世代", "白领", "家长", "学生",
                     "企业", "团队", "个人", "宝妈", "宠物主", "健身", "患者", "医生", "上班族",
                     "kids", "adult", "user", "customer"],
    "scenario": ["场景", "日常", "家里", "家中", "户外", "医院", "健身房", "通勤", "办公室",
                 "睡前", "早上", "晚上", "旅行", "露营", "厨房", "客厅", "卧室", "车里", "出行"],
    "features": ["功能", "可以", "能够", "需要", "支持", "提醒", "监测", "管理", "检测", "记录",
                 "联动", "控制", "分析", "报告", "支付", "预警", "远程", "自动", "识别", "追踪",
                 "feature", "support", "track"],
    "constraints": ["预算", "成本", "价格", "合规", "认证", "技术", "电池", "续航", "尺寸",
                    "平台", "隐私", "安全", "法规", "医疗", "审批", "网络", "离线", "免费",
                    "budget", "cost", "price", "privacy", "regulation"],
}


def _dimensions_covered(messages: list[ClarifyMessage], idea: str = "") -> dict:
    """规则判断 4 维度覆盖情况（用户消息 + 初始 idea 中命中关键词即覆盖）。"""
    covered = {k: False for k in _DIM_KEYWORDS}
    user_texts = [idea] + [m.content for m in messages if m.role == "user"]
    for text in user_texts:
        text = (text or "").lower()
        for dim, kws in _DIM_KEYWORDS.items():
            if covered[dim]:
                continue
            if any(k in text for k in kws):
                covered[dim] = True
    return covered


@router.post("/clarify")
async def clarify_product_idea(body: ClarifyRequest):
    """需求澄清对话（SSE）。

    事件：
      event: content  →  {text}            流式回复
      event: meta     →  {dimensions, enough, rounds_used}  维度覆盖信号
      event: done     →  {finish_reason}
    """
    from langchain_openai import ChatOpenAI

    settings = get_settings()
    if not settings.DEEPSEEK_API_KEY:
        raise HTTPException(status_code=503, detail="LLM API Key 未配置")

    messages: list[dict] = [{"role": "system", "content": _CLARIFY_SYSTEM}]
    if body.idea.strip():
        messages.append({"role": "user", "content": f"我的产品想法是：{body.idea.strip()}"})
    for m in body.messages:
        messages.append({"role": m.role, "content": m.content})

    llm = ChatOpenAI(
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL,
        model=settings.DEEPSEEK_MODEL,
        temperature=0.5,
        streaming=True,
    )

    def _dim_signals() -> dict:
        covered = _dimensions_covered(body.messages, body.idea)
        user_rounds = sum(1 for m in body.messages if m.role == "user")
        enough = all(covered.values()) or user_rounds >= body.max_rounds
        return {
            "dimensions": covered,
            "enough": enough,
            "rounds_used": user_rounds,
            "max_rounds": body.max_rounds,
        }

    async def event_generator():
        try:
            async for chunk in llm.astream(messages):
                if chunk.content:
                    yield f"event: content\ndata: {json.dumps({'text': chunk.content}, ensure_ascii=False)}\n\n"
            # 维度覆盖信号（前端据此决定是否亮起「生成产品」）
            yield f"event: meta\ndata: {json.dumps(_dim_signals(), ensure_ascii=False)}\n\n"
            yield f"event: done\ndata: {json.dumps({'finish_reason': 'stop'})}\n\n"
        except Exception as exc:  # noqa: BLE001
            logger.error("clarify 流式输出失败: %s", exc)
            yield f"event: error\ndata: {json.dumps({'error': str(exc)[:300]}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ================================================================
# 动态补全建议（P1）—— 输入停顿后生成 3 条产品方向建议
# ================================================================

_SUGGEST_SYSTEM = """你是产品创意顾问。根据用户已输入的部分产品想法，补全 3 条具体、可执行的产品方向建议。

要求：
- 每条建议 = 完整的一句话产品想法（含目标用户 + 核心功能），不超过 40 字
- 建议必须与用户输入的方向一致（在其基础上补充场景/功能/人群）
- 只输出 JSON：{"suggestions": ["...", "...", "..."]}，不要输出任何其他内容"""


class SuggestRequest(BaseModel):
    input: str | None = Field(default=None, min_length=2, max_length=200)
    # 兼容别名（历史前端/脚本曾传 idea）
    idea: str | None = Field(default=None, min_length=2, max_length=200)

    @property
    def text(self) -> str:
        return (self.input or self.idea or "").strip()


class SuggestResponse(BaseModel):
    suggestions: list[str] = Field(default_factory=list)


@router.post("/suggest", response_model=SuggestResponse)
async def suggest_product_directions(body: SuggestRequest):
    """基于已输入内容生成 3 条产品方向补全建议（供 SuggestionChips 动态展示）。"""
    from langchain_openai import ChatOpenAI

    settings = get_settings()
    if not settings.DEEPSEEK_API_KEY:
        return SuggestResponse(suggestions=[])
    try:
        llm = ChatOpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            model=settings.DEEPSEEK_MODEL,
            temperature=0.8,
            streaming=False,
        )
        resp = llm.invoke([
            {"role": "system", "content": _SUGGEST_SYSTEM},
            {"role": "user", "content": f"我目前的想法：{body.text}"},
        ])
        text = resp.content or ""
        # 提取 JSON
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1:
            return SuggestResponse(suggestions=[])
        data = json.loads(text[start : end + 1])
        items = [str(x).strip() for x in data.get("suggestions", []) if str(x).strip()][:3]
        return SuggestResponse(suggestions=items)
    except Exception as exc:  # noqa: BLE001 —— 建议失败不阻断主流程
        logger.warning("suggest 生成失败: %s", exc)
        return SuggestResponse(suggestions=[])
