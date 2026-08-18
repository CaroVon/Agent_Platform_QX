"""
============================================================
文档块 (DocumentBlock) ORM 模型
—— 每个章节的原子化内容块，支持块级编辑和局部 AI 改写
============================================================
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Integer, Text, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDType


class DocumentBlock(Base):
    """原子化文档内容块 —— Tiptap 编辑器的最小渲染单元"""

    __tablename__ = "document_blocks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("projects.id"), nullable=False, index=True
    )
    section_title: Mapped[str] = mapped_column(
        String(500), nullable=False, doc="所属章节标题"
    )
    order_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, doc="块在章节内的排序"
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False, default="", doc="块的 Markdown 文本内容"
    )
    citations: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="JSON 格式引用数据：{ref_num: {title, url, snippet}}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
