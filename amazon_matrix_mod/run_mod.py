#!/usr/bin/env python3
"""run_mod.py —— 竞品矩阵 MOD 管道 CLI + Agent 嵌入入口。

流程（确定性数据管道 + LLM 仅做 4 区解读）：
  fetch（适配器） → normalize/metrics → zoning 4 区 → llm 解读 → 静态 PNG + ECharts HTML
  → CSV/MD/JSON 落盘 → 返回 CompetitorMatrix 兼容 dict

CLI:
    python run_mod.py --keyword "wireless mouse" --top-n 8 --source rainforest
    python run_mod.py --keyword "wireless mouse" --source mock            # 离线开发
    python run_mod.py --reuse outputs/raw/rainforest_*.json               # 复用存档
    python run_mod.py --skip-llm                                          # 跳过 LLM 解读

Studio 嵌入:
    from amazon_matrix_mod.run_mod import run_pipeline
    data = run_pipeline(keyword=..., product_id=..., ...)
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys
import time
from datetime import datetime, timezone

import pandas as pd

from amazon_matrix_mod.adapters import get_fetcher
from amazon_matrix_mod import llm_interpret, plot_interactive, plot_static, storage, zoning
from amazon_matrix_mod.metrics import derive_metrics
from amazon_matrix_mod.adapters.rainforest import _iter_products, fetch_reviews

OUT_DIR_DEFAULT = os.environ.get("QX_OUTPUT_DIR", os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs"))


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_reuse(paths: list[str]) -> list[dict]:
    """复用 P1 存档（keepa_*/rainforest_* JSON 的 parsed 数组）。"""
    rows: list[dict] = []
    for pattern in paths:
        for path in glob.glob(pattern) if "*" in pattern else [pattern]:
            with open(path, encoding="utf-8") as f:
                saved = json.load(f)
            rows.extend(saved.get("parsed") or [])
    return rows


def run_pipeline(keyword: str, top_n: int = 50, our_asin: str | None = None,
                 marketplace: str = "amazon.com", source: str = "rainforest",
                 reuse: list[str] | None = None, out_dir: str | None = None,
                 product_id: str | None = None, skip_llm: bool = False,
                 sort_by: str | None = None, exclude_sponsored: bool = True,
                 market_context: str = "", progress=None,
                 reviews_top_n: int = 3, reviews_pages: int = 2,
                 full: bool = False, with_visuals: bool = False) -> dict:
    """完整管道。返回 CompetitorMatrix 兼容 dict；产物落 out_dir（默认 outputs/mod_<kw>_<ts>）。

    注：studio_assets 落盘路径由调用方控制（product_id 时默认
    {OUT_DIR_DEFAULT}/studio_assets/{product_id}/competitor_matrix/）。
    """
    t0 = time.time()
    fetched_at = _utcnow()
    search_raw = None
    products_raw: dict[str, dict] = {}
    reviews_raw: dict[str, list[dict]] = {}

    # 1. 采集（全量原始数据落盘）
    if reuse:
        rows = _load_reuse(reuse)
        credits = None
        print(f"[采集] 复用存档 {len(rows)} 行")
    else:
        fetcher = get_fetcher(source)
        if source == "rainforest":
            candidates, rows, products_raw = [], [], {}
            for row, raw in _iter_products(keyword, top_n, sort_by, exclude_sponsored,
                                           None, progress):
                rows.append(row)
                products_raw[row["asin"]] = raw
            credits = 1 + len(rows)  # search 1 + product N（实测口径）
            print(f"[采集] {source} 获取 {len(rows)} 个竞品（credits≈{credits}）")
        else:
            rows = fetcher(keyword, limit=top_n, sort_by=sort_by,
                           exclude_sponsored=exclude_sponsored, progress=progress)
            credits = 1 + len(rows)
            print(f"[采集] {source} 获取 {len(rows)} 个竞品（credits≈{credits}）")
    if not rows:
        raise RuntimeError("未获取到任何竞品数据")

    # 2. 派生指标
    rows = [derive_metrics(r) for r in rows]

    # 3. 分区
    df = pd.DataFrame(rows)
    df = zoning.classify_zones(df)
    rules = dict(df.attrs.get("zoning_rules", {}))
    summary = zoning.zone_summary(df)
    print(f"[分区] {summary}")

    # 4. 评论分页（第 7 章素材，默认 Top3 × 2 页 = 6 credits 控制）
    if source == "rainforest" and not reuse and reviews_pages > 0:
        top_asins = [r["asin"] for r in
                     sorted(rows, key=lambda r: -(r.get("est_monthly_sales") or 0))[:reviews_top_n]]
        for asin in top_asins:
            try:
                rv = fetch_reviews(asin, pages=reviews_pages)
                if rv:
                    reviews_raw[asin] = rv
                    print(f"[评论] {asin} {len(rv)} 条（{reviews_pages} 页）")
            except Exception as exc:  # noqa: BLE001
                print(f"[评论] {asin} 失败: {str(exc)[:80]}")

    # 4b. 数据资产化落盘（data/）
    if out_dir is None:
        if product_id:
            out_dir = os.path.join(OUT_DIR_DEFAULT, "studio_assets",
                                   product_id, "competitor_matrix")
        else:
            ts = time.strftime("%Y%m%d_%H%M%S")
            out_dir = os.path.join(OUT_DIR_DEFAULT, f"mod_{keyword.replace(' ', '_')}_{ts}")
    os.makedirs(out_dir, exist_ok=True)
    data_dir = storage.task_data_dir(out_dir)
    storage.save_manifest(data_dir, {
        "keyword": keyword, "marketplace": marketplace, "our_asin": our_asin,
        "source": source, "top_n": len(rows), "credits": credits,
        "fetched_at": fetched_at, "reviews_top_n": reviews_top_n,
        "reviews_pages": reviews_pages,
    })
    if source == "rainforest" and not reuse:
        try:
            import requests as _rq
            sr = _rq.get("https://api.rainforestapi.com/request", params={
                "api_key": os.environ.get("RAINFOREST_API_KEY", ""),
                "type": "search", "amazon_domain": "amazon.com",
                "search_term": keyword, "exclude_sponsored": "true" if exclude_sponsored else "false",
            }, timeout=60).json()
            search_raw = sr
        except Exception:  # noqa: BLE001 —— search_raw 缺失不阻塞
            pass
    storage.save_search_raw(data_dir, search_raw)
    for row in rows:
        if row["asin"] in products_raw:
            storage.save_product_raw(data_dir, row["asin"], products_raw[row["asin"]])
        storage.cache_image(data_dir, row["asin"], row.get("main_image_url"))
    for asin, rv in reviews_raw.items():
        storage.save_reviews_raw(data_dir, asin, rv)
    parquet_path, csv_path = storage.save_wide_table(data_dir, df)
    print(f"[存储] data/ 已落盘（{len(rows)} ASIN 全量原始 + 宽表 + 主图缓存）")

    # 5. LLM 4 区解读（失败即报错，已确认策略）
    interpretation = {}
    if not skip_llm:
        samples = {z: zoning.zone_samples(df, z) for z in
                   ("price_gap", "value_opportunity", "demand_heat", "red_ocean")}
        interpretation = llm_interpret.interpret_zones(
            rules, samples, keyword=keyword, marketplace=marketplace,
            our_asin=our_asin, market_context=market_context)
        print(f"[解读] {interpretation.get('verdict', '')}")

    # 6. 图表（主图缩略图优先复用 image_cache）
    png_path = plot_static.render_static_png(
        df, interpretation, os.path.join(out_dir, "mod_report.png"),
        keyword, marketplace, fetched_at, our_asin=our_asin, credits=credits,
        image_cache_dir=data_dir)
    html_path = plot_interactive.render_interactive_html(
        df, interpretation, os.path.join(out_dir, "mod_report.html"),
        keyword, marketplace, fetched_at, our_asin=our_asin,
        image_cache_dir=data_dir)
    print(f"[产物] {png_path}\n[产物] {html_path}")

    # 7. CSV / MD / JSON
    csv_path = os.path.join(out_dir, "data.csv")
    csv_cols = ["asin", "title", "brand", "current_price", "rating", "review_count",
                "est_monthly_sales", "recent_sales_raw", "bsr", "bsr_category",
                "is_fba", "seller_type", "zone", "main_image_url", "url"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=csv_cols, extrasaction="ignore")
        w.writeheader()
        for r in df.to_dict("records"):
            r["is_ours"] = bool(our_asin and r.get("asin") == our_asin)
            w.writerow(r)

    md_path = os.path.join(out_dir, "competitor_matrix.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(_to_markdown(df, interpretation, rules, keyword, marketplace,
                             fetched_at, png_path, html_path, csv_path))

    # 8. 结果对象（PriceCompetitorMatrix 兼容）
    products = []
    for r in df.to_dict("records"):
        products.append({
            "asin": r.get("asin"), "title": r.get("title") or "",
            "brand": r.get("brand"), "main_image_url": r.get("main_image_url"),
            "current_price": r.get("current_price"), "rating": r.get("rating"),
            "review_count": r.get("review_count"),
            "est_monthly_sales": r.get("est_monthly_sales"),
            "bsr": r.get("bsr"), "bsr_category": r.get("bsr_category"),
            "seller_type": r.get("seller_type"), "is_fba": bool(r.get("is_fba")),
            "zone": r.get("zone") or "neutral",
        })
    artifacts = {
        "png": os.path.join("studio_assets", product_id, "competitor_matrix", "mod_report.png")
        if product_id else png_path,
        "html": os.path.join("studio_assets", product_id, "competitor_matrix", "mod_report.html")
        if product_id else html_path,
        "csv": os.path.join("studio_assets", product_id, "competitor_matrix", "data.csv")
        if product_id else csv_path,
        "markdown": os.path.join("studio_assets", product_id, "competitor_matrix", "competitor_matrix.md")
        if product_id else md_path,
    }
    result = {
        "keyword": keyword,
        "marketplace": marketplace,
        "our_asin": our_asin,
        "products": products,
        "zoning_rules": rules,
        "llm_interpretation": interpretation,
        "artifacts_paths": artifacts,
        "fetched_at": fetched_at,
        "cost_estimate": {
            "rainforest_credits": credits,
            "llm_tokens": {},
            "elapsed_sec": round(time.time() - t0, 1),
        },
    }
    with open(os.path.join(out_dir, "zoning.json"), "w", encoding="utf-8") as f:
        json.dump({"zoning_rules": rules, "llm_interpretation": interpretation,
                   "zone_summary": summary, "cost": result["cost_estimate"],
                   "fetched_at": fetched_at}, f, ensure_ascii=False, indent=1)

    # 完整 MOD 增强（14 章 + M3 + 视觉 + 海报/PDF）
    if full:
        extra = _enhance_full(out_dir, df, products_raw, search_raw, reviews_raw,
                              interpretation, rules, keyword, marketplace,
                              fetched_at, our_asin, credits, with_visuals)
        result["full"] = extra

    print(f"[完成] {time.time() - t0:.1f}s ｜ 产物目录: {out_dir}")
    return result


def _to_markdown(df, interpretation, rules, keyword, marketplace,
                 fetched_at, png_path, html_path, csv_path) -> str:
    out = ["# 竞品矩阵（数据驱动 MOD 报告）", ""]
    out += [f"> 主关键词：{keyword} ｜ 站点：{marketplace} ｜ 抓取时间：{fetched_at}", ""]
    out += ["## 4 区一句话解读", ""]
    for k, label in zoning.ZONE_LABELS.items():
        if k == "neutral":
            continue
        out += [f"- **{label}**：{interpretation.get(k, '—')}"]
    out += [f"- **我方定位**：{interpretation.get('verdict', '—')}", ""]
    out += ["## 产物文件", ""]
    out += [f"- 静态 PNG：`{png_path}`", f"- 交互 HTML：`{html_path}`", f"- 数据 CSV：`{csv_path}`", ""]
    out += ["## 分区阈值", ""]
    for zone, rule in rules.items():
        out += [f"- **{zoning.ZONE_LABELS.get(zone, zone)}**：{rule}"]
    out += [""]
    out += ["## 竞品明细", ""]
    out += ["| ASIN | 标题 | 价格$ | 评分 | 评论数 | 月销估算 | BSR | 分区 |", "|---|---|---|---|---|---|---|---|"]
    for r in df.to_dict("records"):
        out.append(f"| {r.get('asin')} | {str(r.get('title') or '')[:40]} | "
                   f"{r.get('current_price')} | {r.get('rating')} | {r.get('review_count')} | "
                   f"{r.get('est_monthly_sales')} | {r.get('bsr')} | {zoning.ZONE_LABELS.get(r.get('zone'), r.get('zone'))} |")
    out += [""]
    out += ["## 数据溯源", ""]
    out += ["- 数据源：Rainforest API（search 关键词发现 + product 详情）"]
    out += ["- 月销估算：Amazon 官方 recent_sales 口径（\"bought in past month\"）解析，缺失回退 BSR 系数"]
    out += [f"- 抓取时间：{fetched_at}", ""]
    return "\n".join(out).strip() + "\n"


def _enhance_full(out_dir: str, df: pd.DataFrame, products_raw: dict,
                  search_raw: dict | None, reviews_raw: dict,
                  interpretation: dict, rules: dict, keyword: str,
                  marketplace: str, fetched_at: str, our_asin: str | None,
                  credits: int | None, with_visuals: bool) -> dict:
    """完整 MOD 增强（--full）：章节引擎 + M3 洞察 + image-01 视觉 + 海报/封面/PDF。"""
    from amazon_matrix_mod import compose, m3_client
    from amazon_matrix_mod.chapters import render_all, render_full_md
    from amazon_matrix_mod.gen_visual import generate_visuals

    data_dir = storage.task_data_dir(out_dir)
    chapters_dir = os.path.join(out_dir, "chapters")
    visuals_dir = os.path.join(out_dir, "visuals")

    # 1. 章节引擎（14 章）
    chapters = render_all(df, products_raw, search_raw, reviews_raw,
                          chapters_dir, interpretation, rules)
    print(f"[章节] {len(chapters)} 章渲染完成")

    # 2. image-01 视觉（增强层，失败降级）
    visuals = {"background": None, "cover": None, "zones": {}}
    if with_visuals:
        try:
            visuals = generate_visuals(keyword, visuals_dir)
            print(f"[视觉] background={'✓' if visuals['background'] else '✗'} "
                  f"cover={'✓' if visuals['cover'] else '✗'} "
                  f"zones={sum(1 for v in visuals['zones'].values() if v)}/4")
        except Exception as exc:  # noqa: BLE001
            print(f"[视觉] 生成失败（降级）: {str(exc)[:100]}")

    # 3. M3 图审（读 1920 主海报）
    m3_insights = {"assess": "", "insights": [], "improvements": []}
    chart_1920 = os.path.join(out_dir, "mod_report.png")
    data_summary = (f"keyword={keyword}, N={len(df)}, "
                    f"价格范围 ${df['current_price'].min():.2f}-${df['current_price'].max():.2f}, "
                    f"zone分布={zoning.zone_summary(df)}")
    try:
        m3_insights = m3_client.audit_chart(chart_1920, data_summary)
        if m3_insights.get("insights"):
            print(f"[M3] 图审 {len(m3_insights['insights'])} 条洞察")
    except Exception as exc:  # noqa: BLE001
        print(f"[M3] 图审失败（降级）: {str(exc)[:100]}")

    # 4. M3 评论聚类深化（覆盖第 7 章结论）
    all_reviews = [r for rv in reviews_raw.values() for r in rv]
    if all_reviews:
        try:
            clustered = m3_client.cluster_reviews(all_reviews)
            if clustered:
                ch7 = next((c for c in chapters if c["num"] == 7), None)
                if ch7:
                    extra = []
                    for k, label in (("pain_points", "痛点"), ("opportunities", "机会"),
                                     ("strengths", "优势")):
                        for item in (clustered.get(k) or [])[:3]:
                            extra.append(f"{label}：{item}")
                    ch7["conclusion"].extend(extra)
                    ch7["md"] += "\n### M3 深化聚类\n" + "\n".join(f"- {e}" for e in extra) + "\n"
                print(f"[M3] 评论聚类 {len(clustered.get('topics', []))} 主题")
        except Exception as exc:  # noqa: BLE001
            print(f"[M3] 评论聚类失败（降级）: {str(exc)[:100]}")

    # 5. 执行摘要（M3 优先，失败降级为确定性汇总）
    exec_summary = ""
    try:
        exec_summary = m3_client.executive_summary(chapters, keyword)
    except Exception as exc:  # noqa: BLE001
        print(f"[M3] 执行摘要失败（降级）: {str(exc)[:100]}")
    if not exec_summary:
        parts = [c for ch in chapters for c in (ch.get("conclusion") or [])[:1]][:5]
        exec_summary = "市场要点：" + "；".join(parts)[:180] if parts else ""
    if exec_summary:
        ch1 = next((c for c in chapters if c["num"] == 1), None)
        if ch1:
            ch1["conclusion"] = [exec_summary]
            ch1["md"] = "## 1. 执行摘要\n\n" + exec_summary + "\n"
        print("[摘要] 执行摘要生成")

    # 6. 高清矩阵图 + 海报合成
    matrix_2x = os.path.join(out_dir, "matrix_2x.png")
    from amazon_matrix_mod.plot_static import render_matrix_only
    render_matrix_only(df, matrix_2x, our_asin=our_asin, image_cache_dir=data_dir)
    poster = compose.compose_poster(
        matrix_2x, interpretation, m3_insights, exec_summary,
        keyword, marketplace, fetched_at, len(df), credits,
        visuals.get("background"), os.path.join(out_dir, "mod_report_2x.png"),
        zone_icons=visuals.get("zones"))
    cover = compose.compose_cover(keyword, visuals.get("cover"),
                                  os.path.join(out_dir, "mod_cover.png"), marketplace)
    insights_page = compose.compose_insights_page(
        m3_insights, os.path.join(out_dir, "mod_insights.png"), keyword)
    print("[合成] 主海报 3840×2160 + 封面 + 洞察页")

    # 7. 完整 14 章 md
    full_md = render_full_md(chapters, keyword, marketplace, fetched_at)
    md_path = os.path.join(out_dir, "competitor_matrix.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(full_md)
    print(f"[报告] 完整 14 章 Markdown -> {md_path}")

    # 8. 多页 PDF
    pdf_pages = [p for p in (cover, poster, insights_page) if p and os.path.isfile(p)]
    for ch in chapters:
        for img in ch.get("images", [])[:2]:
            p = os.path.join(out_dir, img) if not os.path.isabs(img) else img
            if os.path.isfile(p):
                pdf_pages.append(p)
    pdf_path = os.path.join(out_dir, "mod_report.pdf")
    try:
        compose.compose_pdf(pdf_pages, pdf_path)
        print(f"[PDF] {pdf_path}（{len(pdf_pages)} 页）")
    except Exception as exc:  # noqa: BLE001
        print(f"[PDF] 失败: {str(exc)[:100]}")

    # 9. 追加 M3/视觉到结果
    return {"m3_insights": m3_insights, "chapters": len(chapters),
            "executive_summary": exec_summary,
            "artifacts_full": {
                "poster_2x": os.path.join(out_dir, "mod_report_2x.png"),
                "cover": os.path.join(out_dir, "mod_cover.png"),
                "insights": os.path.join(out_dir, "mod_insights.png"),
                "pdf": os.path.join(out_dir, "mod_report.pdf"),
                "chapters": chapters_dir,
            }}


def main():
    ap = argparse.ArgumentParser(description="竞品矩阵 MOD 管道")
    ap.add_argument("--keyword", help="主关键词（核心：关键词→搜索→竞品）")
    ap.add_argument("--top-n", type=int, default=50, help="竞品数量（测试建议 ≤8 省 credits）")
    ap.add_argument("--our-asin", help="我方 ASIN（图中 ★ 标注）")
    ap.add_argument("--source", default="rainforest", choices=("rainforest", "mock"))
    ap.add_argument("--reuse", nargs="*", help="复用 P1 存档路径（跳过 API）")
    ap.add_argument("--out", help="输出目录（默认 outputs/mod_<kw>_<ts>）")
    ap.add_argument("--product-id", help="Studio 任务 ID（落 studio_assets）")
    ap.add_argument("--skip-llm", action="store_true", help="跳过 LLM 解读")
    ap.add_argument("--sort-by", help="search 排序（price_low_to_high 等）")
    ap.add_argument("--include-sponsored", action="store_true")
    ap.add_argument("--reviews-top-n", type=int, default=3, help="评论分页 ASIN 数（第7章素材，控制 credits）")
    ap.add_argument("--reviews-pages", type=int, default=2, help="每 ASIN 评论页数（1页=1 credit）")
    ap.add_argument("--no-reviews", action="store_true", help="跳过评论分页采集")
    ap.add_argument("--full", action="store_true", help="完整 MOD：14 章 + M3 洞察 + 海报/封面/PDF")
    ap.add_argument("--visuals", action="store_true", help="image-01 生成背景/封面/插画（消耗生图额度）")
    args = ap.parse_args()
    if not args.keyword and not args.reuse:
        ap.error("需要 --keyword（或 --reuse 存档）")

    run_pipeline(
        keyword=args.keyword or "keyword_from_archive",
        top_n=args.top_n,
        our_asin=args.our_asin,
        source=args.source,
        reuse=args.reuse,
        out_dir=args.out,
        product_id=args.product_id,
        skip_llm=args.skip_llm,
        sort_by=args.sort_by,
        exclude_sponsored=not args.include_sponsored,
        reviews_top_n=0 if args.no_reviews else args.reviews_top_n,
        reviews_pages=args.reviews_pages,
        full=args.full,
        with_visuals=args.visuals,
    )


if __name__ == "__main__":
    main()
