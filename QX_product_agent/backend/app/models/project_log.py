"""
============================================================
项目运行日志模型 —— 业务级时间轴事件
============================================================

每个日志条目代表 Agent 在后台执行的一个关键动作节点。
前端通过轮询/SSE 获取时间轴数据，在右侧面板渲染为终端控制台风格的实时日志流。

日志级别：
  - info:  常规步骤 (搜索、抓取、生成...)
  - warn:  可恢复的异常 (API 速率限制、重试...)
  - error: 失败事件
  - milestone: 状态机推进关键节点
"""

from __future__ import annotations

import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Enum, func, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDType


class LogLevel(str, enum.Enum):
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    MILESTONE = "milestone"


class ProjectLog(Base):
    """项目执行时间轴日志"""

    __tablename__ = "project_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    level: Mapped[LogLevel] = mapped_column(
        Enum(LogLevel, values_callable=lambda obj: [e.value for e in obj]),
        default=LogLevel.INFO,
        nullable=False,
    )
    step: Mapped[str] = mapped_column(
        String(200), nullable=False,
        doc="当前步骤标识，如 'searching', 'building_kb', 'writing_section'"
    )
    message: Mapped[str] = mapped_column(
        Text, nullable=False,
        doc="人类可读的日志消息，如 '🔍 正在深度抓取 Apple Vision Pro 竞品数据...'"
    )
    icon: Mapped[str | None] = mapped_column(
        String(10), nullable=True,
        doc="emoji 图标，如 🔍 📚 ✍️ ✅ ❌"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
