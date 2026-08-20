"""第 6 章：评价健康度 —— 星级结构（rating_breakdown）/ 评论-销量比。"""
from __future__ import annotations

import pandas as pd

from amazon_matrix_mod.chapters.common import BRAND_COLORS, fp, save_chart, setup_style


def _star_breakdown(product_raw: dict) -> dict | None:
    rb = (product_raw or {}).get("rating_breakdown") or {}
    if not rb:
        return None
    return {
        "five": rb.get("five_star", {}).get("count", 0),
        "four": rb.get("four_star", {}).get("count", 0),
        "three": rb.get("three_star", {}).get("count", 0),
        "two": rb.get("two_star", {}).get("count", 0),
        "one": rb.get("one_star", {}).get("count", 0),
    }


def analyze(df: pd.DataFrame, products_raw: dict, out_dir: str) -> dict:
    setup_style()
    import matplotlib.pyplot as plt

    conclusions: list[str] = []
    images: list[str] = []

    # 评分分布
    ratings = df["rating"].dropna()
    if not ratings.empty:
        fig, ax = plt.subplots(figsize=(10, 4.4))
        ax.hist(ratings, bins=min(10, max(5, int(ratings.nunique()))),
                color=BRAND_COLORS["blue"], alpha=0.85, edgecolor="white")
        ax.axvline(ratings.median(), color=BRAND_COLORS["red"], linestyle="--",
                   label=f"中位 {ratings.median():.2f}")
        ax.set_xlabel("评分", fontproperties=fp(10))
        ax.set_ylabel("竞品数", fontproperties=fp(10))
        ax.set_title(f"竞品评分分布（中位 {ratings.median():.2f}）", fontproperties=fp(12, "bold"))
        ax.legend(prop=fp(9))
        ax.tick_params(labelsize=9)
        fig.tight_layout()
        images.append(save_chart(fig, out_dir, "ch06_rating_dist.png"))
        low = (ratings < 4.0).sum()
        conclusions.append(
            f"评分中位 {ratings.median():.2f}；{low} 个竞品评分 <4.0"
            f"（{'存在质量口碑空档' if low >= 2 else '整体口碑较好'}）")

    # 星级结构（Top5 销量竞品堆叠图）
    top_asins = df.nlargest(5, "est_monthly_sales", keep="first")["asin"].tolist() \
        if "est_monthly_sales" in df else df.head(5)["asin"].tolist()
    stacks = {a: _star_breakdown(products_raw.get(a)) for a in top_asins}
    stacks = {a: s for a, s in stacks.items() if s}
    if stacks:
        fig2, ax2 = plt.subplots(figsize=(10, 4.6))
        labels = [str(df[df["asin"] == a].iloc[0].get("brand") or a)[:14] for a in stacks]
        bottom = [0] * len(stacks)
        stars = [("5星", "five", "#2E7D32"), ("4星", "four", "#66BB6A"),
                 ("3星", "three", "#F9A825"), ("2星", "two", "#FB8C00"),
                 ("1星", "one", "#C62828")]
        for label, key, color in stars:
            vals = [s[key] for s in stacks.values()]
            ax2.bar(labels, vals, bottom=bottom, label=label, color=color, alpha=0.9)
            bottom = [b + v for b, v in zip(bottom, vals)]
        ax2.set_yscale("log")
        ax2.set_ylabel("评论数（对数）", fontproperties=fp(10))
        ax2.set_title("Top5 销量竞品星级结构（评分分布）", fontproperties=fp(12, "bold"))
        ax2.legend(prop=fp(9), ncol=5)
        ax2.tick_params(labelsize=8.5)
        fig2.tight_layout()
        images.append(save_chart(fig2, out_dir, "ch06_star_stack.png"))
        # 差评率结论（Top1）
        top1 = next(iter(stacks.values()))
        t = sum(top1.values()) or 1
        bad = (top1["one"] + top1["two"]) / t
        conclusions.append(f"Top1 竞品差评率（1-2星）{bad * 100:.1f}% —— 差评集中点是差异化切入点")

    # 评论-销量比（评价转化效率）
    sub = df.dropna(subset=["review_count", "est_monthly_sales"])
    if len(sub) >= 3:
        sub = sub.copy()
        sub["review_per_sales"] = sub["review_count"] / sub["est_monthly_sales"].replace(0, 1)
        med = sub["review_per_sales"].median()
        conclusions.append(
            f"评论/月销比中位 {med:.2f}（{'评论积累快、历史口碑厚' if med > 3 else '销量领先评论积累，新进入者窗口' if med < 1 else '正常'}）")

    return {"title": "评价健康度", "conclusion": conclusions, "images": images,
            "md": _md(conclusions)}


def _md(conclusions: list[str]) -> str:
    return "## 6. 评价健康度\n\n" + "\n".join(f"- {c}" for c in conclusions) + "\n"
