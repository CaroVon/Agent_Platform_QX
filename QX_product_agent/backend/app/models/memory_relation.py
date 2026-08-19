"""
============================================================
记忆关系 (MemoryRelation) ORM 模型
—— 知识图边：带证据溯源、权重与时间窗（Graphiti 时序思想简化版）
============================================================
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Float, Text, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDType


class MemoryRelation(Base):
    """记忆图关系边 —— 有向（source → target）+ 关系类型标签"""

    __tablename__ = "memory_relations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )
    source_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("memory_entities.id", ondelete="CASCADE"),
        nullable=False, index=True, doc="头实体"
    )
    target_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("memory_entities.id", ondelete="CASCADE"),
        nullable=False, index=True, doc="尾实体"
    )
    relation_type: Mapped[str] = mapped_column(
        String(100), nullable=False, doc="关系类型（中文，如 竞争/供应商/用于/收购）"
    )
    evidence: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="证据（JSON list: [{source, project_id, section}...]）"
    )
    weight: Mapped[float] = mapped_column(
        Float, default=1.0, server_default="1.0", doc="关系权重（复现累加）"
    )
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), doc="关系成立时间"
    )
    valid_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, doc="关系失效时间（过期后虚线/降权）"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
