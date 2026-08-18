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

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, Response, UploadFile
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
    ProductListResponse,
)
from app.services.ppt_asset_recovery import (
    build_ppt_asset_index,
    build_svg_preview_urls,
    match_asset_for_product,
)
from app.tasks.product_studio_tasks import run_product_studio_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/product", tags=["product-studio"])

_ASSET_KEYS = (
    "requirement",
    "research",
    "competitor_analysis",
    "strategy",
    "design",
    "presentation",
    "ppt_design",
)


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
    }
    for key in _ASSET_KEYS:
        base[key] = package.get(key)
    # 后端 SVG 是最终 PPT 的真实视觉产物。即使 asset_package 已记录 ppt_design，
    # 也重新从其 pptx_relative 定位 svg_final，避免前端展示另一套 DSL 缩略图。
    ppt_design = base.get("ppt_design")
    if ppt_design and ppt_design.get("pptx_relative"):
        pptx_relative = Path(ppt_design["pptx_relative"])
        if not pptx_relative.is_absolute():
            project_dir = Path(get_settings().OUTPUT_DIR).resolve() / pptx_relative.parent.parent
            previews = build_svg_preview_urls(project_dir)
            if previews:
                base["ppt_design"] = {**ppt_design, "svg_previews": previews}
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
    ppt_design = package.get("ppt_design") or {}
    pptx_relative = ppt_design.get("pptx_relative")
    if pptx_relative and Path(settings.OUTPUT_DIR).resolve().joinpath(pptx_relative).is_file():
        from pathlib import Path as _Path

        _p = _Path(settings.OUTPUT_DIR).resolve().joinpath(pptx_relative)
        return ExportPdfResponse(
            product_id=str(product_id),
            pdf_url=f"/api/v1/files/{pptx_relative.replace(os.sep, '/')}",
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
    return {
        "product_id": str(product.id),
        "asset": asset,
        "updated": True,
        "versions": len(versions.get(asset) or []),
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
    return {
        "product_id": str(product.id),
        "status": product.status.value,
        "sources": sources,
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
