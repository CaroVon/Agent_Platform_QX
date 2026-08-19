"""
============================================================
项目相关 API 路由
—— POST/GET 等核心业务接口
    状态机关键交互节点：创建 → 准备 → 待大纲审批 → 撰写 → 完成
============================================================
"""

from __future__ import annotations

import json
import uuid
import os
import time
import logging
import asyncio
from typing import Any
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import get_settings
from app.core.security import get_current_user
from app.models.project import Project, ProjectStatus
from app.schemas import (
    ProjectCreateRequest,
    ProjectCreateResponse,
    ProjectResponse,
    ProjectStatusResponse,
    TaskResponse,
    DownloadResponse,
    MessageResponse,
    OutlineApproveRequest,
    OutlineApproveResponse,
    DocumentBlockResponse,
    DocumentBlockListResponse,
    SSEDraftEvent,
    ReportContentResponse,
    SectionContent,
    SourceItem,
    SourceReviewRequest,
    SourceReviewResponse,
    SourcesListResponse,
    ProjectLogResponse,
    ProjectLogListResponse,
    ExportPdfRequest,
    ImageSearchRequest,
    ImageSearchResponse,
    ImageResultResponse,
    ProjectImagesResponse,
)
from app.models.project_image import ProjectImage
from app.models.project_log import ProjectLog
from app.tasks.report_workflow import (
    run_full_report_workflow,
    prepare_sources_workflow,
    generate_outline_workflow,
    run_draft_sections_workflow,
    _load_sources_from_project,
)
from app.core.celery_db import get_crawled_data_path
from app.models.task import Task, TaskType, TaskStatus
from app.models.user import User
from app.models.document_block import DocumentBlock
from app.models.document import Document
from app.models.base import orm_to_dict
from app.rag.local_parser import parse_local_file
from app.rag.vector_store import build_vector_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects", tags=["projects"])


# ================================================================
# 状态机日志打印（产品化关键标志）
# ================================================================

def log_state_transition(
    project_id: str,
    from_status: str | None,
    to_status: str,
    reason: str = "",
):
    """
    记录项目状态机流转日志。
    这是从"批处理工具"转向"交互式 Agent"的标志性函数——
    每一次状态变化都清晰可追溯。
    """
    logger.info("🔷 [STATE MACHINE] project=%s | %s → %s | reason=%s",
                project_id, from_status or "(初始)", to_status, reason)


# ================================================================
# POST /api/v1/projects —— 创建分析项目，触发「节点1：资料准备」
# ================================================================

@router.post("", response_model=ProjectCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    创建一个产品分析项目，自动触发「节点1：资料准备与大纲生成」。

    状态机详解：
    PREPARING_DATA (初始) →
      当资料准备+大纲生成完成后，自动变为 WAITING_OUTLINE_APPROVAL，
      等待用户通过 POST /approve-outline 确认。

    参数:
    - **topic**: 分析主题，例如 "智能手表产品分析"

    返回项目 ID，前端可用 GET /status 轮询进度。
    """
    # ─── 当前用户（认证注入，替代硬编码演示用户） ──────────────
    current_user_id = user.id

    # ─── 1. 创建 Project 记录（初始状态：PREPARING_DATA） ──────
    project = Project(
        owner_id=current_user_id,
        topic=body.topic,
        status=ProjectStatus.PREPARING_DATA,
        template_type=body.template_type,
        search_depth=body.search_depth,
        images_per_page=body.images_per_page,
    )
    db.add(project)
    await db.flush()

    log_state_transition(str(project.id), None, "preparing_data",
                         f"用户提交分析主题: {body.topic}")

    # ─── 2. 创建 Task 链记录（节点1：搜索 → 知识库 → 大纲） ──
    task_definitions = [
        (TaskType.SEARCH, 1, None),
        (TaskType.BUILD_KNOWLEDGE_BASE, 2, None),
        (TaskType.GENERATE_OUTLINE, 3, None),
    ]
    for task_type, seq, section in task_definitions:
        task = Task(
            project_id=project.id,
            task_type=task_type,
            status=TaskStatus.PENDING,
            sequence_order=seq,
            section_title=section,
        )
        db.add(task)
    await db.commit()
    await db.refresh(project)

    # ─── 3. 提交 Celery 「阶段1：资料搜集」异步任务 ────────────
    celery_task_id: str | None = None
    task_message = "项目已创建"
    try:
        celery_task = prepare_sources_workflow.delay(str(project.id))
        celery_task_id = celery_task.id
        task_message = "项目已创建，正在搜索资料并生成大纲，请稍候通过 /status 查询进度"
        logger.info("项目已创建 | topic=%s | project_id=%s | celery_task=%s",
                    body.topic, project.id, celery_task_id)
    except Exception as e:
        logger.warning("Celery 任务提交失败（Redis 可能未运行）: %s | 项目仍已入库", str(e))
        task_message = "项目已创建，但异步工作流暂不可用（Redis 未连接），请稍后重试或联系管理员"

    return ProjectCreateResponse(
        project=ProjectResponse.model_validate(orm_to_dict(project)),
        celery_task_id=celery_task_id or "",
        message=task_message,
    )


# ================================================================
# GET /api/v1/projects/{project_id}/status —— 查询进度（含大纲暂存）
# ================================================================

@router.get("/{project_id}/status", response_model=ProjectStatusResponse)
async def get_project_status(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    查询指定项目的完整进度状态。

    当项目处于 WAITING_OUTLINE_APPROVAL 状态时，
    返回的 outline_content 字段包含 LLM 生成的大纲 Markdown，
    前端可将其渲染到 Tiptap 编辑器中供用户审阅/修改。

    前端轮询建议间隔：2-5 秒。
    """
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"项目 {project_id} 不存在",
        )
    if project.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该项目",
        )

    # ─── 查询所有任务步 ──────────────────────────────────────
    task_result = await db.execute(
        select(Task)
        .where(Task.project_id == project_id)
        .order_by(Task.sequence_order)
    )
    tasks = task_result.scalars().all()

    # ─── 统计进度 ──────────────────────────────────────────────
    total = len(tasks)
    completed = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
    failed = sum(1 for t in tasks if t.status == TaskStatus.FAILED)
    percentage = round((completed / total * 100), 1) if total > 0 else 0.0

    progress = {
        "total_tasks": total,
        "completed_tasks": completed,
        "failed_tasks": failed,
        "percentage": percentage,
    }

    # 🆕 推导 current_step（从最新 ProjectLog 获取）
    current_step = None
    log_result = await db.execute(
        select(ProjectLog)
        .where(ProjectLog.project_id == project_id)
        .order_by(ProjectLog.sequence.desc())
        .limit(1)
    )
    latest_log = log_result.scalar_one_or_none()
    if latest_log:
        current_step = {
            "step": latest_log.step,
            "message": latest_log.message,
            "icon": latest_log.icon,
            "level": latest_log.level.value if latest_log.level else "info",
        }

    return ProjectStatusResponse(
        project_id=project.id,
        topic=project.topic,
        project_status=project.status,
        template_type=project.template_type or "product",
        outline_content=project.outline_content,
        pdf_path=project.pdf_path,
        search_depth=project.search_depth,
        images_per_page=getattr(project, 'images_per_page', 2),
        logo_url=project.logo_url,
        progress=progress,
        current_step=current_step,
        tasks=[TaskResponse.model_validate(orm_to_dict(t)) for t in tasks],
    )


