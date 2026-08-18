"""
============================================================
文档 (Document) ORM 模型
—— 每个章节的完整文档实体，用于报告全文组装
============================================================
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Integer, Text, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDType


class Document(Base):
    """报告章节文档 —— 每个 section 对应一条记录"""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("projects.id"), nullable=False, index=True
    )
    section_title: Mapped[str] = mapped_column(
        String(500), nullable=False, doc="章节标题"
    )
    section_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, doc="章节排序"
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False, default="", doc="Markdown 正文"
    )
    source_urls: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="JSON 格式的引用源 URL 列表"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
