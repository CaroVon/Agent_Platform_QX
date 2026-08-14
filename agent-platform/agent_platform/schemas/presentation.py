"""
演示生成 —— Presentation Agent 的结构化输出

Slide JSON Schema 设计原则（对齐"AI 生成内容结构，前端控制视觉"）:
  - AI 生成: 内容结构、layout_type（版式类型）、visual_metadata（视觉层级提示）
  - 前端控制: 字体、间距、组件样式（由 SlideRenderer 统一实现）
  - 严禁 LLM 生成 HTML / CSS

Presentation Agent 输出契约（对齐产品需求）:
  {
    "slides": [],
    "sections": []
  }
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SlideBlockType = Literal["title", "subtitle", "text", "bullets", "metric", "quote", "table", "image"]
SlideLayoutType = Literal[
    "cover",
    "section_header",
    "two_column",
    "bullets",
    "timeline",
    "matrix",
    "image_hero",
    "closing",
    "default",
]


class SlideBlock(BaseModel):
    """幻灯片内的单个内容块。"""

    id: str = Field(description="块 ID（幻灯片内唯一，如 b1）")
    block_type: SlideBlockType = Field(default="text", description="内容块类型")
    content: str = Field(default="", description="块内容（纯文本/Markdown，无 HTML）")
    emphasis: Literal["low", "normal", "high"] = Field(
        default="normal", description="视觉强调层级（前端据此放大/着色）"
    )
    meta: dict = Field(default_factory=dict, description="附加结构化数据（表格行、指标数值等）")


class Slide(BaseModel):
    """单页幻灯片。"""

    id: str = Field(description="幻灯片 ID（如 s1）")
    title: str = Field(description="页面标题")
    subtitle: str | None = Field(default=None, description="副标题")
    layout_type: SlideLayoutType = Field(default="default", description="版式类型（前端据此选择渲染模板）")
    blocks: list[SlideBlock] = Field(default_factory=list, description="内容块列表")
    visual_metadata: dict = Field(
        default_factory=dict,
        description="视觉层级提示（如 {'hero': 'title', 'accent_color': 'violet'}），由前端解读",
    )


class DeckSection(BaseModel):
    """演示章节（章节间导航与目录）。"""

    title: str = Field(description="章节标题（如：市场分析）")
    slide_ids: list[str] = Field(default_factory=list, description="该章节包含的幻灯片 ID")


class SlideDeck(BaseModel):
    """Presentation Agent 完整输出 —— Slide JSON Schema 根对象。"""

    topic: str = Field(description="演示主题")
    slides: list[Slide] = Field(default_factory=list)
    sections: list[DeckSection] = Field(default_factory=list)
