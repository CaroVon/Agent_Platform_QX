"""第 4 章：需求与销量分析 —— 月销分布 + 价格-销量弹性（SVG 渲染）。"""
from __future__ import annotations

import pandas as pd

from amazon_matrix_mod.chapters.common import save_chart
from amazon_matrix_mod.svgcharts import charts


def analyze(df: pd.DataFrame, out_dir: str) -> dict:
    conclusions: list[str] = []
    images: list[str] = []

    sales = df["est_monthly_sales"].dropna()
    if not sales.empty:
        p80 = sales.quantile(0.8)
        top = df[df["est_monthly_sales"] >= p80].sort_values("est_monthly_sales",
                                                             ascending=False)
        ordered = df.dropna(subset=["est_monthly_sales"]) \
            .sort_values("est_monthly_sales", ascending=False)
        top_desc = "、".join(
            f"{str(r.get('brand') or '?')[:12]}({int(r.get('est_monthly_sales') or 0)})"
            for _, r in top.head(3).iterrows())

        def _draw_dist(root):
            items = [{"label": f"{str(r.get('brand') or r['asin'])[:14]}",
                      "value": float(r["est_monthly_sales"]),
                      "display": f"{int(r['est_monthly_sales']):,}",
                      "color": "#2E7D32" if r["est_monthly_sales"] >= p80 else "#DCE7F5"}
                     for _, r in ordered.iterrows()]
            charts.bar_h(root, 40, 60, 1020, 360, items,
                         title=f"月销分布（按月销降序，P80={int(p80)}）｜ Top3: {top_desc}",
                         label_width=170)

        images.append(save_chart(_draw_dist, out_dir, "ch04_sales_dist.svg"))
        conclusions.append(
            f"月销 P80={int(p80)}；头部 {len(top)} 个竞品贡献需求主力"
            f"（Top1 {str(top.iloc[0].get('brand') or '?')} "
            f"月销 {int(top.iloc[0]['est_monthly_sales'])}）")

    # 价格-销量关系（对数散点 + log-log OLS 趋势）
    sub = df.dropna(subset=["current_price", "est_monthly_sales"])
    if len(sub) >= 3:
        pts = [(float(r["current_price"]), float(r["est_monthly_sales"]))
               for _, r in sub.iterrows()]

        def _draw_elas(root):
            charts.scatter_fit(
                root, 60, 70, 980, 340, pts,
                x_label="价格 $（对数）", y_label="月销估算（对数）",
                fit_note="趋势斜率 {slope:+.2f}",
                title="价格-销量关系（log-log 散点 + OLS 趋势）")

        images.append(save_chart(_draw_elas, out_dir, "ch04_price_sales.svg"))
        import numpy as np
        k = np.polyfit(np.log([p for p, _ in pts]), np.log([s for _, s in pts]), 1)
        conclusions.append(
            f"价格-销量弹性系数 {k[0]:+.2f}（"
            f"{'降价显著放量，价格敏感市场' if k[0] < -0.8 else '价格非主导因素，竞争点在别处'}）")

    return {"title": "需求与销量分析", "conclusion": conclusions, "images": images,
            "md": _md(conclusions)}


def _md(conclusions: list[str]) -> str:
    return "## 4. 需求与销量分析\n\n" + "\n".join(f"- {c}" for c in conclusions) + "\n"