# ================================================================
# 🎯 GET /api/v1/projects/{project_id}/sources —— 资料预审核面板数据
# ================================================================

@router.get("/{project_id}/sources", response_model=SourcesListResponse)
async def list_sources(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    🎯 **交互节点1**：获取搜索结果/资料来源列表，供用户审核。

    当项目状态为 `waiting_for_sources` 时，用户进入资料审核面板，
    可查看每条资料的标题、URL、摘要，勾选/取消勾选。

    返回格式适配前端「资料审核面板」组件。
    """
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail=f"项目 {project_id} 不存在")

    if project.status not in (ProjectStatus.WAITING_FOR_SOURCES,
                              ProjectStatus.PREPARING_OUTLINE,
                              ProjectStatus.WAITING_FOR_OUTLINE,
                              ProjectStatus.DRAFTING,
                              ProjectStatus.COMPLETED):
        raise HTTPException(
            status_code=409,
            detail=f"项目状态 '{project.status.value}' 不支持获取资料列表。请等待资料搜集完成。",
        )

    # 从暂存文件读取搜索结果
    raw_sources = _load_sources_from_project(str(project_id))
    sources: list[SourceItem] = []
    for i, item in enumerate(raw_sources):
        sources.append(SourceItem(
            index=i + 1,
            title=item.get("title", f"资料 {i + 1}"),
            url=item.get("url", ""),
            snippet=(item.get("content", "") or "")[:200],
            selected=True,
        ))

    return SourcesListResponse(
        project_id=project.id,
        topic=project.topic,
        sources=sources,
        total_count=len(sources),
    )


# ================================================================
# 🎯 POST /api/v1/projects/{project_id}/review-sources —— 确认资料
# ================================================================

@router.post("/{project_id}/review-sources", response_model=SourceReviewResponse)
async def review_sources(
    project_id: uuid.UUID,
    body: SourceReviewRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    🎯 **交互节点1 确认**：用户审核资料后提交筛选结果，触发阶段2（大纲生成）。

    状态机推进：
    WAITING_FOR_SOURCES ──(用户审核资料)──→ PREPARING_OUTLINE

    流程：
    1. 接收用户筛选后的 URL 列表
    2. 根据筛选结果更新爬取数据（过滤掉被剔除的资料）
    3. 状态机推进到 PREPARING_OUTLINE
    4. 触发 Celery 阶段2：生成大纲
    """
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail=f"项目 {project_id} 不存在")

    if project.status != ProjectStatus.WAITING_FOR_SOURCES:
        raise HTTPException(
            status_code=409,
            detail=f"当前状态为 '{project.status.value}'，仅 'waiting_for_sources' 可审核资料。",
        )

    # ── 1. 筛选资料 ──────────────────────────────────────
    raw_sources = _load_sources_from_project(str(project_id))
    kept_sources = [
        s for s in raw_sources
        if s.get("url", "") in body.selected_urls
    ]

    # 重新保存筛选后的资料（供后续知识库构建使用）
    import json as _json
    temp_data_path = get_crawled_data_path(str(project_id))
    with open(temp_data_path, "w", encoding="utf-8") as f:
        _json.dump(kept_sources, f, ensure_ascii=False, indent=2)

    logger.info("资料审核完成 | project=%s | kept=%d/%d | notes=%s",
                project_id, len(kept_sources), len(raw_sources),
                body.additional_notes or "")

    # ── 2. 状态机推进：WAITING_FOR_SOURCES → PREPARING_OUTLINE ──
    old_status = project.status
    project.status = ProjectStatus.PREPARING_OUTLINE
    log_state_transition(str(project.id), old_status, "preparing_outline",
                         f"用户确认 {len(kept_sources)} 条资料（共 {len(raw_sources)} 条），开始生成大纲")
    await db.commit()

    # ── 3. 触发阶段2：生成大纲 ───────────────────────────
    celery_task = generate_outline_workflow.delay(str(project.id))

    return SourceReviewResponse(
        project_id=project.id,
        new_status=ProjectStatus.PREPARING_OUTLINE.value,
        message=f"已确认 {len(kept_sources)} 条资料，正在生成大纲...",
        kept_sources=len(kept_sources),
        celery_task_id=celery_task.id,
    )


# ================================================================
# POST /api/v1/projects/{project_id}/upload-docs —— 本地上传 PDF 入库
# ================================================================

