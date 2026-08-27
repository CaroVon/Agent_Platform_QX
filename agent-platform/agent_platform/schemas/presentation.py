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
    # ── MOD 章节（亚马逊真实数据页，并入主 deck 计划）──
    "mod_overview",        # 市场总览：品牌份额/ASP/KPI/价格带/四分区
    "mod_matrix",          # 价格×月销矩阵散点
    "mod_hero_teardown",   # 单品拆解（Top ASIN 解剖式：特性/评论/商业块）
    "mod_spec_comparison", # 参数对比矩阵（hero 先列+优势高亮）
    "mod_sku_analysis",    # SKU/变体与渠道结构
    "mod_actions",         # 行动建议（owner 行动项）
]

LayoutId = Literal[
    "cover", "summary", "market", "matrix", "persona",
    "journey", "features", "architecture", "roadmap", "closing",
    # ── P1 多样性扩容（10 → 20 版式）──
    "big_number",     # 大数字锚点页（货币级 KPI）
    "comparison",     # 左右对比页（我们 vs 竞品 / 现状 vs 方案）
    "gallery",        # 三/四卡画廊（图片矩阵）
    "kpi_wall",       # KPI 墙（6-8 指标网格）
    "quote_full",     # 全屏引用页（金句/用户原声）
    "timeline_v",     # 竖版时间线（历程/里程碑）
    "funnel",         # 漏斗页（转化/分层）
    "table_dense",    # 密集数据表（宽表）
    "map_split",      # 图文分栏（图左文右）
    "checklist",      # 清单页（行动项/检查表）
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


# 预置主题（含 CyberPPT 8 套咨询风，见 skills/presentation-cyberppt/visual-system.md）
THEME_PRESETS: dict[str, dict] = {
    "default": {
        "name": "咨询蓝",
        "palette": {"bg": "#f8fafc", "surface": "#ffffff", "primary": "#4f46e5",
                    "accent": "#6366f1", "text": "#0f172a", "muted": "#64748b"},
    },
    "cyber-crimson": {
        "name": "经典深红咨询",
        "palette": {"bg": "#F3F4EF", "surface": "#FFFFFF", "primary": "#8B1E1E",
                    "accent": "#B54B4B", "text": "#111111", "muted": "#555555"},
    },
    "cyber-burgundy": {
        "name": "冷灰+勃艮第红",
        "palette": {"bg": "#F5F5F2", "surface": "#FFFFFF", "primary": "#7A1F2B",
                    "accent": "#A04A55", "text": "#000000", "muted": "#6B6B6B"},
    },
    "cyber-ivory-wine": {
        "name": "暖象牙白+暗酒红",
        "palette": {"bg": "#F4F1EA", "surface": "#FFFFFF", "primary": "#8A1538",
                    "accent": "#B04A67", "text": "#121212", "muted": "#77736C"},
    },
    "cyber-ivory-navy": {
        "name": "象牙白+深蓝",
        "palette": {"bg": "#F7F6F0", "surface": "#FFFFFF", "primary": "#12355B",
                    "accent": "#3D6491", "text": "#101820", "muted": "#6F7275"},
    },
    "cyber-grey-green": {
        "name": "浅灰白+墨绿",
        "palette": {"bg": "#F2F3EF", "surface": "#FFFFFF", "primary": "#1F5B4D",
                    "accent": "#4E8577", "text": "#111111", "muted": "#666666"},
    },
    "cyber-paper-copper": {
        "name": "纸张米色+铜棕",
        "palette": {"bg": "#F4F0E8", "surface": "#FFFFFF", "primary": "#9A5A2E",
                    "accent": "#C08A5C", "text": "#161616", "muted": "#76716A"},
    },
    "cyber-black-gold": {
        "name": "纯净浅灰+黑金",
        "palette": {"bg": "#F6F6F4", "surface": "#FFFFFF", "primary": "#2B2A26",
                    "accent": "#A87932", "text": "#000000", "muted": "#707070"},
    },
    "cyber-deep-purple": {
        "name": "冷白灰+深紫",
        "palette": {"bg": "#F4F5F6", "surface": "#FFFFFF", "primary": "#4B2E83",
                    "accent": "#7A5FA8", "text": "#111111", "muted": "#6D7175"},
    },
}


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
        "page_types": ["market_overview", "mod_overview"],
        "grid": "标题 / insight / 左侧要点列表 + 右侧 chart 或 metric",
        "components": ["chart", "metric", "text", "table"],
    },
    "matrix": {
        "name": "竞品矩阵",
        "page_types": ["competitor_matrix", "mod_matrix", "mod_spec_comparison"],
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
        "page_types": ["feature_priority", "mod_hero_teardown", "mod_sku_analysis", "mod_actions"],
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
    # ── P1 多样性扩容版式 ──
    "big_number": {
        "name": "大数字锚点",
        "page_types": ["executive_summary", "market_overview", "mod_overview"],
        "grid": "单一巨型数值（80px+）+ 单位 tspan + 三行支撑说明",
        "components": ["metric", "text"],
    },
    "comparison": {
        "name": "左右对比",
        "page_types": ["competitor_matrix", "mod_spec_comparison", "feature_priority"],
        "grid": "双栏对峙：左现状/竞品 vs 右方案/我方，中线分隔 + 逐行对照",
        "components": ["card", "table", "matrix"],
    },
    "gallery": {
        "name": "卡片画廊",
        "page_types": ["user_persona", "user_journey", "mod_sku_analysis"],
        "grid": "3×N 等宽卡片墙（图/标题/一句话）",
        "components": ["image", "card"],
    },
    "kpi_wall": {
        "name": "KPI 墙",
        "page_types": ["market_overview", "executive_summary", "mod_overview"],
        "grid": "2×3 或 2×4 指标网格（accent 顶条 + 大数值 + 小标签）",
        "components": ["metric"],
    },
    "quote_full": {
        "name": "全屏引用",
        "page_types": ["user_persona", "conclusion"],
        "grid": "全屏留白 + 引文居中 + 出处签名（用户原声/评论）",
        "components": ["quote"],
    },
    "timeline_v": {
        "name": "竖版时间线",
        "page_types": ["roadmap", "user_journey"],
        "grid": "左侧竖轴 + 阶段节点（时期/事件/产出）",
        "components": ["timeline", "card"],
    },
    "funnel": {
        "name": "漏斗",
        "page_types": ["market_overview", "user_journey"],
        "grid": "分层漏斗（层名+量级+转化率标注）",
        "components": ["chart", "metric"],
    },
    "table_dense": {
        "name": "密集数据表",
        "page_types": ["competitor_matrix", "mod_spec_comparison", "mod_sku_analysis"],
        "grid": "全宽表（主色表头 + 斑马纹 + 优势格高亮）",
        "components": ["table"],
    },
    "map_split": {
        "name": "图文分栏",
        "page_types": ["market_overview", "mod_matrix", "product_architecture"],
        "grid": "图占左 55% + 右侧要点列（或反向）",
        "components": ["image", "text"],
    },
    "checklist": {
        "name": "行动清单",
        "page_types": ["feature_priority", "mod_actions", "conclusion"],
        "grid": "编号清单（01-06 + 复选框 + owner/优先级徽标）",
        "components": ["card", "table"],
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
