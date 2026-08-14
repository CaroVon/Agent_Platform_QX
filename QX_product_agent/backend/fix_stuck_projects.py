"""
============================================================
僵死项目修复脚本
—— 识别并重置卡在活跃状态的"任务幽灵"，重新投递到 Celery 队列

问题背景：
  由于 Celery 进程崩溃，Redis 中的任务已被消费，但数据库中项目的状态
  依然卡在 preparing_data / preparing_outline / drafting，且相关任务
  标记为 pending。这些项目成为了永远等不到响应的"幽灵"。

修复策略：
  1. 扫描所有非终态项目（PREPARING_DATA / PREPARING_OUTLINE / DRAFTING）
  2. 将关联任务重置为 PENDING
  3. 将项目状态回退到 PREPARING_DATA
  4. 清理可能存在的暂存文件
  5. 重新投递 prepare_sources_workflow 到 Celery 队列

使用方法：
  在 backend 目录下执行:  python fix_stuck_projects.py
  前提条件: Redis 和 Celery Worker 正在运行
============================================================
"""

from __future__ import annotations

import asyncio
import os
import sys

from sqlalchemy import select

from app.core.celery_db import get_celery_db, get_crawled_data_path
from app.models.project import Project, ProjectStatus
from app.models.task import Task, TaskStatus
from app.tasks.report_workflow import prepare_sources_workflow


async def fix_stuck_projects():
    """主修复逻辑：扫描 → 重置 → 清理 → 重新投递"""

    async with get_celery_db() as db:
        print("🔍 开始扫描僵死项目...")

        # ── 1. 查找所有非终态的项目（卡住的活跃状态） ──────────
        active_statuses = [
            ProjectStatus.PREPARING_DATA,
            ProjectStatus.PREPARING_OUTLINE,
            ProjectStatus.DRAFTING,
        ]

        result = await db.execute(
            select(Project).where(Project.status.in_(active_statuses))
        )
        stuck_projects = result.scalars().all()

        if not stuck_projects:
            print("✅ 未发现卡住的项目。")
            return

        print(f"📋 共发现 {len(stuck_projects)} 个卡住的项目\n")

        for project in stuck_projects:
            print(
                f"⚠️  项目 ID: {project.id}"
                f"  | 主题: {project.topic}"
                f"  | 当前状态: {project.status.value}"
            )

            # ── 2. 清理关联的任务记录，重置为 PENDING ─────────
            tasks_result = await db.execute(
                select(Task).where(Task.project_id == project.id)
            )
            tasks = tasks_result.scalars().all()
            for task in tasks:
                task.status = TaskStatus.PENDING
            print(f"   📝 已重置 {len(tasks)} 个关联任务 → PENDING")

            # ── 3. 将项目状态回退到 PREPARING_DATA ────────────
            project.status = ProjectStatus.PREPARING_DATA
            print(f"   🔄 项目状态: {project.status.value}")

            # ── 4. 清理可能存在的暂存文件 ─────────────────────
            data_path = get_crawled_data_path(str(project.id))
            if os.path.exists(data_path):
                os.remove(data_path)
                print(f"   🧹 已清理暂存数据: {data_path}")

            await db.commit()
            print(f"   💾 数据库已提交")

            # ── 5. 重新投递 Celery 任务 ───────────────────────
            try:
                celery_task = prepare_sources_workflow.delay(str(project.id))
                print(f"   🚀 任务已重新投递至队列! Celery Task ID: {celery_task.id}")
            except Exception as e:
                print(f"   ❌ 重新投递任务失败（请确保 Redis 正在运行）: {e}")

            print()  # 项目之间的空行

        print("=" * 50)
        print("🎉 修复流程结束。")


if __name__ == "__main__":
    # Windows 下修复 asyncio 的 EventLoop 策略
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(fix_stuck_projects())
