#!/usr/bin/env python3
"""
======================================================================
dev_section_loop.py — section_writer → Canvas 单点测试循环
======================================================================

绕过 Celery/Redis，直接调用 write_section() 反复重跑 Phase 3（逐章撰写），
秒级验证 section_writer 输出 → DocumentBlock → Canvas 渲染全链路。

用法:
  # 查看当前检查点状态
  python scripts/dev_section_loop.py status

  # 重跑全部章节（使用已保存的检查点项目）
  python scripts/dev_section_loop.py run

  # 指定项目重跑（自动保存为检查点）
  python scripts/dev_section_loop.py run --project <project_id>

  # 只重跑单个章节
  python scripts/dev_section_loop.py run --section "竞品分析"

  # dry-run：预览输出但不写入数据库
  python scripts/dev_section_loop.py run --dry-run

  # 跳过图片搜索（加速迭代）
  python scripts/dev_section_loop.py run --no-images

  # 与上次运行对比差异
  python scripts/dev_section_loop.py run --diff

典型开发流程:
  1. 前端创建项目 → 审核资料 → 审批大纲（到达 WAITING_FOR_OUTLINE）
  2. python scripts/dev_section_loop.py run --project <project_id>
  3. 打开编辑器查看画布效果
  4. 修改 section_writer.py 或 dataTransform.ts
  5. python scripts/dev_section_loop.py run   # 重跑，清旧块写新块
  6. 刷新浏览器 → 查看效果 → 回到步骤 4
======================================================================
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ══════════════════════════════════════════════════════════════
# sys.path 设置（与 main.py / reset_project.py 一致）
# ══════════════════════════════════════════════════════════════

_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent
_backend_dir = _project_root / "backend"

# 顺序必须与 main.py 一致：backend/ 优先，project_root 次之
# insert(0) 是栈式操作，后插入的在前 → 先插 project_root，后插 backend_dir
# 结果：sys.path[0] = backend/（优先），sys.path[1] = project_root/
for _d in (str(_project_root), str(_backend_dir)):
    if _d not in sys.path:
        sys.path.insert(0, _d)

# 切换到 backend/ 目录 —— .env 中数据库路径（./runtime/local_dev.db）相对于此
os.chdir(str(_backend_dir))

CHECKPOINT_FILE = _script_dir / ".dev_checkpoint.json"

# ══════════════════════════════════════════════════════════════
# 后端 / 研究引擎 导入
# ══════════════════════════════════════════════════════════════

from app.core.celery_db import get_sync_engine
from app.models.project import Project, ProjectStatus
from app.models.document_block import DocumentBlock
from app.models.document import Document
from app.models.project_image import ProjectImage
from app.models.task import Task, TaskStatus
from app.shared.outline_parser import extract_sections
from app.report.section_writer import write_section
from sqlalchemy import select, delete, update
from sqlalchemy.orm import Session

# ══════════════════════════════════════════════════════════════
# 日志
# ══════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("dev_section_loop")


# ══════════════════════════════════════════════════════════════
# 检查点管理
# ══════════════════════════════════════════════════════════════

def _load_checkpoint() -> dict | None:
    """读取保存的检查点。"""
    if CHECKPOINT_FILE.exists():
        try:
            return json.loads(CHECKPOINT_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
    return None


def _save_checkpoint(project_id: str, topic: str = "") -> None:
    """保存检查点到文件。"""
    data = {
        "project_id": project_id,
        "topic": topic,
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("📌 检查点已保存: project_id=%s", project_id)


def _resolve_project_id(cli_arg: str | None) -> str:
    """解析 project_id：CLI 参数 > 检查点文件 > 报错。"""
    if cli_arg:
        return cli_arg
    cp = _load_checkpoint()
    if cp and cp.get("project_id"):
        logger.info("📌 使用已保存的检查点: project_id=%s", cp["project_id"])
        return cp["project_id"]
    logger.error("❌ 未指定 project_id，且无已保存的检查点。请使用 --project 参数。")
    sys.exit(1)


# ══════════════════════════════════════════════════════════════
# 数据库操作
# ══════════════════════════════════════════════════════════════

def get_project_info(project_id: str) -> dict[str, Any]:
    """获取项目基本信息。"""
    engine = get_sync_engine()
    pid = uuid.UUID(project_id)
    with Session(engine) as session:
        project = session.execute(
            select(Project).where(Project.id == pid)
        ).scalar_one_or_none()
        if project is None:
            logger.error("❌ 项目不存在: %s", project_id)
            sys.exit(1)
        return {
            "id": str(project.id),
            "topic": project.topic,
            "status": project.status.value if project.status else "unknown",
            "template_type": getattr(project, "template_type", "product") or "product",
            "search_depth": getattr(project, "search_depth", 10) or 10,
            "outline_content": project.outline_content,
        }


def clear_blocks(project_id: str) -> None:
    """清空项目的所有 DocumentBlock、Document、ProjectImage 记录。"""
    engine = get_sync_engine()
    with Session(engine) as session:
        # DocumentBlock
        deleted_blocks = session.execute(
            delete(DocumentBlock).where(DocumentBlock.project_id == uuid.UUID(project_id))
        ).rowcount
        # Document
        deleted_docs = session.execute(
            delete(Document).where(Document.project_id == uuid.UUID(project_id))
        ).rowcount
        # ProjectImage
        deleted_imgs = session.execute(
            delete(ProjectImage).where(ProjectImage.project_id == uuid.UUID(project_id))
        ).rowcount
        session.commit()
    logger.info("🧹 已清理: %d blocks, %d documents, %d images", deleted_blocks, deleted_docs, deleted_imgs)


def reset_project_to_drafting(project_id: str) -> None:
    """将项目状态重置为 DRAFTING，清空错误信息。"""
    engine = get_sync_engine()
    with Session(engine) as session:
        session.execute(
            update(Project)
            .where(Project.id == uuid.UUID(project_id))
            .values(status=ProjectStatus.DRAFTING, error_message=None)
        )
        # 重置相关任务
        for task_type in ["write_section", "build_report", "generate_pdf"]:
            session.execute(
                update(Task)
                .where(
                    Task.project_id == uuid.UUID(project_id),
                    Task.task_type == task_type,
                )
                .values(
                    status=TaskStatus.PENDING,
                    error_message=None,
                )
            )
        session.commit()
    logger.info("🔄 项目状态已重置为 DRAFTING")


def save_block(project_id: str, section_title: str, content: str, order_index: int) -> None:
    """保存单个章节的 DocumentBlock。"""
    engine = get_sync_engine()
    pid = uuid.UUID(project_id)
    with Session(engine) as session:
        # 查找是否已有同章节同序号的 block
        existing = session.execute(
            select(DocumentBlock).where(
                DocumentBlock.project_id == pid,
                DocumentBlock.section_title == section_title,
                DocumentBlock.order_index == order_index,
            )
        ).scalars().first()

        if existing:
            existing.content = content
        else:
            block = DocumentBlock(
                project_id=pid,
                section_title=section_title,
                content=content,
                citations="{}",
                order_index=order_index,
            )
            session.add(block)
        session.commit()


def complete_project(project_id: str) -> None:
    """标记项目为 COMPLETED。"""
    engine = get_sync_engine()
    with Session(engine) as session:
        session.execute(
            update(Project)
            .where(Project.id == uuid.UUID(project_id))
            .values(status=ProjectStatus.COMPLETED, error_message=None)
        )
        session.commit()
    logger.info("✅ 项目状态已更新为 COMPLETED")


def count_existing_blocks(project_id: str) -> int:
    """查询当前已有的 DocumentBlock 数量。"""
    from sqlalchemy import func
    engine = get_sync_engine()
    pid = uuid.UUID(project_id)
    with Session(engine) as session:
        result = session.execute(
            select(func.count()).select_from(DocumentBlock).where(DocumentBlock.project_id == pid)
        ).scalar()
        return result if result is not None else 0


# ══════════════════════════════════════════════════════════════
# 核心逻辑
# ══════════════════════════════════════════════════════════════

def run_sections(
    project_id: str,
    single_section: str | None = None,
    section_limit: int | None = None,
    dry_run: bool = False,
    no_images: bool = True,
    diff_mode: bool = False,
) -> dict[str, Any]:
    """
    核心循环：解析大纲 → 逐章调用 write_section() → 保存 DocumentBlock。

    Args:
        project_id:     项目 UUID
        single_section: 只跑指定章节（None = 全部）
        dry_run:        预览模式，不写数据库
        no_images:      跳过图片搜索（默认 True，加速迭代）
        diff_mode:      与上次运行对比差异
    """
    # ── 获取项目信息 ──
    info = get_project_info(project_id)
    topic = info["topic"]
    outline = info["outline_content"]
    template_type = info["template_type"]
    search_depth = info["search_depth"]

    if not outline:
        logger.error("❌ 项目大纲为空，无法运行。请先确保项目已完成 Phase 2（大纲生成）。")
        sys.exit(1)

    sections = extract_sections(outline)
    if not sections:
        logger.error("❌ 未能从大纲中解析出章节标题。")
        sys.exit(1)

    # 过滤单章节
    if single_section:
        matched = [s for s in sections if single_section in s]
        if not matched:
            logger.error("❌ 未找到匹配的章节: '%s'。可用章节: %s", single_section, sections)
            sys.exit(1)
        sections = matched
        logger.info("🎯 仅运行章节: %s", sections[0])

    # 限制章节数量
    if section_limit and section_limit < len(sections):
        sections = sections[:section_limit]
        logger.info("🔢 限制为前 %d 章", section_limit)

    logger.info("=" * 60)
    logger.info("🚀 开始逐章撰写 | topic=%s | template=%s | depth=%d | sections=%d",
                topic, template_type, search_depth, len(sections))
    logger.info("=" * 60)

    # ── 清理旧数据 ──
    if not dry_run:
        old_count = count_existing_blocks(project_id)
        clear_blocks(project_id)
        reset_project_to_drafting(project_id)
        logger.info("🧹 已清理 %d 个旧 DocumentBlock", old_count)

    # ── 逐章撰写 ──
    results: list[dict[str, Any]] = []
    total_start = time.time()
    success_count = 0
    fail_count = 0

    for idx, section_title in enumerate(sections):
        section_start = time.time()
        try:
            logger.info("[%d/%d] ✍️  撰写: %s", idx + 1, len(sections), section_title)

            content = write_section(
                topic=topic,
                section_title=section_title,
                project_id=project_id,
                template_type=template_type,
                search_depth=search_depth,
            )

            elapsed = time.time() - section_start
            char_count = len(content) if content else 0

            if not dry_run:
                order = (idx + 1) * 10
                save_block(project_id, section_title, content, order)

            results.append({
                "section": section_title,
                "chars": char_count,
                "time": elapsed,
                "success": True,
                "preview": content[:200] if dry_run else "",
            })
            success_count += 1
            logger.info("  ✅ 完成 | %d 字符 | %.1fs", char_count, elapsed)

        except Exception as exc:
            elapsed = time.time() - section_start
            results.append({
                "section": section_title,
                "chars": 0,
                "time": elapsed,
                "success": False,
                "error": str(exc),
            })
            fail_count += 1
            logger.error("  ❌ 失败: %s (%.1fs)", str(exc)[:100], elapsed)

    total_time = time.time() - total_start

    # ── 标记完成 ──
    if not dry_run:
        complete_project(project_id)

    # ── 输出报告 ──
    _print_report(results, total_time, project_id, success_count, fail_count, dry_run)

    # ── 保存检查点 ──
    if not dry_run:
        _save_checkpoint(project_id, topic)

    return {
        "total_time": total_time,
        "success": success_count,
        "failed": fail_count,
        "results": results,
    }


def _print_report(
    results: list[dict],
    total_time: float,
    project_id: str,
    success: int,
    failed: int,
    dry_run: bool,
) -> None:
    """打印运行摘要报告。"""
    print()
    print("═══ Section Writer Dev Loop ═══")
    print(f"Project:  {project_id}")
    print(f"Mode:     {'DRY-RUN (预览，未写库)' if dry_run else 'LIVE (已写入数据库)'}")
    print(f"Results:  {success} success, {failed} failed, {total_time:.1f}s total")
    print()

    total_chars = 0
    for r in results:
        status = "✅" if r["success"] else "❌"
        print(f"  {status} {r['section']}")
        print(f"     {r['chars']:,} chars | {r['time']:.1f}s")
        if not r["success"]:
            print(f"     Error: {r.get('error', 'unknown')[:120]}")
        total_chars += r["chars"]

    print()
    print(f"Total: {total_chars:,} chars across {len(results)} sections")
    print(f"Canvas: http://localhost:8000/projects/{project_id}/editor")
    print("═══ ═══ ═══ ═══ ═══ ═══ ═══ ═══")


# ══════════════════════════════════════════════════════════════
# status 命令
# ══════════════════════════════════════════════════════════════

def cmd_status() -> None:
    """显示当前检查点和项目状态。"""
    cp = _load_checkpoint()
    print("═══ Dev Section Loop Status ═══")
    print()

    if cp:
        print(f"📌 已保存检查点:")
        print(f"   Project ID:  {cp.get('project_id', 'N/A')}")
        print(f"   Topic:       {cp.get('topic', 'N/A')}")
        print(f"   Saved at:    {cp.get('saved_at', 'N/A')}")
        print()

        try:
            info = get_project_info(cp["project_id"])
            print(f"📋 项目当前状态:")
            print(f"   Topic:       {info['topic']}")
            print(f"   Status:      {info['status']}")
            print(f"   Template:    {info['template_type']}")
            print(f"   Depth:       {info['search_depth']}")
            outline = info.get("outline_content", "")
            if outline:
                sections = extract_sections(outline)
                print(f"   Sections:    {len(sections)}")
                for s in sections:
                    print(f"     - {s}")
            block_count = count_existing_blocks(cp["project_id"])
            print(f"   Blocks:      {block_count}")
        except SystemExit:
            print("   ⚠️  项目已不存在，检查点已失效")
    else:
        print("📌 无已保存的检查点。")
        print("   使用 'run --project <id>' 创建，或 'setup --topic ...' 新建。")

    print()
    print("═══ ═══ ═══ ═══ ═══ ═══ ═══ ═══")


# ══════════════════════════════════════════════════════════════
# CLI 入口
# ══════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="section_writer → Canvas 单点测试循环",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/dev_section_loop.py status
  python scripts/dev_section_loop.py run --project <uuid>
  python scripts/dev_section_loop.py run --section "竞品分析"
  python scripts/dev_section_loop.py run --dry-run
        """,
    )
    sub = parser.add_subparsers(dest="command", help="命令")

    # ── run ──
    run_parser = sub.add_parser("run", help="重跑 section_writer → DocumentBlock")
    run_parser.add_argument("--project", type=str, default=None, help="项目 UUID（可选，默认使用检查点）")
    run_parser.add_argument("--section", type=str, default=None, help="仅重跑指定章节（模糊匹配）")
    run_parser.add_argument("-n", "--limit", type=int, default=None, help="只撰写前 N 章（如 -n 5）")
    run_parser.add_argument("--dry-run", action="store_true", help="预览模式，不写入数据库")
    run_parser.add_argument("--no-images", action="store_true", default=True, help="跳过图片搜索（默认开启）")
    run_parser.add_argument("--diff", action="store_true", help="与上次运行对比（预留）")

    # ── status ──
    sub.add_parser("status", help="显示当前检查点状态")

    args = parser.parse_args()

    if args.command == "status":
        cmd_status()
    elif args.command == "run":
        project_id = _resolve_project_id(args.project)
        run_sections(
            project_id=project_id,
            single_section=args.section,
            section_limit=args.limit,
            dry_run=args.dry_run,
            no_images=args.no_images,
            diff_mode=args.diff,
        )
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
