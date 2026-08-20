"""
============================================================
记忆图 API（P4）
—— 知识关系图数据 / 实体详情 / 洞察 / 手动重建 / 删除纠错
============================================================

端点：
  GET    /memory/graph          关系图数据（nodes/edges，支持搜索/类型/scope）
  GET    /memory/entities/{id}  实体详情 + 邻域 + 关联洞察
  GET    /memory/insights       洞察列表（scope/q 过滤）
  POST   /memory/rebuild/{project_id}  手动触发记忆图重建（幂等）
  DELETE /memory/entities/{id}  删除实体（用户纠错，级联关系）
"""

from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.project import Project
from app.models.studio_product import StudioProduct
from app.models.user import User
from app.core.security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memory", tags=["memory"])


# ================================================================
# GET /api/v1/memory/graph —— 知识关系图
# ================================================================

@router.get("/graph")
async def get_memory_graph(
    scope: str = Query("global", pattern="^(global|project)$", description="记忆范围"),
    project_id: str | None = Query(None, description="项目 ID（scope=project 时使用）"),
    studio_product_id: str | None = Query(None, description="Product Studio 任务 ID（scope=project 时使用）"),
    q: str | None = Query(None, max_length=100, description="实体名搜索（命中聚焦 2 跳邻域）"),
    entity_types: str | None = Query(None, description="实体类型过滤（逗号分隔）"),
    limit: int = Query(300, ge=10, le=2000, description="节点上限（超限按度数截断）"),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0, description="置信度下限"),
):
    """知识关系图数据（节点/边/元信息），供可视化渲染。"""
    from app.rag.memory_extraction import get_memory_graph as _graph

    types = [t.strip() for t in (entity_types or "").split(",") if t.strip()] or None
    try:
        data = _graph(
            scope=scope,
            project_id=project_id,
            studio_product_id=studio_product_id,
            q=q,
            entity_types=types,
            limit=limit,
            min_confidence=min_confidence,
        )
    except Exception as e:  # noqa: BLE001
        logger.error("记忆图查询失败: %s", e)
        raise HTTPException(status_code=500, detail=f"记忆图查询失败: {str(e)}")
    return data


# ================================================================
# GET /api/v1/memory/entities/{entity_id} —— 实体详情 + 邻域
# ================================================================

@router.get("/entities/{entity_id}")
async def get_entity_detail(entity_id: uuid.UUID):
    """实体详情：基本信息 + 邻域关系 + 关联洞察 + 证据溯源。"""
    from app.repositories import ProjectRepo
    from app.models.memory_relation import MemoryRelation

    repo = ProjectRepo()
    entity = repo.get_entity(str(entity_id))
    if entity is None:
        raise HTTPException(status_code=404, detail="实体不存在")

    relations = repo.list_relations_for_entity(str(entity_id), active_only=False)
    neighbors: list[dict] = []
    for rel in relations:
        other_id = str(rel.target_entity_id) if str(rel.source_entity_id) == str(entity_id) else str(rel.source_entity_id)
        other = repo.get_entity(other_id)
        neighbors.append({
            "relation_id": str(rel.id),
            "relation": rel.relation_type,
            "weight": rel.weight,
            "expired": bool(rel.valid_to),
            "direction": "out" if str(rel.source_entity_id) == str(entity_id) else "in",
            "other": {
                "id": other_id,
                "name": other.name if other else "(已删除)",
                "type": other.type if other else "other",
            },
            "evidence": json.loads(rel.evidence) if rel.evidence else [],
        })

    insights = repo.list_insights_by_entity_ids([str(entity_id)], limit=10)
    return {
        "id": str(entity.id),
        "name": entity.name,
        "type": entity.type,
        "scope": entity.scope,
        "summary": entity.summary or "",
        "aliases": json.loads(entity.aliases) if entity.aliases else [],
        "confidence": round(entity.confidence or 0.6, 2),
        "first_seen_at": entity.first_seen_at.isoformat() if entity.first_seen_at else None,
        "last_seen_at": entity.last_seen_at.isoformat() if entity.last_seen_at else None,
        "project_id": str(entity.project_id) if entity.project_id else None,
        "studio_product_id": str(entity.studio_product_id) if entity.studio_product_id else None,
        "relations": neighbors,
        "insights": [
            {"id": str(i.id), "content": i.content, "source": i.source,
             "created_at": i.created_at.isoformat() if i.created_at else None}
            for i in insights
        ],
    }


