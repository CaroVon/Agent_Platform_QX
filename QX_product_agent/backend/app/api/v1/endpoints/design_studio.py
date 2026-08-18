"""
====================================================================
Design Studio v2 API —— 任务级「设计思路 + 图片」资产库
====================================================================

REST 设计（前缀 /api/v1/design-studio）：
  GET    /{product_id}                        读取资产库（惰性导入 pipeline 资产）
  POST   /{product_id}/suggest-components      LLM 智能拆解产品组件建议
  POST   /{product_id}/items                   创建条目（component/standalone）
  POST   /{product_id}/composite               创建组合（组件 + 组合总图条目，原子）
  PATCH  /{product_id}/items/{item_id}         修改名称 / 设计思路（不重新生图）
  POST   /{product_id}/items/{item_id}/generate  生成 / 重新生成图片（按当前文字）
  POST   /{product_id}/items/{item_id}/restore   从版本历史恢复
  DELETE /{product_id}/items/{item_id}         删除条目
  GET    /{product_id}/download                打包下载全部图片（ZIP）
====================================================================
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.studio_product import StudioProduct
from app.models.user import User
from app.services import design_studio as ds
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/design-studio", tags=["design-studio"])


async def _get_product(product_id: uuid.UUID, db: AsyncSession, user: User) -> StudioProduct:
    product = await db.get(StudioProduct, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="产品不存在")
    if product.owner_id is not None and product.owner_id != user.id:
        raise HTTPException(status_code=403, detail="无权访问该产品")
    return product


async def _load_package(product: StudioProduct) -> dict:
    try:
        return json.loads(product.asset_package or "{}")
    except json.JSONDecodeError:
        return {}


# ─── 请求体 ─────────────────────────────────────────────────

class ItemCreateRequest(BaseModel):
    kind: str = Field(..., description="standalone | component | composite")
    name: str = Field(..., min_length=1, max_length=60)
    text: str = Field(default="", max_length=2000)
    parent: str | None = Field(default=None, description="组件所属组合条目 id")
    children: list[str] = Field(default=[], description="组合包含的组件 id 列表")


class ComponentDefRequest(BaseModel):
    """组合内组件定义（无需 kind，创建时固定为 component）。"""
    name: str = Field(..., min_length=1, max_length=60)
    text: str = Field(default="", max_length=2000)


class CompositeCreateRequest(BaseModel):
    name: str = Field(default="产品整体设计", max_length=60)
    text: str = Field(default="", max_length=2000, description="组合总图整体设计思路")
    components: list[ComponentDefRequest] = Field(
        default=[], description="组件定义（name + text），随组合一并创建",
    )


class ItemUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=60)
    text: str | None = Field(default=None, max_length=2000)


class RestoreRequest(BaseModel):
    index: int = Field(..., ge=0, description="版本历史下标")


# ─── 端点 ───────────────────────────────────────────────────

@router.get("/{product_id}")
async def get_library(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """读取任务 Design Studio 资产库（首次访问时自动导入 pipeline 图片资产）。"""
    product = await _get_product(product_id, db, user)
    package = await _load_package(product)
    library = await asyncio.to_thread(ds.import_from_product_package, str(product_id), package)
    library["idea"] = library.get("idea") or product.idea
    library["status"] = product.status.value
    return library


@router.post("/{product_id}/suggest-components")
async def suggest_components(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """LLM 拆解产品组件（返回 [{name, text}] 建议，未生成图片）。"""
    product = await _get_product(product_id, db, user)
    package = await _load_package(product)
    suggestions = await asyncio.to_thread(
        ds.suggest_components, str(product_id), product.idea, package,
    )
    return {"product_id": str(product_id), "suggestions": suggestions}


@router.post("/{product_id}/items")
async def create_item(
    product_id: uuid.UUID,
    body: ItemCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """创建资产条目（组件 / 独立图）。"""
    product = await _get_product(product_id, db, user)
    if body.kind not in ("standalone", "component", "composite"):
        raise HTTPException(status_code=422, detail=f"未知条目类型: {body.kind}")
    try:
        item = await asyncio.to_thread(
            ds.create_item, str(product_id),
            kind=body.kind, name=body.name, text=body.text,
            parent=body.parent, children=body.children,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"product_id": str(product_id), "item": item}


@router.post("/{product_id}/composite")
async def create_composite(
    product_id: uuid.UUID,
    body: CompositeCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """原子创建「组合设计」：先建组件条目，再建组合总图条目（children 关联）。"""
    product = await _get_product(product_id, db, user)
    child_ids: list[str] = []
    for comp in body.components:
        item = await asyncio.to_thread(
            ds.create_item, str(product_id),
            kind="component", name=comp.name, text=comp.text,
        )
        child_ids.append(item["id"])
    composite = await asyncio.to_thread(
        ds.create_item, str(product_id),
        kind="composite", name=body.name, text=body.text, children=child_ids,
    )
    library = await asyncio.to_thread(ds.load_library, str(product_id))
    return {
        "product_id": str(product_id),
        "composite": composite,
        "components": [it for it in library["items"] if it["id"] in child_ids],
    }


@router.patch("/{product_id}/items/{item_id}")
async def update_item(
    product_id: uuid.UUID,
    item_id: str,
    body: ItemUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """修改条目名称 / 设计思路（保存后需调用 generate 才重新生图）。"""
    await _get_product(product_id, db, user)
    try:
        item = await asyncio.to_thread(
            ds.update_item, str(product_id), item_id,
            name=body.name, text=body.text,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="资产条目不存在")
    return {"product_id": str(product_id), "item": item}


@router.post("/{product_id}/items/{item_id}/generate")
async def generate_item_image(
    product_id: uuid.UUID,
    item_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """按条目当前文字生成 / 重新生成图片（同步等待，生图模型调用）。"""
    await _get_product(product_id, db, user)
    try:
        item = await asyncio.to_thread(ds.generate_image_for_item, str(product_id), item_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="资产条目不存在")
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"product_id": str(product_id), "item": item}


@router.post("/{product_id}/items/{item_id}/restore")
async def restore_item_version(
    product_id: uuid.UUID,
    item_id: str,
    body: RestoreRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """从版本历史恢复条目（回滚文字 + 图片）。"""
    await _get_product(product_id, db, user)
    try:
        item = await asyncio.to_thread(ds.restore_version, str(product_id), item_id, body.index)
    except KeyError:
        raise HTTPException(status_code=404, detail="资产条目不存在")
    except IndexError:
        raise HTTPException(status_code=404, detail="版本不存在")
    return {"product_id": str(product_id), "item": item}


@router.delete("/{product_id}/items/{item_id}")
async def delete_item(
    product_id: uuid.UUID,
    item_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """删除资产条目（组合删除时组件脱离组合；组件删除时从组合摘除）。"""
    await _get_product(product_id, db, user)
    try:
        await asyncio.to_thread(ds.delete_item, str(product_id), item_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="资产条目不存在")
    return {"product_id": str(product_id), "deleted": item_id}


@router.get("/{product_id}/download")
async def download_library(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """打包下载资产库全部图片（ZIP，中文名自动落盘）。"""
    product = await _get_product(product_id, db, user)
    data = await asyncio.to_thread(ds.build_zip_bytes, str(product_id))
    if data is None:
        raise HTTPException(status_code=404, detail="资产库暂无图片")
    import re as _re
    from urllib.parse import quote as _quote

    # RFC 5987：filename 用 ASCII 兜底，filename* 用 UTF-8 百分号编码（中文名）
    safe_idea = _re.sub(r"[^\w\u4e00-\u9fff\-]+", "_", product.idea)[:40] or str(product_id)[:8]
    ascii_name = _re.sub(r"[^A-Za-z0-9\-]+", "_", safe_idea) or str(product_id)[:8]
    return Response(
        content=data,
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f'attachment; filename="design_studio_{ascii_name}.zip"; '
                f"filename*=UTF-8''{_quote(f'design_studio_{safe_idea}.zip')}"
            )
        },
    )
