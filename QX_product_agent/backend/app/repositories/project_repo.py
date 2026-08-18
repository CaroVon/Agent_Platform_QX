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
from app.models.knowledge_asset import KnowledgeAsset
from app.models.domain_experience import DomainExperience

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
                # 终态守卫：FAILED / COMPLETED 不允许被改回执行中状态（防幽灵任务复活）
                if project.status in (ProjectStatus.FAILED, ProjectStatus.COMPLETED) \
                        and status not in (ProjectStatus.FAILED, ProjectStatus.COMPLETED):
                    logger.warning(
                        "[Repo] 拒绝非法状态迁移 | project=%s | %s → %s（终态不可回退）",
                        project_id, project.status.value, status.value,
                    )
                    return
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
    # 🆕 知识系统（P1-P3）：图片分析 / 任务画像 / 经验包 / 知识资产
    # ══════════════════════════════════════════════════════════

    def create_kb_image(
        self,
        project_id: str,
        title: str,
        file_path: str,
        query: str = "",
        source: str = "upload",
    ) -> ProjectImage:
        """创建一张"知识库图片"记录（status=pending，等待 VL 分析）。"""
        pid = self._pid(project_id)
        with Session(self._engine) as session:
            img = ProjectImage(
                project_id=pid,
                query=query,
                title=title,
                image_url=f"image://{project_id}/{file_path.split('/')[-1]}",
                source_url=f"local://{title}",
                thumbnail_url=None,
                source=source,
                status="pending",
                file_path=file_path,
                search_depth=0,
            )
            session.add(img)
            session.commit()
            session.refresh(img)
            session.expunge(img)
            return img

    def get_image(self, image_id: str) -> ProjectImage | None:
        """按 ID 获取图片记录。"""
        with Session(self._engine) as session:
            img = session.execute(
                select(ProjectImage).where(ProjectImage.id == uuid.UUID(image_id))
            ).scalar_one_or_none()
            if img is None:
                return None
            session.expunge(img)
            return img

    def update_image_analysis(
        self,
        image_id: str,
        status: str,
        analysis_text: str | None = None,
        tags: list[str] | None = None,
        error: str | None = None,
    ) -> None:
        """更新图片分析状态与结果。"""
        with Session(self._engine) as session:
            img = session.execute(
                select(ProjectImage).where(ProjectImage.id == uuid.UUID(image_id))
            ).scalar_one_or_none()
            if img is None:
                logger.warning("图片不存在: %s", image_id)
                return
            img.status = status
            if analysis_text is not None:
                img.analysis_text = analysis_text
            if tags is not None:
                img.tags = ",".join(tags)[:1000]
            if error and status == "failed":
                img.title = f"{img.title}（分析失败）"
            session.commit()

    # ── 任务画像（相似度） ──────────────────────────────────

    def update_project_profile(
        self,
        project_id: str,
        topic_embedding: list[float] | None = None,
        domain_tags: list[str] | None = None,
    ) -> None:
        """持久化项目 topic 向量与领域标签。"""
        pid = self._pid(project_id)
        with Session(self._engine) as session:
            project = session.execute(
                select(Project).where(Project.id == pid)
            ).scalar_one_or_none()
            if project is None:
                logger.warning("未找到项目: %s", project_id)
                return
            if topic_embedding is not None:
                project.topic_embedding = json.dumps(topic_embedding)
            if domain_tags is not None:
                project.domain_tags = json.dumps(domain_tags, ensure_ascii=False)
            session.commit()

    def list_projects_for_similarity(self) -> list[Project]:
        """列出参与相似度比较的项目（排除早期半成品状态）。"""
        with Session(self._engine) as session:
            rows = session.execute(
                select(Project).where(
                    Project.status.in_([
                        ProjectStatus.WAITING_FOR_OUTLINE,
                        ProjectStatus.DRAFTING,
                        ProjectStatus.COMPLETED,
                    ])
                )
            ).scalars().all()
            for p in rows:
                session.expunge(p)
            return list(rows)

    # ── 经验包 ──────────────────────────────────────────────

    def save_domain_experience(
        self,
        project_id: str,
        domain_tags: list[str],
        topic: str,
        summary: str,
        source_url: str | None = None,
    ):
        """保存领域经验包，返回 DomainExperience 实例。"""
        pid = self._pid(project_id)
        with Session(self._engine) as session:
            exp = DomainExperience(
                project_id=pid,
                domain_tags=json.dumps(domain_tags, ensure_ascii=False),
                topic=topic,
                summary=summary,
                source_url=source_url,
            )
            session.add(exp)
            session.commit()
            session.refresh(exp)
            session.expunge(exp)
            return exp

    def list_domain_experiences(self, project_id: str, limit: int = 5) -> list[DomainExperience]:
        """列出某项目产出的经验包（时间倒序）。"""
        with Session(self._engine) as session:
            rows = session.execute(
                select(DomainExperience)
                .where(DomainExperience.project_id == uuid.UUID(project_id))
                .order_by(DomainExperience.created_at.desc())
                .limit(limit)
            ).scalars().all()
            for e in rows:
                session.expunge(e)
            return list(rows)

    def list_all_domain_experiences(self, limit: int = 100) -> list[DomainExperience]:
        """列出全部经验包（管理面板用）。"""
        with Session(self._engine) as session:
            rows = session.execute(
                select(DomainExperience).order_by(DomainExperience.created_at.desc()).limit(limit)
            ).scalars().all()
            for e in rows:
                session.expunge(e)
            return list(rows)

    # ── 知识资产（全局/领域登记表） ─────────────────────────

    def save_knowledge_asset(
        self,
        scope: str,
        title: str,
        source: str,
        source_url: str | None = None,
        tags: list[str] | None = None,
        chunk_count: int = 0,
        owner_id: str | None = None,
        extra: dict | None = None,
        stale_at=None,
    ) -> KnowledgeAsset:
        """登记一条知识资产（幂等：source_url+scope 重复则更新）。"""
        with Session(self._engine) as session:
            existing = None
            if source_url:
                existing = session.execute(
                    select(KnowledgeAsset).where(
                        KnowledgeAsset.source_url == source_url,
                        KnowledgeAsset.scope == scope,
                    )
                ).scalar_one_or_none()
            if existing:
                existing.title = title
                existing.tags = json.dumps(tags, ensure_ascii=False) if tags else existing.tags
                existing.chunk_count = chunk_count
                if stale_at is not None:
                    existing.stale_at = stale_at
                session.commit()
                session.refresh(existing)
                session.expunge(existing)
                return existing
            asset = KnowledgeAsset(
                scope=scope,
                owner_id=uuid.UUID(owner_id) if owner_id else None,
                source=source,
                title=title,
                source_url=source_url,
                tags=json.dumps(tags, ensure_ascii=False) if tags else None,
                chunk_count=chunk_count,
                stale_at=stale_at,
                extra=json.dumps(extra, ensure_ascii=False) if extra else None,
            )
            session.add(asset)
            session.commit()
            session.refresh(asset)
            session.expunge(asset)
            return asset

    def list_knowledge_assets(
        self,
        scope: str | None = None,
        source: str | None = None,
        limit: int = 200,
    ) -> list[KnowledgeAsset]:
        """列出知识资产（按更新时间倒序）。"""
        with Session(self._engine) as session:
            stmt = select(KnowledgeAsset).order_by(KnowledgeAsset.updated_at.desc()).limit(limit)
            if scope:
                stmt = stmt.where(KnowledgeAsset.scope == scope)
            if source:
                stmt = stmt.where(KnowledgeAsset.source == source)
            rows = session.execute(stmt).scalars().all()
            for a in rows:
                session.expunge(a)
            return list(rows)

    def delete_knowledge_asset_by_url(self, source_url: str, scope: str | None = None) -> int:
        """按 source_url 删除知识资产（Obsidian 删除同步用），返回删除条数。"""
        with Session(self._engine) as session:
            stmt = select(KnowledgeAsset).where(KnowledgeAsset.source_url == source_url)
            if scope:
                stmt = stmt.where(KnowledgeAsset.scope == scope)
            rows = session.execute(stmt).scalars().all()
            for a in rows:
                session.delete(a)
            session.commit()
            return len(rows)

    def list_document_blocks(self, project_id: str, limit: int = 200) -> list[DocumentBlock]:
        """列出项目文档块（经验包抽取用）。"""
        with Session(self._engine) as session:
            rows = session.execute(
                select(DocumentBlock)
                .where(DocumentBlock.project_id == uuid.UUID(project_id))
                .order_by(DocumentBlock.order_index)
                .limit(limit)
            ).scalars().all()
            for b in rows:
                session.expunge(b)
            return list(rows)

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
