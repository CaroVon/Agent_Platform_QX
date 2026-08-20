#!/usr/bin/env python3
"""P1: 合并报告 — 汇总 raw 目录下各数据源存档（Keepa / Rainforest / 卖家精灵MCP），
输出字段完整性 + 矩阵数据报告。

用法:
    python merge_report.py                      # 汇总 outputs/raw 下所有存档
    python merge_report.py --raw outputs/raw/keepa_20260819_120000.json   # 只看指定存档
    python merge_report.py --no-canopy          # 跳过 Canopy 补充（未注册时）

输出:
    outputs/matrix_report.md   P1 验收报告
"""
import argparse
import glob
import json
import os
import time
from datetime import datetime, timezone

import requests

CANOPY_BASE = "https://api.canopyapi.co"

# ---- 默认配置（复制 config.example.py 为 config.py 可覆盖；环境变量优先）----
OUT_DIR = "outputs"
MARKETPLACE = "US"
CANOPY_API_KEY = os.environ.get("CANOPY_API_KEY", "")
try:
    from config import *  # noqa: F401,F403  用户配置覆盖
except ImportError:
    pass


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_canopy(asin: str) -> dict:
    """Canopy 产品详情（防御性解析，字段以实际返回为准）。"""
    url = f"{CANOPY_BASE}/v1/products/{asin}"
    try:
        r = requests.get(url, params={"marketplace": MARKETPLACE},
                         headers={"Authorization": f"Bearer {CANOPY_API_KEY}"}, timeout=30)
        if r.status_code != 200:
            return {"error": f"HTTP {r.status_code}"}
        data = r.json()
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}

    # 兼容 data.product / product 两种包裹
    prod = (data.get("data") or {}).get("product") or data.get("product") or {}
    images = prod.get("images") or []
    main = None
    if images and isinstance(images, list):
        for cand in images:  # 常见结构: {large, medium, thumb} / [urls]
            if isinstance(cand, dict):
                main = cand.get("large") or cand.get("medium") or cand.get("thumb")
                if main:
                    break
            elif isinstance(cand, str):
                main = cand
                break
    return {
        "title": prod.get("title"),
        "current_price": prod.get("price"),
        "rating": prod.get("ratingValue") or prod.get("rating"),
        "review_count": prod.get("reviewsCount") or prod.get("ratingsCount"),
        "main_image_url": main,
        "raw_keys": sorted(prod.keys()),
    }


def est_monthly_sales(bsr) -> int:
    """BSR → 月销量粗估（分段经验系数，P2 用类目基准校准；报告标注估算值）。"""
    if not bsr:
        return None
    if bsr < 50:
        return 3000
    if bsr < 200:
        return 1500
    if bsr < 500:
        return 800
    if bsr < 1000:
        return 450
    if bsr < 3000:
        return 200
    if bsr < 10000:
        return 80
    return 20


def load_rows(raw_path: str) -> tuple:
    """读一个存档 → (rows, source)。Keepa/Rainforest 用 parsed；卖家精灵用 rows[].result。"""
    with open(raw_path, encoding="utf-8") as f:
        saved = json.load(f)
    source = saved.get("source", "keepa" if "keepa" in os.path.basename(raw_path) else "unknown")
    if source == "sellersprite_mcp":
        rows = []
        for r in saved.get("rows", []):
            parsed = r.get("parsed")
            if isinstance(parsed, dict):
                row = {"asin": r["asin"]}
                # 卖家精灵返回字段名未知，尽力映射常见变体
                for k, aliases in {
                    "current_price": ("price", "priceUsd", "salePrice", "currentPrice", "Price"),
                    "rating": ("rating", "score", "starRating", "Rating"),
                    "review_count": ("reviewCount", "reviews", "ratingNumber", "ReviewCount"),
                    "main_image_url": ("image", "mainImage", "imageUrl", "Image"),
                    "bsr": ("bsr", "rank", "salesRank", "BSR"),
                    "est_monthly_sales": ("monthSales", "sales", "monthlySales", "MonthSales"),
                    "title": ("title", "Title"),
                }.items():
                    row[k] = next((parsed[a] for a in aliases if a in parsed), None)
                row["raw_result"] = r.get("result")
                rows.append(row)
            else:
                rows.append({"asin": r["asin"], "raw_result": r.get("result"),
                             "error": r.get("error")})
        return rows, source
    return saved.get("parsed", []), source


