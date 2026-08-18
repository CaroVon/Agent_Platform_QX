"""
============================================================
轻量 schema 演进助手
—— 对既有 SQLite 运行库补充新增列（create_all 不会修改已有表）
   Postgres 部署请使用 Alembic 迁移（此助手对 Postgres 安全跳过/或需手动迁移）
============================================================
"""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)

# (表名, 列名, 列定义 SQL 片段)
_ENSURES: list[tuple[str, str, str]] = [
    ("studio_products", "owner_id", "CHAR(32)"),
    ("studio_products", "celery_task_id", "VARCHAR(64)"),
    ("studio_products", "progress_log", "TEXT"),
    ("studio_products", "idempotency_key", "VARCHAR(128)"),
    ("studio_products", "idea_hash", "VARCHAR(64)"),
    ("projects", "canvas_data", "TEXT"),
    ("projects", "topic_embedding", "TEXT"),
    ("projects", "domain_tags", "TEXT"),
    ("studio_products", "asset_versions", "TEXT"),
]


async def ensure_columns(engine: AsyncEngine) -> None:
    """启动时确保新列存在（仅对缺失列执行 ALTER TABLE ADD COLUMN）。"""
    try:
        async with engine.connect() as conn:
            def _ensure(sync_conn) -> list[tuple[str, str]]:
                # Inspector 必须在 run_sync 回调内完整使用，不能把绑定了同步连接的
                # Inspector 带出回调后再调用，否则 async SQLite 会触发 greenlet 错误。
                inspector = inspect(sync_conn)
                tables = set(inspector.get_table_names())
                added: list[tuple[str, str]] = []
                for table, column, ddl in _ENSURES:
                    if table not in tables:
                        continue
                    cols = {c["name"] for c in inspector.get_columns(table)}
                    if column in cols:
                        continue
                    sync_conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {ddl}'))
                    added.append((table, column))
                return added

            for table, column in await conn.run_sync(_ensure):
                logger.info("[schema] 已补充列 %s.%s", table, column)
            await conn.commit()
    except Exception as exc:  # noqa: BLE001 —— 启动不应因迁移失败而崩溃
        logger.warning("[schema] ensure_columns 跳过（%s）", exc)
