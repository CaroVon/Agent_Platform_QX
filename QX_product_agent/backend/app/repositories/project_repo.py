"""
============================================================
Project Repository —— Celery Worker 同步数据库访问层
============================================================

使用同步 SQLAlchemy 引擎 + ORM 查询，消除：
  - 散落在各任务中的 text("SELECT ...") raw SQL
  - 无处不在的 asyncio.run() 调用
  - 重复的 UUID hex 转换和错误处理样板代码
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.celery_db import get_sync_engine
from app.models.task import Task, TaskStatus, TaskType
from app.models.project import Project, ProjectStatus
from app.models.document import Document
from app.models.document_block import DocumentBlock
from app.models.project_log import ProjectLog, LogLevel
from app.models.project_image import ProjectImage

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    """统一的 UTC 时间戳工厂。"""
    return datetime.now(timezone.utc)


class ProjectNotFoundError(Exception):
    """项目不存在异常。"""
    pass


class ProjectRepo:
    """
    同步数据库仓库——专供 Celery Worker 使用。

    所有方法都是同步的，直接使用 SQLAlchemy 同步引擎，
    无需 asyncio.run() / 事件循环 / nest_asyncio。
    """

    def __init__(self):
        self._engine = get_sync_engine()

    # ══════════════════════════════════════════════════════════
    # 内部工具
    # ══════════════════════════════════════════════════════════

    def _pid(self, project_id: str) -> uuid.UUID:
        """将字符串 project_id 转为 UUID，并验证项目存在。"""
        return uuid.UUID(project_id)

    # ══════════════════════════════════════════════════════════
    # 项目查询
    # ══════════════════════════════════════════════════════════

    def get_project(self, project_id: str) -> Project:
        """
        获取项目 ORM 对象。若不存在则抛出 ProjectNotFoundError。
        """
        pid = self._pid(project_id)
        with Session(self._engine) as session:
            project = session.execute(
                select(Project).where(Project.id == pid)
            ).scalar_one_or_none()
            if project is None:
                raise ProjectNotFoundError(f"项目不存在: {project_id}")
            # detach 以便在 session 外使用
            session.expunge(project)
            return project

    def get_project_topic(self, project_id: str) -> str:
        """获取项目的 topic 字段。"""
        return self.get_project(project_id).topic

    def get_project_outline(self, project_id: str) -> str | None:
        """获取项目的 outline_content 字段。"""
        return self.get_project(project_id).outline_content

    def get_project_template(self, project_id: str) -> str:
        """获取项目的模板类型（product 或 design），默认返回 "product"。"""
        return self.get_project(project_id).template_type or "product"

    def get_project_search_depth(self, project_id: str) -> int:
        """获取项目的搜索强度，默认返回 10。"""
        return getattr(self.get_project(project_id), 'search_depth', 10) or 10

    def get_project_images_per_page(self, project_id: str) -> int:
        """🆕 获取项目每页自动搜索图片数量，默认返回 2。"""
        return getattr(self.get_project(project_id), 'images_per_page', 2) or 2

    # ══════════════════════════════════════════════════════════
    # 项目状态更新
    # ══════════════════════════════════════════════════════════

    def update_project_status(
        self,
        project_id: str,
        status: ProjectStatus | None = None,
        error_message: str | None = None,
        pdf_path: str | None = None,
        md_path: str | None = None,
    ) -> None:
        """
        更新项目整体状态。
        status 为 None 时仅更新可选字段。
        """
        pid = self._pid(project_id)
        with Session(self._engine) as session:
            project = session.execute(
                select(Project).where(Project.id == pid)
            ).scalar_one_or_none()
            if project is None:
                logger.warning("未找到项目: %s", project_id)
                return

            if status is not None:
                project.status = status
            if error_message:
                project.error_message = error_message[:1000]
            if pdf_path:
                project.pdf_path = pdf_path
            if md_path:
                project.md_path = md_path
            project.updated_at = _utcnow()

            session.commit()
            logger.info(
                "[Repo] 更新项目状态 | project=%s | status=%s",
                project_id,
                status.value if status is not None else "(unchanged)",
            )

    def update_project_outline(self, project_id: str, outline_content: str) -> None:
        """保存大纲到项目记录。"""
        pid = self._pid(project_id)
        with Session(self._engine) as session:
            project = session.execute(
                select(Project).where(Project.id == pid)
            ).scalar_one_or_none()
            if project is None:
                logger.warning("未找到项目: %s", project_id)
                return
            project.outline_content = outline_content
            session.commit()
            logger.info("[Repo] 保存大纲 | project=%s | len=%d", project_id, len(outline_content))

    # ══════════════════════════════════════════════════════════
    # 任务状态更新
    # ══════════════════════════════════════════════════════════

    def update_task_status(
        self,
        project_id: str,
        task_type: TaskType,
        status: TaskStatus,
        error_message: str | None = None,
    ) -> None:
        """更新指定类型任务的状态。"""
        pid = self._pid(project_id)
        with Session(self._engine) as session:
            task = session.execute(
                select(Task).where(
                    Task.project_id == pid,
                    Task.task_type == task_type,
                )
            ).scalar_one_or_none()
            if task is None:
                logger.warning("未找到任务: project=%s type=%s", project_id, task_type.value)
                return

            task.status = status
            if status == TaskStatus.PROCESSING:
                task.started_at = _utcnow()
            elif status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                task.completed_at = _utcnow()
            if error_message:
                task.error_message = error_message[:500]
            elif status == TaskStatus.COMPLETED:
                # 任务成功完成时清空之前可能残留的旧错误信息
                task.error_message = None

            session.commit()
            logger.info(
                "[Repo] 更新任务状态 | project=%s | type=%s | status=%s",
                project_id, task_type.value, status.value,
            )

    def update_section_task_status(
        self,
        project_id: str,
        section_title: str,
        status: TaskStatus,
        error_message: str | None = None,
    ) -> None:
        """更新指定章节的 WRITE_SECTION 任务状态。"""
        pid = self._pid(project_id)
        with Session(self._engine) as session:
            task = session.execute(
                select(Task).where(
                    Task.project_id == pid,
                    Task.task_type == TaskType.WRITE_SECTION,
                    Task.section_title == section_title,
                )
            ).scalar_one_or_none()
            if task is None:
                logger.warning(
                    "未找到章节任务: project=%s section=%s", project_id, section_title
                )
                return

            task.status = status
            if status == TaskStatus.PROCESSING:
                task.started_at = _utcnow()
            elif status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                task.completed_at = _utcnow()
            if error_message:
                task.error_message = error_message[:500]
            elif status == TaskStatus.COMPLETED:
                task.error_message = None

            session.commit()
            logger.info(
                "[Repo] 更新章节任务 | project=%s | section=%s | status=%s",
                project_id, section_title, status.value,
            )

    def create_section_tasks(
        self, project_id: str, section_titles: list[str]
    ) -> None:
        """根据大纲动态创建 WRITE_SECTION 任务。"""
        pid = self._pid(project_id)
        with Session(self._engine) as session:
            for idx, title in enumerate(section_titles):
                existing = session.execute(
                    select(Task).where(
                        Task.project_id == pid,
                        Task.section_title == title,
                    )
                ).scalar_one_or_none()
                if existing:
                    continue

                task = Task(
                    project_id=pid,
                    task_type=TaskType.WRITE_SECTION,
                    status=TaskStatus.PENDING,
                    sequence_order=10 + idx,
                    section_title=title,
                )
                session.add(task)
            session.commit()
            logger.info("[Repo] 创建 %d 个章节撰写任务 | project=%s", len(section_titles), project_id)

    # ══════════════════════════════════════════════════════════
    # 文档块 (DocumentBlock)
    # ══════════════════════════════════════════════════════════

    def save_document_block(
        self,
        project_id: str,
        section_title: str,
        content: str,
        citations: dict[str, str] | None = None,
        order_index: int = 0,
    ) -> None:
        """保存或更新文档块。"""
        pid = self._pid(project_id)
        json_citations = json.dumps(citations, ensure_ascii=False) if citations else "{}"

        with Session(self._engine) as session:
            block = session.execute(
                select(DocumentBlock).where(
                    DocumentBlock.project_id == pid,
                    DocumentBlock.section_title == section_title,
                    DocumentBlock.order_index == order_index,
                )
            ).scalars().first()

            if block:
                block.content = content
                block.citations = json_citations
                logger.info(
                    "[Repo] 更新文档块 | project=%s | section=%s | order=%d",
                    project_id, section_title, order_index,
                )
            else:
                block = DocumentBlock(
                    project_id=pid,
                    section_title=section_title,
                    content=content,
                    citations=json_citations,
                    order_index=order_index,
                )
                session.add(block)
                logger.info(
                    "[Repo] 新增文档块 | project=%s | section=%s | order=%d",
                    project_id, section_title, order_index,
                )
            session.commit()

    # ══════════════════════════════════════════════════════════
    # 文档 (Document)
    # ══════════════════════════════════════════════════════════

    def save_document(
        self,
        project_id: str,
        section_title: str,
        content: str,
        source_urls: list[str] | None = None,
        section_order: int = 0,
    ) -> None:
        """保存章节文档快照。"""
        pid = self._pid(project_id)
        with Session(self._engine) as session:
            doc = Document(
                project_id=pid,
                section_title=section_title,
                section_order=section_order,
                content=content,
                source_urls=json.dumps(source_urls, ensure_ascii=False) if source_urls else None,
            )
            session.add(doc)
            session.commit()
            logger.info("[Repo] 保存章节文档 | project=%s | section=%s", project_id, section_title)

    # ══════════════════════════════════════════════════════════
    # 🆕 项目图片库 (ProjectImage)
    # ══════════════════════════════════════════════════════════

    def save_project_image(
        self,
        project_id: str,
        query: str,
        title: str,
        image_url: str,
        source_url: str | None = None,
        thumbnail_url: str | None = None,
        search_depth: int = 10,
        page_number: int | None = None,
    ) -> ProjectImage:
        """🆕 持久化一张项目图片记录（供自动搜索使用）。"""
        pid = self._pid(project_id)
        with Session(self._engine) as session:
            img = ProjectImage(
                project_id=pid,
                query=query,
                title=title,
                image_url=image_url,
                source_url=source_url,
                thumbnail_url=thumbnail_url or image_url,
                search_depth=search_depth,
                page_number=page_number,
            )
            session.add(img)
            session.commit()
            session.expunge(img)
            return img

    # ══════════════════════════════════════════════════════════
    # 项目时间轴日志 (ProjectLog)
    # ══════════════════════════════════════════════════════════

    # 日志序列号缓存
    _log_seq_cache: dict[str, int] = {}

    def append_project_log(
        self,
        project_id: str,
        step: str,
        message: str,
        level: LogLevel = LogLevel.INFO,
        icon: str | None = None,
    ) -> None:
        """向项目时间轴写入一条业务级日志。"""
        pid = self._pid(project_id)

        # 序列号递增
        self._log_seq_cache[project_id] = self._log_seq_cache.get(project_id, 0) + 1
        seq = self._log_seq_cache[project_id]

        with Session(self._engine) as session:
            log_entry = ProjectLog(
                project_id=pid,
                sequence=seq,
                level=level,
                step=step,
                message=message,
                icon=icon,
            )
            session.add(log_entry)
            session.commit()
