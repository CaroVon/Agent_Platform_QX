"""svgcharts 视觉规范 —— 与 Studio PPT 管线一致的浅色咨询风。"""
from __future__ import annotations

# 字体链：与 ppt-design-agent 页面 SVG 一致（Chromium 渲染时命中系统 Noto Sans CJK）
FONT_CHAIN = "Noto Sans SC, Source Han Sans SC, PingFang SC, Microsoft YaHei, sans-serif"


class C:
    """调色板（低饱和咨询风）。"""
    BG = "#F7F6F0"          # 页面底
    CARD = "#FFFFFF"        # 卡片面
    INK = "#101820"         # 主文字
    SUB = "#5C6068"         # 次级文字
    NAVY = "#12355B"        # 主色（标题/轴线）
    BLUE = "#1565C0"
    LIGHT_BLUE = "#DCE7F5"
    GREEN = "#2E7D32"
    AMBER = "#F9A825"
    RED = "#C62828"
    GREY = "#9E9E9E"
    GOLD = "#D4A017"        # 我方产品高亮
    GRID = "#E3E1D8"        # 网格线
    BAND = "#12355B14"      # 参考带（8% 不透明度 navy）


# 4 区配色（沿用分区引擎语义色）
ZONE_COLORS = {
    "price_gap": "#2E7D32",          # 价格缺口 → 绿（机会）
    "value_opportunity": "#1565C0",  # 性价比 → 蓝
    "demand_heat": "#F9A825",        # 需求热度 → 琥珀
    "red_ocean": "#C62828",          # 红海 → 红
    "neutral": "#9E9E9E",            # 未分区 → 灰
}

ZONE_LABELS = {
    "price_gap": "价格缺口区",
    "value_opportunity": "性价比机会区",
    "demand_heat": "需求热度区",
    "red_ocean": "红海警示区",
    "neutral": "未分区",
}

# 系列色（多分类图表循环取用）
SERIES = ["#12355B", "#1565C0", "#2E7D32", "#F9A825", "#C62828",
          "#6A4C93", "#00838F", "#8D6E63"]


def apply_theme(theme) -> None:
    """把 deck 主题 tokens 应用到模块调色板（页面 chrome/图表轴系随主题）。

    仅覆盖 chrome 类颜色（底/卡面/文字/主色/次色/网格）；zone 语义色
    （绿/蓝/琥珀/红）与系列色保留——数据语义不随主题漂移。
    渲染为单线程顺序执行，页面构建前调用一次即可。
    """
    C.BG = theme.bg
    C.CARD = theme.surface
    C.INK = theme.text
    C.NAVY = theme.primary
    C.BLUE = theme.accent
    C.SUB = theme.muted
    C.GREY = theme.muted
    C.GRID = theme.muted + "38"
    C.LIGHT_BLUE = theme.accent + "26"
    C.BAND = theme.primary + "14"