@router.post("/{project_id}/upload-docs")
async def upload_local_docs(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    上传本地 PDF 文件并打入项目知识库（Chroma + BM25）。

    设计约束（严格遵守）：
    - **绝不**修改 ProjectStatus，也**绝不**触发任何 Celery 任务。
    - 用户上传文件后仍需通过 /review-sources 接口手动推进状态机。
    - 所有本地解析文件的 source URL 统一使用 local://{filename} 格式。

    状态约束：仅 PREPARING_DATA 或 WAITING_FOR_SOURCES 状态可上传。
    """
    # ── 1. 验证项目存在 ──────────────────────────────────────
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"项目 {project_id} 不存在",
        )

    # ── 2. 状态机守卫 ────────────────────────────────────────
    if project.status not in (ProjectStatus.PREPARING_DATA, ProjectStatus.WAITING_FOR_SOURCES):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"当前项目状态为 '{project.status.value}'，"
                "仅 'preparing_data' 或 'waiting_for_sources' 状态可上传文件。"
            ),
        )

    # ── 2.5 安全校验：文件名 sanitize + 扩展名白名单 ──────────
    raw_name = (file.filename or "").strip()
    if not raw_name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="文件名不能为空")
    # 关键：剥离所有目录成分，仅保留 basename，杜绝路径穿越
    safe_name = Path(raw_name).name
    ext = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else ""
    allowed = {e.strip().lower() for e in get_settings().ALLOWED_UPLOAD_EXTS.split(",") if e.strip()}
    if ext not in allowed:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"不支持的文件类型 '.{ext}'，仅允许: {', '.join(sorted(allowed))}",
        )

    # ── 3. 确保上传目录存在（私有目录：不对外静态挂载） ─────
    settings = get_settings()
    upload_dir = os.path.join(settings.OUTPUT_DIR, "private", "uploads", str(project_id))
    os.makedirs(upload_dir, exist_ok=True)

    # ── 3.5 大小限制（防磁盘 DoS，超限直接拒绝） ─────────────
    max_bytes = get_settings().MAX_UPLOAD_MB * 1024 * 1024
    content = b""
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        content += chunk
        if len(content) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"文件超过大小上限 {get_settings().MAX_UPLOAD_MB}MB",
            )

    # ── 4. 保存上传文件到磁盘（sanitize 后的安全文件名） ─────
    file_path = os.path.join(upload_dir, safe_name)
    with open(file_path, "wb") as f:
        f.write(content)

    logger.info("文件已保存 | project=%s | filename=%s | size=%d",
                project_id, safe_name, len(content))

    # ── 5. 解析文件 → 切片（PDF/TXT/MD/DOCX 自动分派） ────────
    try:
        chunks = parse_local_file(file_path, safe_name)
    except Exception as e:
        logger.error("文件解析失败 | project=%s | file=%s | error=%s",
                     project_id, safe_name, str(e))
        # 解析失败即清理已落盘文件，避免孤儿文件堆积
        try:
            os.remove(file_path)
        except OSError:
            pass
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"文件解析失败: {str(e)}",
        )

    if not chunks:
        try:
            os.remove(file_path)
        except OSError:
            pass
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="文件解析后无有效文本内容（可能为纯图片 PDF）。",
        )

    # ── 6. 写入向量库 + BM25（追加模式，不覆盖已有数据） ────
    try:
        build_vector_store(chunks, project_id=str(project_id))
    except Exception as e:
        logger.error("向量库写入失败 | project=%s | error=%s", project_id, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"知识库写入失败: {str(e)}",
        )

    # ── 6.5 回写 Document 表（知识页列表可见，含文件全文摘要） ─
    try:
        doc = Document(
            project_id=project.id,
            section_title=f"📎 {safe_name}",
            section_order=0,
            content="\n\n".join(c["content"] for c in chunks[:50])[:20000],
            source_urls=json.dumps([f"local://{safe_name}"]),
        )
        db.add(doc)
        await db.commit()
    except Exception as e:
        # 向量库已写入成功，Document 回写失败仅告警不阻断
        logger.warning("上传文档回写 Document 表失败 | project=%s | error=%s",
                       project_id, str(e))

    logger.info("本地文件已入库 | project=%s | file=%s | chunks=%d",
                project_id, safe_name, len(chunks))

    # ── 7. 返回成功信息（不做任何 DB commit / 状态变更） ────
    return {
        "message": f"文件 '{safe_name}' 已成功上传并入库",
        "chunk_count": len(chunks),
        "project_id": str(project_id),
    }


# ================================================================
# POST /api/v1/projects/{project_id}/approve-outline —— 🎯 交互核心节点2
# ================================================================

@router.post("/{project_id}/approve-outline", response_model=OutlineApproveResponse)
async def approve_outline(
    project_id: uuid.UUID,
    body: OutlineApproveRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    🎯 **产品交互核心节点**：用户确认/修改大纲后触发「节点2：分章节撰写」。

    状态机推进：
    WAITING_OUTLINE_APPROVAL ──(用户审批)──→ DRAFTING

    流程：
    1. 接收前端提交的最终大纲（用户可能已在 Tiptap 中修改了 LLM 生成的内容）
    2. 将最终大纲保存到 project.outline_content
    3. 从大纲的 Markdown 中解析出 ## 章节标题
    4. 将 Project.status 从 waiting_outline_approval → drafting
    5. 为每个章节创建 Task (WRITE_SECTION) + DocumentBlock 占位
    6. 异步触发 Celery 任务，逐章节生成草稿内容

    请求体：
    - **outline**: 最终确认的大纲 Markdown（用户修改后的版本）

    状态约束：
    - 仅当项目状态为 `waiting_outline_approval` 时可调用
    - 否则返回 409 Conflict
    """
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"项目 {project_id} 不存在",
        )

    # ─── 校验状态 ──────────────────────────────────────────────
    if project.status != ProjectStatus.WAITING_FOR_OUTLINE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"当前项目状态为 '{project.status.value}'，"
                "仅当状态为 'waiting_for_outline' 时可以审批大纲。"
                "请先等待资料审核和大纲生成完成。"
            ),
        )

    # ─── 1. 保存最终确定的大纲 ─────────────────────────────────
    project.outline_content = body.outline

    # ─── 2. 解析章节标题 ──────────────────────────────────────
    sections = _extract_sections_from_outline(body.outline)

    if not sections:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="解析大纲失败：未找到任何 '## ' 开头的章节标题。"
                   "请确保大纲使用 Markdown 二级标题格式。",
        )

    # ─── 3. 状态机推进：WAITING_OUTLINE_APPROVAL → DRAFTING ────
    old_status = project.status
    project.status = ProjectStatus.DRAFTING
    log_state_transition(
        str(project.id),
        old_status,
        "drafting",
        f"用户确认大纲，共 {len(sections)} 个章节，即将开始异步撰写",
    )

    # ─── 4. 清理旧 DocumentBlock 占位 + 创建新的 Task & Block ──
    # 先删除该项目下所有旧的 DocumentBlock 占位记录（防止重复调用导致 MultipleResultsFound）
    await db.execute(
        delete(DocumentBlock).where(DocumentBlock.project_id == project.id)
    )

    for idx, section_title in enumerate(sections):
        # 创建 Task
        write_task = Task(
            project_id=project.id,
            task_type=TaskType.WRITE_SECTION,
            status=TaskStatus.PENDING,
            sequence_order=10 + idx,
            section_title=section_title,
        )
        db.add(write_task)

        # 创建 DocumentBlock 占位（内容为空，等待撰写完成后填充）
        block = DocumentBlock(
            project_id=project.id,
            section_title=section_title,
            order_index=(idx + 1) * 10,  # 10, 20, 30...
            content=f"## {section_title}\n\n_等待生成中..._\n",
            citations="{}",
        )
        db.add(block)

    # ─── 确保有 BUILD_REPORT + GENERATE_PDF 收尾任务 ──────────
    existing_types = await db.execute(
        select(Task.task_type).where(
            Task.project_id == project.id,
            Task.task_type.in_([TaskType.BUILD_REPORT, TaskType.GENERATE_PDF]),
        )
    )
    existing_type_set = {row[0] for row in existing_types.fetchall()}

    if TaskType.BUILD_REPORT not in existing_type_set:
        db.add(Task(
            project_id=project.id,
            task_type=TaskType.BUILD_REPORT,
            status=TaskStatus.PENDING,
            sequence_order=97,
        ))
    if TaskType.GENERATE_PDF not in existing_type_set:
        db.add(Task(
            project_id=project.id,
            task_type=TaskType.GENERATE_PDF,
            status=TaskStatus.PENDING,
            sequence_order=98,
        ))

    await db.commit()

    # ─── 5. 触发「节点2：分章节异步撰写」 ─────────────────────
    celery_task = run_draft_sections_workflow.delay(str(project.id))

    logger.info("大纲已确认 | project=%s | sections=%d | celery_task=%s",
                project.id, len(sections), celery_task.id)

    return OutlineApproveResponse(
        project_id=project.id,
        new_status=ProjectStatus.DRAFTING.value,
        message=f"大纲已确认，共 {len(sections)} 个章节，异步撰写任务已提交",
        sections_count=len(sections),
        celery_task_id=celery_task.id,
    )


