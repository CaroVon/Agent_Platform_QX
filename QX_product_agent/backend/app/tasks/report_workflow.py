"""
============================================================
报告生成工作流（三阶段交互式状态机）
—— 🎯 状态机驱动：从线性流水线 → 交互式多步 Agent

阶段1: prepare_sources_workflow（自动 → 等待用户审核资料）
  搜索 → 抓取 → 暂存资料列表 → 🛑 WAITING_FOR_SOURCES

阶段2: generate_outline_workflow（用户审核资料后触发）
  知识库构建 → 大纲生成 → 🛑 WAITING_FOR_OUTLINE

阶段3: run_draft_sections_workflow（用户确认大纲后触发）
  分章节撰写 → 组装报告 → PDF渲染 → ✅ COMPLETED

状态机映射：
  PREPARING_DATA                        ← 阶段1 开始
    → WAITING_FOR_SOURCES               ← 🛑 交互节点1：等待用户审核资料
      → PREPARING_OUTLINE               ← 阶段2 开始（用户确认资料后）
        → WAITING_FOR_OUTLINE           ← 🛑 交互节点2：等待用户确认大纲
          → DRAFTING                    ← 阶段3 开始（用户确认大纲后）
            → COMPLETED                 ← ✅ 完成
============================================================
"""

from __future__ import annotations

import json
import logging
import os

from celery import chain, group, signature

from app.core.celery_app import celery_app
from app.core.celery_db import get_crawled_data_path
from app.repositories import ProjectRepo
from app.models.project_log import LogLevel
from app.models.task import TaskStatus, TaskType
from app.models.project import ProjectStatus

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# 辅助函数
# ══════════════════════════════════════════════════════════════

def _extract_sections(outline: str) -> list[str]:
    """从大纲 Markdown 中提取 ## 章节标题（委托给共享模块）。"""
    from app.shared.outline_parser import extract_sections as _es
    return _es(outline)


def log_state(project_id: str, step: str, msg: str):
    """状态机日志打印——产品化关键标志。"""
    logger.info("🔷 [STATE] project=%s | step=%s | %s", project_id, step, msg)


# ══════════════════════════════════════════════════════════════
# 🎯 阶段1：资料搜集（自动 → 等待用户审核）
# ══════════════════════════════════════════════════════════════

@celery_app.task(
    bind=True,
    name="workflow.prepare_sources",
    max_retries=1,
    default_retry_delay=30,
    acks_late=True,
)
def prepare_sources_workflow(self, project_id: str):
    """
    🎯 阶段1：资料搜集与暂存
    =========================
    状态机：PREPARING_DATA → (自动) → WAITING_FOR_SOURCES
    """
    logger.info("=" * 60)
    logger.info("[PHASE 1] 🚀 资料搜集 | project_id=%s", project_id)
    logger.info("[PHASE 1] 状态: PREPARING_DATA → WAITING_FOR_SOURCES")
    logger.info("=" * 60)

    repo = ProjectRepo()

    try:
        log_state(project_id, "searching", "阶段1 开始：搜索 + 抓取")
        repo.append_project_log(project_id, "searching",
                                "🔍 正在全网搜索相关资料...", LogLevel.INFO, "🔍")

        # ── 1. 搜索 + 抓取 ────────────────────────────────
        repo.update_task_status(project_id, TaskType.SEARCH, TaskStatus.PROCESSING)

        try:
            from app.tasks.search_tasks import search_and_crawl
            search_result = search_and_crawl(project_id)
            logger.info("[PHASE 1] 搜索完成，共获取 %d 条结果", len(search_result))
            repo.append_project_log(project_id, "searching",
                                    f"📥 搜索完成，共获取 {len(search_result)} 条相关资料",
                                    LogLevel.MILESTONE, "📥")
        except Exception as e:
            repo.update_task_status(project_id, TaskType.SEARCH, TaskStatus.FAILED, str(e))
            repo.append_project_log(project_id, "searching",
                                    f"❌ 搜索失败: {str(e)[:100]}", LogLevel.ERROR, "❌")
            raise

        repo.update_task_status(project_id, TaskType.SEARCH, TaskStatus.COMPLETED)

        # ── 2. 暂存资料到项目 ─────────────────────────────
        _save_sources_to_project(project_id, search_result, repo)

        # ── 3. 状态机推进：PREPARING_DATA → WAITING_FOR_SOURCES ──
        log_state(project_id, "waiting_for_sources",
                  f"✅ 资料搜集完毕，共 {len(search_result)} 条，等待用户审核")
        repo.update_project_status(project_id, ProjectStatus.WAITING_FOR_SOURCES)

        logger.info("=" * 60)
        logger.info("[PHASE 1] ✅ 资料就绪 | project=%s | sources=%d",
                    project_id, len(search_result))
        logger.info("[PHASE 1] 🔔 请用户通过 GET /sources 查看资料、POST /review-sources 确认")
        logger.info("=" * 60)

        return {
            "project_id": project_id,
            "status": "waiting_for_sources",
            "sources_count": len(search_result),
        }

    except Exception as exc:
        logger.error("[PHASE 1] ❌ 失败 | project=%s | error=%s", project_id, str(exc))
        repo.update_project_status(project_id, ProjectStatus.FAILED, error_message=str(exc))
        try:
            self.retry(exc=exc)
        except Exception:
            raise
        return {"project_id": project_id, "status": "failed", "error": str(exc)}


