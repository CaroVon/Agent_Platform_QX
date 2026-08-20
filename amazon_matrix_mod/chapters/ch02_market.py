"""第 2 章：市场概览与竞争格局 —— 品牌集中度（HHI）/ 广告占比（SVG 渲染）。"""
from __future__ import annotations

import pandas as pd

from amazon_matrix_mod.chapters.common import save_chart, chart_title
from amazon_matrix_mod.svgcharts import charts
from amazon_matrix_mod.svgcharts.style import C, FONT_CHAIN


def hhi(shares: list[float]) -> float:
    """赫芬达尔指数（0-1）：品牌销量份额平方和。>0.25 高集中，0.15-0.25 中度，<0.15 分散。"""
    s = sum(x * x for x in shares) if shares else 0
    return round(s, 3)


def analyze(df: pd.DataFrame, search_raw: dict | None, out_dir: str) -> dict:
    conclusions: list[str] = []
    images: list[str] = []

    # ── 品牌集中度（按月销估算份额） ─────────────────────
    brand_sales = df.dropna(subset=["est_monthly_sales"]).groupby(
        df["brand"].fillna("未知"))["est_monthly_sales"].sum().sort_values(ascending=False)
    total = brand_sales.sum() or 1
    shares = [v / total for v in brand_sales.values]
    h = hhi(shares)
    top5 = brand_sales.head(5)
    conc = "高集中" if h > 0.25 else ("中度" if h > 0.15 else "分散")

    def _draw_brand(root):
        chart_title(root, f"品牌月销份额 Top5 ｜ HHI={h}（{conc}）")
        items = [{"label": str(b)[:16],
                  "value": float(v),
                  "display": f"{v:,.0f}"}
                 for b, v in top5.items()]
        charts.bar_h(root, 40, 90, 1020, 330, items,
                     title="月销估算合计（官方 recent_sales 口径）",
                     label_width=170)

    images.append(save_chart(_draw_brand, out_dir, "ch02_brand_hhi.svg"))
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
            def _draw_ads(root):
                chart_title(root, f"搜索结果首页广告占比（{n} 条）")
                charts.donut(root, 320, 250, 120,
                             [{"label": f"广告位 {sponsored}", "value": sponsored,
                               "color": C.AMBER},
                              {"label": f"自然位 {n - sponsored}", "value": n - sponsored,
                               "color": C.BLUE}],
                             center_total=f"{sponsored / n * 100:.0f}%",
                             center_label="广告位占比",
                             legend_x=620, legend_y=220)

            images.append(save_chart(_draw_ads, out_dir, "ch02_ads_share.svg"))
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
