"""第 3 章：价格带分析 —— 分布直方图/箱线图 + 价格缺口（空档带）检测。"""
from __future__ import annotations

import numpy as np
import pandas as pd

from amazon_matrix_mod.chapters.common import BRAND_COLORS, fp, save_chart, setup_style


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
    setup_style()
    import matplotlib.pyplot as plt

    prices = df["current_price"].dropna()
    if prices.empty:
        return {"title": "价格带分析", "conclusion": ["无价格数据"], "images": [],
                "md": "## 3. 价格带分析\n\n- 无价格数据\n"}
    p25, p50, p75 = prices.quantile([0.25, 0.5, 0.75])
    gaps = find_price_gaps(list(prices))

    # 直方图 + 分位数线
    fig, ax = plt.subplots(figsize=(10, 4.6))
    ax.hist(prices, bins=min(16, max(8, len(prices))), color=BRAND_COLORS["light"],
            edgecolor=BRAND_COLORS["blue"], alpha=0.95)
    for v, c, label in ((p25, BRAND_COLORS["amber"], "P25"), (p50, BRAND_COLORS["green"], "P50"),
                        (p75, BRAND_COLORS["red"], "P75")):
        ax.axvline(v, color=c, linestyle="--", linewidth=1.3)
        ax.text(v, ax.get_ylim()[1] * 0.94, f"{label} ${v:.2f}", color=c, fontsize=9,
                fontproperties=fp(9))
    if gaps:
        for g in gaps:
            ax.axvspan(g["low"], g["high"], color=BRAND_COLORS["amber"], alpha=0.18)
            ax.text((g["low"] + g["high"]) / 2, ax.get_ylim()[1] * 0.5,
                    f"缺口\n${g['low']:.0f}-{g['high']:.0f}", ha="center", fontsize=9,
                    color="#8a6d00", fontproperties=fp(9))
    ax.set_xlabel("价格 $", fontproperties=fp(10))
    ax.set_title(f"价格分布（N={len(prices)}）｜ P25=${p25:.2f} P50=${p50:.2f} P75=${p75:.2f}"
                 + (f" ｜ 缺口带 {len(gaps)} 处" if gaps else ""),
                 fontproperties=fp(12, "bold"))
    ax.grid(axis="y", linestyle=":", alpha=0.4)
    ax.tick_params(labelsize=9)
    fig.tight_layout()
    img1 = save_chart(fig, out_dir, "ch03_price_hist.png")

    # 箱线图（按品牌）
    fig2, ax2 = plt.subplots(figsize=(10, 4.6))
    brands = df.groupby(df["brand"].fillna("未知"))["current_price"].agg(["count", "median"]) \
        .sort_values("median", ascending=False).head(8).index
    data = [df[df["brand"].fillna("未知") == b]["current_price"].dropna().tolist() for b in brands]
    bp = ax2.boxplot(data, patch_artist=True,
                     medianprops=dict(color=BRAND_COLORS["navy"]))
    ax2.set_xticklabels([str(b)[:14] for b in brands], fontsize=8.5)
    for patch in bp["boxes"]:
        patch.set_facecolor(BRAND_COLORS["light"])
        patch.set_edgecolor(BRAND_COLORS["blue"])
    ax2.set_ylabel("价格 $", fontproperties=fp(10))
    ax2.set_title("品牌价格区间对比（Top8 品牌）", fontproperties=fp(12, "bold"))
    ax2.tick_params(labelsize=8.5)
    fig2.tight_layout()
    img2 = save_chart(fig2, out_dir, "ch03_price_box.png")

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
