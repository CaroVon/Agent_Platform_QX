"""
============================================================
Celery Worker 数据库基础设施
—— 提供同步/异步引擎和共享工具函数

核心设计原则：
  • 所有业务逻辑数据库操作统一走 ProjectRepo（同步）
  • 本模块仅提供引擎创建、路径工具等基础设施
  • Celery Worker 和 FastAPI 使用相同配置但独立引擎
============================================================
"""

from __future__ import annotations

import os
import sys
import asyncio
import logging
import tempfile
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import create_engine, event
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ─── Windows asyncio 兼容性修复 ─────────────────────────────────
if sys.platform == "win32" and sys.version_info < (3, 14):
    try:
        from asyncio import WindowsSelectorEventLoopPolicy
        asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())
    except ImportError:
        pass

# ─── 配置 ──────────────────────────────────────────────────────
settings = get_settings()
_is_sqlite = "sqlite" in settings.DATABASE_URL_ASYNC


# ══════════════════════════════════════════════════════════════
# 异步引擎（Celery Worker 专用——供 fix_project.py 等脚本使用）
# ══════════════════════════════════════════════════════════════

if _is_sqlite:
    celery_engine = create_async_engine(
        settings.DATABASE_URL_ASYNC,
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
else:
    celery_engine = create_async_engine(
        settings.DATABASE_URL_ASYNC,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )

CeleryAsyncSession = async_sessionmaker(
    celery_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@event.listens_for(celery_engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """SQLite 连接时自动启用 WAL 模式和 foreign key 约束"""
    if _is_sqlite:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.close()


@asynccontextmanager
async def get_celery_db() -> AsyncGenerator[AsyncSession, None]:
    """Celery Worker 中使用的异步数据库会话上下文管理器"""
    session = CeleryAsyncSession()
    try:
        yield session
        await session.commit()
    except Exception as e:
        await session.rollback()
        logger.error("Celery DB 操作回滚: %s", str(e))
        raise
    finally:
        await session.close()


# ══════════════════════════════════════════════════════════════
# 同步引擎（Celery Worker 专用——供 ProjectRepo 使用）
# ══════════════════════════════════════════════════════════════

_sync_engine = None


def get_sync_engine():
    """获取共享的同步数据库引擎（延迟初始化，线程安全）"""
    global _sync_engine
    if _sync_engine is None:
        sync_url = settings.DATABASE_URL_SYNC
        if "sqlite" in sync_url:
            _sync_engine = create_engine(
                sync_url,
                connect_args={"check_same_thread": False},
                poolclass=NullPool,
            )
        else:
            _sync_engine = create_engine(
                sync_url,
                pool_size=3,
                max_overflow=5,
                pool_pre_ping=True,
            )
    return _sync_engine


# ══════════════════════════════════════════════════════════════
# 平台工具
# ══════════════════════════════════════════════════════════════

def _get_temp_dir() -> str:
    """获取平台感知的临时目录路径"""
    return settings.OUTPUT_DIR or tempfile.gettempdir()


def get_crawled_data_path(project_id: str) -> str:
    """获取项目爬取数据的暂存文件路径（跨平台兼容）"""
    temp_dir = _get_temp_dir()
    os.makedirs(temp_dir, exist_ok=True)
    return os.path.join(temp_dir, f"crawled_data_{project_id}.json")
