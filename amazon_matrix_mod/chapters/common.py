"""章节引擎公共组件 —— 图表样式/中文字体/保存。"""
from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.font_manager import FontProperties, fontManager  # noqa: E402

from amazon_matrix_mod.plot_static import _CJK  # 复用中文字体探测

BRAND_COLORS = {
    "blue": "#1565C0", "green": "#2E7D32", "amber": "#F9A825",
    "red": "#C62828", "grey": "#9E9E9E", "navy": "#12355B",
    "light": "#E3F2FD",
}
ZONE_COLORS = {
    "price_gap": "#2E7D32", "value_opportunity": "#1565C0",
    "demand_heat": "#F9A825", "red_ocean": "#C62828", "neutral": "#9E9E9E",
}


def setup_style():
    plt.rcParams["font.sans-serif"] = [_CJK]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.facecolor"] = "white"


def save_chart(fig, out_dir: str, name: str, dpi: int = 110) -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, name)
    fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def fp(size: int = 10, weight: str = "normal") -> FontProperties:
    return FontProperties(family=_CJK, size=size, weight=weight)
