"""
============================================================
记忆实体 (MemoryEntity) ORM 模型
—— 知识图节点：全局记忆（scope=global）与项目记忆（scope=project）
============================================================
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Float, Text, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDType


class MemoryEntity(Base):
    """记忆图实体节点 —— 公司/产品/技术/人物/市场/指标等"""

    __tablename__ = "memory_entities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )
    scope: Mapped[str] = mapped_column(
        String(20), nullable=False, default="project", server_default="project",
        index=True, doc="记忆范围: global（跨项目合并）/ project（项目特有）"
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True, index=True, doc="归属项目（scope=project 时非空）"
    )
    studio_product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("studio_products.id", ondelete="CASCADE"),
        nullable=True, index=True, doc="AI Product Studio 任务 ID"
    )
    type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="other", server_default="other",
        doc="实体类型: company/product/technology/person/market/metric/other"
    )
    name: Mapped[str] = mapped_column(
        String(500), nullable=False, index=True, doc="归一化主名"
    )
    aliases: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="别名（JSON list）"
    )
    summary: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="实体摘要（跨任务合并维护）"
    )
    embedding: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="name+summary 向量（JSON float 列表）"
    )
    confidence: Mapped[float] = mapped_column(
        Float, default=0.6, server_default="0.6",
        doc="置信度（0-1）：跨任务复现提升，长期未引用衰减"
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )
