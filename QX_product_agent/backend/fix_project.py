"""
============================================================
数据库维护工具 —— 通用数据库诊断与修复
============================================================

用法:
  python fix_project.py                    # 列出所有项目状态
  python fix_project.py --fix <project_id> # 修复卡住的项目
  python fix_project.py --reset <project_id> # 重置项目到初始状态
  python fix_project.py --verify           # 验证数据库完整性
"""

import sys
import uuid
import argparse
from sqlalchemy import text

# 确保可以从当前目录导入 app 模块
sys.path.insert(0, ".")

from app.core.celery_db import get_sync_engine


def list_projects():
    """列出所有项目及其状态"""
    engine = get_sync_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, topic, status, created_at, "
                "CASE WHEN pdf_path IS NOT NULL THEN '✓' ELSE '✗' END as has_pdf, "
                "CASE WHEN outline_content IS NOT NULL THEN '✓' ELSE '✗' END as has_outline "
                "FROM projects ORDER BY created_at DESC"
            )
        ).fetchall()

    if not rows:
        print("📭 暂无项目记录")
        return

    print(f"\n{'='*80}")
    print(f"{'项目列表':^80}")
    print(f"{'='*80}")
    print(f"{'ID':<38} {'主题':<18} {'状态':<22} {'PDF':<5} {'大纲':<5}")
    print(f"{'-'*80}")

    for row in rows:
        pid_short = row[0][:8] + "..."
        topic = (row[1] or "")[:16]
        status = row[2] or "unknown"
        print(f"  {pid_short:<38} {topic:<18} {status:<22} {row[4]:<5} {row[5]:<5}")

    print(f"{'='*80}")
    print(f"  共 {len(rows)} 个项目\n")


def fix_project(project_id: str):
    """
    修复卡住的项目：
    - 将所有 FAILED 的任务重置为 COMPLETED
    - 清理 error_message
    - 如果所有任务都完成了，将项目状态推进到 COMPLETED
    """
    engine = get_sync_engine()
    pid_hex = uuid.UUID(project_id).hex

    with engine.connect() as conn:
        # 1. 查看项目当前状态
        row = conn.execute(
            text("SELECT id, topic, status FROM projects WHERE id = :pid"),
            {"pid": pid_hex},
        ).fetchone()

        if not row:
            print(f"❌ 项目 {project_id} 不存在")
            return

        print(f"\n📋 项目: {row[1]}")
        print(f"   当前状态: {row[2]}")

        # 2. 修复失败的任务
        failed_tasks = conn.execute(
            text(
                "SELECT task_type, error_message FROM tasks "
                "WHERE project_id = :pid AND status = 'failed'"
            ),
            {"pid": pid_hex},
        ).fetchall()

        if failed_tasks:
            print(f"\n🔧 发现 {len(failed_tasks)} 个失败任务，正在修复...")
            for ft in failed_tasks:
                print(f"   - {ft[0]}: {ft[1][:80] if ft[1] else '(无错误信息)'}")

            conn.execute(
                text(
                    "UPDATE tasks SET status = 'completed', error_message = NULL "
                    "WHERE project_id = :pid AND status = 'failed'"
                ),
                {"pid": pid_hex},
            )
            conn.commit()
            print(f"   ✅ 已重置 {len(failed_tasks)} 个任务为 completed")
        else:
            print("   ✅ 无失败任务")

        # 3. 统计任务完成情况
        task_stats = conn.execute(
            text(
                "SELECT COUNT(*) as total, "
                "SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed, "
                "SUM(CASE WHEN status IN ('pending', 'processing') THEN 1 ELSE 0 END) as in_progress "
                "FROM tasks WHERE project_id = :pid"
            ),
            {"pid": pid_hex},
        ).fetchone()

        total = task_stats[0] or 0
        completed = task_stats[1] or 0
        in_progress = task_stats[2] or 0

        print(f"\n📊 任务统计: {completed}/{total} 已完成, {in_progress} 进行中")

        # 4. 如果所有任务已完成，推进项目状态
        if in_progress == 0 and completed == total and row[2] != "completed":
            conn.execute(
                text("UPDATE projects SET status = 'completed', error_message = NULL WHERE id = :pid"),
                {"pid": pid_hex},
            )
            conn.commit()
            print(f"   ✅ 项目状态已推进到 completed")
        elif row[2] == "failed":
            conn.execute(
                text("UPDATE projects SET status = 'completed', error_message = NULL WHERE id = :pid"),
                {"pid": pid_hex},
            )
            conn.commit()
            print(f"   ✅ 项目状态从 failed 修复为 completed")

        print(f"\n✨ 修复完成")


