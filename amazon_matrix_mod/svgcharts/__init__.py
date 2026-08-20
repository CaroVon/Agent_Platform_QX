"""svgcharts —— 纯 SVG 确定性图表渲染（替代 matplotlib 呈现层）。

设计约束：
  - 输出 SVG 遵循 ppt-master svg_to_pptx 画布契约（viewBox "0 0 W H"）
  - 所有数值来自真实数据，缺失显式标注「数据缺失」，禁止编造
  - 中文通过字体链渲染（Noto Sans SC → wqy 兜底），无 matplotlib 依赖
"""
from amazon_matrix_mod.svgcharts.svg import el, svg_document, fmt
from amazon_matrix_mod.svgcharts.style import (FONT_CHAIN, C, ZONE_COLORS,
                                               ZONE_LABELS)
from amazon_matrix_mod.svgcharts.layout import resolve_collisions, Node

__all__ = [
    "el", "svg_document", "fmt",
    "FONT_CHAIN", "C", "ZONE_COLORS", "ZONE_LABELS",
    "resolve_collisions", "Node",
]
