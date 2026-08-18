"""
============================================================
Celery 运维助手 —— 任务取消（供 API 端点调用）
============================================================
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def revoke_task(task_id: str | None) -> bool:
    """按任务 ID 撤销（terminate 仅对 prefork 池生效）。"""
    if not task_id:
        return False
    try:
        from app.core.celery_app import celery_app

        celery_app.control.revoke(task_id, terminate=True, signal="SIGKILL")
        logger.info("[celery-ops] 已撤销任务 %s", task_id)
        return True
    except Exception as exc:  # noqa: BLE001 —— 撤销失败不阻断状态更新
        logger.warning("[celery-ops] 撤销任务失败 %s: %s", task_id, exc)
        return False


def revoke_active_tasks_for(entity_id: str) -> int:
    """Best-effort：撤销所有「首个参数 == entity_id」的运行中任务。

    entity_id 为 project_id（v1）或 product_id（v2，兼容旧记录无任务 ID 的情况）。
    """
    try:
        from celery.app.control import Inspect

        from app.core.celery_app import celery_app

        inspector = Inspect(app=celery_app)
        active = inspector.active() or {}
        revoked = 0
        for tasks in active.values():
            for t in tasks:
                args = t.get("args") or []
                if args and str(args[0]) == entity_id:
                    celery_app.control.revoke(t["id"], terminate=True, signal="SIGKILL")
                    revoked += 1
        if revoked:
            logger.info("[celery-ops] 已撤销 %d 个运行中任务 | entity=%s", revoked, entity_id)
        return revoked
    except Exception as exc:  # noqa: BLE001
        logger.warning("[celery-ops] 扫描撤销失败 %s: %s", entity_id, exc)
        return 0
