"""
============================================================
看门狗（Watchdog）
—— 回收卡死的 running/queued 任务，防止「永久生成中」
============================================================

触发方式：
  1. 应用启动时执行一次
  2. lifespan 中每 WATCHDOG_INTERVAL_MINUTES 分钟执行一次

回收规则：
  - studio_products：status ∈ (queued, running) 且 updated_at 早于
    WATCHDOG_STALE_HOURS 小时 → 置 failed（error_message 标注 watchdog）
  - projects（v1）：status ∈ (preparing_data, preparing_outline, drafting)
    且 updated_at 早于阈值 → 置 failed

阈值默认 3 小时：大于 studio 任务硬超时（70min）+ 重投递窗口，避免误杀
正常执行的慢任务（ppt_design 逐页 SVG 重试）。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from app.core.config import get_settings
from app.models.project import Project, ProjectStatus
from app.models.studio_product import StudioProduct, StudioProductStatus

logger = logging.getLogger(__name__)

# 任务硬超时上限（product_studio_tasks: 70min / v1 全局 45min）之上留余量
STALE_HOURS_DEFAULT = 3
INTERVAL_MINUTES_DEFAULT = 15

_RECOVERABLE_PROJECT_STATES = (
    ProjectStatus.PREPARING_DATA,
    ProjectStatus.PREPARING_OUTLINE,
    ProjectStatus.DRAFTING,
)


async def recover_stale_tasks(db) -> int:
    """回收所有超期未完成的 v1/v2 任务，返回回收数量。"""
    settings = get_settings()
    stale_hours = settings.WATCHDOG_STALE_HOURS
    cutoff = datetime.now(timezone.utc) - timedelta(hours=stale_hours)
    recovered = 0

    # ── v2: studio_products ─────────────────────────────────────
    # 兼容旧记录 updated_at 为空：以 created_at 计
    products = (await db.execute(
        select(StudioProduct).where(
            StudioProduct.status.in_([
                StudioProductStatus.QUEUED,
                StudioProductStatus.RUNNING,
            ])
        )
    )).scalars().all()
    for p in products:
        ref = p.updated_at or p.created_at
        if ref is not None and ref.replace(tzinfo=timezone.utc if ref.tzinfo is None else ref.tzinfo) < cutoff:
            await db.execute(
                update(StudioProduct)
                .where(StudioProduct.id == p.id)
                .values(
                    status=StudioProductStatus.FAILED,
                    error_message=f"watchdog: 任务超过 {stale_hours} 小时未完成，已自动回收（请重试）",
                )
            )
            recovered += 1
            logger.warning("[watchdog] 回收卡死产品 | id=%s | 最后更新=%s", p.id, ref)

    # ── v1: projects ────────────────────────────────────────────
    projects = (await db.execute(
        select(Project).where(Project.status.in_(_RECOVERABLE_PROJECT_STATES))
    )).scalars().all()
    for p in projects:
        ref = p.updated_at or p.created_at
        if ref is not None and ref.replace(tzinfo=timezone.utc if ref.tzinfo is None else ref.tzinfo) < cutoff:
            await db.execute(
                update(Project)
                .where(Project.id == p.id)
                .values(
                    status=ProjectStatus.FAILED,
                    error_message=f"watchdog: 任务超过 {stale_hours} 小时未完成，已自动回收（请重试）",
                )
            )
            recovered += 1
            logger.warning("[watchdog] 回收卡死项目 | id=%s | 最后更新=%s", p.id, ref)

    if recovered:
        await db.commit()
        logger.info("[watchdog] 共回收 %d 个卡死任务", recovered)
    return recovered


async def watchdog_loop() -> None:
    """周期性看门狗循环（由 FastAPI lifespan 启动，进程退出即停止）。"""
    from app.core.database import AsyncSessionLocal

    interval_minutes = get_settings().WATCHDOG_INTERVAL_MINUTES
    while True:
        await asyncio.sleep(interval_minutes * 60)
        try:
            async with AsyncSessionLocal() as db:
                await recover_stale_tasks(db)
        except Exception as exc:  # noqa: BLE001 —— 看门狗自身失败不影响主服务
            logger.warning("[watchdog] 本轮回收失败: %s", exc)


import asyncio  # noqa: E402 —— 保持导入位于文件尾部以清晰标注循环依赖
