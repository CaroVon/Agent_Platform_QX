"""
============================================================
项目资产库 API —— 每个任务的全部资产归档 / 单文件下载 / 打包下载
============================================================

REST 设计（前缀 /api/v1/project-assets）：
  GET    /                            任务资产库列表（含资产统计）
  GET    /{product_id}                任务资产库明细（惰性补产文本 md/pdf）
  GET    /{product_id}/download       打包下载全部资产（ZIP）
  单文件下载：直接使用 /api/v1/files 静态地址（文件条目中的 url 字段）
============================================================
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from urllib.parse import quote as _quote

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.studio_product import StudioProduct
from app.models.user import User
from app.services import project_assets as pa

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/project-assets", tags=["project-assets"])


async def _get_product(product_id: uuid.UUID, db: AsyncSession, user: User) -> StudioProduct:
    product = await db.get(StudioProduct, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if product.owner_id is not None and product.owner_id != user.id:
        raise HTTPException(status_code=403, detail="无权访问该任务")
    return product


def _load_package(product: StudioProduct) -> dict:
    try:
        return json.loads(product.asset_package or "{}")
    except json.JSONDecodeError:
        return {}


def _summary(product: StudioProduct, files: list[dict]) -> dict:
    total = sum(f["size"] for f in files)
    by_kind = {k: 0 for k in ("doc", "ppt", "presentation", "keywords", "image")}
    for f in files:
        by_kind[f["kind"]] = by_kind.get(f["kind"], 0) + 1
    previews: list[str] = []
    for f in files:
        if f.get("preview_urls"):
            previews = f["preview_urls"]
            break
    return {
        "product_id": str(product.id),
        "idea": product.idea,
        "status": product.status.value,
        "updated_at": product.updated_at.isoformat() if product.updated_at else None,
        "file_count": len(files),
        "total_size": total,
        "doc_count": by_kind.get("doc", 0),
        "ppt_count": by_kind.get("ppt", 0),
        "presentation_count": by_kind.get("presentation", 0),
        "keywords_count": by_kind.get("keywords", 0),
        "image_count": by_kind.get("image", 0),
        "has_pptx": by_kind.get("ppt", 0) > 0,
        "has_presentation": by_kind.get("presentation", 0) > 0,
        "has_keywords": by_kind.get("keywords", 0) > 0,
        "svg_previews": previews,
    }


@router.get("")
async def list_project_asset_libraries(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """任务资产库列表：每个任务的资产统计（只读，不补产文本）。"""
    from sqlalchemy import or_, select

    result = await db.execute(
        select(StudioProduct)
        .where(or_(
            StudioProduct.owner_id == user.id,
            StudioProduct.owner_id.is_(None),
        ))
        .order_by(StudioProduct.updated_at.desc())
    )
    products = result.scalars().all()
    libraries = []
    for p in products:
        package = _load_package(p)
        files = await asyncio.to_thread(pa.collect_files, str(p.id), package)
        libraries.append(_summary(p, files))
    return libraries


@router.get("/{product_id}")
async def get_project_asset_library(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """任务资产库明细：惰性补产文本 md/pdf 后返回全部资产清单。"""
    product = await _get_product(product_id, db, user)
    package = _load_package(product)
    # 惰性补产：文本资产 → md（必产）+ pdf（尽力）；已有产出时幂等跳过
    await asyncio.to_thread(pa.ensure_text_assets, str(product_id), package)
    files = await asyncio.to_thread(pa.collect_files, str(product_id), package)
    index = await asyncio.to_thread(pa.save_library_index, str(product_id), package)
    return {
        "product_id": str(product.id),
        "idea": product.idea,
        "status": product.status.value,
        "updated_at": product.updated_at.isoformat() if product.updated_at else None,
        "files": files,
        "total_size": sum(f["size"] for f in files),
        "generated_at": index.get("generated_at"),
    }


@router.get("/{product_id}/download")
async def download_project_asset_library(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """打包下载任务全部资产（ZIP，按类别分子目录，中文名自动落盘）。"""
    product = await _get_product(product_id, db, user)
    package = _load_package(product)
    await asyncio.to_thread(pa.ensure_text_assets, str(product_id), package)
    data = await asyncio.to_thread(
        pa.build_task_zip_bytes, str(product_id), package, product.idea,
    )
    if not data:
        raise HTTPException(status_code=404, detail="任务暂无资产")

    # RFC 5987：filename 用 ASCII 兜底，filename* 用 UTF-8 百分号编码（中文名）
    safe_idea = re.sub(r"[^\w\u4e00-\u9fff\-]+", "_", product.idea)[:40] or str(product_id)[:8]
    ascii_name = re.sub(r"[^A-Za-z0-9\-]+", "_", safe_idea) or str(product_id)[:8]
    return Response(
        content=data,
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f'attachment; filename="project_assets_{ascii_name}.zip"; '
                f"filename*=UTF-8''{_quote(f'项目资产_{safe_idea}.zip')}"
            )
        },
    )
