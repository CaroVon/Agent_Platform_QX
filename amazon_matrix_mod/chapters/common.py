"""章节引擎公共组件 —— SVG 图表渲染（svgcharts 层，matplotlib 已移除）。"""
from __future__ import annotations

import os

from amazon_matrix_mod.svgcharts import charts
from amazon_matrix_mod.svgcharts.svg import el, save, svg_document, text
from amazon_matrix_mod.svgcharts.style import C, FONT_CHAIN, SERIES

# 章节图统一画布（白色底，嵌入报告/PPT 均可）
CHART_W, CHART_H = 1100, 460

# 兼容旧引用的颜色常量（matplotlib 版遗留命名）
BRAND_COLORS = {
    "blue": "#1565C0", "green": "#2E7D32", "amber": "#F9A825",
    "red": "#C62828", "grey": "#9E9E9E", "navy": "#12355B",
    "light": "#DCE7F5",
}
ZONE_COLORS = {
    "price_gap": "#2E7D32", "value_opportunity": "#1565C0",
    "demand_heat": "#F9A825", "red_ocean": "#C62828", "neutral": "#9E9E9E",
}


def save_chart(draw, out_dir: str, name: str, w: int = CHART_W,
               h: int = CHART_H) -> str:
    """渲染章节图。draw(root) 在白色画布内绘制；返回文件名（非绝对路径，
    供 md 相对引用与 run_mod 统一拼装）。"""
    os.makedirs(out_dir, exist_ok=True)
    root = svg_document(w, h, bg="#FFFFFF")
    draw(root)
    save(root, os.path.join(out_dir, name))
    return name


def chart_title(root, title: str, y: float = 34) -> None:
    text(root, 40, y, title, size=15, fill=C.NAVY, weight="600", family=FONT_CHAIN)