# ================================================================
# GET /api/v1/memory/insights —— 洞察列表
# ================================================================

@router.get("/insights")
async def list_memory_insights(
    scope: str = Query("project", pattern="^(global|project)$"),
    project_id: str | None = Query(None),
    studio_product_id: str | None = Query(None),
    q: str | None = Query(None, max_length=200),
    limit: int = Query(50, ge=1, le=200),
):
    """记忆洞察列表（high-level 记忆）。"""
    from app.repositories import ProjectRepo
    repo = ProjectRepo()
    insights = repo.list_insights(
        scope=scope,
        project_id=project_id,
        studio_product_id=studio_product_id,
        limit=200,
    )
    if q:
        insights = [i for i in insights if q.lower() in (i.content or "").lower()]
    return {
        "total": len(insights[:limit]),
        "insights": [
            {
                "id": str(i.id),
                "scope": i.scope,
                "project_id": str(i.project_id) if i.project_id else None,
                "studio_product_id": str(i.studio_product_id) if i.studio_product_id else None,
                "content": i.content,
                "source": i.source,
                "confidence": round(i.confidence or 0.7, 2),
                "created_at": i.created_at.isoformat() if i.created_at else None,
            }
            for i in insights[:limit]
        ],
    }


# ================================================================
# POST /api/v1/memory/rebuild/{project_id} —— 手动重建记忆图
# ================================================================

@router.post("/rebuild/{project_id}")
async def rebuild_project_memory(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """手动触发某项目的记忆图重建（幂等；由 Celery 异步执行）。"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail=f"项目 {project_id} 不存在")
    if project.owner_id != user.id:
        raise HTTPException(status_code=403, detail="无权访问该项目")

    from app.tasks.knowledge_tasks import build_memory_graph
    try:
        celery_task = build_memory_graph.delay(str(project_id))
        task_id = celery_task.id
    except Exception as e:
        logger.warning("记忆图重建任务投递失败: %s", e)
        task_id = ""

    return {
        "project_id": str(project_id),
        "message": "记忆图重建任务已提交（异步执行）",
        "celery_task_id": task_id,
    }


@router.post("/rebuild-studio/{product_id}")
async def rebuild_studio_memory(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """手动重建 Product Studio 任务记忆图。"""
    product = await db.get(StudioProduct, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product Studio 任务不存在")
    if product.owner_id is not None and product.owner_id != user.id:
        raise HTTPException(status_code=403, detail="无权访问该任务")
    from app.tasks import knowledge_tasks

    task = knowledge_tasks.build_studio_memory_graph.delay(str(product_id))
    return {
        "product_id": str(product_id),
        "message": "Product Studio 任务记忆图重建已提交（异步执行）",
        "celery_task_id": task.id,
    }


# ================================================================
# POST /api/v1/memory/entities/{entity_id}/promote —— 手动提升到全局
# ================================================================

@router.post("/entities/{entity_id}/promote")
async def promote_memory_entity(entity_id: uuid.UUID):
    """手动把项目实体提升为全局记忆（跨任务沉淀通用知识）。"""
    import asyncio

    from app.rag.memory_extraction import promote_entity_to_global

    result = await asyncio.to_thread(promote_entity_to_global, str(entity_id))
    if not result.get("promoted"):
        if result.get("reason") == "实体不存在":
            raise HTTPException(status_code=404, detail="实体不存在")
        return {"promoted": False, "detail": result.get("reason", "")}
    return {"promoted": True, **{k: v for k, v in result.items() if k != "promoted"}}


# ================================================================
# DELETE /api/v1/memory/entities/{entity_id} —— 删除实体（纠错）
# ================================================================

@router.delete("/entities/{entity_id}")
async def delete_memory_entity(entity_id: uuid.UUID):
    """删除记忆实体及其全部关系（用户纠错；洞察保留但解除链接）。"""
    from app.rag.memory_extraction import delete_entity_cascade
    ok = delete_entity_cascade(str(entity_id))
    if not ok:
        raise HTTPException(status_code=404, detail="实体不存在")
    return {"detail": "实体已删除（级联关系）"}
