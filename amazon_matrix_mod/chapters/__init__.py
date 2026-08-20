"""章节引擎 —— 14 章完整 MOD 分析（P3.2）。

render_all(df, products_raw, search_raw, reviews_raw, out_dir, extra) -> list[dict]
每章返回 {num, title, conclusion[], images[], md}。
"""
from __future__ import annotations

import os

import pandas as pd

from amazon_matrix_mod.chapters import (
    ch02_market, ch03_price, ch04_demand, ch06_health, ch07_reviews, ch89_others,
)


def render_all(df: pd.DataFrame, products_raw: dict, search_raw: dict | None,
               reviews_raw: dict, out_dir: str,
               zone_interpretation: dict | None = None,
               zones_rules: dict | None = None) -> list[dict]:
    """渲染全部章节，返回章节列表（含 md 片段与图路径）。"""
    os.makedirs(out_dir, exist_ok=True)
    chapters: list[dict] = []

    chapters.append({"num": 1, "title": "执行摘要",
                     "conclusion": [], "images": [], "md": ""})  # 由 M3/汇总阶段填充
    chapters.append(ch02_market.analyze(df, search_raw, out_dir))
    chapters.append(ch03_price.analyze(df, out_dir))
    chapters.append(ch04_demand.analyze(df, out_dir))

    # 第 5 章：气泡矩阵 = 核心主图（matrix_chart.svg），由 run_mod 顶层生成
    chapters.append({"num": 5, "title": "竞品矩阵（核心图）",
                     "conclusion": [f"N={len(df)} 个竞品；4 区分布见分区引擎"],
                     "images": ["matrix_chart.svg"],
                     "md": "## 5. 竞品气泡矩阵\n\n见核心主图 `matrix_chart.svg`"
                           "（价格×月销对数轴，缩略图=竞品主图，边框色=分区，"
                           "我方产品金框高亮；PPT 版见 competitor_matrix.pptx）。\n"})

    chapters.append(ch06_health.analyze(df, products_raw, out_dir))
    chapters.append(ch07_reviews.analyze(df, reviews_raw, products_raw, out_dir))
    chapters.append(ch89_others.ch08_listing(df, products_raw, out_dir))
    chapters.append(ch89_others.ch09_variants(df, products_raw, out_dir))
    chapters.append(ch89_others.ch10_fulfillment(df, out_dir))
    chapters.append(ch89_others.ch11_ads(search_raw, out_dir))

    # 第 12 章：价格历史与趋势（P4 占位）
    chapters.append({"num": 12, "title": "价格历史与趋势",
                     "conclusion": ["当前为快照数据；P4 接入快照累积/Keepa MCP 后启用"],
                     "images": [], "md": "## 12. 价格历史与趋势\n\n（P4：快照累积后生成 90 天价格曲线）\n"})

    # 第 13 章：战略建议（4 区机会 + 解读）
    interp = zone_interpretation or {}
    md13 = ["## 13. 战略建议（4 区机会 + 定位）\n"]
    concl13 = []
    for zone, label in (("price_gap", "价格缺口区"), ("value_opportunity", "性价比机会区"),
                        ("demand_heat", "需求热度区"), ("red_ocean", "红海警示区")):
        txt = interp.get(zone, "—")
        concl13.append(f"{label}：{txt}")
        md13.append(f"- **{label}**：{txt}")
    if interp.get("verdict"):
        concl13.append(f"我方定位：{interp['verdict']}")
        md13.append(f"- **我方定位**：{interp['verdict']}")
    if zones_rules:
        md13.append("\n分区阈值：")
        for z, rule in zones_rules.items():
            md13.append(f"  - {z}: {rule}")
    chapters.append({"num": 13, "title": "战略建议", "conclusion": concl13,
                     "images": [], "md": "\n".join(md13) + "\n"})

    # 第 14 章：数据附录
    n_asin = len(df)
    chapters.append({"num": 14, "title": "数据附录",
                     "conclusion": [f"{n_asin} 个竞品，全量原始数据见 data/ 目录"],
                     "images": [], "md": _md_appendix(df)})
    return chapters


def _md_appendix(df: pd.DataFrame) -> str:
    out = ["## 14. 数据附录\n", "| ASIN | 标题 | 价格$ | 评分 | 评论数 | 月销估算 | BSR | 分区 |",
           "|---|---|---|---|---|---|---|---|"]
    for r in df.to_dict("records"):
        out.append(f"| {r.get('asin')} | {str(r.get('title') or '')[:36]} | "
                   f"{r.get('current_price')} | {r.get('rating')} | {r.get('review_count')} | "
                   f"{r.get('est_monthly_sales')} | {r.get('bsr')} | {r.get('zone')} |")
    out.append("")
    out.append("数据存储：`data/manifest.json`（溯源）/ `data/products/{ASIN}.json`（49 字段全量）/ "
               "`data/products.parquet`（宽表）/ `data/image_cache/`（主图缓存）")
    return "\n".join(out) + "\n"


def render_full_md(chapters: list[dict], keyword: str, marketplace: str,
                   fetched_at: str) -> str:
    """14 章 → 完整报告 Markdown（第 1 章执行摘要非空时置顶）。"""
    out = [f"# 竞品矩阵完整 MOD 分析报告 — {keyword}",
           "", f"> 站点：{marketplace} ｜ 抓取时间：{fetched_at}", ""]
    for ch in chapters:
        md = ch.get("md") or ""
        if not md:
            continue
        out.append(md)
    return "\n".join(out).strip() + "\n"