def _extract_sections_from_outline(outline: str) -> list[str]:
    """
    从大纲 Markdown 中提取所有 ## 二级标题作为章节名。
    委托给共享模块 app.shared.outline_parser.extract_sections 的唯一实现。
    """
    from app.shared.outline_parser import extract_sections
    return extract_sections(outline)


# ================================================================
# 加分项：GET /api/v1/projects/{project_id}/stream-draft —— SSE 流式输出
# ================================================================

@router.get("/{project_id}/stream-draft")
async def stream_draft(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    🌊 **SSE (Server-Sent Events) 流式草稿输出**（加分项）

    前端可通过 EventSource 连接此接口，实时接收各章节撰写完成事件。
    每完成一个 DocumentBlock，后端通过 SSE 推送该块内容，
    前端 Tiptap 编辑器可即时插入，实现"逐块流式呈现"的效果。

    SSE 事件格式:
    - event: section_start   → 某章节开始撰写
    - event: section_chunk   → 章节的某个块已完成（含完整 DocumentBlock 数据）
    - event: section_complete → 某章节全部完成
    - event: draft_complete  → 所有章节撰写完毕
    - event: error           → 发生错误

    前端使用示例:
    ```typescript
    const es = new EventSource(`/api/v1/projects/${id}/stream-draft`);
    es.addEventListener('section_chunk', (e) => {
      const block = JSON.parse(e.data);
      // 插入到 Tiptap 编辑器
    });
    ```

    NOTE: 当前为伪代码实现。生产环境中，Celery 任务完成时应将事件
    写入 Redis Pub/Sub 或数据库轮询表，SSE 端点从中读取并推送。
    此处使用轮询方式模拟 SSE 流。
    """
    pid_str = str(project_id)

    async def event_generator():
        """
        SSE 事件生成器 —— 轮询 DocumentBlock 表推送给前端。

        生产环境中可升级为 Redis Pub/Sub：
        1. Celery Worker 写完 DocumentBlock 后向 Redis 发布事件
        2. 此端点订阅 Redis 频道实时推送
        3. 前端 EventSource 连接后即刻收到推送
        """
        import asyncio as _asyncio

        # ─── 确认项目存在 ──────────────────────────────────────
        result = await db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()
        if project is None:
            yield f"event: error\ndata: {json.dumps({'error': '项目不存在'})}\n\n"
            return

        if project.status not in (ProjectStatus.DRAFTING, ProjectStatus.COMPLETED):
            yield f"event: error\ndata: {json.dumps({'error': f'项目状态为 {project.status}，无法流式输出'})}\n\n"
            return

        last_block_count = 0
        max_wait_cycles = 300  # 最多 300 个轮询周期（约 10 分钟，2s 间隔）
        wait_cycles = 0
        heartbeat_interval = 10  # 每 10 个周期发送一次心跳

        sections = _extract_sections_from_outline(project.outline_content or "")
        total_sections = len(sections) if sections else 0

        yield f"event: draft_start\ndata: {json.dumps({'project_id': pid_str, 'total_sections': total_sections})}\n\n"

        while wait_cycles < max_wait_cycles:
            # 强制刷新 project 对象以获取最新状态
            await db.refresh(project)

            # ── 心跳注释（保持连接存活） ──────────────────────
            if wait_cycles % heartbeat_interval == 0:
                yield f": heartbeat {wait_cycles}\n\n"

            # 查询最新的 DocumentBlock
            block_result = await db.execute(
                select(DocumentBlock)
                .where(DocumentBlock.project_id == project_id)
                .order_by(DocumentBlock.order_index)
            )
            all_blocks = block_result.scalars().all()

            if len(all_blocks) > last_block_count:
                # 有新块完成，逐条推送
                for block in all_blocks[last_block_count:]:
                    block_data = DocumentBlockResponse.model_validate(
                        orm_to_dict(block)
                    ).model_dump(mode="json")

                    yield (
                        f"event: section_chunk\n"
                        f"data: {json.dumps(block_data, ensure_ascii=False)}\n\n"
                    )

                last_block_count = len(all_blocks)

            # 也检查项目是否已到终态
            if project.status == ProjectStatus.COMPLETED:
                yield (
                    f"event: draft_complete\n"
                    f"data: {json.dumps({'project_id': pid_str, 'total_blocks': last_block_count, 'reason': 'project_completed'})}\n\n"
                )
                return

            if project.status == ProjectStatus.FAILED:
                err_msg = f"项目失败: {project.error_message or '未知错误'}"
                yield (
                    f"event: error\n"
                    f"data: {json.dumps({'error': err_msg})}\n\n"
                )
                return

            await _asyncio.sleep(2)  # 每 2 秒轮询一次
            wait_cycles += 1

        yield f"event: error\ndata: {json.dumps({'error': 'SSE 流超时（已等待约 10 分钟）'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ================================================================
# GET /api/v1/projects/{project_id}/blocks —— 获取所有文档块
# ================================================================

@router.get("/{project_id}/blocks", response_model=DocumentBlockListResponse)
async def list_document_blocks(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    获取项目所有文档块（按 order_index 排序）。
    前端 Tiptap 编辑器加载此数据，渲染为可编辑的块列表。
    """
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"项目 {project_id} 不存在",
        )

    block_result = await db.execute(
        select(DocumentBlock)
        .where(DocumentBlock.project_id == project_id)
        .order_by(DocumentBlock.order_index)
    )
    blocks = block_result.scalars().all()

    return DocumentBlockListResponse(
        project_id=project.id,
        blocks=[DocumentBlockResponse.model_validate(orm_to_dict(b)) for b in blocks],
    )


