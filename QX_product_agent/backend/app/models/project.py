"""
============================================================
项目 (Project) ORM 模型
============================================================
"""

from __future__ import annotations

import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Enum, Integer, Text, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDType


class ProjectStatus(str, enum.Enum):
    """项目状态机枚举 —— 与前端 types/api.ts 保持同步"""
    PREPARING_DATA = "preparing_data"
    WAITING_FOR_SOURCES = "waiting_for_sources"
    PREPARING_OUTLINE = "preparing_outline"
    WAITING_FOR_OUTLINE = "waiting_for_outline"
    DRAFTING = "drafting"
    COMPLETED = "completed"
    FAILED = "failed"


class Project(Base):
    """产品分析项目"""

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("users.id"), nullable=False, index=True
    )
    topic: Mapped[str] = mapped_column(
        String(500), nullable=False, doc="分析主题"
    )
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus, values_callable=lambda obj: [e.value for e in obj]),
        default=ProjectStatus.PREPARING_DATA,
        nullable=False,
        index=True,
        doc="项目当前状态"
    )
    outline_content: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="暂存的大纲 Markdown"
    )
    pdf_path: Mapped[str | None] = mapped_column(
        String(500), nullable=True, doc="PDF 文件路径"
    )
    md_path: Mapped[str | None] = mapped_column(
        String(500), nullable=True, doc="Markdown 文件路径"
    )
    template_type: Mapped[str] = mapped_column(
        String(50), default="product", server_default="product",
        nullable=False, doc="模板类型：product 或 design"
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="错误信息"
    )
    search_depth: Mapped[int] = mapped_column(
        Integer, default=10, server_default="10",
        nullable=False, doc="搜索强度: 5/10/15/20"
    )
    logo_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True, doc="Logo 图片 URL"
    )
    canvas_data: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="Canvas 编辑器持久化数据（Konva slides JSON）"
    )
    images_per_page: Mapped[int] = mapped_column(
        Integer, default=2, server_default="2",
        nullable=False, doc="每页自动搜索图片数量: 0=关闭, 1-5"
    )
    topic_embedding: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        doc="主题向量（JSON float 列表，bge-small-zh-v1.5），用于任务相似度判别"
    )
    domain_tags: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        doc="领域标签（JSON list，如 [\"industry:消费电子\", \"category:智能穿戴\"]）"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )
