"""
============================================================
异步数据库引擎与会话工厂
使用 SQLAlchemy 2.0 asyncio 扩展

SQLite 特殊处理：
- 使用 NullPool 避免连接池冲突
- 启用 WAL 模式提升并发读写性能
- check_same_thread=False 允许多线程访问
============================================================
"""

from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.models.base import Base  # 复用 models 中的统一 Base

settings = get_settings()

_is_sqlite = "sqlite" in settings.DATABASE_URL_ASYNC

# ─── 异步引擎 ───────────────────────────────────────────────────
if _is_sqlite:
    # SQLite：NullPool 避免连接池问题；check_same_thread=False 允许多线程
    engine = create_async_engine(
        settings.DATABASE_URL_ASYNC,
        echo=settings.DEBUG,
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, connection_record):
        """SQLite 连接时启用 WAL 模式（提升并发读写性能）和 foreign key 约束"""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.close()
else:
    engine = create_async_engine(
        settings.DATABASE_URL_ASYNC,
        echo=settings.DEBUG,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
    )

# ─── 异步会话工厂 ───────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # 防止 commit 后属性过期
)


async def get_db() -> AsyncSession:
    """FastAPI 依赖注入：获取异步数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
