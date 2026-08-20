"""
============================================================
Knowledge Base API —— 三层知识库（全局/领域/任务）检索与资产
============================================================

端点：
  GET /knowledge/documents      知识库文档列表（跨项目，只读聚合）
  GET /knowledge/search         三层融合检索（L2 任务 + L1 领域 + L0 全局）
  GET /knowledge/assets         知识资产登记列表（upload/obsidian/experience）
  GET /knowledge/domains        领域经验包列表
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.document import Document
from app.models.project import Project
from app.schemas.studio import KnowledgeDocumentResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("/documents", response_model=list[KnowledgeDocumentResponse])
async def list_knowledge_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """知识库文档列表 —— 全部研究项目的章节文档（按更新时间倒序）。"""
    result = await db.execute(
        select(Document, Project.topic)
        .join(Project, Document.project_id == Project.id)
        .order_by(Document.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    rows = result.all()
    return [
        KnowledgeDocumentResponse(
            document_id=str(doc.id),
            project_id=str(doc.project_id),
            project_topic=topic,
            section_title=doc.section_title,
            section_order=doc.section_order,
            updated_at=doc.created_at.isoformat() if doc.created_at else None,
        )
        for doc, topic in rows
    ]


# ================================================================
# GET /api/v1/knowledge/search —— 三层融合检索
# ================================================================

@router.get("/search")
async def search_knowledge(
    q: str = Query(..., min_length=1, max_length=500, description="检索关键词"),
    scope: str = Query("", description="限定范围: task/domain/global/空=全部"),
    project_id: str | None = Query(None, description="任务库项目 ID（scope=task 时必填）"),
    k: int = Query(8, ge=1, le=30, description="返回条数"),
    db: AsyncSession = Depends(get_db),
):
    """
    三层知识库融合检索：
      - L2 任务库（project_id 指定）
      - L1 领域库（项目的 domain_tags 自动匹配）
      - L0 全局库（企业文档/Obsidian/经验包）
    另附 documents 表全文模糊匹配作为文本兜底。
    """
    from app.rag.rag_pipeline import build_scopes, _get_project_domain_tags
    from app.rag.retriever import retrieve_scoped

    scopes: list[tuple[str, str | None, float]] = []
    if scope == "task" and project_id:
        scopes = [("", project_id, 1.0)]
    elif scope == "domain":
        tags = _get_project_domain_tags(project_id) if project_id else []
        scopes = build_scopes(None, tags)
        scopes = [s for s in scopes if s[0].startswith("domain")]
    elif scope == "global":
        scopes = [("global", None, 1.0)]
    else:
        scopes = build_scopes(project_id)

    hits: list[dict] = []
    try:
        docs = retrieve_scoped(q, scopes, k=k)
        for r in docs:
            hits.append({
                "scope": r.metadata.get("layer", scope or "unknown"),
                "content": r.page_content[:600],
                "source_url": r.metadata.get("url", "unknown"),
                "score": round(float(r.metadata.get("score", 0) or 0), 4),
            })
    except Exception as e:  # noqa: BLE001
        logger.warning("向量检索失败，降级为文本检索: %s", e)

    # ── 文本兜底：documents 表全文模糊匹配（全局文档） ────────
    text_fallback: list[dict] = []
    if not hits or scope in ("", "global"):
        try:
            result = await db.execute(
                select(Document, Project.topic)
                .join(Project, Document.project_id == Project.id)
                .where(or_(
                    Document.content.ilike(f"%{q}%"),
                    Document.section_title.ilike(f"%{q}%"),
                ))
                .order_by(Document.created_at.desc())
                .limit(k)
            )
            for doc, topic in result.all():
                text_fallback.append({
                    "scope": "document",
                    "content": (doc.content or "")[:600],
                    "source_url": f"document://{doc.id}",
                    "score": 0.0,
                    "title": doc.section_title,
                    "project_topic": topic,
                })
        except Exception as e:  # noqa: BLE001
            logger.debug("documents 文本检索失败: %s", e)

    merged = hits + [h for h in text_fallback if h["source_url"] not in {x["source_url"] for x in hits}]
    return {
        "query": q,
        "scope": scope or "all",
        "total": len(merged),
        "hits": merged[:k],
    }


# ================================================================
# GET /api/v1/knowledge/assets —— 知识资产登记列表
# ================================================================

@router.get("/assets")
async def list_knowledge_assets(
    scope: str | None = Query(None, description="过滤范围: global / domain:{tag}"),
    source: str | None = Query(None, description="过滤来源: upload/obsidian/experience"),
    studio_product_id: str | None = Query(None, description="Product Studio 任务 ID"),
    limit: int = Query(200, ge=1, le=500),
):
    """知识资产列表（全局/领域登记表）。"""
    from app.repositories import ProjectRepo
    assets = ProjectRepo().list_knowledge_assets(
        scope=scope,
        source=source,
        studio_product_id=studio_product_id,
        limit=limit,
    )
    return {
        "total": len(assets),
        "assets": [
            {
                "id": str(a.id),
                "scope": a.scope,
                "source": a.source,
                "studio_product_id": str(a.studio_product_id) if a.studio_product_id else None,
                "title": a.title,
                "source_url": a.source_url,
                "tags": json.loads(a.tags) if a.tags else [],
                "chunk_count": a.chunk_count,
                "version": a.version,
                "stale_at": a.stale_at.isoformat() if a.stale_at else None,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in assets
        ],
    }


# ================================================================
# GET /api/v1/knowledge/domains —— 领域经验包列表
# ================================================================

@router.get("/domains")
async def list_domain_experiences(
    limit: int = Query(100, ge=1, le=500),
):
    """领域经验包列表（跨任务可借用的领域知识）。"""
    from app.repositories import ProjectRepo
    experiences = ProjectRepo().list_all_domain_experiences(limit=limit)
    return {
        "total": len(experiences),
        "experiences": [
            {
                "id": str(e.id),
                "project_id": str(e.project_id),
                "topic": e.topic,
                "domain_tags": json.loads(e.domain_tags) if e.domain_tags else [],
                "summary": e.summary,
                "source_url": e.source_url,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in experiences
        ],
    }