# ══════════════════════════════════════════════════════════════
# 🎯 阶段2：大纲生成（用户审核资料后触发）
# ══════════════════════════════════════════════════════════════

@celery_app.task(
    bind=True,
    name="workflow.generate_outline",
    max_retries=1,
    default_retry_delay=30,
    acks_late=True,
)
def generate_outline_workflow(self, project_id: str):
    """
    🎯 阶段2：知识库构建 + 大纲生成
    ================================
    状态机：WAITING_FOR_SOURCES → (用户确认资料) → WAITING_FOR_OUTLINE
    """
    logger.info("=" * 60)
    logger.info("[PHASE 2] 🚀 大纲生成 | project_id=%s", project_id)
    logger.info("[PHASE 2] 状态: PREPARING_OUTLINE → WAITING_FOR_OUTLINE")
    logger.info("=" * 60)

    repo = ProjectRepo()

    try:
        log_state(project_id, "building_knowledge", "阶段2 开始：知识库 + 大纲")
        repo.append_project_log(project_id, "building_kb",
                                "📚 正在进行向量库切片与索引...", LogLevel.INFO, "📚")

        # ── 1. 知识库构建 ────────────────────────────────
        repo.update_task_status(project_id, TaskType.BUILD_KNOWLEDGE_BASE, TaskStatus.PROCESSING)
        try:
            from app.tasks.knowledge_tasks import build_knowledge_base
            build_knowledge_base(project_id)
            repo.append_project_log(project_id, "building_kb",
                                    "✅ 知识库构建完成，向量索引已就绪", LogLevel.MILESTONE, "✅")
        except Exception as e:
            repo.update_task_status(project_id, TaskType.BUILD_KNOWLEDGE_BASE, TaskStatus.FAILED, str(e))
            repo.append_project_log(project_id, "building_kb",
                                    f"❌ 知识库构建失败: {str(e)[:100]}", LogLevel.ERROR, "❌")
            raise
        repo.update_task_status(project_id, TaskType.BUILD_KNOWLEDGE_BASE, TaskStatus.COMPLETED)

        # ── 2. 大纲生成 ──────────────────────────────────
        # 获取项目的模板类型，透传给 LLM 层
        template_type = repo.get_project_template(project_id)
        logger.info("[PHASE 2] 模板类型: %s", template_type)

        repo.update_task_status(project_id, TaskType.GENERATE_OUTLINE, TaskStatus.PROCESSING)
        repo.append_project_log(project_id, "generating_outline",
                                "📝 正在规划产品研究大纲结构...", LogLevel.INFO, "📝")
        try:
            from app.tasks.writing_tasks import generate_outline_task
            outline = generate_outline_task(project_id, template_type=template_type)
            logger.info("[PHASE 2] 大纲生成完成 (%d 字符)", len(outline))
            repo.append_project_log(project_id, "generating_outline",
                                    f"📋 大纲规划完成，共 {len(_extract_sections(outline))} 个章节",
                                    LogLevel.MILESTONE, "📋")
        except Exception as e:
            repo.update_task_status(project_id, TaskType.GENERATE_OUTLINE, TaskStatus.FAILED, str(e))
            repo.append_project_log(project_id, "generating_outline",
                                    f"❌ 大纲生成失败: {str(e)[:100]}", LogLevel.ERROR, "❌")
            raise
        repo.update_task_status(project_id, TaskType.GENERATE_OUTLINE, TaskStatus.COMPLETED)

        # ── 3. 暂存大纲 ──────────────────────────────────
        repo.update_project_outline(project_id, outline)

        # ── 4. 状态机推进：PREPARING_OUTLINE → WAITING_FOR_OUTLINE ──
        log_state(project_id, "waiting_for_outline",
                  f"✅ 大纲就绪 ({len(outline)} 字符)，等待用户审核确认")
        repo.update_project_status(project_id, ProjectStatus.WAITING_FOR_OUTLINE)

        logger.info("=" * 60)
        logger.info("[PHASE 2] ✅ 大纲就绪 | project=%s", project_id)
        logger.info("[PHASE 2] 🔔 请用户通过 GET /status 查看大纲、POST /approve-outline 确认")
        logger.info("=" * 60)

        return {"project_id": project_id, "status": "waiting_for_outline", "outline_length": len(outline)}

    except Exception as exc:
        logger.error("[PHASE 2] ❌ 失败 | project=%s | error=%s", project_id, str(exc))
        repo.update_project_status(project_id, ProjectStatus.FAILED, error_message=str(exc))
        try:
            self.retry(exc=exc)
        except Exception:
            raise
        return {"project_id": project_id, "status": "failed", "error": str(exc)}