def reset_project(project_id: str):
    """将项目重置到初始状态 (PREPARING_DATA)"""
    engine = get_sync_engine()
    pid_hex = uuid.UUID(project_id).hex

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT topic FROM projects WHERE id = :pid"),
            {"pid": pid_hex},
        ).fetchone()

        if not row:
            print(f"❌ 项目 {project_id} 不存在")
            return

        confirm = input(f"\n⚠️  确定要重置项目「{row[0]}」(ID: {project_id[:8]}...) 吗? [y/N] ")
        if confirm.lower() != "y":
            print("已取消")
            return

        conn.execute(
            text("UPDATE projects SET status = 'preparing_data', error_message = NULL, "
                 "outline_content = NULL, pdf_path = NULL, md_path = NULL WHERE id = :pid"),
            {"pid": pid_hex},
        )
        conn.execute(
            text("UPDATE tasks SET status = 'pending', error_message = NULL, "
                 "started_at = NULL, completed_at = NULL WHERE project_id = :pid"),
            {"pid": pid_hex},
        )
        conn.execute(
            text("DELETE FROM document_blocks WHERE project_id = :pid"),
            {"pid": pid_hex},
        )
        conn.execute(
            text("DELETE FROM documents WHERE project_id = :pid"),
            {"pid": pid_hex},
        )
        conn.execute(
            text("DELETE FROM project_logs WHERE project_id = :pid"),
            {"pid": pid_hex},
        )
        conn.commit()
        print(f"   ✅ 项目已重置为 preparing_data")


def verify_database():
    """验证数据库完整性"""
    engine = get_sync_engine()
    issues = []

    with engine.connect() as conn:
        # 1. 检查孤儿任务
        orphan_tasks = conn.execute(
            text(
                "SELECT t.id, t.task_type FROM tasks t "
                "LEFT JOIN projects p ON t.project_id = p.id "
                "WHERE p.id IS NULL"
            )
        ).fetchall()
        if orphan_tasks:
            issues.append(f"发现 {len(orphan_tasks)} 个孤儿任务（所属项目已不存在）")

        # 2. 检查孤儿文档块
        orphan_blocks = conn.execute(
            text(
                "SELECT COUNT(*) FROM document_blocks db "
                "LEFT JOIN projects p ON db.project_id = p.id "
                "WHERE p.id IS NULL"
            )
        ).scalar()
        if orphan_blocks:
            issues.append(f"发现 {orphan_blocks} 个孤儿文档块")

        # 3. 检查卡住的项目（长时间处于非终态）
        stuck = conn.execute(
            text(
                "SELECT id, topic, status FROM projects "
                "WHERE status NOT IN ('completed', 'failed')"
            )
        ).fetchall()
        if stuck:
            issues.append(f"发现 {len(stuck)} 个卡住的项目（非终态）:")
            for s in stuck:
                issues.append(f"  - {s[0][:8]}... | {s[1][:20]} | {s[2]}")

    print(f"\n{'='*60}")
    print(f"{'数据库完整性验证':^60}")
    print(f"{'='*60}")

    if issues:
        print(f"\n⚠️  发现 {len(issues)} 个问题:\n")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
    else:
        print("\n✅ 数据库完整性检查通过 — 无异常")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="QX Agent 数据库维护工具")
    parser.add_argument("--fix", type=str, metavar="PROJECT_ID", help="修复指定项目")
    parser.add_argument("--reset", type=str, metavar="PROJECT_ID", help="重置指定项目")
    parser.add_argument("--verify", action="store_true", help="验证数据库完整性")
    args = parser.parse_args()

    if args.fix:
        fix_project(args.fix)
    elif args.reset:
        reset_project(args.reset)
    elif args.verify:
        verify_database()
    else:
        list_projects()
