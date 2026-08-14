"""
============================================================
Knowledge Base API —— 全局知识资产只读聚合
============================================================
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.document import Document
from app.models.project import Project
from app.schemas.studio import KnowledgeDocumentResponse

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