# ================================================================
# GET /api/v1/projects/{project_id}/content —— 获取报告全文内容
# ================================================================

@router.get("/{project_id}/content", response_model=ReportContentResponse)
async def get_report_content(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    获取项目的完整报告内容（按章节顺序排列）。

    返回每章的 Markdown 正文 + 引用 URL 映射，
    供 ReportPage 渲染带溯源的报告阅读器。
    """
    # 1. 验证项目存在
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"项目 {project_id} 不存在",
        )

    # 2. 查询所有章节文档，按 section_order 排序
    doc_result = await db.execute(
        select(Document)
        .where(Document.project_id == project_id)
        .order_by(Document.section_order)
    )
    documents = doc_result.scalars().all()

    # 3. 组装返回数据
    sections: list[SectionContent] = []
    for doc in documents:
        citations: dict[str, str] = {}
        if doc.source_urls:
            try:
                urls: list[str] = json.loads(doc.source_urls)
                for idx, url in enumerate(urls):
                    citations[str(idx + 1)] = url
            except json.JSONDecodeError:
                logger.warning(
                    "解析 source_urls JSON 失败 | project_id=%s | section='%s' | raw=%s",
                    project_id, doc.section_title, doc.source_urls,
                )

        sections.append(SectionContent(
            title=doc.section_title,
            order=doc.section_order,
            content=doc.content,
            citations=citations,
        ))

    return ReportContentResponse(
        project_id=project.id,
        topic=project.topic,
        sections=sections,
    )


# ================================================================
# GET /api/v1/projects/{project_id}/download —— 获取 PDF 下载链接
# ================================================================

@router.get("/{project_id}/download", response_model=DownloadResponse)
async def download_report(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    当报告生成完毕后，获取 PDF 文件的下载链接。

    - 如果项目尚未完成，返回 409 Conflict
    - 如果项目已完成，返回可下载的 URL
    """
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"项目 {project_id} 不存在",
        )

    if project.status in (ProjectStatus.PREPARING_DATA, ProjectStatus.WAITING_FOR_SOURCES,
                          ProjectStatus.PREPARING_OUTLINE, ProjectStatus.WAITING_FOR_OUTLINE,
                          ProjectStatus.DRAFTING):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"报告正在生成中（当前状态: {project.status}），请先查询进度接口等待完成",
        )
    if project.status == ProjectStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"报告生成失败，错误原因: {project.error_message or '未知错误'}",
        )

    if not project.pdf_path:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="项目已完成但 PDF 路径为空，请联系管理员",
        )

    settings = get_settings()
    pdf_full_path = os.path.join(settings.OUTPUT_DIR, project.pdf_path)
    if not os.path.exists(pdf_full_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PDF 文件未找到（路径: {pdf_full_path}），可能已被清理",
        )

    file_size = os.path.getsize(pdf_full_path)
    download_url = f"{settings.PDF_DOWNLOAD_BASE_URL}/{project.pdf_path}"

    return DownloadResponse(
        project_id=project.id,
        topic=project.topic,
        download_url=download_url,
        filename=os.path.basename(project.pdf_path),
        file_size_bytes=file_size,
        report_ready=True,
    )


# ================================================================
# GET /api/v1/projects —— 获取当前用户的项目列表
# ================================================================

