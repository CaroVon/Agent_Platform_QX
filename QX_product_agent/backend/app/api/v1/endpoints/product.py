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
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models.studio_product import StudioProduct, StudioProductStatus
from app.schemas import (
    ExportPdfResponse,
    PresentationUpdateRequest,
    ProductAssetResponse,
    ProductCreateRequest,
    ProductCreateResponse,
    ProductListResponse,
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
        "node_status": meta.get("node_status") or {},
        "errors": meta.get("errors") or {},
        "critic_score": package.get("critic_score"),
        "gate_report": package.get("gate_report"),
    }
    for key in _ASSET_KEYS:
        base[key] = package.get(key)
    base["document"] = package.get("document")
    return ProductAssetResponse(**base)


@router.post("/create", response_model=ProductCreateResponse, status_code=201)
async def create_product(
    body: ProductCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    创建产品并触发多 Agent 流水线（异步）。

    请求示例: {"idea": "Build an AI fitness application"}
    完成后通过 GET /api/v1/product/{product_id} 获取
    {research, strategy, design, presentation} 结构化资产包。
    """
    product = StudioProduct(
        idea=body.idea.strip(),
        status=StudioProductStatus.QUEUED,
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)

    celery_task = run_product_studio_pipeline.delay(str(product.id))
    logger.info(
        "🎯 [Product Studio] product=%s | idea=%s | celery=%s",
        product.id, product.idea, celery_task.id,
    )
    return ProductCreateResponse(
        product_id=str(product.id),
        idea=product.idea,
        status=product.status.value,
    )


@router.get("", response_model=list[ProductListResponse])
async def list_products(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """产品列表（按创建时间倒序）。"""
    result = await db.execute(
        select(StudioProduct)
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
):
    """获取产品资产包（前端轮询此端点直至 status=completed/failed）。"""
    product = await db.get(StudioProduct, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="产品不存在")
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

    gate = await _export_via_node(str(product_id), "pptx", pptx_path)

    return ExportPdfResponse(
        product_id=str(product_id),
        pdf_url=f"/api/v1/files/studio_assets/{product_id}.pptx",
        message=f"PPTX 导出成功 | 页数 {gate.get('pages', len(presentation['pages']))}",
    )
