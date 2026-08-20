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

from sqlalchemy import select, delete
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
from app.models.memory_entity import MemoryEntity
from app.models.memory_relation import MemoryRelation
from app.models.memory_insight import MemoryInsight

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
        studio_product_id: str | None = None,
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
                if studio_product_id:
                    existing.studio_product_id = uuid.UUID(studio_product_id)
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
                studio_product_id=uuid.UUID(studio_product_id) if studio_product_id else None,
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
        studio_product_id: str | None = None,
        limit: int = 200,
    ) -> list[KnowledgeAsset]:
        """列出知识资产（按更新时间倒序）。"""
        with Session(self._engine) as session:
            stmt = select(KnowledgeAsset).order_by(KnowledgeAsset.updated_at.desc()).limit(limit)
            if scope:
                stmt = stmt.where(KnowledgeAsset.scope == scope)
            if source:
                stmt = stmt.where(KnowledgeAsset.source == source)
            if studio_product_id:
                stmt = stmt.where(
                    KnowledgeAsset.studio_product_id == uuid.UUID(studio_product_id)
                )
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

    # ══════════════════════════════════════════════════════════
    # 🆕 记忆图（P4）：实体 / 关系 / 洞察
    # ══════════════════════════════════════════════════════════

    # ── 实体 ─────────────────────────────────────────────────

    def save_memory_entity(
        self,
        scope: str,
        name: str,
        type: str = "other",
        summary: str | None = None,
        project_id: str | None = None,
        studio_product_id: str | None = None,
        confidence: float = 0.6,
        first_seen=None,
        last_seen=None,
    ) -> MemoryEntity:
        """新建记忆实体。"""
        with Session(self._engine) as session:
            entity = MemoryEntity(
                scope=scope,
                project_id=uuid.UUID(project_id) if project_id else None,
                studio_product_id=uuid.UUID(studio_product_id) if studio_product_id else None,
                type=type,
                name=name,
                summary=summary,
                confidence=confidence,
                first_seen_at=first_seen,
                last_seen_at=last_seen,
            )
            session.add(entity)
            session.commit()
            session.refresh(entity)
            session.expunge(entity)
            return entity

    def get_entity(self, entity_id: str) -> MemoryEntity | None:
        with Session(self._engine) as session:
            entity = session.execute(
                select(MemoryEntity).where(MemoryEntity.id == uuid.UUID(entity_id))
            ).scalar_one_or_none()
            if entity is None:
                return None
            session.expunge(entity)
            return entity

    def find_project_entity(self, project_id: str, name: str) -> MemoryEntity | None:
        with Session(self._engine) as session:
            entity = session.execute(
                select(MemoryEntity).where(
                    MemoryEntity.scope == "project",
                    MemoryEntity.project_id == uuid.UUID(project_id),
                    MemoryEntity.name == name,
                )
            ).scalar_one_or_none()
            if entity is None:
                return None
            session.expunge(entity)
            return entity

    def find_studio_entity(self, studio_product_id: str, name: str) -> MemoryEntity | None:
        with Session(self._engine) as session:
            entity = session.execute(
                select(MemoryEntity).where(
                    MemoryEntity.scope == "project",
                    MemoryEntity.studio_product_id == uuid.UUID(studio_product_id),
                    MemoryEntity.name == name,
                )
            ).scalar_one_or_none()
            if entity is None:
                return None
            session.expunge(entity)
            return entity

    def list_studio_entities(self, studio_product_id: str) -> list[MemoryEntity]:
        with Session(self._engine) as session:
            rows = session.execute(
                select(MemoryEntity).where(
                    MemoryEntity.scope == "project",
                    MemoryEntity.studio_product_id == uuid.UUID(studio_product_id),
                )
            ).scalars().all()
            for entity in rows:
                session.expunge(entity)
            return list(rows)

    def find_global_entity(self, name: str) -> MemoryEntity | None:
        with Session(self._engine) as session:
            entity = session.execute(
                select(MemoryEntity).where(
                    MemoryEntity.scope == "global",
                    MemoryEntity.name == name,
                )
            ).scalar_one_or_none()
            if entity is None:
                return None
            session.expunge(entity)
            return entity

    def list_project_entities(self, project_id: str) -> list[MemoryEntity]:
        with Session(self._engine) as session:
            rows = session.execute(
                select(MemoryEntity).where(
                    MemoryEntity.scope == "project",
                    MemoryEntity.project_id == uuid.UUID(project_id),
                )
            ).scalars().all()
            for e in rows:
                session.expunge(e)
            return list(rows)

    def list_global_entities(self) -> list[MemoryEntity]:
        with Session(self._engine) as session:
            rows = session.execute(
                select(MemoryEntity).where(MemoryEntity.scope == "global")
            ).scalars().all()
            for e in rows:
                session.expunge(e)
            return list(rows)

    def count_entity_by_name_across_projects(self, name: str, exclude_project: str) -> int:
        """统计同名词实体出现在多少个不同项目（全局提升用）。"""
        with Session(self._engine) as session:
            rows = session.execute(
                select(MemoryEntity.project_id).where(
                    MemoryEntity.scope == "project",
                    MemoryEntity.name == name,
                    MemoryEntity.project_id.is_not(None),
                    MemoryEntity.project_id != uuid.UUID(exclude_project),
                )
            ).all()
            return len({r[0] for r in rows})

    def count_studio_entity_by_name_across_products(
        self, name: str, exclude_product: str,
    ) -> int:
        """统计同名 Studio 实体出现在多少个其他 Product Studio 任务。"""
        with Session(self._engine) as session:
            rows = session.execute(
                select(MemoryEntity.studio_product_id).where(
                    MemoryEntity.scope == "project",
                    MemoryEntity.name == name,
                    MemoryEntity.studio_product_id.is_not(None),
                    MemoryEntity.studio_product_id != uuid.UUID(exclude_product),
                )
            ).all()
            return len({row[0] for row in rows})

    def count_entity_across_all_tasks(
        self, name: str,
        exclude_project: str | None = None,
        exclude_product: str | None = None,
    ) -> int:
        """同名实体出现的不同任务总数（research 项目 + Studio 任务合并计数）。

        全局提升的双通道合并口径：此前 research 与 Studio 互不计数，单一
        通道任务永不满足 ≥2 复现条件 → 全局记忆永远为空（实测根因）。
        """
        with Session(self._engine) as session:
            stmt = select(
                MemoryEntity.project_id, MemoryEntity.studio_product_id,
            ).where(
                MemoryEntity.scope == "project",
                MemoryEntity.name == name,
            )
            if exclude_project:
                stmt = stmt.where(
                    (MemoryEntity.project_id != uuid.UUID(exclude_project))
                    | MemoryEntity.project_id.is_(None),
                )
            if exclude_product:
                stmt = stmt.where(
                    (MemoryEntity.studio_product_id != uuid.UUID(exclude_product))
                    | MemoryEntity.studio_product_id.is_(None),
                )
            rows = session.execute(stmt).all()
            tasks: set = set()
            for project_id, studio_product_id in rows:
                if project_id is not None:
                    tasks.add(("p", project_id))
                if studio_product_id is not None:
                    tasks.add(("s", studio_product_id))
            return len(tasks)

    def search_entities_by_keyword(
        self, query: str, scope: str = "project",
        project_id: str | None = None, limit: int = 5,
    ) -> list[MemoryEntity]:
        """实体名/别名关键词检索（向量检索兜底）。"""
        kw = f"%{query}%"
        with Session(self._engine) as session:
            stmt = select(MemoryEntity).where(
                MemoryEntity.scope == scope,
                MemoryEntity.name.ilike(kw),
            )
            if project_id:
                stmt = stmt.where(MemoryEntity.project_id == uuid.UUID(project_id))
            rows = session.execute(stmt.order_by(MemoryEntity.confidence.desc()).limit(limit)).scalars().all()
            for e in rows:
                session.expunge(e)
            return list(rows)

    def list_memory_entities(
        self,
        scope: str = "global",
        project_id: str | None = None,
        studio_product_id: str | None = None,
        q: str | None = None,
        entity_types: list[str] | None = None,
        min_confidence: float = 0.0,
    ) -> list[MemoryEntity]:
        """关系图节点查询（支持关键词/类型/置信度过滤）。"""
        with Session(self._engine) as session:
            stmt = select(MemoryEntity).where(MemoryEntity.scope == scope)
            if project_id:
                stmt = stmt.where(MemoryEntity.project_id == uuid.UUID(project_id))
            if studio_product_id:
                stmt = stmt.where(
                    MemoryEntity.studio_product_id == uuid.UUID(studio_product_id)
                )
            if q:
                stmt = stmt.where(MemoryEntity.name.ilike(f"%{q}%"))
            if entity_types:
                stmt = stmt.where(MemoryEntity.type.in_(entity_types))
            if min_confidence > 0:
                stmt = stmt.where(MemoryEntity.confidence >= min_confidence)
            rows = session.execute(stmt.order_by(MemoryEntity.confidence.desc())).scalars().all()
            for e in rows:
                session.expunge(e)
            return list(rows)

    def update_entity_merge(
        self,
        entity_id: str,
        new_alias: str | None = None,
        new_summary: str | None = None,
        confidence_delta: float = 0.0,
        last_seen=None,
    ) -> None:
        """实体合并更新：追加别名/摘要、置信度上调、刷新 seen 时间。"""
        with Session(self._engine) as session:
            entity = session.execute(
                select(MemoryEntity).where(MemoryEntity.id == uuid.UUID(entity_id))
            ).scalar_one_or_none()
            if entity is None:
                return
            if new_alias and new_alias != entity.name:
                aliases = json.loads(entity.aliases) if entity.aliases else []
                if new_alias not in aliases:
                    aliases.append(new_alias)
                entity.aliases = json.dumps(aliases, ensure_ascii=False)[:2000]
            if new_summary:
                # 摘要合并：取更长的（信息更全）
                if not entity.summary or len(new_summary) > len(entity.summary):
                    entity.summary = new_summary[:500]
            if confidence_delta:
                entity.confidence = min(0.95, (entity.confidence or 0.6) + confidence_delta)
            if last_seen is not None:
                entity.last_seen_at = last_seen
            session.commit()

    def decay_stale_entities(self, cutoff, step: float, floor: float) -> int:
        """对 last_seen 早于 cutoff 的实体做置信度衰减。"""
        with Session(self._engine) as session:
            rows = session.execute(
                select(MemoryEntity).where(
                    MemoryEntity.last_seen_at.is_not(None),
                    MemoryEntity.last_seen_at < cutoff,
                    MemoryEntity.confidence > floor,
                )
            ).scalars().all()
            for e in rows:
                e.confidence = max(floor, (e.confidence or 0.6) - step)
            session.commit()
            return len(rows)

    def delete_entities_with_relations(self, entity_ids: list[str]) -> None:
        """级联删除实体及其全部关系。"""
        if not entity_ids:
            return
        ids = [uuid.UUID(e) for e in entity_ids]
        with Session(self._engine) as session:
            session.execute(
                delete(MemoryRelation).where(
                    MemoryRelation.source_entity_id.in_(ids)
                )
            )
            session.execute(
                delete(MemoryRelation).where(
                    MemoryRelation.target_entity_id.in_(ids)
                )
            )
            session.execute(delete(MemoryEntity).where(MemoryEntity.id.in_(ids)))
            session.commit()

    # ── 关系 ─────────────────────────────────────────────────

    def save_memory_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
        evidence: str | None = None,
        weight: float = 1.0,
        valid_from=None,
    ) -> MemoryRelation:
        with Session(self._engine) as session:
            rel = MemoryRelation(
                source_entity_id=uuid.UUID(source_id),
                target_entity_id=uuid.UUID(target_id),
                relation_type=relation_type,
                evidence=evidence,
                weight=weight,
                valid_from=valid_from,
            )
            session.add(rel)
            session.commit()
            session.refresh(rel)
            session.expunge(rel)
            return rel

    def find_relation(
        self, source_id: str, target_id: str, relation_type: str,
        active_only: bool = True,
    ) -> MemoryRelation | None:
        with Session(self._engine) as session:
            stmt = select(MemoryRelation).where(
                MemoryRelation.source_entity_id == uuid.UUID(source_id),
                MemoryRelation.target_entity_id == uuid.UUID(target_id),
                MemoryRelation.relation_type == relation_type,
            )
            if active_only:
                stmt = stmt.where(MemoryRelation.valid_to.is_(None))
            rel = session.execute(stmt.order_by(MemoryRelation.created_at.desc())).scalars().first()
            if rel is None:
                return None
            session.expunge(rel)
            return rel

    def update_relation_weight(
        self, relation_id: str, weight: float, evidence: str | None = None,
    ) -> None:
        with Session(self._engine) as session:
            rel = session.execute(
                select(MemoryRelation).where(MemoryRelation.id == uuid.UUID(relation_id))
            ).scalar_one_or_none()
            if rel is None:
                return
            rel.weight = weight
            if evidence:
                rel.evidence = evidence
            session.commit()

    def expire_relation(self, relation_id: str, valid_to) -> None:
        with Session(self._engine) as session:
            rel = session.execute(
                select(MemoryRelation).where(MemoryRelation.id == uuid.UUID(relation_id))
            ).scalar_one_or_none()
            if rel is None:
                return
            rel.valid_to = valid_to
            session.commit()

    def list_relations_for_entity(
        self, entity_id: str, active_only: bool = True, limit: int = 50,
    ) -> list[MemoryRelation]:
        with Session(self._engine) as session:
            stmt = select(MemoryRelation).where(
                (MemoryRelation.source_entity_id == uuid.UUID(entity_id))
                | (MemoryRelation.target_entity_id == uuid.UUID(entity_id))
            )
            if active_only:
                stmt = stmt.where(MemoryRelation.valid_to.is_(None))
            rows = session.execute(stmt.order_by(MemoryRelation.weight.desc()).limit(limit)).scalars().all()
            for r in rows:
                session.expunge(r)
            return list(rows)

    def list_relations_between(
        self, entity_ids: set[str], active_only: bool = True, limit: int = 3000,
    ) -> list[MemoryRelation]:
        if not entity_ids:
            return []
        ids = [uuid.UUID(e) for e in entity_ids]
        with Session(self._engine) as session:
            stmt = select(MemoryRelation).where(
                MemoryRelation.source_entity_id.in_(ids),
                MemoryRelation.target_entity_id.in_(ids),
            )
            if active_only:
                stmt = stmt.where(MemoryRelation.valid_to.is_(None))
            rows = session.execute(stmt.order_by(MemoryRelation.weight.desc()).limit(limit)).scalars().all()
            for r in rows:
                session.expunge(r)
            return list(rows)

    # ── 洞察 ─────────────────────────────────────────────────

    def save_memory_insight(
        self,
        scope: str,
        content: str,
        project_id: str | None = None,
        studio_product_id: str | None = None,
        entity_ids: list[str] | None = None,
        source: str = "task_summary",
        source_url: str | None = None,
        confidence: float = 0.7,
    ) -> MemoryInsight:
        with Session(self._engine) as session:
            insight = MemoryInsight(
                scope=scope,
                project_id=uuid.UUID(project_id) if project_id else None,
                studio_product_id=uuid.UUID(studio_product_id) if studio_product_id else None,
                content=content,
                entity_ids=json.dumps(entity_ids or [], ensure_ascii=False),
                source=source,
                source_url=source_url,
                confidence=confidence,
            )
            session.add(insight)
            session.commit()
            session.refresh(insight)
            session.expunge(insight)
            return insight

    def list_insights(
        self, scope: str = "project", project_id: str | None = None,
        studio_product_id: str | None = None, limit: int = 50,
    ) -> list[MemoryInsight]:
        with Session(self._engine) as session:
            stmt = select(MemoryInsight).where(MemoryInsight.scope == scope)
            if project_id:
                stmt = stmt.where(MemoryInsight.project_id == uuid.UUID(project_id))
            if studio_product_id:
                stmt = stmt.where(
                    MemoryInsight.studio_product_id == uuid.UUID(studio_product_id)
                )
            rows = session.execute(stmt.order_by(MemoryInsight.created_at.desc()).limit(limit)).scalars().all()
            for i in rows:
                session.expunge(i)
            return list(rows)

    def list_insights_by_entity_ids(self, entity_ids: list[str], limit: int = 10) -> list[MemoryInsight]:
        """召回链接了指定实体的洞察（entity_ids JSON 包含匹配）。"""
        if not entity_ids:
            return []
        with Session(self._engine) as session:
            rows = session.execute(
                select(MemoryInsight).order_by(MemoryInsight.created_at.desc()).limit(200)
            ).scalars().all()
            matched = []
            for i in rows:
                try:
                    linked = json.loads(i.entity_ids) if i.entity_ids else []
                except (json.JSONDecodeError, TypeError):
                    continue
                if any(eid in linked for eid in entity_ids):
                    matched.append(i)
                    if len(matched) >= limit:
                        break
            for i in matched:
                session.expunge(i)
            return matched

    def find_global_insight_by_content(self, content: str) -> MemoryInsight | None:
        with Session(self._engine) as session:
            insight = session.execute(
                select(MemoryInsight).where(
                    MemoryInsight.scope == "global",
                    MemoryInsight.content == content,
                )
            ).scalar_one_or_none()
            if insight is None:
                return None
            session.expunge(insight)
            return insight

    def delete_insights_by_project(self, project_id: str, scope: str | None = None) -> None:
        with Session(self._engine) as session:
            stmt = delete(MemoryInsight).where(
                MemoryInsight.project_id == uuid.UUID(project_id)
            )
            if scope:
                stmt = stmt.where(MemoryInsight.scope == scope)
            session.execute(stmt)
            session.commit()

    # ── 知识库图片（记忆抽取语料） ───────────────────────────

    def list_kb_images(self, project_id: str, limit: int = 20) -> list[ProjectImage]:
        """列出项目知识库图片（含 VL 分析文本，供记忆抽取）。"""
        with Session(self._engine) as session:
            rows = session.execute(
                select(ProjectImage)
                .where(
                    ProjectImage.project_id == uuid.UUID(project_id),
                    ProjectImage.source == "upload",
                )
                .order_by(ProjectImage.created_at.desc())
                .limit(limit)
            ).scalars().all()
            for i in rows:
                session.expunge(i)
            return list(rows)

    def get_entities_by_ids(self, entity_ids: list[str]) -> list[MemoryEntity]:
        """按 ID 批量取实体（全局图邻接节点加载）。"""
        if not entity_ids:
            return []
        ids = [uuid.UUID(e) for e in entity_ids]
        with Session(self._engine) as session:
            rows = session.execute(
                select(MemoryEntity).where(MemoryEntity.id.in_(ids))
            ).scalars().all()
            for e in rows:
                session.expunge(e)
            return list(rows)

    def get_studio_product(self, product_id: str):
        """读取 AI Product Studio 产品（记忆图语料源）。"""
        from app.models.studio_product import StudioProduct
        try:
            pid = uuid.UUID(product_id)
        except ValueError:
            return None
        with Session(self._engine) as session:
            product = session.execute(
                select(StudioProduct).where(StudioProduct.id == pid)
            ).scalar_one_or_none()
            if product is None:
                return None
            session.expunge(product)
            return product