@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """
    获取当前用户的所有项目列表（按创建时间倒序）。
    """
    result = await db.execute(
        select(Project)
        .where(Project.owner_id == user.id)
        .order_by(Project.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    projects = result.scalars().all()
    return [ProjectResponse.model_validate(orm_to_dict(p)) for p in projects]


# ================================================================
# 🆕 GET /api/v1/projects/{project_id}/logs —— 时间轴实时日志
# ================================================================

@router.get("/{project_id}/logs", response_model=ProjectLogListResponse)
async def list_project_logs(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    after_sequence: int = Query(0, ge=0, description="仅返回 sequence > 此值的日志（增量拉取）"),
):
    """
    🖥️ **实时运行日志**：获取项目的业务级时间轴日志。

    前端右侧面板通过此 API 获取 Agent 后台执行的实时进度，
    渲染为终端控制台风格的时间轴 UI。

    支持增量拉取：
    - 前端记录 `lastSequence`，每次轮询时传 `after_sequence` 参数
    - 仅返回新日志条目，避免重复传输

    参数:
    - **after_sequence**: 增量拉取的起始序号（不含）
    """
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail=f"项目 {project_id} 不存在")

    # 查询日志（按 sequence 排序，支持增量拉取）
    log_query = (
        select(ProjectLog)
        .where(
            ProjectLog.project_id == project_id,
            ProjectLog.sequence > after_sequence,
        )
        .order_by(ProjectLog.sequence.asc())
    )
    log_result = await db.execute(log_query)
    logs = log_result.scalars().all()

    return ProjectLogListResponse(
        project_id=project.id,
        logs=[ProjectLogResponse.model_validate(orm_to_dict(l)) for l in logs],
        total_count=len(logs),
    )


# ================================================================
# DELETE /api/v1/projects/{project_id} —— 删除项目
# ================================================================

@router.delete("/{project_id}", response_model=MessageResponse)
async def delete_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    删除指定项目及其所有关联数据。

    清理范围：
    - 数据库：Project、Task、DocumentBlock、Document、ProjectLog
    - 磁盘：爬取数据缓存、PDF 报告、Markdown 报告
    """
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"项目 {project_id} 不存在",
        )
    if project.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该项目",
        )

    # ── 1. 删除关联子记录（手动级联，因 ORM relationship 未配置 cascade） ──
    await db.execute(delete(Task).where(Task.project_id == project_id))
    await db.execute(delete(DocumentBlock).where(DocumentBlock.project_id == project_id))
    await db.execute(delete(Document).where(Document.project_id == project_id))
    await db.execute(delete(ProjectLog).where(ProjectLog.project_id == project_id))
    # 记忆图级联清理（P4c：项目实体/洞察；全局实体保留）
    try:
        from app.rag.memory_extraction import delete_project_memories
        delete_project_memories(str(project_id))
    except Exception as e:
        logger.warning("项目记忆清理失败（忽略）: %s", e)

    # ── 2. 清理磁盘文件 ──────────────────────────────────────────
    settings = get_settings()

    # 爬取数据缓存
    crawled_path = get_crawled_data_path(str(project_id))
    if os.path.exists(crawled_path):
        os.remove(crawled_path)
        logger.info("已清理爬取数据缓存 | project=%s | path=%s", project_id, crawled_path)

    # 任务向量库 + BM25（三层知识库：任务库目录）
    import shutil
    for base in (settings.CHROMA_PERSIST_DIR, settings.BM25_PERSIST_DIR):
        vec_dir = os.path.join(base, str(project_id))
        if os.path.isdir(vec_dir):
            shutil.rmtree(vec_dir, ignore_errors=True)
            logger.info("已清理向量库目录 | project=%s | path=%s", project_id, vec_dir)

    # 上传文档目录 + 知识库图片目录
    for sub in ("uploads", "kb_images"):
        up_dir = os.path.join(settings.OUTPUT_DIR, "private", sub, str(project_id))
        if os.path.isdir(up_dir):
            shutil.rmtree(up_dir, ignore_errors=True)
            logger.info("已清理私有目录 | project=%s | path=%s", project_id, up_dir)

    # PDF 文件
    if project.pdf_path:
        pdf_full = os.path.join(settings.OUTPUT_DIR, project.pdf_path)
        if os.path.exists(pdf_full):
            os.remove(pdf_full)
            logger.info("已清理 PDF | project=%s | path=%s", project_id, pdf_full)

    # Markdown 文件
    if project.md_path:
        md_full = os.path.join(settings.OUTPUT_DIR, project.md_path)
        if os.path.exists(md_full):
            os.remove(md_full)
            logger.info("已清理 Markdown | project=%s | path=%s", project_id, md_full)

    # ── 3. 删除项目本身 ──────────────────────────────────────────
    await db.delete(project)
    await db.commit()

    log_state_transition(str(project_id), project.status.value, "(已删除)", "用户手动删除项目")
    logger.info("项目已删除 | project=%s | topic=%s", project_id, project.topic)

    return MessageResponse(detail=f"项目 '{project.topic}' 已删除")


# ================================================================
# 🆕 POST /api/v1/projects/{project_id}/assets —— 幻灯片图片暂存
# ================================================================

@router.post("/{project_id}/assets")
async def upload_slide_asset(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
):
    """
    🖼️ **幻灯片图片暂存 API**：接收用户在 Tiptap 编辑器中粘贴或上传的本地图片，
    保存至静态目录并返回公开访问 URL，供编辑器直接插入。

    返回格式：`{"url": "/api/v1/files/assets/{project_id}/{uuid_filename}"}`
    """
    settings = get_settings()
    asset_dir = os.path.join(settings.OUTPUT_DIR, "assets", str(project_id))
    os.makedirs(asset_dir, exist_ok=True)

    # 保留原扩展名，使用 UUID 避免文件名冲突
    file_ext = os.path.splitext(file.filename or "image.png")[1] or ".png"
    safe_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(asset_dir, safe_filename)

    # 将文件二进制内容写入磁盘
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    logger.info("幻灯片图片已保存 | project=%s | filename=%s | size=%d",
                project_id, safe_filename, len(content))

    # 返回给 Tiptap 编辑器直接插入的公开访问 URL
    public_url = f"/api/v1/files/assets/{project_id}/{safe_filename}"
    return {"url": public_url}


# ================================================================
# 🆕 POST /api/v1/projects/{project_id}/export-pdf —— 手动导出 PDF
# ================================================================

@router.post("/{project_id}/export-pdf", response_model=DownloadResponse)
async def export_manual_pdf(
    project_id: uuid.UUID,
    body: ExportPdfRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    📄 **手动导出 PDF**：前端完成 Tiptap 编辑后，提交最终 HTML 内容，
    后端调用 WeasyPrint 渲染真实分页 PDF 并返回下载链接。

    流程：
    1. 接收前端传来的合并后 HTML（每页由 .manual-pdf-page 包裹）
    2. 生成基于时间戳的 PDF 文件名
    3. 调用 render_custom_html_to_pdf 执行 WeasyPrint 渲染
    4. 更新数据库 project.pdf_path
    5. 返回 DownloadResponse（含 download_url）
    """
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")

    settings = get_settings()

    # 生成基于时间戳的 PDF 文件名
    pdf_filename = f"manual_report_{project_id}_{int(time.time())}.pdf"
    pdf_full_path = os.path.join(settings.OUTPUT_DIR, pdf_filename)

    # 调用 WeasyPrint 核心排版引擎
    from app.report.pdf_generator import render_custom_html_to_pdf
    try:
        render_custom_html_to_pdf(
            raw_html=body.html_content,
            topic=project.topic,
            output_pdf_path=pdf_full_path,
        )
    except Exception as e:
        logger.error("WeasyPrint 手动导出失败: %s", str(e))
        raise HTTPException(status_code=500, detail=f"PDF 渲染失败: {str(e)}")

    # 更新数据库，指向最新的手动导出 PDF 成果
    project.pdf_path = pdf_filename
    await db.commit()

    return DownloadResponse(
        project_id=project_id,
        topic=project.topic,
        download_url=f"{settings.PDF_DOWNLOAD_BASE_URL}/{pdf_filename}",
        filename=f"{project.topic}_终版报告.pdf",
        file_size_bytes=os.path.getsize(pdf_full_path),
        report_ready=True,
    )


# ================================================================
# POST /api/v1/projects/{project_id}/logo —— 上传项目 Logo
# ================================================================

@router.post("/{project_id}/logo")
async def upload_project_logo(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    上传项目 Logo 图片（PNG/JPG/WebP/SVG/GIF，最大 2MB）。

    保存到 outputs/logos/{project_id}/ 目录，
    更新项目的 logo_url 字段并通过 StaticFiles 公开访问。
    """
    ALLOWED_CONTENT_TYPES = {
        "image/png", "image/jpeg", "image/webp",
        "image/svg+xml", "image/gif",
    }
    MAX_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB

    # 验证项目存在
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"项目 {project_id} 不存在",
        )

    # 验证文件类型
    if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"不支持的文件类型 '{file.content_type}'，仅支持 PNG/JPG/WebP/SVG/GIF",
        )

    # 读取文件内容并验证大小
    content = await file.read()
    if len(content) > MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"文件过大 ({len(content)} bytes)，最大允许 2 MB",
        )

    # 保存到 outputs/logos/{project_id}/
    settings = get_settings()
    logo_dir = os.path.join(settings.OUTPUT_DIR, "logos", str(project_id))
    os.makedirs(logo_dir, exist_ok=True)

    file_ext = os.path.splitext(file.filename or "logo.png")[1] or ".png"
    safe_filename = f"logo{file_ext}"
    file_path = os.path.join(logo_dir, safe_filename)

    with open(file_path, "wb") as f:
        f.write(content)

    # 构建公开 URL：/api/v1/files/logos/{project_id}/logo.ext
    public_url = f"/api/v1/files/logos/{project_id}/{safe_filename}"

    # 更新数据库
    project.logo_url = public_url
    await db.commit()

    logger.info("Logo 已上传 | project=%s | url=%s", project_id, public_url)

    return {
        "project_id": str(project_id),
        "logo_url": public_url,
        "message": "Logo 已成功上传",
    }


# ================================================================
# 🆕 POST /api/v1/projects/{project_id}/search-images —— 图片搜索
# ================================================================

def _map_search_depth_to_max_results(search_depth: int) -> int:
    """将 search_depth (5-20) 映射为合理的图片搜索数量"""
    if search_depth <= 5:
        return 2
    elif search_depth <= 10:
        return 4
    elif search_depth <= 15:
        return 6
    else:
        return 8


@router.post("/{project_id}/search-images", response_model=ImageSearchResponse)
async def search_project_images(
    project_id: uuid.UUID,
    body: ImageSearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    🔍 **图片搜索 API**：使用 DuckDuckGo 搜索与查询相关的图片，
    将结果持久化到 project_images 表，返回搜索结果供前端 ImageGallery 展示。

    `search_depth` 控制搜索强度：浅度搜索返回较少结果，深度搜索返回较多结果。
    """
    # 验证项目存在
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"项目 {project_id} 不存在",
        )

    # 根据 search_depth 计算 max_results
    effective_max = _map_search_depth_to_max_results(body.search_depth)
    if body.max_results and body.max_results < effective_max:
        effective_max = body.max_results

    # 调用 DuckDuckGo 图片搜索
    try:
        from app.search.image_search import search_images
        results = search_images(body.query, max_results=effective_max)
    except Exception as e:
        logger.error("图片搜索失败 | query=%s | error=%s", body.query, str(e))
        raise HTTPException(
            status_code=500,
            detail=f"图片搜索失败: {str(e)}",
        )

    # 持久化搜索结果（支持 page_number 关联）
    # 如果请求中包含 page_number（从自动搜索调用），则关联到对应页码
    page_num: int | None = getattr(body, 'page_number', None)
    saved_images: list[ProjectImage] = []
    for r in results:
        img = ProjectImage(
            project_id=project_id,
            query=body.query,
            title=r.get("title", ""),
            image_url=r.get("image", ""),
            source_url=r.get("url", ""),
            thumbnail_url=r.get("image", ""),  # DuckDuckGo 返回相同 URL
            search_depth=body.search_depth,
            page_number=page_num,
        )
        db.add(img)
        saved_images.append(img)

    await db.commit()

    # Refresh 以获取 server_default 生成的 id / created_at
    for img in saved_images:
        await db.refresh(img)

    images_resp = [
        ImageResultResponse(
            id=img.id,
            query=img.query,
            title=img.title,
            image_url=img.image_url,
            source_url=img.source_url,
            search_depth=img.search_depth,
            page_number=img.page_number,
            created_at=img.created_at,
        )
        for img in saved_images
    ]

    logger.info(
        "图片搜索完成 | project=%s | query=%s | results=%d",
        project_id, body.query, len(images_resp),
    )

    return ImageSearchResponse(images=images_resp, total_count=len(images_resp))


# ================================================================
# 🆕 GET /api/v1/projects/{project_id}/images —— 获取项目图片库
# ================================================================

@router.get("/{project_id}/images", response_model=ProjectImagesResponse)
async def get_project_images(
    project_id: uuid.UUID,
    page_number: int | None = Query(None, ge=0, description="按页码筛选（可选）"),
    db: AsyncSession = Depends(get_db),
):
    """
    🖼️ **项目图片库 API**：返回该项目所有已搜索并保存的图片，
    按创建时间降序排列，供前端 ImageGallery 面板加载。
    支持通过 `?page_number=0` 筛选特定页的图片。
    """
    stmt = (
        select(ProjectImage)
        .where(ProjectImage.project_id == project_id)
    )
    if page_number is not None:
        stmt = stmt.where(ProjectImage.page_number == page_number)
    stmt = stmt.order_by(ProjectImage.created_at.desc())

    result = await db.execute(stmt)
    images = result.scalars().all()

    images_resp = []
    for img in images:
        item = ImageResultResponse(
            id=img.id,
            query=img.query,
            title=img.title,
            image_url=img.image_url,
            source_url=img.source_url,
            search_depth=img.search_depth,
            page_number=img.page_number,
            created_at=img.created_at,
        )
        # ── 知识库图片字段（P1） ──
        item.source = getattr(img, "source", "search") or "search"
        item.status = getattr(img, "status", None)
        item.analysis_text = getattr(img, "analysis_text", None)
        item.thumbnail_url = getattr(img, "thumbnail_url", None)
        item.file_path = getattr(img, "file_path", None)
        raw_tags = getattr(img, "tags", None)
        if raw_tags:
            try:
                item.tags = json.loads(raw_tags) if raw_tags.startswith("[") else [
                    t.strip() for t in raw_tags.split(",") if t.strip()
                ]
            except (json.JSONDecodeError, AttributeError):
                item.tags = []
        images_resp.append(item)

    return ProjectImagesResponse(
        project_id=project_id,
        images=images_resp,
        total_count=len(images_resp),
    )


# ================================================================
# 🆕 DELETE /api/v1/projects/{project_id}/images/{image_id} —— 删除图片
# ================================================================

@router.delete("/{project_id}/images/{image_id}", response_model=MessageResponse)
async def delete_project_image(
    project_id: uuid.UUID,
    image_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    🗑️ **删除图片库条目**：从 project_images 表中移除指定图片记录。
    """
    result = await db.execute(
        select(ProjectImage).where(
            ProjectImage.id == image_id,
            ProjectImage.project_id == project_id,
        )
    )
    img = result.scalar_one_or_none()
    if img is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"图片 {image_id} 不存在或不属于该项目",
        )

    await db.delete(img)
    await db.commit()

    logger.info("图片已删除 | project=%s | image_id=%s", project_id, image_id)

    return MessageResponse(detail=f"图片 {image_id} 已删除")


# ================================================================
# POST /api/v1/projects/{project_id}/cancel —— 取消 v1 报告流水线
# ================================================================

@router.post("/{project_id}/cancel")
async def cancel_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """取消进行中的报告流水线：撤销 Celery 任务并置为 failed（原因=用户取消）。"""
    from app.core.celery_ops import revoke_active_tasks_for

    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail=f"项目 {project_id} 不存在")
    if project.owner_id != user.id:
        raise HTTPException(status_code=403, detail="无权访问该项目")
    if project.status in (ProjectStatus.COMPLETED, ProjectStatus.FAILED):
        raise HTTPException(
            status_code=409,
            detail=f"项目已处于 {project.status.value} 状态，无法取消",
        )

    revoke_active_tasks_for(str(project_id))

    project.status = ProjectStatus.FAILED
    project.error_message = "用户取消"
    await db.commit()
    return {"project_id": str(project_id), "status": "cancelled", "message": "项目流水线已取消"}


# ================================================================
# Canvas 编辑器持久化 —— POST/GET /projects/{id}/canvas
# ================================================================

@router.post("/{project_id}/canvas")
async def save_project_canvas(
    project_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """保存 Canvas 编辑器数据（Konva slides JSON）。修复「编辑永不保存、刷新即丢」。"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail=f"项目 {project_id} 不存在")
    if project.owner_id != user.id:
        raise HTTPException(status_code=403, detail="无权访问该项目")

    slides = body.get("slides")
    if slides is None:
        raise HTTPException(status_code=422, detail="缺少 slides 字段")
    project.canvas_data = json.dumps(slides, ensure_ascii=False)
    await db.commit()
    return {"project_id": str(project_id), "saved": True, "updated_at": project.updated_at.isoformat() if project.updated_at else None}


@router.get("/{project_id}/canvas")
async def get_project_canvas(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """获取 Canvas 编辑器持久化数据。"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail=f"项目 {project_id} 不存在")
    if project.owner_id != user.id:
        raise HTTPException(status_code=403, detail="无权访问该项目")
    try:
        slides = json.loads(project.canvas_data) if project.canvas_data else {}
    except json.JSONDecodeError:
        slides = {}
    return {"project_id": str(project_id), "slides": slides, "saved_at": project.updated_at.isoformat() if project.updated_at else None}


# ================================================================
# 🆕 POST /api/v1/projects/{project_id}/kb-images —— 图片知识库入库
# ================================================================

@router.post("/{project_id}/kb-images")
async def upload_kb_images(
    project_id: uuid.UUID,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    🖼️ **图片知识库入库 API**：接收本地图片（PNG/JPG/JPEG/WebP/GIF），
    保存至私有目录后触发 Celery 异步执行 MiniMax VL 分析入库。

    与 /assets（编辑器素材，不分析）的区别：
    - 本端点保存到 outputs/private/kb_images/（不公开挂载）
    - 写 project_images 行（source='upload'），返回 image_id 与 status=pending
    - Celery knowledge.analyze_image 完成分析后 status=ready

    前端轮询 GET /images 或刷新列表查看分析状态。
    """
    settings = get_settings()
    IMG_EXTS = {"png", "jpg", "jpeg", "webp", "gif", "bmp"}
    max_bytes = settings.KB_IMAGE_MAX_MB * 1024 * 1024
    max_count = settings.KB_IMAGE_MAX_PER_BATCH * 2

    # ── 1. 验证项目存在 + 归属 ─────────────────────────────
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail=f"项目 {project_id} 不存在")
    if project.owner_id != user.id:
        raise HTTPException(status_code=403, detail="无权访问该项目")

    if not files or len(files) > max_count:
        raise HTTPException(
            status_code=422,
            detail=f"一次最多上传 {max_count} 张图片",
        )

    # ── 2. 逐张校验 + 落盘 + 入库 ──────────────────────────
    from app.repositories import ProjectRepo
    repo = ProjectRepo()
    saved: list[dict] = []
    errors: list[str] = []

    for file in files:
        raw_name = (file.filename or "").strip()
        safe_name = os.path.basename(raw_name)
        ext = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else ""
        if ext not in IMG_EXTS:
            errors.append(f"{safe_name}: 不支持的图片格式 .{ext}")
            continue

        content = await file.read()
        if len(content) > max_bytes:
            errors.append(f"{safe_name}: 超过大小上限 {settings.KB_IMAGE_MAX_MB}MB")
            continue
        if not content:
            errors.append(f"{safe_name}: 空文件")
            continue

        img_dir = os.path.join(settings.OUTPUT_DIR, "private", "kb_images", str(project_id))
        os.makedirs(img_dir, exist_ok=True)
        stored_name = f"{uuid.uuid4().hex}.{ext}"
        file_path = os.path.join(img_dir, stored_name)
        with open(file_path, "wb") as f:
            f.write(content)

        img = repo.create_kb_image(
            project_id=str(project_id),
            title=safe_name,
            file_path=file_path,
            query="",
            source="upload",
        )
        saved.append({
            "image_id": str(img.id),
            "title": safe_name,
            "status": img.status,
        })
        logger.info("图片已入库待分析 | project=%s | image=%s | %s",
                    project_id, img.id, safe_name)

    # ── 3. 触发异步 VL 分析（逐个投递，互不阻塞） ────────────
    from app.tasks.knowledge_tasks import analyze_image
    for item in saved:
        try:
            analyze_image.delay(item["image_id"])
        except Exception as e:
            logger.warning("图片分析任务投递失败 | image=%s | %s", item["image_id"], e)

    return {
        "project_id": str(project_id),
        "saved": saved,
        "errors": errors,
        "message": f"已接收 {len(saved)} 张图片进入分析，{len(errors)} 张失败",
    }


# ================================================================
# 🆕 GET /api/v1/projects/{project_id}/similar —— 相似任务判别
# ================================================================

@router.get("/{project_id}/similar")
async def get_similar_projects(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    🔗 **相似任务判别 API**（L1 领域知识层核心）：
    计算当前任务与历史任务的相似度（主题向量 0.6 + 领域标签 0.3 + 模板 0.1），
    返回可借用的相似任务及其经验包摘要。

    相似度阈值与 top-k 由配置 SIMILARITY_BORROW_THRESHOLD / SIMILARITY_TOP_K 控制。
    """
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail=f"项目 {project_id} 不存在")
    if project.owner_id != user.id:
        raise HTTPException(status_code=403, detail="无权访问该项目")

    from app.rag.task_similarity import find_similar_projects, retrieve_experiences
    settings = get_settings()
    try:
        similar = find_similar_projects(
            str(project_id),
            top_k=settings.SIMILARITY_TOP_K,
            min_similarity=settings.SIMILARITY_BORROW_THRESHOLD,
        )
    except Exception as e:
        logger.error("相似任务计算失败 | project=%s | %s", project_id, e)
        raise HTTPException(status_code=500, detail=f"相似任务计算失败: {str(e)}")

    return {
        "project_id": str(project_id),
        "topic": project.topic,
        "threshold": settings.SIMILARITY_BORROW_THRESHOLD,
        "similar_projects": similar,
        "borrowable_experience": retrieve_experiences(str(project_id)),
    }
