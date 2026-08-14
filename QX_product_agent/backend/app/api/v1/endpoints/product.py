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
    }
    for key in _ASSET_KEYS:
        base[key] = package.get(key)
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


@router.post("/{product_id}/export-pdf", response_model=ExportPdfResponse)
async def export_product_pdf(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    将演示资产（Slide JSON Schema）渲染为 16:9 PPT 风格 PDF。

    渲染路径: Slide JSON → 结构化 HTML → WeasyPrint PDF
    （AI 只生成结构，排版样式由后端模板控制）。
    """
    product = await db.get(StudioProduct, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="产品不存在")
    if product.status != StudioProductStatus.COMPLETED or not product.asset_package:
        raise HTTPException(status_code=409, detail="产品资产包尚未生成完成")

    package = json.loads(product.asset_package)
    slides = (package.get("presentation") or {}).get("slides") or []
    if not slides:
        raise HTTPException(status_code=422, detail="资产包中无演示内容")

    from app.services.studio_render import slides_to_pdf

    settings = get_settings()
    out_dir = Path(settings.OUTPUT_DIR) / "studio_assets"
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / f"{product_id}.pdf"

    slides_to_pdf(package, str(pdf_path))

    return ExportPdfResponse(
        product_id=str(product_id),
        pdf_url=f"/api/v1/files/studio_assets/{product_id}.pdf",
        message="PDF 导出成功",
    )
