"""
============================================================
工作流重触发工具 —— 将项目重置到指定阶段并重新触发 Celery 任务
============================================================

用法:
  python reset_project.py <project_id> --stage outline   # 从大纲生成阶段开始
  python reset_project.py <project_id> --stage drafting   # 从撰写阶段开始
  python reset_project.py <project_id> --stage sources    # 从资料搜集阶段开始
"""

import sys
import uuid
import argparse

sys.path.insert(0, ".")

from sqlalchemy import text
from app.core.celery_db import get_sync_engine
from app.models.project import ProjectStatus

STAGE_CONFIG = {
    "sources": {
        "status": ProjectStatus.PREPARING_DATA,
        "reset_tasks": ["search", "build_knowledge_base", "generate_outline", "write_section", "build_report", "generate_pdf"],
        "trigger_task": "prepare_sources_workflow",
    },
    "outline": {
        "status": ProjectStatus.PREPARING_OUTLINE,
        "reset_tasks": ["build_knowledge_base", "generate_outline", "write_section", "build_report", "generate_pdf"],
        "trigger_task": "generate_outline_workflow",
    },
    "drafting": {
        "status": ProjectStatus.DRAFTING,
        "reset_tasks": ["write_section", "build_report", "generate_pdf"],
        "trigger_task": "run_draft_sections_workflow",
    },
}


def reset_and_trigger(project_id: str, stage: str):
    config = STAGE_CONFIG[stage]
    engine = get_sync_engine()
    pid_hex = uuid.UUID(project_id).hex

    with engine.connect() as conn:
        # 验证项目存在
        row = conn.execute(
            text("SELECT topic, status FROM projects WHERE id = :pid"),
            {"pid": pid_hex},
        ).fetchone()
        if not row:
            print(f"❌ 项目 {project_id} 不存在")
            return

        print(f"📋 项目: {row[0]}")
        print(f"   当前状态: {row[1]} → {config['status'].value}")

        # 更新项目状态
        conn.execute(
            text("UPDATE projects SET status = :status, error_message = NULL WHERE id = :pid"),
            {"pid": pid_hex, "status": config["status"].value},
        )

        # 重置相关任务
        for task_type in config["reset_tasks"]:
            conn.execute(
                text(
                    "UPDATE tasks SET status = 'pending', error_message = NULL, "
                    "started_at = NULL, completed_at = NULL "
                    "WHERE project_id = :pid AND task_type = :task_type"
                ),
                {"pid": pid_hex, "task_type": task_type},
            )
        conn.commit()
        print(f"   ✅ 项目已重置到 {config['status'].value}")

    # 重新触发 Celery 工作流
    print(f"\n🚀 正在触发 {config['trigger_task']}...")
    try:
        from app.tasks.report_workflow import (
            prepare_sources_workflow,
            generate_outline_workflow,
            run_draft_sections_workflow,
        )

        task_map = {
            "prepare_sources_workflow": prepare_sources_workflow,
            "generate_outline_workflow": generate_outline_workflow,
            "run_draft_sections_workflow": run_draft_sections_workflow,
        }

        task_fn = task_map[config["trigger_task"]]
        result = task_fn.delay(project_id)
        print(f"   ✅ Celery 任务已提交: {result.id}")
    except Exception as e:
        print(f"   ⚠️  Celery 任务提交失败 (Redis 可能未运行): {e}")
        print(f"   项目状态已更新，可在 Redis 就绪后手动触发")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="QX Agent 工作流重触发工具")
    parser.add_argument("project_id", type=str, help="项目 UUID")
    parser.add_argument(
        "--stage",
        type=str,
        required=True,
        choices=["sources", "outline", "drafting"],
        help="重置到哪个阶段",
    )
    args = parser.parse_args()
    reset_and_trigger(args.project_id, args.stage)
