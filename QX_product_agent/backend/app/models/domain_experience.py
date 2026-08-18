"""
============================================================
领域经验包 (DomainExperience) ORM 模型
—— L1 领域知识层：相似任务的"经验包"（结论/方法/避坑）
   任务完成时由 LLM 抽取，新任务按领域标签召回注入
============================================================
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Text, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDType


class DomainExperience(Base):
    """领域经验包 —— 单条可借用的跨任务经验"""

    __tablename__ = "domain_experiences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True, doc="来源项目 ID"
    )
    domain_tags: Mapped[str] = mapped_column(
        String(1000), nullable=False, default="[]", server_default="[]",
        doc="领域标签（JSON list），检索时按标签匹配"
    )
    topic: Mapped[str] = mapped_column(
        String(500), nullable=False, doc="来源项目主题"
    )
    summary: Mapped[str] = mapped_column(
        Text, nullable=False, doc="经验包摘要（≤ EXPERIENCE_MAX_CHARS 字符）"
    )
    source_url: Mapped[str | None] = mapped_column(
        String(2048), nullable=True, doc="报告/PDF 等产出物标识"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