def main():
    ap = argparse.ArgumentParser(description="P1: 合并多数据源存档生成验收报告")
    ap.add_argument("--raw", help="指定单个存档路径（默认汇总 raw 目录下全部存档）")
    ap.add_argument("--out", default=OUT_DIR, help="输出目录")
    ap.add_argument("--no-canopy", action="store_true", help="跳过 Canopy 补充")
    args = ap.parse_args()

    if args.raw:
        raw_files = [args.raw]
    else:
        raw_files = sorted(glob.glob(os.path.join(args.out, "raw", "*.json")))
    if not raw_files:
        raise SystemExit(f"{args.out}/raw 下没有存档，先运行任一 fetch_*.py")

    all_rows, sources = [], []
    for path in raw_files:
        rows, source = load_rows(path)
        all_rows.extend(rows)
        sources.append(source)

    # Canopy 补充（仅对 keepa/rainforest 的标准化行）
    canopy_keys = set()
    if not args.no_canopy and CANOPY_API_KEY:
        print("[Canopy] 有 key，对标准化行逐 ASIN 补拉详情 ...")
        std_rows = [r for r in all_rows if r.get("asin") and r.get("current_price") is not None]
        for i, p in enumerate(std_rows, 1):
            c = fetch_canopy(p["asin"])
            if "error" in c:
                print(f"  [{i}/{len(std_rows)}] {p['asin']} Canopy 失败: {c['error']}")
                continue
            canopy_keys.update(c.get("raw_keys", []))
            for k in ("main_image_url", "current_price", "rating", "review_count"):
                if not p.get(k) and c.get(k):
                    p[k] = c[k]
            print(f"  [{i}/{len(std_rows)}] {p['asin']} OK")
    elif not args.no_canopy:
        print("[Canopy] 未配置 CANOPY_API_KEY，跳过")

    std_rows = [r for r in all_rows if r.get("current_price") is not None or r.get("rating") is not None]
    std_asins = {id(r) for r in std_rows}
    raw_only = [r for r in all_rows if id(r) not in std_asins]

    # 按 asin 去重（多存档合并时保留最后一次）
    seen, dedup = set(), []
    for r in std_rows:
        if r.get("asin") in seen:
            continue
        seen.add(r.get("asin"))
        dedup.append(r)
    std_rows = dedup

    for p in std_rows:
        # recent_sales 解析值（fetch 层已填 est_monthly_sales）优先，缺失才用 BSR 粗估
        if not p.get("est_monthly_sales"):
            p["est_monthly_sales"] = est_monthly_sales(p.get("bsr"))

    # 字段完整性：按数据源区分（Rainforest 无价格历史/卖家字段）
    field_sets = {
        "rainforest": ["current_price", "rating", "review_count", "bsr", "main_image_url"],
        "keepa": ["current_price", "price_min_90d", "price_max_90d", "rating",
                  "review_count", "bsr", "main_image_url", "seller_type"],
    }
    per_asin_source = {}
    for path in raw_files:
        with open(path, encoding="utf-8") as f:
            src = json.load(f).get("source", "")
        for r in (json.load(open(path, encoding="utf-8")).get("parsed") or []):
            per_asin_source.setdefault(r.get("asin"), src)
    complete = 0
    for r in std_rows:
        fields = field_sets.get(per_asin_source.get(r.get("asin"), "rainforest"),
                                field_sets["rainforest"])
        if all(r.get(f) is not None for f in fields):
            complete += 1

    os.makedirs(args.out, exist_ok=True)
    report_path = os.path.join(args.out, "matrix_report.md")
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# P1 数据验证报告（数据源: {', '.join(sorted(set(sources))) or '无'}{' + Canopy' if canopy_keys else ''}）\n\n")
        f.write(f"- 生成时间：{ts}\n- 存档数：{len(raw_files)} ｜ 标准化行：{len(std_rows)}（已按 ASIN 去重）｜ 仅原始文本行：{len(raw_only)}\n")
        f.write(f"- 字段完整：{complete}/{len(std_rows)}（按数据源契约：Rainforest=现价/评分/评论/BSR/主图）\n")
        f.write("- 数据源说明：Rainforest=实时快照（search 关键词发现 + product 详情）；Keepa=历史+榜单；卖家精灵MCP=官方AI接口\n\n")
        f.write("| ASIN | 标题 | 现价$ | 90d低$ | 90d高$ | 评分 | 评论数 | BSR | 月销估算* | 卖家 | 主图 |\n")
        f.write("|---|---|---|---|---|---|---|---|---|---|---|\n")
        for r in std_rows:
            title = (r.get("title") or "")[:28]
            img = (r.get("main_image_url") or "缺失")[:44]
            f.write(f"| {r['asin']} | {title} | {r.get('current_price')} | "
                    f"{r.get('price_min_90d')} | {r.get('price_max_90d')} | {r.get('rating')} | "
                    f"{r.get('review_count')} | {r.get('bsr')} | {r.get('est_monthly_sales')} | "
                    f"{r.get('seller_type') or '?'} | {img} |\n")
        if raw_only:
            f.write("\n**以下行数据源未返回标准化字段（原始文本见存档）：**\n\n")
            f.write("| ASIN | 说明 |\n|---|---|\n")
            for r in raw_only:
                note = (r.get("result") or r.get("error") or r.get("raw_result") or "")[:60].replace("|", "/")
                f.write(f"| {r.get('asin', '?')} | {note} |\n")
        f.write("\n\\* 月销估算 = BSR 分段经验系数，仅为量级参考，P2 用类目基准校准。\n")

    print(f"\n[完成] 报告已生成: {report_path}")
    print(f"[标准化行] {len(std_rows)} ｜ [完整性] {complete}/{len(std_rows)} 全字段齐全")
    print(f"[仅原始文本行] {len(raw_only)}（卖家精灵/未知结构，见报告尾部）")
    print(f"[Canopy 字段] {sorted(canopy_keys) or '未使用'}")


if __name__ == "__main__":
    main()
