"""
============================================================
Pydantic V2 请求/响应模型
—— 用于 API 路由的校验和文档生成
    新增状态机交互相关的 Schema：大纲审批、DocumentBlock 块级响应、SSE 事件
============================================================
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, ConfigDict, field_validator


# ════════════════════════════════════════════════════════════════
# 枚举字面量 —— 编译期契约，与 models/task.py 的 TaskType/TaskStatus
# 以及前端 types/api.ts 的 TaskTypeEnum/TaskStatusEnum 保持一致
# ════════════════════════════════════════════════════════════════

TaskTypeLiteral = Literal[
    "search",
    "build_knowledge_base",
    "generate_outline",
    "write_section",
    "build_report",
    "generate_pdf",
    "image_generation",
]

TaskStatusLiteral = Literal[
    "pending",
    "processing",
    "completed",
    "failed",
]


# ================================================================
# 通用消息响应
# ================================================================

class MessageResponse(BaseModel):
    """通用消息响应"""
    detail: str = Field(..., description="操作结果消息")


class ErrorResponse(BaseModel):
    """标准错误响应"""
    detail: str = Field(..., description="错误详情")
    error_code: str | None = Field(None, description="错误码")


# ================================================================
# 项目 (Project) Schemas
# ================================================================

class ProjectCreateRequest(BaseModel):
    """创建项目的请求体"""
    topic: str = Field(
        ...,
        min_length=2,
        max_length=500,
        description="产品分析主题，例如：'智能手表产品分析'",
        examples=["智能手表产品分析"],
    )

    @field_validator("topic")
    @classmethod
    def _strip_topic(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("主题不能为空或过短（去除首尾空格后至少 2 个字符）")
        return v
    template_type: str = Field(
        default="product",
        description="模板类型：product（产品预研）或 design（工业设计推演）",
        examples=["product", "design"],
    )
    search_depth: int = Field(
        default=10,
        ge=5,
        le=20,
        description="搜索强度: 5=快速, 10=标准, 15=深度, 20=极致",
        examples=[5, 10, 15, 20],
    )
    images_per_page: int = Field(
        default=2,
        ge=0,
        le=5,
        description="每页自动搜索图片数量: 0=关闭, 默认 2",
        examples=[0, 1, 2, 3, 5],
    )


class ProjectResponse(BaseModel):
    """项目响应（列表/详情）"""
    id: uuid.UUID = Field(..., description="项目 UUID")
    topic: str = Field(..., description="分析主题")
    status: str = Field(..., description="项目状态")
    template_type: str = Field(default="product", description="模板类型：product 或 design")
    outline_content: str | None = Field(None, description="暂存的大纲 Markdown")
    pdf_path: str | None = Field(None, description="PDF 文件路径")
    md_path: str | None = Field(None, description="Markdown 文件路径")
    error_message: str | None = Field(None, description="错误信息")
    search_depth: int = Field(default=10, description="搜索强度")
    logo_url: str | None = Field(None, description="Logo 图片 URL")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime | None = Field(None, description="更新时间")

    model_config = ConfigDict(from_attributes=True)


class ProjectCreateResponse(BaseModel):
    """创建项目后的响应（含任务跟踪信息）"""
    project: ProjectResponse = Field(..., description="项目信息")
    celery_task_id: str = Field(..., description="Celery 根任务 ID（可用于后续查询）")
    message: str = Field(default="项目已创建，异步任务已提交", description="提示消息")


# ================================================================
# 🎯 资料预审核 (Source Review) Schemas —— 交互节点1
# ================================================================

class SourceItem(BaseModel):
    """单个搜索结果/资料来源"""
    index: int = Field(..., description="资料序号（从1开始）")
    title: str = Field(..., description="资料标题或网页标题")
    url: str = Field(..., description="资料 URL")
    snippet: str = Field("", description="内容摘要（前200字）")
    selected: bool = Field(default=True, description="是否被选中（前端可切换）")


class SourceReviewRequest(BaseModel):
    """
    用户审核资料后的提交请求体。
    用户在资料审核面板中可以取消勾选低质量资料，
    或手动添加新的参考 URL，确认后提交。
    """
    selected_urls: list[str] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="用户最终选择的资料 URL 列表（剔除低质资料后的结果）",
    )
    additional_notes: str | None = Field(
        None,
        max_length=2000,
        description="用户的补充说明（如：'重点关注官网数据，忽略论坛帖子'）",
    )


class SourceReviewResponse(BaseModel):
    """资料审核确认后的响应"""
    project_id: uuid.UUID = Field(..., description="项目 UUID")
    new_status: str = Field(..., description="项目新状态（应为 'preparing_outline'）")
    message: str = Field(..., description="提示消息")
    kept_sources: int = Field(..., description="保留的资料数量")
    celery_task_id: str | None = Field(None, description="已触发的大纲生成 Celery 任务 ID")


class SourcesListResponse(BaseModel):
    """资料列表响应 — 前端审核面板的数据源"""
    project_id: uuid.UUID = Field(..., description="项目 UUID")
    topic: str = Field(..., description="分析主题")
    sources: list[SourceItem] = Field(default_factory=list, description="搜索结果/资料来源列表")
    total_count: int = Field(0, description="资料总数")


# ================================================================
# 大纲审批 (Outline Approval) Schemas
# ================================================================

class OutlineApproveRequest(BaseModel):
    """
    用户确认/修改大纲的请求体。
    用户可以在前端 Tiptap 编辑器中修改大纲后提交，
    或者直接确认 LLM 生成的原始大纲。
    """
    outline: str = Field(
        ...,
        min_length=10,
        max_length=50000,
        description="最终确认的大纲 Markdown 内容（用户可能已在前端修改）",
        examples=[
            "# 智能手表产品深度分析\n"
            "## 1. 产品概述\n"
            "## 2. 市场定位\n"
            "## 3. 竞品对比\n"
            "## 4. 技术特性\n"
            "## 5. 用户体验\n"
            "## 6. 风险与挑战\n"
        ],
    )


class OutlineApproveResponse(BaseModel):
    """大纲确认后的响应"""
    project_id: uuid.UUID = Field(..., description="项目 UUID")
    new_status: str = Field(..., description="项目新状态（应为 'drafting'）")
    message: str = Field(..., description="提示消息")
    sections_count: int = Field(..., description="从大纲解析出的章节数量")
    celery_task_id: str | None = Field(None, description="已触发的草稿生成根任务 ID")


# ================================================================
# 任务 (Task) Schemas
# ================================================================

class TaskResponse(BaseModel):
    """单个任务步骤的响应"""
    id: uuid.UUID = Field(..., description="任务 UUID")
    task_type: TaskTypeLiteral = Field(..., description="任务类型")
    status: TaskStatusLiteral = Field(..., description="任务状态")
    sequence_order: int = Field(..., description="执行顺序")
    section_title: str | None = Field(None, description="关联章节标题")
    retry_count: int = Field(0, description="已重试次数")
    error_message: str | None = Field(None, description="错误信息")
    started_at: datetime | None = Field(None, description="开始时间")
    completed_at: datetime | None = Field(None, description="完成时间")
    created_at: datetime = Field(..., description="创建时间")

    model_config = ConfigDict(from_attributes=True)


class ProjectStatusResponse(BaseModel):
    """项目进度查询响应"""
    project_id: uuid.UUID = Field(..., description="项目 UUID")
    topic: str = Field(..., description="分析主题")
    project_status: str = Field(..., description="项目整体状态")
    template_type: str = Field(default="product", description="模板类型：product 或 design")
    outline_content: str | None = Field(None, description="暂存大纲内容（WAITING_OUTLINE_APPROVAL 时有值）")
    pdf_path: str | None = Field(None, description="PDF 文件相对路径（完成后有值）")
    search_depth: int = Field(default=10, description="搜索强度")
    images_per_page: int = Field(default=2, description="每页自动搜索图片数量")
    logo_url: str | None = Field(None, description="Logo 图片 URL")
    current_step: dict[str, Any] | None = Field(
        None,
        description="🆕 当前执行步骤（step/message/icon/level），从前端实时日志时间轴推导",
    )
    progress: dict[str, Any] = Field(
        default_factory=lambda: {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "percentage": 0.0,
        },
        description="进度概览",
    )
    tasks: list[TaskResponse] = Field(default_factory=list, description="所有任务步骤详情")

    model_config = ConfigDict(from_attributes=True)


# ================================================================
# 文档块 (DocumentBlock) Schemas
# ================================================================

class DocumentBlockResponse(BaseModel):
    """文档块响应——面向 Tiptap 块级编辑器"""
    id: uuid.UUID = Field(..., description="文档块 UUID")
    section_title: str = Field(..., description="归属的章节标题")
    order_index: int = Field(..., description="全局排序序号")
    content: str = Field(..., description="块内容（Markdown）")
    citations: str | None = Field(None, description="引用映射（JSON 格式）")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime | None = Field(None, description="更新时间")

    model_config = ConfigDict(from_attributes=True)


class DocumentBlockListResponse(BaseModel):
    """项目所有文档块列表"""
    project_id: uuid.UUID = Field(..., description="项目 UUID")
    blocks: list[DocumentBlockResponse] = Field(
        default_factory=list,
        description="按 order_index 排序的文档块列表",
    )


# ================================================================
# 文档 (Document) Schemas
# ================================================================

class DocumentResponse(BaseModel):
    """章节文档响应"""
    id: uuid.UUID = Field(..., description="文档 UUID")
    section_title: str = Field(..., description="章节标题")
    section_order: int = Field(..., description="章节顺序")
    version: int = Field(1, description="版本号")
    content: str = Field(..., description="章节内容（Markdown）")
    source_urls: str | None = Field(None, description="参考来源 URL 列表（JSON）")
    created_at: datetime = Field(..., description="创建时间")

    model_config = ConfigDict(from_attributes=True)


# ================================================================
# SSE (Server-Sent Events) Schemas
# ================================================================

class SSEDraftEvent(BaseModel):
    """
    SSE 草稿流事件负载。
    当后端逐块完成撰写时，通过 SSE 推送给前端，
    前端 Tiptap 编辑器可实时插入/追加内容块。
    """
    event: str = Field(
        ...,
        description="事件类型：section_start | section_chunk | section_complete | draft_complete | error",
    )
    project_id: str = Field(..., description="项目 ID")
    section_title: str | None = Field(None, description="当前处理的章节标题")
    block: DocumentBlockResponse | None = Field(None, description="已完成的文档块")
    error: str | None = Field(None, description="错误信息")


# ================================================================
# 编辑器 (Editor) Schemas
# ================================================================

class EditorReviseRequest(BaseModel):
    """编辑器 AI 改写请求"""
    selected_text: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="用户在编辑器中选中的文本内容",
    )
    instruction: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="改写指令，例如：扩写、精简、润色、正式化等",
        examples=["扩写", "精简", "润色", "使表达更正式"],
    )
    context: str | None = Field(
        None,
        max_length=20000,
        description="可选的上下文信息（如段落前后文），帮助 LLM 理解语境",
    )


class EditorReviseResponse(BaseModel):
    """编辑器 AI 改写响应"""
    revised_text: str = Field(
        ...,
        description="LLM 改写后的文本",
    )


# ================================================================
# 报告内容 (Report Content) Schema
# ================================================================

class ReportContentResponse(BaseModel):
    """报告全文内容响应"""
    project_id: uuid.UUID = Field(..., description="项目 UUID")
    topic: str = Field(..., description="分析主题")
    sections: list[SectionContent] = Field(
        default_factory=list,
        description="按顺序排列的章节内容列表",
    )


class SectionContent(BaseModel):
    """单个章节内容"""
    title: str = Field(..., description="章节标题")
    order: int = Field(..., description="章节顺序")
    content: str = Field(..., description="Markdown 正文")
    citations: dict[str, str] = Field(
        default_factory=dict,
        description="引用映射 {序号: URL}",
    )


# ================================================================
# 下载 Schemas
# ================================================================

class DownloadResponse(BaseModel):
    """下载链接响应"""
    project_id: uuid.UUID = Field(..., description="项目 UUID")
    topic: str = Field(..., description="分析主题")
    download_url: str = Field(..., description="PDF 下载链接")
    filename: str = Field(..., description="推荐的文件名")
    file_size_bytes: int | None = Field(None, description="文件大小（字节）")
    report_ready: bool = Field(True, description="报告是否已就绪")


# ================================================================
# 🆕 项目时间轴日志 (ProjectLog) Schemas
# ================================================================

class ProjectLogResponse(BaseModel):
    """单条项目时间轴日志"""
    id: uuid.UUID = Field(..., description="日志 UUID")
    sequence: int = Field(..., description="序号")
    level: str = Field(..., description="日志级别: info | warn | error | milestone")
    step: str = Field(..., description="步骤标识")
    message: str = Field(..., description="人类可读日志消息")
    icon: str | None = Field(None, description="emoji 图标")
    created_at: datetime = Field(..., description="创建时间")

    model_config = ConfigDict(from_attributes=True)


class ProjectLogListResponse(BaseModel):
    """项目时间轴日志列表"""
    project_id: uuid.UUID = Field(..., description="项目 UUID")
    logs: list[ProjectLogResponse] = Field(
        default_factory=list,
        description="按 sequence 排序的日志列表",
    )
    total_count: int = Field(0, description="日志总数")


# ================================================================
# 🆕 Task 2: 核心 API 追加契约
# ================================================================

class EditorChatMessage(BaseModel):
    """侧边栏聊天历史消息"""
    role: Literal["user", "assistant"] = Field(..., description="发送方角色")
    content: str = Field(..., description="消息内容")


class EditorChatRequest(BaseModel):
    """侧边栏大模型对话请求"""
    project_id: uuid.UUID | None = Field(
        default=None,
        description="项目 UUID（可为空：仅检索全局/领域知识）",
    )
    chat_mode: Literal["chat", "work"] = Field(
        default="work",
        description="对话模式：chat (自由闲聊) | work (专业工作型)",
    )
    message: str = Field(..., description="当前用户的提问")
    selected_text: str | None = Field(None, description="编辑器中选中的文本上下文")
    history: list[EditorChatMessage] = Field(default_factory=list, description="历史对话记录")


class ExportPdfRequest(BaseModel):
    """前端发起 HTML/Markdown 导出 PDF 请求"""
    html_content: str = Field(..., description="前端 Tiptap 编辑器输出的完整内容")


class UploadDocsResponse(BaseModel):
    """本地文件上传响应"""
    project_id: uuid.UUID = Field(..., description="项目 UUID")
    chunk_count: int = Field(..., description="成功解析并入库的文本切片数量")
    message: str = Field(..., description="操作结果说明")


# ================================================================
# 🆕 图片搜索 (Image Search) Schemas
# ================================================================

class ImageSearchRequest(BaseModel):
    """图片搜索请求"""
    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="图片搜索关键词",
        examples=["iPhone 产品设计"],
    )
    max_results: int = Field(
        default=3,
        ge=1,
        le=20,
        description="期望返回的图片数量（实际取决于搜索引擎）",
    )
    search_depth: int = Field(
        default=10,
        ge=5,
        le=20,
        description="搜索强度: 5=快速, 10=标准, 15=深度, 20=极致",
    )
    page_number: int | None = Field(
        default=None,
        ge=0,
        description="关联的幻灯片页码（自动搜索时由后端传入），手动搜索不填",
    )


class ImageResultResponse(BaseModel):
    """单条图片搜索结果（含知识库分析字段，P1 扩展）"""
    id: uuid.UUID = Field(..., description="图片记录 UUID")
    query: str = Field(..., description="搜索关键词")
    title: str = Field(..., description="图片标题")
    image_url: str = Field(..., description="图片直链 URL")
    source_url: str | None = Field(None, description="来源网页 URL")
    search_depth: int = Field(default=10, description="搜索强度")
    page_number: int | None = Field(None, description="关联的幻灯片页码（0-based），手动搜索时为 null")
    created_at: datetime = Field(..., description="创建时间")
    # ── 知识库图片（P1） ──
    source: str = Field(default="search", description="图片来源: search / upload")
    status: str | None = Field(None, description="VL 分析状态: pending/analyzing/ready/failed")
    analysis_text: str | None = Field(None, description="MiniMax VL 结构化分析 JSON")
    tags: list[str] = Field(default_factory=list, description="分析标签")
    thumbnail_url: str | None = Field(None, description="缩略图 URL")
    file_path: str | None = Field(None, description="本地文件相对路径")

    model_config = ConfigDict(from_attributes=True)


class ImageSearchResponse(BaseModel):
    """图片搜索响应"""
    images: list[ImageResultResponse] = Field(
        default_factory=list,
        description="本次搜索返回的图片列表",
    )
    total_count: int = Field(0, description="本次搜索返回的图片总数")


class ProjectImagesResponse(BaseModel):
    """项目图片库响应"""
    project_id: uuid.UUID = Field(..., description="项目 UUID")
    images: list[ImageResultResponse] = Field(
        default_factory=list,
        description="该项目所有已搜索保存的图片",
    )
    total_count: int = Field(0, description="图片总数")

# ────────────────────────────────────────────────────────────────
# AI Product Studio Schemas（agent-platform 集成）
# ────────────────────────────────────────────────────────────────
from app.schemas.studio import (
    ExportPdfResponse,
    KnowledgeDocumentResponse,
    PresentationUpdateRequest,
    ProductAssetResponse,
    ProductCreateRequest,
    ProductCreateResponse,
    ProductImageResult,
    ProductImageSearchRequest,
    ProductImageSearchResponse,
    ProductListResponse,
)
