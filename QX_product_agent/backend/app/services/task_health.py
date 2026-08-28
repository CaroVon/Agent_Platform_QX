"""任务健康守护（P0.2）—— worker 心跳 + 失联自愈。

问题背景（E2E 亲历）：prefork 子进程被 OOM 静默击杀后，产品永远卡在
RUNNING（Celery unacked 消息需等 1 小时 visibility timeout 重投，而
claim 幂等守卫又会拒绝 RUNNING 态的重投）。

机制：
  - worker 每次进度事件写 Redis TTL 心跳键 qx:hb:{product_id}（120s）；
  - 看门狗（API lifespan 内每 60s）扫描：status=running 且心跳键缺失
    且 3 分钟无任何进度更新 → 判定失联 → 回退 queued 并重投任务
    （幂等 claim 允许 queued 领取，从 checkpoint/GatePause 快照恢复）。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.config import get_settings

logger = logging.getLogger(__name__)

HEARTBEAT_KEY = "qx:hb:{product_id}"
HEARTBEAT_TTL = 120
RUN_LOCK_KEY = "qx:run-lock:{product_id}"
RUN_LOCK_TTL = 900
# 无进度事件宽限（采集/长 LLM 阶段心跳仍在，故可短）
STALE_NO_PROGRESS_SEC = 180
SELF_HEAL_INTERVAL = 60


def acquire_run_lock(product_id: str) -> bool:
    """任务级互斥锁（DB 状态机之外的第二道防线）：
    同产品重复投递/状态窗口漏防时，仅持锁任务执行，其余直接返回。
    心跳事件顺带续期；任务终态显式释放。"""
    try:
        return bool(_redis().set(RUN_LOCK_KEY.format(product_id=product_id),
                                 "1", nx=True, ex=RUN_LOCK_TTL))
    except Exception:  # noqa: BLE001 —— Redis 不可用时放行（退化为仅 DB 判定）
        return True


def release_run_lock(product_id: str) -> None:
    try:
        _redis().delete(RUN_LOCK_KEY.format(product_id=product_id))
    except Exception:  # noqa: BLE001
        pass


def _redis():
    import os

    import redis

    # 非容器部署回退本机（settings 默认 "redis" 是 compose 服务名）
    host = get_settings().REDIS_HOST
    if host == "redis":
        host = os.environ.get("QX_REDIS_FALLBACK_HOST", "127.0.0.1")
    return redis.Redis(host=host, port=get_settings().REDIS_PORT, db=get_settings().REDIS_DB,
                       socket_connect_timeout=3, socket_timeout=3)


def heartbeat(product_id: str) -> None:
    """worker 侧：刷新任务心跳 + 运行锁续期（失败静默——进度主流程不受影响）。"""
    try:
        r = _redis()
        r.setex(HEARTBEAT_KEY.format(product_id=product_id), HEARTBEAT_TTL, "1")
        r.expire(RUN_LOCK_KEY.format(product_id=product_id), RUN_LOCK_TTL)
    except Exception:  # noqa: BLE001
        pass


def clear_heartbeat(product_id: str) -> None:
    """任务终态（completed/failed/waiting_approval）时清除心跳。"""
    try:
        _redis().delete(HEARTBEAT_KEY.format(product_id=product_id))
    except Exception:  # noqa: BLE001
        pass


def self_heal_stale() -> int:
    """看门狗：复位失联任务。返回复位数量。

    判定（三条件同时满足，避免误杀慢任务）：
      1. status == running
      2. Redis 心跳键不存在（worker ≥120s 未发任何事件）
      3. DB updated_at 距今 > STALE_NO_PROGRESS_SEC
    动作：置 queued + error_message 自愈说明 + 重投 Celery 任务。
    """
    from app.models.studio_product import StudioProduct, StudioProductStatus
    from app.core.celery_db import get_sync_engine
    from sqlalchemy.orm import Session

    healed = 0
    now = datetime.now(timezone.utc)
    try:
        r = _redis()
        with Session(get_sync_engine()) as session:
            rows = session.execute(
                select(StudioProduct).where(
                    StudioProduct.status == StudioProductStatus.RUNNING)
            ).scalars().all()
            for p in rows:
                pid = str(p.id)
                try:
                    if r.exists(HEARTBEAT_KEY.format(product_id=pid)):
                        continue
                except Exception:  # noqa: BLE001 —— Redis 不可用时不做任何复位
                    return 0
                updated = p.updated_at or now
                if updated.tzinfo is None:
                    updated = updated.replace(tzinfo=timezone.utc)
                if now - updated < timedelta(seconds=STALE_NO_PROGRESS_SEC):
                    continue
                p.status = StudioProductStatus.QUEUED
                p.error_message = f"自愈：worker 失联（≥{HEARTBEAT_TTL}s 无心跳）已重投"
                healed += 1
            if healed:
                session.commit()
        # 重投（独立于 DB 事务；claim 幂等保证仅一个 worker 生效）
        from app.core.celery_db import get_sync_engine as _gse  # noqa: F401
        from app.core.celery_app import celery_app

        with Session(get_sync_engine()) as session:
            rows = session.execute(
                select(StudioProduct).where(
                    StudioProduct.status == StudioProductStatus.QUEUED,
                    StudioProduct.error_message.like("自愈：%"),
                )
            ).scalars().all()
            for p in rows:
                celery_app.send_task(
                    "app.tasks.product_studio_tasks.run_product_studio_pipeline",
                    args=[str(p.id)])
                p.error_message = None
            if rows:
                session.commit()
        if healed:
            logger.warning("[SelfHeal] 复位 %s 个失联任务为 queued 并重投", healed)
    except Exception as exc:  # noqa: BLE001 —— 看门狗自身永不抛出
        logger.warning("[SelfHeal] 扫描失败: %s", exc)
    return healed


async def watchdog_loop() -> None:
    """FastAPI lifespan 内的周期看门狗（async 包装，线程池执行避免阻塞）。"""
    import asyncio

    while True:
        await asyncio.to_thread(self_heal_stale)
        await asyncio.sleep(SELF_HEAL_INTERVAL)


def publish_event(product_id: str, event: dict) -> None:
    """进度事件 → Redis Pub/Sub（SSE 通道，P0.3）。失败静默。"""
    try:
        _redis().publish(f"qx:events:{product_id}",
                         json.dumps(event, ensure_ascii=False, default=str))
    except Exception:  # noqa: BLE001
        pass
