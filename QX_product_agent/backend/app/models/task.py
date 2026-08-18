"""
============================================================
任务 (Task) ORM 模型
============================================================
"""

from __future__ import annotations

import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Enum, Text, Integer, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDType


class TaskType(str, enum.Enum):
    """任务类型 —— 与前端 types/api.ts 保持同步"""
    SEARCH = "search"
    BUILD_KNOWLEDGE_BASE = "build_knowledge_base"
    GENERATE_OUTLINE = "generate_outline"
    WRITE_SECTION = "write_section"
    BUILD_REPORT = "build_report"
    GENERATE_PDF = "generate_pdf"
    IMAGE_GENERATION = "image_generation"


class TaskStatus(str, enum.Enum):
    """任务状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Task(Base):
    """项目下的异步任务单元"""

    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("projects.id"), nullable=False, index=True
    )
    task_type: Mapped[TaskType] = mapped_column(
        Enum(TaskType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        doc="任务类型"
    )
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, values_callable=lambda obj: [e.value for e in obj]),
        default=TaskStatus.PENDING,
        nullable=False,
    )
    sequence_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, doc="任务顺序"
    )
    section_title: Mapped[str | None] = mapped_column(
        String(500), nullable=True, doc="关联的章节标题"
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="任务失败时的错误信息"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )
