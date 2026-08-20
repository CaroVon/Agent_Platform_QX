"""第 6 章：评价健康度 —— 评分分布 + 星级结构 + 评论-销量比（SVG 渲染）。"""
from __future__ import annotations

import pandas as pd

from amazon_matrix_mod.chapters.common import save_chart, chart_title
from amazon_matrix_mod.svgcharts import charts
from amazon_matrix_mod.svgcharts.svg import el, text
from amazon_matrix_mod.svgcharts.style import FONT_CHAIN

_STARS = [("5星", "five", "#2E7D32"), ("4星", "four", "#66BB6A"),
          ("3星", "three", "#F9A825"), ("2星", "two", "#FB8C00"),
          ("1星", "one", "#C62828")]


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
    conclusions: list[str] = []
    images: list[str] = []

    # 评分分布
    ratings = df["rating"].dropna()
    if not ratings.empty:
        med = ratings.median()

        def _draw_rating(root):
            charts.histogram(root, 40, 60, 1020, 340,
                             [float(v) for v in ratings],
                             bins=min(10, max(5, int(ratings.nunique()))),
                             quantiles={"P50": med},
                             title=f"竞品评分分布（中位 {med:.2f}）")

        images.append(save_chart(_draw_rating, out_dir, "ch06_rating_dist.svg"))
        low = (ratings < 4.0).sum()
        conclusions.append(
            f"评分中位 {med:.2f}；{low} 个竞品评分 <4.0"
            f"（{'存在质量口碑空档' if low >= 2 else '整体口碑较好'}）")

    # 星级结构（Top5 销量竞品 100% 堆叠条）
    top_asins = df.nlargest(5, "est_monthly_sales", keep="first")["asin"].tolist() \
        if "est_monthly_sales" in df else df.head(5)["asin"].tolist()
    stacks = {a: _star_breakdown(products_raw.get(a)) for a in top_asins}
    stacks = {a: s for a, s in stacks.items() if s}
    if stacks:
        labels = {a: str(df[df["asin"] == a].iloc[0].get("brand") or a)[:14]
                  for a in stacks}

        def _draw_stack(root):
            chart_title(root, "Top5 销量竞品星级结构（100% 堆叠）")
            x0, bar_w, row_h = 200, 700, 46
            for i, (asin, s) in enumerate(stacks.items()):
                cy = 110 + i * row_h
                total = sum(s.values()) or 1
                text(root, 40, cy + 16, labels[asin], size=12, family=FONT_CHAIN)
                cx = x0
                for _label, key, color in _STARS:
                    frac = s[key] / total
                    if frac <= 0:
                        continue
                    w = bar_w * frac
                    el(root, "rect", x=cx, y=cy, width=w, height=24,
                       fill=color, stroke="white", stroke_width=0.8)
                    if frac > 0.12:
                        text(root, cx + w / 2, cy + 16, f"{frac * 100:.0f}%",
                             size=10.5, fill="white", anchor="middle",
                             family=FONT_CHAIN)
                    cx += w
                text(root, x0 + bar_w + 12, cy + 16, f"{total:,} 条", size=11,
                     family=FONT_CHAIN)
            lx = x0
            for label, _key, color in _STARS:
                el(root, "rect", x=lx, y=380, width=11, height=11, fill=color, rx=2)
                text(root, lx + 16, 390, label, size=11, family=FONT_CHAIN)
                lx += 70

        images.append(save_chart(_draw_stack, out_dir, "ch06_star_stack.svg"))
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
        med2 = sub["review_per_sales"].median()
        conclusions.append(
            f"评论/月销比中位 {med2:.2f}"
            f"（{'评论积累快、历史口碑厚' if med2 > 3 else '销量领先评论积累，新进入者窗口' if med2 < 1 else '正常'}）")

    return {"title": "评价健康度", "conclusion": conclusions, "images": images,
            "md": _md(conclusions)}


def _md(conclusions: list[str]) -> str:
    return "## 6. 评价健康度\n\n" + "\n".join(f"- {c}" for c in conclusions) + "\n"
