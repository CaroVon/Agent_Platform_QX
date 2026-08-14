"""
============================================================
大纲生成 & 章节撰写任务
—— 封装原有的 app/planner/outline_generator.py 和 app/report/section_writer.py
============================================================
"""

from __future__ import annotations

import os
import re
import json
import logging
from typing import Any

from celery import Task

from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.repositories import ProjectRepo

from app.models.task import TaskType, TaskStatus

logger = logging.getLogger(__name__)


class WritingTask(Task):
    _settings = None

    @property
    def settings(self):
        if self._settings is None:
            self._settings = get_settings()
        return self._settings


@celery_app.task(
    bind=True,
    base=WritingTask,
    name="writing.generate_outline",
    max_retries=2,
    default_retry_delay=10,
    acks_late=True,
)
def generate_outline_task(
    self: WritingTask,
    project_id: str,
    template_type: str = "product",
) -> str:
    """
    第3步：生成分析报告大纲
    —— 封装原有的 outline_generator.py，支持多态模板

    Args:
        project_id:    项目 UUID
        template_type: 模板类型（"product" 或 "design"）

    返回 Markdown 大纲文本。
    """
    logger.info("[TASK] 生成大纲 | project_id=%s | template=%s", project_id, template_type)

    # 通过 Repository 获取 topic（替代 raw SQL）
    repo = ProjectRepo()
    topic = repo.get_project_topic(project_id)

    from app.planner.outline_generator import generate_outline

    outline = generate_outline(topic, template_type=template_type)
    logger.info("[TASK] 大纲生成完成 | project=%s | template=%s", project_id, template_type)

    return outline


@celery_app.task(
    bind=True,
    base=WritingTask,
    name="writing.write_section",
    max_retries=3,
    default_retry_delay=15,
    acks_late=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
)
def write_single_section(
    self: WritingTask,
    project_id: str,
    section_title: str,
    section_order: int = 0,
    template_type: str = "product",
) -> str:
    """
    第4步（子步骤）：撰写单个章节
    —— 封装原有的 section_writer.py，支持多态模板

    包含:
    - 混合检索 (BM25 + 向量检索 + Source Ranking)
    - LLM 调用撰写（根据 template_type 选择 System Prompt）
    - 溯源角标解析
    - 多模态生图（当章节名包含"生图/图鉴/概念图"时）

    参数:
        project_id:    项目 UUID
        section_title: 章节标题（如 "1. 产品设计理念"）
        section_order: 章节顺序
        template_type: 模板类型（"product" 或 "design"）

    返回:
        Markdown 格式的章节完整内容
    """
    logger.info("[TASK] 撰写章节 | project=%s | section=%s | template=%s",
                project_id, section_title, template_type)

    settings = self.settings
    repo = ProjectRepo()

    # ─── 1. 设置环境变量（LLM API Key 等） ────────────────
    os.environ["DEEPSEEK_API_KEY"] = settings.DEEPSEEK_API_KEY
    os.environ["DEEPSEEK_BASE_URL"] = settings.DEEPSEEK_BASE_URL

    # ─── 2. 从 Repository 获取 topic 与 search_depth ──────
    topic = repo.get_project_topic(project_id)
    search_depth = repo.get_project_search_depth(project_id)

    # ─── 3. 调用核心撰写逻辑 ──────────────────────────────
    from app.report.section_writer import write_section

    try:
        content = write_section(
            topic, section_title,
            project_id=project_id,
            template_type=template_type,
            search_depth=search_depth,
        )

        if not content:
            content = f"## {section_title}\n\n[本章节生成内容为空]\n"

        # ─── 4. 保存章节快照到数据库 ──────────────────────
        source_urls = re.findall(r'<([^>]+)>', content) if content else []
        repo.save_document(
            project_id=project_id,
            section_title=section_title,
            content=content,
            source_urls=list(set(source_urls)),
            section_order=section_order,
        )

        # ─── 5. 🆕 自动图片搜索（每节写完后搜索相关图片并持久化）──
        try:
            images_per_page = repo.get_project_images_per_page(project_id)
            if images_per_page > 0:
                from app.search.image_search import search_images
                logger.info("[IMAGE-SEARCH] 自动搜索图片 | project=%s | section='%s' | count=%d | page=%d",
                            project_id, section_title, images_per_page, section_order)
                img_results = search_images(section_title, max_results=images_per_page)
                for r in img_results:
                    repo.save_project_image(
                        project_id=project_id,
                        query=section_title,
                        title=r.get("title", ""),
                        image_url=r.get("image", ""),
                        source_url=r.get("url", ""),
                        thumbnail_url=r.get("image", ""),
                        search_depth=10,
                        page_number=section_order,
                    )
                logger.info("[IMAGE-SEARCH] 图片搜索完成 | project=%s | section='%s' | found=%d",
                            project_id, section_title, len(img_results))
        except Exception as img_err:
            # 图片搜索失败不阻塞撰写流程
            logger.warning("[IMAGE-SEARCH] 自动图片搜索失败（非致命）| project=%s | section='%s' | error=%s",
                           project_id, section_title, str(img_err))

        logger.info("[TASK] 章节撰写完成 | project=%s | section='%s' | len=%d",
                    project_id, section_title, len(content))
        return content

    except Exception as e:
        logger.error("[TASK] 章节撰写失败 | project=%s | section='%s' | error=%s",
                     project_id, section_title, str(e))
        raise self.retry(exc=e)
