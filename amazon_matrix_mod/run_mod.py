#!/usr/bin/env python3
"""run_mod.py —— 竞品矩阵 MOD 管道 CLI + Agent 嵌入入口。

流程（确定性数据管道 + LLM 增强）：
  fetch（适配器） → normalize/metrics → zoning 4 区 → DeepSeek 解读
  → 核心矩阵图 matrix_chart.svg/png → CSV/MD/JSON 落盘
  → full：14 章（SVG 图表）→ image-01 视觉 → M3 聚类/摘要
        → PPT（ppt-master svg_to_pptx）→ M3 审图回环 → competitor_matrix.pptx

产物（full）：
  competitor_matrix.md / competitor_matrix.pptx / matrix_chart.svg(+png)
  zoning.json / data.csv / chapters/*.svg / visuals/ / data/ / deck_audit.json

CLI:
    python run_mod.py --keyword "wireless mouse" --top-n 8 --source rainforest
    python run_mod.py --keyword "wireless mouse" --source mock            # 离线开发
    python run_mod.py --reuse outputs/mod_xxx/data                       # 复用存档目录（0 credit）
    python run_mod.py --skip-llm                                         # 跳过 LLM 解读

Studio 嵌入:
    from amazon_matrix_mod.run_mod import run_pipeline
    data = run_pipeline(keyword=..., product_id=..., full=True, ...)
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
from amazon_matrix_mod import llm_interpret, storage, zoning
from amazon_matrix_mod.metrics import derive_metrics
from amazon_matrix_mod.adapters.rainforest import _iter_products, fetch_reviews

OUT_DIR_DEFAULT = os.environ.get("QX_OUTPUT_DIR", os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs"))


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_reuse(paths: list[str]) -> tuple[list[dict], dict]:
    """复用存档。支持两种形态：

    1. 目录（推荐，即历史任务的 data/ 目录）：products/{ASIN}.json +
       search_raw.json + reviews/{ASIN}.json 全套复用（0 credit 回放）
    2. 单文件（P1 存档 JSON 的 parsed 数组，兼容旧行为）

    返回 (rows, extra)，extra={products_raw, search_raw, reviews_raw}。
    """
    rows: list[dict] = []
    extra: dict = {"products_raw": {}, "search_raw": None, "reviews_raw": {}}
    for pattern in paths:
        for path in (glob.glob(pattern) if "*" in pattern else [pattern]):
            if os.path.isdir(path):
                from amazon_matrix_mod.adapters.rainforest import product_from_raw
                for pf in sorted(glob.glob(os.path.join(path, "products", "*.json"))):
                    with open(pf, encoding="utf-8") as f:
                        raw = json.load(f)
                    asin = (raw.get("asin") or os.path.basename(pf)[:-5])
                    extra["products_raw"][asin] = raw
                    rows.append(product_from_raw(raw, asin))
                sr = os.path.join(path, "search_raw.json")
                if os.path.isfile(sr):
                    with open(sr, encoding="utf-8") as f:
                        extra["search_raw"] = json.load(f)
                for rf in glob.glob(os.path.join(path, "reviews", "*.json")):
                    with open(rf, encoding="utf-8") as f:
                        rv = json.load(f)
                    if rv.get("reviews"):
                        extra["reviews_raw"][rv.get("asin") or
                                             os.path.basename(rf)[:-5]] = rv["reviews"]
            else:
                with open(path, encoding="utf-8") as f:
                    saved = json.load(f)
                rows.extend(saved.get("parsed") or [])
    return rows, extra


def run_pipeline(keyword: str, top_n: int = 50, our_asin: str | None = None,
                 marketplace: str = "amazon.com", source: str = "rainforest",
                 reuse: list[str] | None = None, out_dir: str | None = None,
                 product_id: str | None = None, skip_llm: bool = False,
                 sort_by: str | None = None, exclude_sponsored: bool = True,
                 market_context: str = "", progress=None,
                 reviews_top_n: int = 3, reviews_pages: int = 2,
                 full: bool = False, with_visuals: bool = False,
                 theme_id: str | None = None) -> dict:
    """完整管道。返回 CompetitorMatrix 兼容 dict；产物落 out_dir（默认 outputs/mod_<kw>_<ts>）。

    注：studio_assets 落盘路径由调用方控制（product_id 时默认
    {OUT_DIR_DEFAULT}/studio_assets/{product_id}/competitor_matrix/）。
    """
    t0 = time.time()
    fetched_at = _utcnow()
    search_raw = None
    products_raw: dict[str, dict] = {}
    reviews_raw: dict[str, list[dict]] = {}

    # 1. 采集（全量原始数据落盘；search_raw 在采集内捕获，不重复请求）
    if reuse:
        rows, reuse_extra = _load_reuse(reuse)
        products_raw.update(reuse_extra["products_raw"])
        search_raw = reuse_extra["search_raw"]
        reviews_raw.update(reuse_extra["reviews_raw"])
        credits = None
        print(f"[采集] 复用存档 {len(rows)} 行（products={len(products_raw)} "
              f"reviews={len(reviews_raw)} search_raw={'✓' if search_raw else '✗'}）")
    else:
        fetcher = get_fetcher(source)
        if source == "rainforest":
            candidates, rows = [], []
            fetch_meta: dict = {}
            for row, raw in _iter_products(keyword, top_n, sort_by, exclude_sponsored,
                                           None, progress, meta=fetch_meta):
                rows.append(row)
                products_raw[row["asin"]] = raw
            search_raw = fetch_meta.get("search_raw") or None
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
        "reviews_pages": reviews_pages, "reuse": bool(reuse),
    })
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

    # 6. 核心矩阵图（SVG 确定性渲染 + PNG 预览尽力而为）
    matrix_svg = _render_matrix_chart(df, out_dir, keyword, marketplace,
                                      fetched_at, our_asin=our_asin,
                                      image_cache_dir=data_dir)
    matrix_png = _rasterize_best_effort(matrix_svg)
    print(f"[产物] {matrix_svg}" + (f"\n[产物] {matrix_png}" if matrix_png else ""))

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
                             fetched_at, matrix_svg, csv_path))

    # 8. 结果对象（PriceCompetitorMatrix 兼容）
    def _clean_num(v):
        """NaN → None（pydantic finite_number 校验拒绝 NaN；mock/缺失数据常见）。"""
        if isinstance(v, float) and v != v:
            return None
        return v

    def _clean_str(v):
        if v is None or (isinstance(v, float) and v != v):
            return None
        return v if isinstance(v, str) else _clean_num(v)

    products = []
    for r in df.to_dict("records"):
        products.append({
            "asin": r.get("asin"), "title": _clean_str(r.get("title")) or "",
            "brand": _clean_str(r.get("brand")),
            "main_image_url": _clean_str(r.get("main_image_url")),
            "current_price": _clean_num(r.get("current_price")),
            "rating": _clean_num(r.get("rating")),
            "review_count": _clean_num(r.get("review_count")),
            "est_monthly_sales": _clean_num(r.get("est_monthly_sales")),
            "bsr": _clean_num(r.get("bsr")),
            "bsr_category": _clean_str(r.get("bsr_category")),
            "seller_type": _clean_str(r.get("seller_type")),
            "is_fba": bool(r.get("is_fba")) if r.get("is_fba") == r.get("is_fba") else False,
            "zone": r.get("zone") or "neutral",
        })
    base_rel = os.path.join("studio_assets", product_id, "competitor_matrix") \
        if product_id else out_dir
    artifacts = {
        "markdown": _rel(base_rel, out_dir, md_path),
        "csv": _rel(base_rel, out_dir, csv_path),
        "matrix_chart": _rel(base_rel, out_dir, matrix_svg),
        "zoning": _rel(base_rel, out_dir, os.path.join(out_dir, "zoning.json")),
    }
    if matrix_png:
        artifacts["matrix_chart_png"] = _rel(base_rel, out_dir, matrix_png)
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
    result = _to_native(result)
    with open(os.path.join(out_dir, "zoning.json"), "w", encoding="utf-8") as f:
        json.dump({"zoning_rules": rules, "llm_interpretation": interpretation,
                   "zone_summary": summary, "cost": result["cost_estimate"],
                   "fetched_at": fetched_at}, f, ensure_ascii=False, indent=1)

    # 完整 MOD 增强（14 章 + M3 + 视觉 + PPT）
    if full:
        extra = _enhance_full(out_dir, df, products_raw, search_raw, reviews_raw,
                              interpretation, rules, keyword, marketplace,
                              fetched_at, our_asin, credits, with_visuals,
                              matrix_svg, matrix_png, theme_id=theme_id)
        result["full"] = extra
        result["artifacts_paths"]["pptx"] = _rel(
            base_rel, out_dir, extra.get("artifacts_full", {}).get("pptx")
            or os.path.join(out_dir, "competitor_matrix.pptx"))
        if extra.get("artifacts_full", {}).get("matrix_chart_png"):
            result["artifacts_paths"]["matrix_chart_png"] = _rel(
                base_rel, out_dir, extra["artifacts_full"]["matrix_chart_png"])

    print(f"[完成] {time.time() - t0:.1f}s ｜ 产物目录: {out_dir}")
    return result


def _to_native(obj):
    """深度转换为 Python 原生类型（numpy 标量 → float/int/bool）。

    Celery msgpack 结果序列化与 LangGraph checkpoint 均不接受 numpy 标量
    （np.float64 等）；zoning 分位数等产品会携带，统一在出口清洗。
    """
    import numpy as _np
    if isinstance(obj, dict):
        return {str(k): _to_native(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_native(v) for v in obj]
    if isinstance(obj, _np.floating):
        return float(obj)
    if isinstance(obj, _np.integer):
        return int(obj)
    if isinstance(obj, _np.bool_):
        return bool(obj)
    return obj


def _rel(base_rel: str, out_dir: str, path: str | None) -> str:
    """产物路径 → 对外相对路径（studio 模式相对 OUTPUT_DIR，CLI 模式原样）。"""
    if not path:
        return ""
    if base_rel != out_dir:  # studio 模式
        return os.path.join(base_rel, os.path.relpath(path, out_dir))
    return path


def _render_matrix_chart(df: pd.DataFrame, out_dir: str, keyword: str,
                         marketplace: str, fetched_at: str,
                         our_asin: str | None, image_cache_dir: str) -> str:
    """核心矩阵图（SVG）：价格×月销对数轴 + 竞品主图缩略图 + 防重叠。"""
    from amazon_matrix_mod.svgcharts import charts
    from amazon_matrix_mod.svgcharts.svg import el, save, svg_document, text
    from amazon_matrix_mod.svgcharts.style import FONT_CHAIN

    root = svg_document(1280, 720)
    text(root, 40, 44, f"价格 × 月销竞品矩阵 — {keyword}", size=22,
         fill="#101820", weight="bold", family=FONT_CHAIN)
    text(root, 40, 70, f"站点 {marketplace} ｜ 抓取 {fetched_at} ｜ "
         f"缩略图=竞品主图，边框色=分区，尺寸∝评论数", size=12,
         fill="#5C6068", family=FONT_CHAIN)
    g = el(root, "g")
    charts.matrix_chart(g, 24, 88, 1232, 600, df=df, our_asin=our_asin,
                        image_cache_dir=image_cache_dir, uid="mod")
    path = os.path.join(out_dir, "matrix_chart.svg")
    save(root, path)
    return path


def _rasterize_best_effort(svg_path: str) -> str | None:
    """SVG → PNG（Chromium）。无 playwright/失败时返回 None（不阻塞）。"""
    try:
        from amazon_matrix_mod.svgcharts.rasterize import svg_to_png
        png = svg_path[:-4] + ".png"
        return svg_to_png(svg_path, png, width=1280)
    except Exception:  # noqa: BLE001
        return None


def _to_markdown(df, interpretation, rules, keyword, marketplace,
                 fetched_at, matrix_svg, csv_path) -> str:
    out = ["# 竞品矩阵（数据驱动 MOD 报告）", ""]
    out += [f"> 主关键词：{keyword} ｜ 站点：{marketplace} ｜ 抓取时间：{fetched_at}", ""]
    out += [f"![核心矩阵图](matrix_chart.svg)", ""]
    out += ["## 4 区一句话解读", ""]
    for k, label in zoning.ZONE_LABELS.items():
        if k == "neutral":
            continue
        out += [f"- **{label}**：{interpretation.get(k, '—')}"]
    out += [f"- **我方定位**：{interpretation.get('verdict', '—')}", ""]
    out += ["## 产物文件", ""]
    out += [f"- 核心矩阵图：`{os.path.basename(matrix_svg)}`",
            f"- 数据 CSV：`{os.path.basename(csv_path)}`", ""]
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


def _persist_deck_ctx(out_dir: str, ctx: dict, deck_result: dict) -> None:
    """持久化 deck 渲染输入（双管线合并时 PptDesignAgent 用主 deck 主题重渲染）。

    df/products_raw/search_raw 全量入 JSON（真实数据，不压缩），visuals 存
    相对 out_dir 路径，image_cache_dir 同理；合并侧用绝对路径还原。
    """
    import json as _json

    rel = lambda p: (os.path.relpath(p, out_dir) if p and os.path.isabs(p) else p)

    payload = {
        "df": ctx["df"].to_dict("records"),
        "interpretation": ctx.get("interpretation") or {},
        "rules": {k: (dict(v) if isinstance(v, dict) else v)
                  for k, v in (ctx.get("rules") or {}).items()},
        "chapters": [{"num": c.get("num"), "title": c.get("title"),
                      "conclusion": c.get("conclusion") or []}
                     for c in (ctx.get("chapters") or [])],
        "exec_summary": ctx.get("exec_summary") or "",
        "m3_insights": ctx.get("m3_insights") or {},
        "visuals": {
            "background": rel((ctx.get("visuals") or {}).get("background")),
            "cover": rel((ctx.get("visuals") or {}).get("cover")),
            "zones": {k: rel(v) for k, v in
                      ((ctx.get("visuals") or {}).get("zones") or {}).items()},
        },
        "keyword": ctx.get("keyword"), "marketplace": ctx.get("marketplace"),
        "fetched_at": ctx.get("fetched_at"), "credits": ctx.get("credits"),
        "our_asin": ctx.get("our_asin"),
        "image_cache_dir": rel(ctx.get("image_cache_dir")),
        "search_raw": ctx.get("search_raw"),
        "products_raw": ctx.get("products_raw") or {},
        "theme_id": (ctx.get("theme").id if ctx.get("theme") else None),
        "pages": deck_result.get("pages") or [],
    }
    path = os.path.join(out_dir, "ppt", "deck_ctx.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        _json.dump(payload, f, ensure_ascii=False, default=str)


def _reuse_visuals(visuals_dir: str) -> dict | None:
    """visuals/ 已有完整产物（background+cover）时复用，避免重复消耗生图额度。"""
    import glob as _glob

    def _find(stem: str) -> str | None:
        for cand in _glob.glob(os.path.join(visuals_dir, f"{stem}.*")):
            if os.path.getsize(cand) > 10000:
                return cand
        return None

    bg, cover = _find("background"), _find("cover")
    if not (bg and cover):
        return None
    zones = {}
    for zone in ("price_gap", "value_opportunity", "demand_heat", "red_ocean"):
        p = _find(f"zone_{zone}")
        if p:
            zones[zone] = p
    return {"background": bg, "cover": cover, "zones": zones}


def _enhance_full(out_dir: str, df: pd.DataFrame, products_raw: dict,
                  search_raw: dict | None, reviews_raw: dict,
                  interpretation: dict, rules: dict, keyword: str,
                  marketplace: str, fetched_at: str, our_asin: str | None,
                  credits: int | None, with_visuals: bool,
                  matrix_svg: str, matrix_png: str | None,
                  theme_id: str | None = None) -> dict:
    """完整 MOD 增强（--full）：14 章 + M3 洞察 + image-01 视觉 + PPT 构建。"""
    from amazon_matrix_mod import m3_client
    from amazon_matrix_mod.chapters import render_all, render_full_md
    from amazon_matrix_mod.gen_visual import generate_visuals
    from amazon_matrix_mod.deck.themes import Theme

    data_dir = storage.task_data_dir(out_dir)
    chapters_dir = os.path.join(out_dir, "chapters")
    visuals_dir = os.path.join(out_dir, "visuals")

    # 1. 章节引擎（14 章，SVG 图表）
    chapters = render_all(df, products_raw, search_raw, reviews_raw,
                          chapters_dir, interpretation, rules)
    print(f"[章节] {len(chapters)} 章渲染完成（SVG）")

    # 2. image-01 视觉（增强层，失败降级；已有产物直接复用避免重复耗额度）
    visuals = {"background": None, "cover": None, "zones": {}}
    if with_visuals:
        reused = _reuse_visuals(visuals_dir)
        if reused:
            visuals = reused
            print(f"[视觉] 复用已有 visuals/（background={'✓' if visuals['background'] else '✗'} "
                  f"cover={'✓' if visuals['cover'] else '✗'} "
                  f"zones={sum(1 for v in visuals['zones'].values() if v)}/4）")
        else:
            try:
                visuals = generate_visuals(keyword, visuals_dir)
                print(f"[视觉] background={'✓' if visuals['background'] else '✗'} "
                      f"cover={'✓' if visuals['cover'] else '✗'} "
                      f"zones={sum(1 for v in visuals['zones'].values() if v)}/4")
            except Exception as exc:  # noqa: BLE001
                print(f"[视觉] 生成失败（降级）: {str(exc)[:100]}")

    # 3. M3 图审（核心矩阵图 PNG；无 PNG 时跳过）
    m3_insights = {"assess": "", "insights": [], "improvements": []}
    audit_target = matrix_png or _rasterize_best_effort(matrix_svg)
    if audit_target:
        data_summary = (f"keyword={keyword}, N={len(df)}, "
                        f"价格范围 ${df['current_price'].min():.2f}-${df['current_price'].max():.2f}, "
                        f"zone分布={zoning.zone_summary(df)}")
        try:
            m3_insights = m3_client.audit_chart(audit_target, data_summary)
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

    # 6. PPT 构建（ppt-master svg_to_pptx + M3 审图回环；失败降级 md+SVG）
    deck_result: dict = {}
    pptx_path: str | None = None
    try:
        from amazon_matrix_mod.deck import build as deck_build
        from amazon_matrix_mod.deck import audit as deck_audit
        ctx = {
            "df": df, "interpretation": interpretation, "rules": rules,
            "chapters": chapters, "exec_summary": exec_summary,
            "m3_insights": m3_insights, "visuals": visuals,
            "keyword": keyword, "marketplace": marketplace,
            "fetched_at": fetched_at, "credits": credits, "our_asin": our_asin,
            "image_cache_dir": data_dir, "search_raw": search_raw,
            "products_raw": products_raw,
            "theme": Theme(theme_id) if theme_id else Theme("cyber-ivory-navy"),
        }
        deck_result = deck_build.build_deck(
            out_dir, ctx, audit_hook=deck_audit.audit_deck)
        pptx_path = deck_result.get("pptx")
        print(f"[PPT] {len(deck_result.get('pages') or [])} 页 → {pptx_path}")
        _persist_deck_ctx(out_dir, ctx, deck_result)
    except Exception as exc:  # noqa: BLE001 —— PPT 失败降级：md + SVG 仍完整
        print(f"[PPT] 构建失败（降级为 md+SVG）: {str(exc)[:160]}")

    # 7. 完整 14 章 md
    full_md = render_full_md(chapters, keyword, marketplace, fetched_at)
    md_path = os.path.join(out_dir, "competitor_matrix.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(full_md)
    print(f"[报告] 完整 14 章 Markdown -> {md_path}")

    # 8. 结果
    return {"m3_insights": m3_insights, "chapters": len(chapters),
            "executive_summary": exec_summary,
            "artifacts_full": {
                "pptx": pptx_path or "",
                "deck_pages": len(deck_result.get("pages") or []),
                "matrix_chart": matrix_svg,
                "matrix_chart_png": matrix_png,
                "chapters": chapters_dir,
            }}


def main():
    ap = argparse.ArgumentParser(description="竞品矩阵 MOD 管道")
    ap.add_argument("--keyword", help="主关键词（核心：关键词→搜索→竞品）")
    ap.add_argument("--top-n", type=int, default=20, help="竞品数量（search 1 + product N credits）")
    ap.add_argument("--our-asin", help="我方 ASIN（图中 ★ 标注）")
    ap.add_argument("--source", default="rainforest", choices=("rainforest", "mock"))
    ap.add_argument("--reuse", nargs="*", help="复用存档（data/ 目录或 P1 存档 JSON，跳过 API）")
    ap.add_argument("--out", help="输出目录（默认 outputs/mod_<kw>_<ts>）")
    ap.add_argument("--product-id", help="Studio 任务 ID（落 studio_assets）")
    ap.add_argument("--skip-llm", action="store_true", help="跳过 LLM 解读")
    ap.add_argument("--sort-by", help="search 排序（price_low_to_high 等）")
    ap.add_argument("--include-sponsored", action="store_true")
    ap.add_argument("--reviews-top-n", type=int, default=3, help="评论分页 ASIN 数（第7章素材，控制 credits）")
    ap.add_argument("--reviews-pages", type=int, default=2, help="每 ASIN 评论页数（1页=1 credit）")
    ap.add_argument("--no-reviews", action="store_true", help="跳过评论分页采集")
    ap.add_argument("--full", action="store_true", help="完整 MOD：14 章 + M3 洞察 + PPT")
    ap.add_argument("--visuals", action="store_true", help="image-01 生成封面/插画（消耗生图额度）")
    ap.add_argument("--theme", help="设计主题 id（THEME_PRESETS，默认 cyber-ivory-navy）")
    args = ap.parse_args()
    if not args.keyword and not args.reuse:
        ap.error("需要 --keyword（或 --reuse 存档）")

    keyword = args.keyword
    if not keyword and args.reuse:
        keyword = _reuse_keyword(args.reuse) or "keyword_from_archive"

    run_pipeline(
        keyword=keyword,
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
        theme_id=args.theme,
    )


def _reuse_keyword(paths: list[str]) -> str | None:
    """从存档目录的 manifest.json 读关键词（CLI 无 --keyword 时）。"""
    for pattern in paths:
        for path in (glob.glob(pattern) if "*" in pattern else [pattern]):
            mf = os.path.join(path, "manifest.json") if os.path.isdir(path) else None
            if mf and os.path.isfile(mf):
                try:
                    with open(mf, encoding="utf-8") as f:
                        return json.load(f).get("keyword")
                except Exception:  # noqa: BLE001
                    pass
    return None


if __name__ == "__main__":
    main()
