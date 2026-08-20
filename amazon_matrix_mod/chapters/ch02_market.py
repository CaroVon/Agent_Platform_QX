"""第 2 章：市场概览与竞争格局 —— 品牌集中度（HHI）/ 广告占比 / 类目分布。"""
from __future__ import annotations

import pandas as pd

from amazon_matrix_mod.chapters.common import BRAND_COLORS, fp, save_chart, setup_style


def hhi(shares: list[float]) -> float:
    """赫芬达尔指数（0-1）：品牌销量份额平方和。>0.25 高集中，0.15-0.25 中度，<0.15 分散。"""
    s = sum(x * x for x in shares) if shares else 0
    return round(s, 3)


def analyze(df: pd.DataFrame, search_raw: dict | None, out_dir: str) -> dict:
    setup_style()
    import matplotlib.pyplot as plt

    conclusions: list[str] = []
    images: list[str] = []

    # ── 品牌集中度（按月销估算份额） ─────────────────────
    brand_sales = df.dropna(subset=["est_monthly_sales"]).groupby(
        df["brand"].fillna("未知"))["est_monthly_sales"].sum().sort_values(ascending=False)
    total = brand_sales.sum() or 1
    shares = [v / total for v in brand_sales.values]
    h = hhi(shares)
    top5 = brand_sales.head(5)
    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.barh([str(b)[:18] for b in top5.index][::-1],
                   [v for v in top5.values][::-1], color=BRAND_COLORS["blue"], alpha=0.85)
    for i, b in enumerate(bars):
        ax.text(b.get_width() + total * 0.01, b.get_y() + b.get_height() / 2,
                f"{top5.values[::-1][i]:,}", va="center", fontsize=9)
    ax.set_xlabel("月销估算合计（官方 recent_sales 口径）", fontproperties=fp(10))
    ax.set_title(f"品牌月销份额 Top5 ｜ HHI={h}（{'高集中' if h > 0.25 else '中度' if h > 0.15 else '分散'}）",
                 fontproperties=fp(12, "bold"))
    ax.grid(axis="x", linestyle=":", alpha=0.4)
    ax.tick_params(labelsize=9)
    images.append(save_chart(fig, out_dir, "ch02_brand_hhi.png"))
    conclusions.append(
        f"品牌集中度 HHI={h}（{'高' if h > 0.25 else '中' if h > 0.15 else '低'}）："
        f"头部品牌 {', '.join(str(b)[:12] for b in top5.index[:3])} 占月销 "
        f"{sum(top5.values[:3]) / total * 100:.0f}%" if total else "")

    # ── 广告占比（search 首页 sponsored） ─────────────────
    if search_raw:
        results = search_raw.get("search_results") or []
        sponsored = sum(1 for r in results if r.get("sponsored"))
        n = len(results)
        if n:
            fig2, ax2 = plt.subplots(figsize=(6, 4.5))
            ax2.pie([sponsored, n - sponsored],
                    labels=[f"广告位 {sponsored}", f"自然位 {n - sponsored}"],
                    colors=[BRAND_COLORS["amber"], BRAND_COLORS["blue"]],
                    autopct="%1.0f%%", startangle=90,
                    textprops={"fontproperties": fp(10)})
            ax2.set_title(f"搜索结果首页广告占比（{n} 条）", fontproperties=fp(12, "bold"))
            images.append(save_chart(fig2, out_dir, "ch02_ads_share.png"))
            conclusions.append(
                f"首页广告位占比 {sponsored / n * 100:.0f}%"
                f"（{'广告竞争激烈' if sponsored / n > 0.4 else '广告竞争温和'}）")

    return {
        "title": "市场概览与竞争格局",
        "conclusion": conclusions,
        "images": images,
        "md": _md(conclusions),
    }


def _md(conclusions: list[str]) -> str:
    return "## 2. 市场概览与竞争格局\n\n" + "\n".join(f"- {c}" for c in conclusions) + "\n"
