"""第 4 章：需求与销量分析 —— BSR 分布 + 价格-销量关系。"""
from __future__ import annotations

import numpy as np
import pandas as pd

from amazon_matrix_mod.chapters.common import BRAND_COLORS, fp, save_chart, setup_style


def analyze(df: pd.DataFrame, out_dir: str) -> dict:
    setup_style()
    import matplotlib.pyplot as plt

    conclusions: list[str] = []
    images: list[str] = []

    sales = df["est_monthly_sales"].dropna()
    if not sales.empty:
        p80 = sales.quantile(0.8)
        top = df[df["est_monthly_sales"] >= p80].sort_values("est_monthly_sales", ascending=False)
        fig, ax = plt.subplots(figsize=(10, 4.6))
        ordered = df.dropna(subset=["est_monthly_sales"]).sort_values("est_monthly_sales", ascending=False)
        ax.bar(range(len(ordered)), ordered["est_monthly_sales"],
               color=[BRAND_COLORS["green"] if v >= p80 else BRAND_COLORS["light"]
                      for v in ordered["est_monthly_sales"]],
               edgecolor=BRAND_COLORS["grey"], linewidth=0.4)
        ax.axhline(p80, color=BRAND_COLORS["red"], linestyle="--", linewidth=1.2)
        ax.text(len(ordered) * 0.98, p80 * 1.05, f"P80={int(p80)}", ha="right",
                color=BRAND_COLORS["red"], fontsize=9, fontproperties=fp(9))
        ax.set_yscale("log")
        ax.set_xlabel("竞品（按月销降序）", fontproperties=fp(10))
        ax.set_ylabel("月销估算（官方口径，对数）", fontproperties=fp(10))
        top_desc = "、".join(
            f"{str(r.get('brand') or '?')[:12]}({int(r.get('est_monthly_sales') or 0)})"
            for _, r in top.head(3).iterrows())
        ax.set_title(f"月销分布｜Top3: {top_desc}", fontproperties=fp(11, "bold"))
        ax.tick_params(labelsize=9)
        fig.tight_layout()
        images.append(save_chart(fig, out_dir, "ch04_sales_dist.png"))
        conclusions.append(
            f"月销 P80={int(p80)}；头部 {len(top)} 个竞品贡献需求主力"
            f"（Top1 {str(top.iloc[0].get('brand') or '?')} 月销 {int(top.iloc[0]['est_monthly_sales'])}）")

    # 价格-销量关系（对数散点 + 趋势）
    sub = df.dropna(subset=["current_price", "est_monthly_sales"])
    if len(sub) >= 3:
        fig2, ax2 = plt.subplots(figsize=(10, 4.6))
        ax2.scatter(sub["current_price"], sub["est_monthly_sales"],
                    s=60, color=BRAND_COLORS["blue"], alpha=0.7, edgecolor="white", linewidth=0.6)
        x = np.log(sub["current_price"])
        y = np.log(sub["est_monthly_sales"])
        k = np.polyfit(x, y, 1)
        xs = np.linspace(sub["current_price"].min(), sub["current_price"].max(), 50)
        ax2.plot(xs, np.exp(np.polyval(k, np.log(xs))), "--",
                 color=BRAND_COLORS["red"], linewidth=1.5,
                 label=f"趋势斜率 {k[0]:+.2f}（{'价格弹性高' if abs(k[0]) > 0.8 else '价格敏感度中等'}）")
        ax2.set_xscale("log"); ax2.set_yscale("log")
        ax2.set_xlabel("价格 $（对数）", fontproperties=fp(10))
        ax2.set_ylabel("月销估算（对数）", fontproperties=fp(10))
        ax2.set_title("价格-销量关系（对数散点）", fontproperties=fp(12, "bold"))
        ax2.legend(prop=fp(9))
        ax2.tick_params(labelsize=9)
        fig2.tight_layout()
        images.append(save_chart(fig2, out_dir, "ch04_price_sales.png"))
        conclusions.append(
            f"价格-销量弹性系数 {k[0]:+.2f}（"
            f"{'降价显著放量，价格敏感市场' if k[0] < -0.8 else '价格非主导因素，竞争点在别处'}）")

    return {"title": "需求与销量分析", "conclusion": conclusions, "images": images,
            "md": _md(conclusions)}


def _md(conclusions: list[str]) -> str:
    return "## 4. 需求与销量分析\n\n" + "\n".join(f"- {c}" for c in conclusions) + "\n"
