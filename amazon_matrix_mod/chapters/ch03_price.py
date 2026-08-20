"""第 3 章：价格带分析 —— 分布直方图 + 品牌价格区间 + 价格缺口检测（SVG 渲染）。"""
from __future__ import annotations

import numpy as np
import pandas as pd

from amazon_matrix_mod.chapters.common import save_chart, chart_title
from amazon_matrix_mod.svgcharts import charts


def find_price_gaps(prices: list[float], bins: int = 12) -> list[dict]:
    """直方图空档检测：连续空 bin 且跨度为总价程 ≥8% 记为缺口带。"""
    if len(prices) < 4:
        return []
    hist, edges = np.histogram(prices, bins=bins)
    span = (edges[-1] - edges[0]) or 1
    gaps = []
    i = 0
    while i < bins:
        if hist[i] == 0:
            j = i
            while j < bins and hist[j] == 0:
                j += 1
            lo, hi = edges[i], edges[j]
            if (hi - lo) / span >= 0.08:
                gaps.append({"low": round(float(lo), 2), "high": round(float(hi), 2),
                             "width_ratio": round((hi - lo) / span, 2)})
            i = j
        else:
            i += 1
    return gaps


def analyze(df: pd.DataFrame, out_dir: str) -> dict:
    prices = df["current_price"].dropna()
    if prices.empty:
        return {"title": "价格带分析", "conclusion": ["无价格数据"], "images": [],
                "md": "## 3. 价格带分析\n\n- 无价格数据\n"}
    p25, p50, p75 = prices.quantile([0.25, 0.5, 0.75])
    gaps = find_price_gaps(list(prices))

    # 直方图 + 分位数线 + 缺口带
    def _draw_hist(root):
        charts.histogram(root, 40, 60, 1020, 340,
                         [float(v) for v in prices],
                         bins=min(16, max(8, len(prices))),
                         quantiles={"P25": p25, "P50": p50, "P75": p75},
                         gaps=gaps,
                         title=f"价格分布（N={len(prices)}）｜ "
                               f"P25=${p25:.2f} P50=${p50:.2f} P75=${p75:.2f}"
                               + (f" ｜ 缺口带 {len(gaps)} 处" if gaps else ""))

    img1 = save_chart(_draw_hist, out_dir, "ch03_price_hist.svg")

    # 品牌价格区间（min-max + 中位）
    brands = df.groupby(df["brand"].fillna("未知"))["current_price"] \
        .agg(["min", "median", "max", "count"])
    brands = brands[brands["count"] >= 1].sort_values("median", ascending=False).head(8)
    items = [{"label": str(b)[:14], "lo": float(r["min"]),
              "hi": float(r["max"]), "mid": float(r["median"])}
             for b, r in brands.iterrows()]

    def _draw_brands(root):
        chart_title(root, "品牌价格区间对比（Top8 品牌，按中位价降序）")
        charts.interval_bars(root, 40, 90, 1020, 330, items)

    img2 = save_chart(_draw_brands, out_dir, "ch03_price_box.svg")

    conclusions = [
        f"价格中位数 ${p50:.2f}，P25-P75 区间 ${p25:.2f}-${p75:.2f}"
        f"（价程 ${p75 - p25:.2f}）"]
    if gaps:
        gap_desc = "、".join(f"${g['low']:.2f}-${g['high']:.2f}" for g in gaps[:3])
        conclusions.append(f"检测到价格缺口带：{gap_desc} —— 可作为差异化切入价位")
    else:
        conclusions.append("未检测到显著价格空档（价格带连续）")
    return {
        "title": "价格带分析",
        "conclusion": conclusions,
        "images": [img1, img2],
        "md": _md(conclusions, gaps),
    }


def _md(conclusions: list[str], gaps: list[dict]) -> str:
    out = ["## 3. 价格带分析\n"]
    out += [f"- {c}" for c in conclusions]
    if gaps:
        out.append("\n| 缺口带 | 跨度占比 |\n|---|---|")
        for g in gaps:
            out.append(f"| ${g['low']:.2f}-${g['high']:.2f} | {g['width_ratio'] * 100:.0f}% |")
    return "\n".join(out) + "\n"
