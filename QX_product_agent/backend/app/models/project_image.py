"""
============================================================
项目图片库 (ProjectImage) ORM 模型
—— 持久化图片搜索结果，供前端 ImageGallery 面板展示
============================================================
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Integer, Text, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDType


class ProjectImage(Base):
    """项目图片库条目 —— 每次图片搜索的结果持久化存储"""

    __tablename__ = "project_images"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True, doc="归属项目 ID"
    )
    query: Mapped[str] = mapped_column(
        String(500), nullable=False, doc="搜索关键词"
    )
    title: Mapped[str] = mapped_column(
        String(500), nullable=False, doc="图片标题"
    )
    image_url: Mapped[str] = mapped_column(
        String(2048), nullable=False, doc="图片直链 URL"
    )
    source_url: Mapped[str | None] = mapped_column(
        String(2048), nullable=True, doc="来源网页 URL"
    )
    thumbnail_url: Mapped[str | None] = mapped_column(
        String(2048), nullable=True, doc="缩略图 URL（通常与 image_url 相同）"
    )
    # ─── 知识库图片（本地上传分析）字段 ────────────────────────
    source: Mapped[str] = mapped_column(
        String(20), default="search", server_default="search",
        nullable=False, doc="图片来源: search（网络搜索）/ upload（本地上传入库）"
    )
    status: Mapped[str | None] = mapped_column(
        String(20), nullable=True, index=True,
        doc="知识库图片分析状态: analyzing / ready / failed / pending"
    )
    analysis_text: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="MiniMax VL 分析的结构化 JSON 文本"
    )
    tags: Mapped[str | None] = mapped_column(
        String(1000), nullable=True, doc="分析标签（JSON list 或逗号分隔）"
    )
    file_path: Mapped[str | None] = mapped_column(
        String(1000), nullable=True, doc="本地文件相对路径（outputs/private/kb_images/...）"
    )
    search_depth: Mapped[int] = mapped_column(
        Integer, default=10, doc="搜索时使用的强度"
    )
    page_number: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True,
        doc="关联的幻灯片页码（0-based），手动搜索时为 null"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
