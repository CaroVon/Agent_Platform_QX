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

    返回 (rows, extra)，extra={products_raw, search_raw, reviews_raw, pre_derived}。
    pre_derived=True 表示 rows 来自统一采集层的 rows.json（已派生指标，可直接进分区）。
    """
    rows: list[dict] = []
    extra: dict = {"products_raw": {}, "search_raw": None, "reviews_raw": {},
                   "pre_derived": False}
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
                # 归一化行存档优先（统一采集层 rows.json：mock 等无 raw 源也可 0-credit 回放）
                saved_rows = storage.load_rows(path)
                if saved_rows:
                    rows = saved_rows
                    extra["pre_derived"] = True
            else:
                with open(path, encoding="utf-8") as f:
                    saved = json.load(f)
                rows.extend(saved.get("parsed") or [])
    return rows, extra


def _read_archived_meta(data_dir: str) -> dict:
    """读取归档 manifest（回放/续跑时还原真实 fetched_at 与 credits，保数据溯源）。"""
    mf = os.path.join(data_dir, "manifest.json")
    if os.path.isfile(mf):
        try:
            with open(mf, encoding="utf-8") as f:
                return json.load(f)
        except Exception:  # noqa: BLE001 —— manifest 损坏不影响主流程
            return {}
    return {}


def collect_amazon_data(keyword: str, top_n: int = 20, marketplace: str = "amazon.com",
                        source: str = "rainforest", out_dir: str | None = None,
                        product_id: str | None = None, sort_by: str | None = None,
                        exclude_sponsored: bool = True, reviews_top_n: int = 3,
                        reviews_pages: int = 2, progress=None) -> tuple[dict, dict]:
    """统一采集入口（B/C 共享数据层）：fetch + 评论分页 + data/ 全量归档。

    供 Studio source_gathering 节点调用（与 Tavily 网络检索同阶段完成亚马逊采集）；
    后续 run_pipeline(reuse=[data_dir]) 以 0 credit 回放本函数归档的数据，
    两条分支（市场研究 / 竞品矩阵）共用同一份原始数据。

    Returns:
        (summary, payload)
        summary —— 轻量摘要（gate 展示 / state["amazon_collection"]）：
            keyword/marketplace/source/n_products/credits/fetched_at/price_range/
            rating_avg/reviews_count/zone_counts/top_asins/data_dir
        payload —— run_pipeline 直接消费的重负载（rows 已派生指标）：
            rows/products_raw/search_raw/reviews_raw/credits/fetched_at/out_dir
    """
    fetched_at = _utcnow()
    products_raw: dict[str, dict] = {}
    reviews_raw: dict[str, list[dict]] = {}
    search_raw = None

    if out_dir is None:
        if product_id:
            out_dir = os.path.join(OUT_DIR_DEFAULT, "studio_assets",
                                   product_id, "competitor_matrix")
        else:
            ts = time.strftime("%Y%m%d_%H%M%S")
            out_dir = os.path.join(OUT_DIR_DEFAULT, f"mod_{keyword.replace(' ', '_')}_{ts}")
    os.makedirs(out_dir, exist_ok=True)
    data_dir = storage.task_data_dir(out_dir)

    # 1. fetch（search_raw 在采集内捕获，不重复请求）
    if source == "rainforest":
        rows: list[dict] = []
        fetch_meta: dict = {}
        for row, raw in _iter_products(keyword, top_n, sort_by, exclude_sponsored,
                                       None, progress, meta=fetch_meta):
            rows.append(row)
            products_raw[row["asin"]] = raw
        search_raw = fetch_meta.get("search_raw") or None
        credits = 1 + len(rows)  # search 1 + product N（实测口径）
    else:
        fetcher = get_fetcher(source)
        rows = fetcher(keyword, limit=top_n, sort_by=sort_by,
                       exclude_sponsored=exclude_sponsored, progress=progress)
        credits = 1 + len(rows)
    if not rows:
        raise RuntimeError(f"未获取到任何竞品数据（keyword={keyword}, source={source}）")
    print(f"[采集] {source} 获取 {len(rows)} 个竞品（credits≈{credits}）")

    # 2. 派生指标（评论选择与摘要需要月销/分区；run_pipeline 回放时不再重复派生）
    metric_rows = [derive_metrics(r) for r in rows]

    # 3. 评论分页（Top 销量 ASIN；rainforest 限定）
    if source == "rainforest" and reviews_pages > 0:
        top_asins = [r["asin"] for r in
                     sorted(metric_rows, key=lambda r: -(r.get("est_monthly_sales") or 0))[:reviews_top_n]]
        for asin in top_asins:
            try:
                rv = fetch_reviews(asin, pages=reviews_pages)
                if rv:
                    reviews_raw[asin] = rv
                    print(f"[评论] {asin} {len(rv)} 条（{reviews_pages} 页）")
            except Exception as exc:  # noqa: BLE001
                print(f"[评论] {asin} 失败: {str(exc)[:80]}")

    # 4. 归档（manifest/search_raw/products/reviews/主图缓存；宽表由 run_pipeline 补齐）
    storage.save_manifest(data_dir, {
        "keyword": keyword, "marketplace": marketplace, "our_asin": None,
        "source": source, "top_n": len(rows), "credits": credits,
        "fetched_at": fetched_at, "reviews_top_n": reviews_top_n,
        "reviews_pages": reviews_pages, "reuse": False,
    })
    storage.save_search_raw(data_dir, search_raw)
    for row in rows:
        if row["asin"] in products_raw:
            storage.save_product_raw(data_dir, row["asin"], products_raw[row["asin"]])
        storage.cache_image(data_dir, row["asin"], row.get("main_image_url"))
    for asin, rv in reviews_raw.items():
        storage.save_reviews_raw(data_dir, asin, rv)
    storage.save_rows(data_dir, _to_native(metric_rows))
    # 5. 摘要（分区仅用于展示统计；run_pipeline 会正式重算并落盘 zoning.json）
    zone_counts: dict = {}
    try:
        sdf = zoning.classify_zones(pd.DataFrame(metric_rows))
        zone_counts = {str(k): int(v) for k, v in sdf["zone"].value_counts().items()}
    except Exception:  # noqa: BLE001 —— 分区失败不影响采集归档
        pass

    def _num(v):
        if v is None or (isinstance(v, float) and v != v):
            return None
        return round(float(v), 2) if isinstance(v, float) else v

    prices = [r.get("current_price") for r in metric_rows if r.get("current_price")]
    ratings = [r.get("rating") for r in metric_rows if r.get("rating")]
    top_rows = sorted(metric_rows, key=lambda r: -(r.get("est_monthly_sales") or 0))[:8]
    top_asins_summary = [{
        "asin": r.get("asin"), "title": (r.get("title") or "")[:80],
        "brand": r.get("brand"), "current_price": _num(r.get("current_price")),
        "rating": _num(r.get("rating")), "review_count": r.get("review_count"),
        "est_monthly_sales": r.get("est_monthly_sales"), "bsr": r.get("bsr"),
        "is_fba": bool(r.get("is_fba")), "seller_type": r.get("seller_type"),
        "zone": r.get("zone") or "neutral", "main_image_url": r.get("main_image_url"),
    } for r in top_rows]
    summary = _to_native({
        "keyword": keyword, "marketplace": marketplace, "source": source,
        "n_products": len(rows), "credits": credits, "fetched_at": fetched_at,
        "price_range": {"min": _num(min(prices)) if prices else None,
                         "max": _num(max(prices)) if prices else None,
                         "avg": _num(sum(prices) / len(prices)) if prices else None},
        "rating_avg": _num(sum(ratings) / len(ratings)) if ratings else None,
        "reviews_count": sum(len(rv) for rv in reviews_raw.values()),
        "zone_counts": zone_counts,
        "top_asins": top_asins_summary,
        "data_dir": data_dir, "out_dir": out_dir,
    })
    payload = {"rows": metric_rows, "products_raw": products_raw, "search_raw": search_raw,
               "reviews_raw": reviews_raw, "credits": credits,
               "fetched_at": fetched_at, "out_dir": out_dir}
    print(f"[采集] 统一采集完成：{len(rows)} 竞品 / {summary['reviews_count']} 条评论 "
          f"/ credits={credits} → {data_dir}")
    return summary, payload


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

    # 0. 输出目录（统一采集与回放共用同一目录解析）
    if out_dir is None:
        if product_id:
            out_dir = os.path.join(OUT_DIR_DEFAULT, "studio_assets",
                                   product_id, "competitor_matrix")
        else:
            ts = time.strftime("%Y%m%d_%H%M%S")
            out_dir = os.path.join(OUT_DIR_DEFAULT, f"mod_{keyword.replace(' ', '_')}_{ts}")
    os.makedirs(out_dir, exist_ok=True)
    data_dir = storage.task_data_dir(out_dir)

    # 1. 采集：统一入口 collect_amazon_data（B/C 共享数据层）或存档回放（0 credit）
    from_collect = False
    rows_pre_derived = False
    if reuse:
        rows, reuse_extra = _load_reuse(reuse)
        products_raw.update(reuse_extra["products_raw"])
        search_raw = reuse_extra["search_raw"]
        reviews_raw.update(reuse_extra["reviews_raw"])
        rows_pre_derived = bool(reuse_extra.get("pre_derived"))
        credits = None
        print(f"[采集] 复用存档 {len(rows)} 行（products={len(products_raw)} "
              f"reviews={len(reviews_raw)} search_raw={'✓' if search_raw else '✗'}"
              f"{' ·rows.json' if rows_pre_derived else ''}）")
    else:
        _summary, payload = collect_amazon_data(
            keyword=keyword, top_n=top_n, marketplace=marketplace, source=source,
            out_dir=out_dir, sort_by=sort_by, exclude_sponsored=exclude_sponsored,
            reviews_top_n=reviews_top_n, reviews_pages=reviews_pages, progress=progress)
        rows = payload["rows"]
        products_raw = payload["products_raw"]
        search_raw = payload["search_raw"]
        reviews_raw = payload["reviews_raw"]
        credits = payload["credits"]
        fetched_at = payload["fetched_at"]
        from_collect = True
    if not rows:
        raise RuntimeError("未获取到任何竞品数据")

    # 回放/续跑溯源：归档 manifest 还原真实采集时间与 credits（引用口径一致）
    archived = _read_archived_meta(data_dir)
    if archived:
        fetched_at = archived.get("fetched_at") or fetched_at
        if credits is None:
            credits = archived.get("credits")

    # 2. 派生指标（collect 路径与 rows.json 回放均已派生）
    if not from_collect and not rows_pre_derived:
        rows = [derive_metrics(r) for r in rows]

    # 3. 分区
    df = pd.DataFrame(rows)
    df = zoning.classify_zones(df)
    rules = dict(df.attrs.get("zoning_rules", {}))
    summary = zoning.zone_summary(df)
    print(f"[分区] {summary}")

    # 4. 评论分页（第 7 章素材，默认 Top3 × 2 页 = 6 credits 控制；collect 已采则跳过）
    if source == "rainforest" and not reuse and not from_collect and reviews_pages > 0:
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

    # 4b. 数据资产化落盘（data/；collect 已归档原始层，此处补 manifest/宽表）
    storage.save_manifest(data_dir, {
        "keyword": keyword, "marketplace": marketplace, "our_asin": our_asin,
        "source": source, "top_n": len(rows), "credits": credits,
        "fetched_at": fetched_at, "reviews_top_n": reviews_top_n,
        "reviews_pages": reviews_pages, "reuse": bool(reuse),
    })
    if not from_collect:
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

    # 6b. MOD 组件库（主 deck 竞品矩阵章节的确定性图表资产，B/C 共享）
    mod_charts: dict = {}
    try:
        from amazon_matrix_mod.svgcharts.mod_components import render_mod_charts
        theme = None
        if theme_id:
            from amazon_matrix_mod.deck.themes import Theme as _DeckTheme
            theme = _DeckTheme(theme_id)
        mod_charts = render_mod_charts(
            out_dir, df, keyword=keyword, marketplace=marketplace,
            fetched_at=fetched_at, our_asin=our_asin, theme=theme,
            interpretation=interpretation, rules=rules)
    except Exception as exc:  # noqa: BLE001 —— 组件失败不阻塞主管线
        print(f"[charts] MOD 组件库渲染失败（跳过）: {str(exc)[:120]}")

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
    if mod_charts:
        artifacts["charts"] = _rel(base_rel, out_dir, os.path.join(out_dir, "charts"))
    if matrix_png:
        artifacts["matrix_chart_png"] = _rel(base_rel, out_dir, matrix_png)
    result = {
        "keyword": keyword,
        "marketplace": marketplace,
        "our_asin": our_asin,
        "products": products,
        "zoning_rules": rules,
        "llm_interpretation": interpretation,
        "mod_charts": mod_charts,
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
    """完整 MOD 增强（--full）：14 章 + M3 洞察 + image-01 视觉。

    PPT 构建已退役（主 deck MOD 章节 + 独立 pptx 由 ppt_design 单一制作双产出）。
    """
    from amazon_matrix_mod import m3_client
    from amazon_matrix_mod.chapters import render_all, render_full_md
    from amazon_matrix_mod.gen_visual import generate_visuals

    data_dir = storage.task_data_dir(out_dir)
    chapters_dir = os.path.join(out_dir, "chapters")
    visuals_dir = os.path.join(out_dir, "visuals")

    # ── 耗时优化：并行组（四路互不依赖，产物与串行一致） ──
    #   A. visuals 生图（仅依赖 keyword，子进程 ~2-3min，最重）
    #   B. chapters 渲染（确定性）
    #   C. M3 图审（依赖 matrix_png，已在入参就绪）
    #   D. M3 评论聚类（依赖 reviews）
    from concurrent.futures import ThreadPoolExecutor

    def _do_visuals() -> dict:
        visuals = {"background": None, "cover": None, "zones": {}}
        if not with_visuals:
            return visuals
        reused = _reuse_visuals(visuals_dir)
        if reused:
            print(f"[视觉] 复用已有 visuals/（background={'✓' if reused['background'] else '✗'} "
                  f"cover={'✓' if reused['cover'] else '✗'} "
                  f"zones={sum(1 for v in reused['zones'].values() if v)}/4）")
            return reused
        try:
            vis = generate_visuals(keyword, visuals_dir)
            print(f"[视觉] background={'✓' if vis['background'] else '✗'} "
                  f"cover={'✓' if vis['cover'] else '✗'} "
                  f"zones={sum(1 for v in vis['zones'].values() if v)}/4")
            return vis
        except Exception as exc:  # noqa: BLE001
            print(f"[视觉] 生成失败（降级）: {str(exc)[:100]}")
            return visuals

    def _do_audit() -> dict:
        m3 = {"assess": "", "insights": [], "improvements": []}
        audit_target = matrix_png or _rasterize_best_effort(matrix_svg)
        if not audit_target:
            return m3
        data_summary = (f"keyword={keyword}, N={len(df)}, "
                        f"价格范围 ${df['current_price'].min():.2f}-${df['current_price'].max():.2f}, "
                        f"zone分布={zoning.zone_summary(df)}")
        try:
            m3 = m3_client.audit_chart(audit_target, data_summary)
            if m3.get("insights"):
                print(f"[M3] 图审 {len(m3['insights'])} 条洞察")
        except Exception as exc:  # noqa: BLE001
            print(f"[M3] 图审失败（降级）: {str(exc)[:100]}")
        return m3

    def _do_cluster():
        all_reviews = [r for rv in reviews_raw.values() for r in rv]
        if not all_reviews:
            return {}
        try:
            clustered = m3_client.cluster_reviews(all_reviews)
            if clustered:
                print(f"[M3] 评论聚类 {len(clustered.get('topics', []))} 主题")
            return clustered
        except Exception as exc:  # noqa: BLE001
            print(f"[M3] 评论聚类失败（降级）: {str(exc)[:100]}")
            return {}

    with ThreadPoolExecutor(max_workers=4, thread_name_prefix="mod-full") as ex:
        fut_visuals = ex.submit(_do_visuals)
        fut_chapters = ex.submit(
            render_all, df, products_raw, search_raw, reviews_raw,
            chapters_dir, interpretation, rules)
        fut_audit = ex.submit(_do_audit)
        fut_cluster = ex.submit(_do_cluster)
        visuals = fut_visuals.result()
        chapters = fut_chapters.result()
        m3_insights = fut_audit.result()
        clustered = fut_cluster.result()
    print(f"[章节] {len(chapters)} 章渲染完成（SVG，与视觉/图审/聚类并行）")

    # 4. M3 评论聚类深化（覆盖第 7 章结论；依赖 chapters+clustered，组后执行）
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

    # 6. PPT 构建：已退役薄渲染路径（deck/pages.py）——
    # 主 deck 的 MOD 章节由 ppt_design 同源制作，独立 competitor_matrix.pptx
    # 由 PptDesignAgent._export_mod_standalone 双产出导出（单一制作，风格一致）。
    deck_result: dict = {}
    pptx_path: str | None = None

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
