"""
============================================================
知识资产 (KnowledgeAsset) ORM 模型
—— 三层知识库的统一资产登记表（全局/领域/任务）
   记录来源、范围、版本、失效时间，支撑知识生命周期管理
============================================================
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Integer, Text, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDType


class KnowledgeAsset(Base):
    """知识资产条目 —— 全局库（scope=global）与领域库（scope=domain:tag）的登记表"""

    __tablename__ = "knowledge_assets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )
    scope: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True,
        doc="知识范围: global（全局）/ domain:{tag}（领域）/ {project_id}（任务）"
    )
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True,
        doc="资产归属用户（NULL=系统级资产）"
    )
    studio_product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("studio_products.id", ondelete="CASCADE"),
        nullable=True, index=True, doc="AI Product Studio 任务 ID"
    )
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, default="upload", server_default="upload",
        doc="来源: upload（上传）/ obsidian（Vault 同步）/ experience（经验包）/ studio（平台记忆）"
    )
    title: Mapped[str] = mapped_column(
        String(1000), nullable=False, doc="资产标题（文件名/笔记标题/经验标题）"
    )
    source_url: Mapped[str | None] = mapped_column(
        String(2048), nullable=True, doc="来源标识（local://、obsidian://、image:// 等）"
    )
    tags: Mapped[str | None] = mapped_column(
        String(1000), nullable=True, doc="标签（JSON list）"
    )
    chunk_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", doc="入库切片数量"
    )
    version: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", doc="资产版本号"
    )
    stale_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True,
        doc="失效时间（过期后检索降权/剔除，NULL=永不过期）"
    )
    extra: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="扩展元数据（JSON）"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )
