"""
============================================================
AI Product Studio API Schemas
—— POST /api/product/create 等端点的请求/响应契约
============================================================
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ProductCreateRequest(BaseModel):
    """创建产品（触发 Research → Product → Design → Presentation 流水线）。"""

    idea: str = Field(..., min_length=1, max_length=500, description="产品想法")


class ProductCreateResponse(BaseModel):
    """创建成功 —— 异步流水线立即返回，前端轮询 GET /api/product/{id}。"""

    product_id: str
    idea: str
    status: str


class ProductAssetResponse(BaseModel):
    """产品资产包查询响应（对齐 POST /api/product/create 的目标响应形状）。"""

    product_id: str
    idea: str
    status: str
    error_message: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    # ── 六节点结构化资产（未完成时为 None） ──
    requirement: dict[str, Any] | None = None
    research: dict[str, Any] | None = None
    competitor_analysis: dict[str, Any] | None = None
    strategy: dict[str, Any] | None = None
    design: dict[str, Any] | None = None
    presentation: dict[str, Any] | None = None
    ppt_design: dict[str, Any] | None = None
    document: dict[str, Any] | None = None
    node_models: dict[str, str] | None = None
    # ── P5: 质量层 ──
    critic_score: int | None = None
    gate_report: dict[str, Any] | None = None
    # ── 进度与失败记录 ──
    node_status: dict[str, str] = Field(default_factory=dict)
    errors: dict[str, str] = Field(default_factory=dict)


class ProductListResponse(BaseModel):
    """产品列表项（轻量）。"""

    product_id: str
    idea: str
    status: str
    created_at: str | None = None


class ExportPdfResponse(BaseModel):
    """PPT 风格 PDF 导出结果。"""

    product_id: str
    pdf_url: str
    message: str


class KnowledgeDocumentResponse(BaseModel):
    """知识库文档条目（全局聚合，只读）。"""

    document_id: str
    project_id: str
    project_topic: str
    section_title: str
    section_order: int = 0
    updated_at: str | None = None


class PresentationUpdateRequest(BaseModel):
    """演示编辑器保存：回写 Presentation DSL。"""

    presentation: dict[str, Any] = Field(..., description="完整 Presentation DSL")


class ProductImageSearchRequest(BaseModel):
    """编辑器素材搜索（无状态，DuckDuckGo）。"""

    query: str = Field(..., min_length=1)
    max_results: int = Field(default=12, ge=1, le=20)
    search_depth: int = Field(default=5, ge=5, le=20)


class ProductImageResult(BaseModel):
    """搜索结果条目（不持久化，临时 id）。"""

    id: str
    query: str
    title: str
    image_url: str
    source_url: str | None = None


class ProductImageSearchResponse(BaseModel):
    """编辑器素材搜索结果。"""

    images: list[ProductImageResult]
    total_count: int
