"""
============================================================
记忆洞察 (MemoryInsight) ORM 模型
—— 高层记忆（LightRAG high-level 检索载体）：结论级知识
   链接到实体，检索时随邻域召回
============================================================
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Float, Text, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDType


class MemoryInsight(Base):
    """记忆洞察 —— 任务沉淀的结论/经验（≤500 字），可提升为全局"""

    __tablename__ = "memory_insights"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )
    scope: Mapped[str] = mapped_column(
        String(20), nullable=False, default="project", server_default="project",
        index=True, doc="记忆范围: global / project"
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True, index=True, doc="来源项目"
    )
    studio_product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("studio_products.id", ondelete="CASCADE"),
        nullable=True, index=True, doc="AI Product Studio 任务 ID"
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False, doc="洞察/结论文本（≤500 字）"
    )
    entity_ids: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="关联实体 ID（JSON list，检索时按实体邻域召回）"
    )
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, default="task_summary", server_default="task_summary",
        doc="来源: task_summary（任务总结）/ conversation / image_analysis / manual"
    )
    source_url: Mapped[str | None] = mapped_column(
        String(2048), nullable=True, doc="来源标识（obsidian:// / image:// / experience://）"
    )
    confidence: Mapped[float] = mapped_column(
        Float, default=0.7, server_default="0.7", doc="置信度"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
