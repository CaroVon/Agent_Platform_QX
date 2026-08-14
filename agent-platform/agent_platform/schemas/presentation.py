"""
============================================================
Presentation DSL —— 视觉叙事层契约（P2）
============================================================

职责边界（layout.md 第 3 步）:
  - Presentation Agent 只输出「视觉语义决策」: 页型 / 布局选择 / 组件类型 /
    信息层级 / 图表选择 —— 绝不输出 HTML/CSS/像素
  - 视觉一致性由 Layout Library + Component Library + Renderer 保证

结构:
  Presentation
    ├── theme         主题 tokens（palette / font_scale）
    └── pages         页面列表
          └── Page    type(语义页型) + layout(布局枚举) + title/subtitle/insight
              └── components  Component(type + data + emphasis)
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ══════════════════════════════════════════════════════════
# 组件层 —— Renderer 只需处理这 9 种有限组件
# ══════════════════════════════════════════════════════════

ComponentType = Literal[
    "metric", "text", "chart", "table", "card", "timeline", "matrix", "quote", "image",
]

# ══════════════════════════════════════════════════════════
# 页面层 —— 语义页型 + 布局枚举
# ══════════════════════════════════════════════════════════

PageType = Literal[
    "cover",
    "executive_summary",
    "market_overview",
    "competitor_matrix",
    "user_persona",
    "user_journey",
    "feature_priority",
    "product_architecture",
    "roadmap",
    "conclusion",
]

LayoutId = Literal[
    "cover", "summary", "market", "matrix", "persona",
    "journey", "features", "architecture", "roadmap", "closing",
]


class Theme(BaseModel):
    """主题 tokens —— 品牌视觉规范的唯一来源（渲染层解读）。"""

    id: str = Field(default="default", description="主题 ID")
    name: str = Field(default="默认主题", description="主题名")
    palette: dict[str, str] = Field(
        default_factory=lambda: {
            "bg": "#f8fafc",
            "surface": "#ffffff",
            "primary": "#4f46e5",
            "accent": "#6366f1",
            "text": "#0f172a",
            "muted": "#64748b",
        },
        description="色彩 tokens（语义键，前端映射为 CSS 变量）",
    )
    font_scale: float = Field(default=1.0, ge=0.8, le=1.3, description="字号缩放系数")


class Component(BaseModel):
    """页面组件 —— 纯数据 + 枚举化视觉参数。"""

    id: str = Field(description="页面内唯一 ID")
    type: ComponentType
    data: dict = Field(default_factory=dict, description="组件数据（结构随 type 而定）")
    emphasis: Literal["low", "normal", "high"] = Field(
        default="normal", description="视觉强调层级（渲染层据此放大/着色）"
    )


class Page(BaseModel):
    """单个语义页 —— 布局只能从 Layout Library 枚举选择。"""

    id: str = Field(description="页面 ID（如 p1）")
    type: PageType = Field(description="语义页型")
    layout: LayoutId = Field(description="布局（Layout Library 枚举）")
    title: str = Field(description="页面标题")
    subtitle: str | None = Field(default=None, description="副标题")
    insight: str | None = Field(
        default=None, description="一句话结论（该页唯一核心信息，one slide = one message）"
    )
    components: list[Component] = Field(default_factory=list)


class Presentation(BaseModel):
    """Presentation DSL 根对象。"""

    title: str = Field(description="演示主题")
    theme: Theme = Field(default_factory=Theme)
    pages: list[Page] = Field(default_factory=list)


# ══════════════════════════════════════════════════════════
# Layout Library —— 10 个固定布局（模型只选，不造）
# ══════════════════════════════════════════════════════════

LAYOUT_LIBRARY: dict[str, dict] = {
    "cover": {
        "name": "封面",
        "page_types": ["cover"],
        "grid": "全屏居中：标题 / 副标题 / 底部来源",
        "components": ["text", "metric", "image"],
    },
    "summary": {
        "name": "执行摘要",
        "page_types": ["executive_summary"],
        "grid": "标题 / insight 结论条 / 2-3 个 metric 卡",
        "components": ["metric", "text", "card"],
    },
    "market": {
        "name": "市场概览",
        "page_types": ["market_overview"],
        "grid": "标题 / insight / 左侧要点列表 + 右侧 chart 或 metric",
        "components": ["chart", "metric", "text", "table"],
    },
    "matrix": {
        "name": "竞品矩阵",
        "page_types": ["competitor_matrix"],
        "grid": "标题 / 一句话结论 / 象限图 + 关键洞察双栏 / 底部来源",
        "components": ["matrix", "chart", "table", "card"],
    },
    "persona": {
        "name": "用户画像",
        "page_types": ["user_persona"],
        "grid": "标题 / insight / 2-3 列画像卡（目标/痛点/行为）",
        "components": ["card", "text"],
    },
    "journey": {
        "name": "用户旅程",
        "page_types": ["user_journey"],
        "grid": "标题 / 横向旅程条（步骤 + 触点 + 情绪）",
        "components": ["timeline", "card"],
    },
    "features": {
        "name": "功能优先级",
        "page_types": ["feature_priority"],
        "grid": "标题 / P0-P2 分组矩阵（名称/说明/优先级）",
        "components": ["table", "card", "matrix"],
    },
    "architecture": {
        "name": "产品架构",
        "page_types": ["product_architecture"],
        "grid": "标题 / 分层架构图（layer 卡片栈）",
        "components": ["card", "image", "text"],
    },
    "roadmap": {
        "name": "路线图",
        "page_types": ["roadmap"],
        "grid": "标题 / 三阶段横向时间线（阶段/目标/里程碑）",
        "components": ["timeline", "card"],
    },
    "closing": {
        "name": "结语",
        "page_types": ["conclusion"],
        "grid": "全屏居中：金句 / 行动号召",
        "components": ["quote", "text"],
    },
}

# ══════════════════════════════════════════════════════════
# 兼容层 —— 旧版 SlideDeck（deprecated，仅供旧数据/旧前端）
# ══════════════════════════════════════════════════════════

SlideBlockType = Literal["title", "subtitle", "text", "bullets", "metric", "quote", "table", "image"]
SlideLayoutType = Literal[
    "cover", "section_header", "two_column", "bullets", "timeline",
    "matrix", "image_hero", "closing", "default",
]


class SlideBlock(BaseModel):
    """@deprecated 旧版幻灯片内容块（P2 起由 Component 取代）。"""

    id: str
    block_type: SlideBlockType = "text"
    content: str = ""
    emphasis: Literal["low", "normal", "high"] = "normal"
    meta: dict = Field(default_factory=dict)


class Slide(BaseModel):
    """@deprecated 旧版幻灯片（P2 起由 Page 取代）。"""

    id: str
    title: str
    subtitle: str | None = None
    layout_type: SlideLayoutType = "default"
    blocks: list[SlideBlock] = Field(default_factory=list)
    visual_metadata: dict = Field(default_factory=dict)


class DeckSection(BaseModel):
    """@deprecated 旧版章节（新 DSL 中章节信息并入 pages 顺序与 insight）。"""

    title: str
    slide_ids: list[str] = Field(default_factory=list)


class SlideDeck(BaseModel):
    """@deprecated 旧版演示（P2 起由 Presentation 取代；仅兼容旧资产包）。"""

    topic: str
    slides: list[Slide] = Field(default_factory=list)
    sections: list[DeckSection] = Field(default_factory=list)