# ══════════════════════════════════════════════════════════════
# 🎯 阶段3：分章节异步撰写（用户确认大纲后触发）
# ══════════════════════════════════════════════════════════════

@celery_app.task(
    bind=True,
    name="workflow.run_draft_sections",
    max_retries=1,
    default_retry_delay=30,
    acks_late=True,
)
def run_draft_sections_workflow(self, project_id: str):
    """
    🎯 节点2：分章节异步撰写（重构后不再自动生成 PDF）
    =========================
    状态机：DRAFTING → (自动) → COMPLETED

    COMPLETED 终态现在代表"AI 初始草稿生成完成"，
    等待用户在各页面中自由编辑与排版后，由前端手动触发 PDF 导出。
    """
    logger.info("=" * 60)
    logger.info("[PHASE 3] 🚀 分章节异步撰写 | project_id=%s", project_id)
    logger.info("[PHASE 3] 状态: DRAFTING → COMPLETED（草稿就绪，等待用户编辑后手动导出 PDF）")
    logger.info("=" * 60)

    repo = ProjectRepo()

    try:
        log_state(project_id, "drafting", "节点2 开始执行：分章节异步撰写")

        # ─── 1. 从仓库获取项目信息 ────────────────────────
        project = repo.get_project(project_id)
        topic = project.topic
        outline_content = project.outline_content

        if not outline_content:
            logger.warning("[PHASE 3] outline_content 为空，使用默认大纲")
            outline_content = "# 默认大纲\n## 1. 行业概述\n## 2. 市场分析\n"

        # ─── 2. 解析章节标题 ──────────────────────────────
        section_titles = _extract_sections(outline_content)
        logger.info("[PHASE 3] 共 %d 个章节待撰写", len(section_titles))

        if not section_titles:
            section_titles = ["1. 行业概述", "2. 市场分析", "3. 竞争格局"]
            logger.warning("[PHASE 3] 大纲解析结果为空，使用默认章节: %s", section_titles)

        # ─── 获取模板类型，透传给 LLM 撰写层 ──────────────
        template_type = repo.get_project_template(project_id)
        logger.info("[PHASE 3] 模板类型: %s", template_type)

        # ─── 3. 逐章节撰写 ────────────────────────────────
        section_results = []
        for idx, section_title in enumerate(section_titles):
            logger.info("[STEP %d/%d] 撰写章节: '%s'", idx + 1, len(section_titles), section_title)

            repo.append_project_log(project_id, "writing_section",
                                    f"✍️ 正在撰写「{section_title}」({idx + 1}/{len(section_titles)})...",
                                    LogLevel.INFO, "✍️")

            repo.update_section_task_status(project_id, section_title, TaskStatus.PROCESSING)

            try:
                from app.tasks.writing_tasks import write_single_section
                content = write_single_section(
                    project_id, section_title, idx,
                    template_type=template_type,
                )

                if not content:
                    content = f"## {section_title}\n\n[本章节内容为空]\n"

                section_results.append(content)

                # 将章节拆分为多个 DocumentBlock 保存
                _save_section_as_blocks(repo, project_id, section_title, content, idx)

                repo.update_section_task_status(project_id, section_title, TaskStatus.COMPLETED)

                logger.info("  [OK] 章节 '%s' 撰写完成 (%d 字符)", section_title, len(content))
                repo.append_project_log(project_id, "writing_section",
                                        f"✅ 「{section_title}」撰写完成 ({len(content)} 字符)",
                                        LogLevel.MILESTONE, "✅")

            except Exception as e:
                logger.error("  [FAIL] 章节 '%s' 撰写失败: %s", section_title, str(e))
                repo.update_section_task_status(project_id, section_title, TaskStatus.FAILED, str(e))
                repo.append_project_log(project_id, "writing_section",
                                        f"❌ 「{section_title}」撰写失败: {str(e)[:100]}",
                                        LogLevel.ERROR, "❌")
                section_results.append(f"## {section_title}\n\n[本章节生成失败: {str(e)}]\n")

        # ─── 【核心重构：切断自动流】 ──────────────────────
        # 原步骤 4（组装 Markdown 报告）和步骤 5（生成 PDF）已移除。
        # 现在的 COMPLETED 终态代表"AI 初始草稿生成完成"，
        # 等待用户在各页面中自由编辑与排版后，由前端手动触发 PDF 导出。

        # 直接将项目状态推进到 COMPLETED（草稿已就绪，等待用户编辑）
        repo.update_project_status(project_id, ProjectStatus.COMPLETED, pdf_path=None, md_path=None)

        repo.append_project_log(project_id, "drafting_complete",
                                "🎉 AI 草稿分页生成完毕！已导入 Canvas 工作台。",
                                LogLevel.MILESTONE, "🎉")

        log_state(project_id, "completed",
                  f"✅ AI 草稿分页生成完毕！共撰写 {len(section_titles)} 个章节")

        logger.info("=" * 60)
        logger.info("[PHASE 3] ✅ AI 草稿分页生成完毕 | project_id=%s", project_id)
        logger.info("[PHASE 3] 🔔 请用户在各页面中自由编辑与排版，完成后手动导出 PDF")
        logger.info("=" * 60)

        return {"project_id": project_id, "status": "completed"}

    except Exception as exc:
        logger.error("[PHASE 3] ❌ 撰写失败 | project_id=%s | error=%s", project_id, str(exc), exc_info=True)
        repo.update_project_status(project_id, ProjectStatus.FAILED, error_message=str(exc))

        try:
            self.retry(exc=exc)
        except Exception as retry_exc:
            logger.error("[PHASE 3] 重试也失败: %s", str(retry_exc))
            raise

        return {
            "project_id": project_id,
            "status": "failed",
            "error": str(exc),
        }


