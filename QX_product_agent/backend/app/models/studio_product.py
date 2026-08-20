"""
============================================================
StudioProduct ORM 模型 —— AI Product Studio 产品资产包
============================================================
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDType


class StudioProductStatus(str, enum.Enum):
    """Product Studio 流水线状态。"""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING_APPROVAL = "waiting_approval"
    PAUSED = "paused"


class StudioProduct(Base):
    """AI Product Studio 产品（一次 product/create 调用对应一条记录）。"""

    __tablename__ = "studio_products"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )
    idea: Mapped[str] = mapped_column(
        String(500), nullable=False, doc="产品想法"
    )
    # 兼容旧记录为空；新建记录始终写入，唯一约束覆盖并发提交。
    idempotency_key: Mapped[str | None] = mapped_column(
        String(128), nullable=True, unique=True, index=True,
        doc="创建请求幂等键",
    )
    idea_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True, index=True,
        doc="规范化产品想法哈希，用于拦截重复提交",
    )
    status: Mapped[StudioProductStatus] = mapped_column(
        Enum(StudioProductStatus, values_callable=lambda obj: [e.value for e in obj]),
        default=StudioProductStatus.QUEUED,
        nullable=False,
        index=True,
        doc="流水线状态",
    )
    asset_package: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="完整产品资产包（JSON 字符串）"
    )
    node_status: Mapped[str | None] = mapped_column(
        Text, nullable=True, default="{}",
        doc="实时节点进度（JSON 字符串：节点名 → running/completed/failed）",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="流水线失败原因"
    )
    # ── 安全与运维（认证 + 取消） ─────────────────────────────
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, nullable=True, index=True, doc="所属用户（单用户工作区为 admin）"
    )
    celery_task_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, doc="Celery 流水线任务 ID（用于取消/追踪）"
    )
    progress_log: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="执行进度事件日志（JSON Lines，供前端真实进度展示）"
    )
    asset_versions: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="资产版本历史（JSON：资产名 → [{ts, data}]）"
    )
    keywords: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="产品关键词组（JSON：方面 → 关键词列表，如 design/function/appearance/audience/scenario）"
    )
    # ── 模板选择权（前端指定设计主题/风格方法论；空 = LLM 自主决策） ──
    theme_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, doc="设计主题 id（THEME_PRESETS，用户指定）"
    )
    style_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, doc="风格方法论 id（ppt-master styles，用户指定）"
    )
    # 用户是否手动编辑过 keywords（编辑过则跳过自动重算）
    keywords_edited: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="0",
        doc="keywords 手动编辑标记（True 时 regenerate 不自动重算）"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )
