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
import time
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

# 列表汇总缓存（体验优化）：(product_id, updated_at) → summary，60s TTL
_LIB_CACHE: dict[str, tuple[str, dict, float]] = {}
_LIB_CACHE_TTL = 60.0


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
    """任务资产库列表：每个任务的资产统计（只读，不补产文本）。

    性能（体验优化）：
    - collect_files(ensure=False)：纯 stat/glob 扫描，不触发 md/pdf 生成
    - 并行收集（8 线程）替代串行循环
    - (product_id, updated_at) 键 + TTL 缓存：二次请求直接命中内存
    """
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

    # 先查缓存：仅对（无缓存 / updated_at 变化 / TTL 过期）的产品执行扫描
    now = time.time()
    stale: list[StudioProduct] = []
    cached_map: dict[str, dict] = {}
    for p in products:
        key = str(p.id)
        updated = p.updated_at.isoformat() if p.updated_at else ""
        cached = _LIB_CACHE.get(key)
        if cached and cached[0] == updated and now - cached[2] < _LIB_CACHE_TTL:
            cached_map[key] = cached[1]
        else:
            stale.append(p)

    def _collect(p):
        package = _load_package(p)
        return pa.collect_files(str(p.id), package, ensure=False)

    from concurrent.futures import ThreadPoolExecutor

    if stale:
        with ThreadPoolExecutor(max_workers=8) as ex:
            files_list = list(ex.map(_collect, stale))
        for p, files in zip(stale, files_list):
            summary = _summary(p, files)
            updated = p.updated_at.isoformat() if p.updated_at else ""
            _LIB_CACHE[str(p.id)] = (updated, summary, time.time())
            cached_map[str(p.id)] = summary
    return [cached_map[str(p.id)] for p in products]


@router.get("/{product_id}")
async def get_project_asset_library(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """任务资产库明细：惰性补产文本 md（幂等）后返回全部资产清单。

    性能（体验优化）：ensure×1 / collect×1 —— save_library_index 接受
    已算好的 files 结果，不再内部二次 collect；PDF 不在本请求路径。
    """
    product = await _get_product(product_id, db, user)
    package = _load_package(product)
    # 惰性补产：文本资产 md（必产，幂等跳过）；pdf 由完成态后处理或
    # POST /render-pdf 显式生成
    await asyncio.to_thread(pa.ensure_text_assets, str(product_id), package,
                            render_pdf=False)
    files = await asyncio.to_thread(pa.collect_files, str(product_id), package,
                                    ensure=False)
    index = await asyncio.to_thread(pa.save_library_index, str(product_id),
                                    package, files=files)
    return {
        "product_id": str(product.id),
        "idea": product.idea,
        "status": product.status.value,
        "updated_at": product.updated_at.isoformat() if product.updated_at else None,
        "files": files,
        "total_size": sum(f["size"] for f in files),
        "generated_at": index.get("generated_at"),
    }


@router.post("/{product_id}/render-pdf")
async def render_product_pdfs(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """按需渲染文本资产 PDF（weasyprint 同步耗时，移出常规读路径）。"""
    product = await _get_product(product_id, db, user)
    package = _load_package(product)
    written = await asyncio.to_thread(pa.ensure_text_assets, str(product_id),
                                      package, render_pdf=True)
    return {"product_id": str(product.id), "rendered": written}


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