# ══════════════════════════════════════════════════════════════
# 保留旧版「一键全自动」工作流（向后兼容）
# ══════════════════════════════════════════════════════════════

@celery_app.task(
    bind=True,
    name="workflow.run_full_report",
    max_retries=1,
    default_retry_delay=30,
    acks_late=True,
)
def run_full_report_workflow(self, project_id: str):
    """
    （旧版兼容）全自动流水线——从搜索到 PDF 一步到位。
    新项目应优先使用三阶段交互式流程。
    """
    logger.info("[WORKFLOW] 旧版全自动流水线（一步到位）| project_id=%s", project_id)
    prepare_sources_workflow(project_id)
    generate_outline_workflow(project_id)
    run_draft_sections_workflow(project_id)
    logger.info("[WORKFLOW] 旧版全自动流水线完成 | project_id=%s", project_id)


# ══════════════════════════════════════════════════════════════
# 内部辅助函数
# ══════════════════════════════════════════════════════════════

def _save_sources_to_project(project_id: str, search_result: list[dict], repo: ProjectRepo | None = None) -> None:
    """将搜索结果暂存到项目记录中。"""
    temp_data_path = get_crawled_data_path(project_id)
    os.makedirs(os.path.dirname(temp_data_path), exist_ok=True)
    with open(temp_data_path, "w", encoding="utf-8") as f:
        json.dump(search_result, f, ensure_ascii=False, indent=2)
    logger.info("[DB] 搜索结果已暂存 | project=%s | path=%s | count=%d",
                project_id, temp_data_path, len(search_result))

    # 同步写入项目日志
    if repo is None:
        repo = ProjectRepo()
    repo.append_project_log(project_id, "searching",
                            f"📥 搜索完成，共获取 {len(search_result)} 条相关资料",
                            LogLevel.MILESTONE, "📥")


def _load_sources_from_project(project_id: str) -> list[dict]:
    """读取暂存的搜索结果。"""
    temp_data_path = get_crawled_data_path(project_id)
    if not os.path.exists(temp_data_path):
        return []
    with open(temp_data_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_section_as_blocks(
    repo: ProjectRepo,
    project_id: str,
    section_title: str,
    content: str,
    section_index: int,
):
    """
    将单章节的 Markdown 内容保存为一个完整的 DocumentBlock，
    使前端 Canvas 以章节为单位进行分页排版，避免段落级拆分导致
    每个 Block 都带装饰区（120-180px 开销）而产生过多碎片页。
    """
    citations: dict[str, str] = {}
    block_order = (section_index + 1) * 10

    if content.strip():
        repo.save_document_block(
            project_id=project_id,
            section_title=section_title,
            content=content,
            citations=citations,
            order_index=block_order,
        )
        logger.info("[BLOCKS] 章节 '%s' 保存为 1 个 DocumentBlock (section-level)",
                     section_title)
    else:
        logger.warning("[BLOCKS] 章节 '%s' 内容为空，跳过保存", section_title)
