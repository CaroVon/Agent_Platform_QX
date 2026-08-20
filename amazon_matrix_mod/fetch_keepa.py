#!/usr/bin/env python3
"""P1: Keepa 数据拉取 — 关键词→ASIN 发现 / 指定 ASIN → 详情+历史统计拉取。

用法:
    python fetch_keepa.py --keyword "yoga mat" --limit 10
    python fetch_keepa.py --asins B0XXXXXXXX,B0YYYYYYYY
    python fetch_keepa.py --keyword "yoga mat" --limit 10 --range 30 --stats 180

输出:
    outputs/raw/keepa_<ts>.json   原始响应存档（字段核对用）
    stdout 摘要表

说明:
    - 防御性解析：Keepa 字段以实际返回为准，缺失字段记 None 不报错。
    - token 消耗：Keepa 响应中如含 tokensConsumed 则打印；否则以官网控制台为准。
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import requests

KEEPA_BASE = "https://api.keepa.com"

# ---- 默认配置（复制 config.example.py 为 config.py 可覆盖；环境变量优先）----
DEFAULT_KEYWORD = "yoga mat"
DEFAULT_LIMIT = 10
DEFAULT_RANGE = 30
DEFAULT_STATS = 180
OUT_DIR = "outputs"
DOMAIN = 1
KEEPA_API_KEY = os.environ.get("KEEPA_API_KEY", "")
try:
    from config import *  # noqa: F401,F403  用户配置覆盖
except ImportError:
    pass


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_key() -> str:
    key = os.environ.get("KEEPA_API_KEY") or KEEPA_API_KEY
    if not key:
        sys.exit("缺少 KEEPA_API_KEY：请设置环境变量或填写 config.py（见 README 注册指引）")
    return key


def api_get(params: dict) -> dict:
    """调 Keepa API，带重试与限流退避。"""
    params["key"] = get_key()
    for attempt in range(3):
        try:
            r = requests.get(f"{KEEPA_BASE}/product", params=params, timeout=30)
            if r.status_code == 429:
                wait = 60 * (attempt + 1)
                print(f"[限流 429] 等待 {wait}s 后重试 ...")
                time.sleep(wait)
                continue
            r.raise_for_status()
            data = r.json()
            if data.get("error"):
                # 常见: 无效 key / token 不足 / 参数错误
                sys.exit(f"Keepa API 错误: {data['error']} (HTTP {r.status_code})")
            return data
        except requests.RequestException as e:
            print(f"[重试 {attempt + 1}/3] {e}")
            time.sleep(5 * (attempt + 1))
    sys.exit("Keepa API 连续失败，请检查网络与 key")


def discover_asins(keyword: str, limit: int, domain: int) -> list:
    """方式 A：按关键词搜索类目，返回竞品 ASIN 列表。"""
    params = {"domain": domain, "type": 0, "title": keyword}
    params["key"] = get_key()
    r = requests.get(f"{KEEPA_BASE}/search", params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    if data.get("error"):
        sys.exit(f"Keepa 搜索错误: {data['error']}")
    asins = data.get("asinList", [])
    print(f"[搜索] 关键词 '{keyword}' 命中 {data.get('totalResultCount', '?')} 个商品，取前 {limit} 个")
    print(f"[token] 搜索消耗: {data.get('tokensConsumed', '未知（以 Keepa 控制台为准）')}")
    return asins[:limit]


def parse_int_ts(ts) -> int:
    """Keepa 时间戳为 int32 秒（负数表示 >= 2^31 溢出），还原为标准 unix 秒。"""
    if ts is None:
        return None
    if ts < 0:
        ts += 2**32
    return ts


def cents_to_dollars(v) -> float:
    """美亚价格单位=美分；-1 表示无数据（缺货等）。"""
    if v is None or v == -1:
        return None
    return round(v / 100.0, 2)


def normalize_rating(v) -> float:
    """评分归一化为 0-5。Keepa csv[3] 为百分制(450→4.5)；新版直接字段为 0-5。
    防御性处理：>1000 按千分制，>100 按百分制。"""
    if v is None or v <= 0:
        return None
    if v > 1000:
        return round(v / 1000.0, 2)
    if v > 100:
        return round(v / 100.0, 2)
    return round(v, 2)


def latest(arr) :
    """取 csv 时间序列的最新值（Keepa 按时间升序，末尾为最新）。"""
    if not arr:
        return None
    v = arr[-1]
    return None if v == -1 else v


def parse_product(p: dict) -> dict:
    """防御性解析单个 Keepa product 对象 → 归一化字段。"""
    csv = p.get("csv") or []
    stats = p.get("stats") or {}
    stat = stats.get("current") or []
    avg90 = stats.get("avg90") or []
    min90 = stats.get("min90") or []
    max90 = stats.get("max90") or []

    # 主图：新版 imagesCSV（完整 URL 列表）→ 旧版 images[hash]
    main_image = None
    images_csv = p.get("imagesCSV")
    if images_csv:
        main_image = str(images_csv).split(",")[0].strip()
    if not main_image and p.get("images"):
        h = p["images"][0]
        main_image = f"https://m.media-amazon.com/images/I/{h}"

    # 评分/评论数：新版直接字段优先，回退 csv/stats
    rating = p.get("rating") or normalize_rating(stat[3] if len(stat) > 3 else latest(csv[3] if len(csv) > 3 else []))
    review_count = p.get("reviewCount") or latest(csv[2] if len(csv) > 2 else [])

    # 价格：buyBoxPrice 直接字段优先（美分），回退 csv[0] 最新
    price_cents = p.get("buyBoxPrice")
    if price_cents is None:
        price_cents = latest(csv[0] if csv else [])

    # 卖家/发货
    seller_summary = p.get("sellerIdsSummary") or {}
    fba_sellers = seller_summary.get("FBA") or []
    fbm_sellers = seller_summary.get("FBM") or []
    fulfillment = p.get("fulfillmentChannel")

    # 类目（取叶子类目名）
    category = None
    tree = p.get("categoryTree") or []
    if tree:
        category = tree[-1].get("name")

    bsr = latest(csv[1] if len(csv) > 1 else [])

    return {
        "asin": p.get("asin"),
        "title": p.get("title"),
        "main_image_url": main_image,
        "current_price": cents_to_dollars(price_cents),
        "price_min_90d": cents_to_dollars(min90[0] if min90 else None),
        "price_max_90d": cents_to_dollars(max90[0] if max90 else None),
        "price_avg_90d": cents_to_dollars(avg90[0] if avg90 else None),
        "rating": rating,
        "review_count": review_count,
        "bsr": bsr,
        "bsr_category": category,
        "seller_type": fulfillment or ("FBA" if fba_sellers else ("FBM" if fbm_sellers else None)),
        "is_fba": bool(fba_sellers) or fulfillment == "FBA",
        "fetched_at": utcnow(),
    }


def main():
    ap = argparse.ArgumentParser(description="P1: Keepa 竞品数据拉取")
    ap.add_argument("--keyword", help="方式A：搜索关键词（自动发现竞品 ASIN）")
    ap.add_argument("--asins", help="方式B：逗号分隔的 ASIN 列表")
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="竞品数量上限")
    ap.add_argument("--range", type=int, default=DEFAULT_RANGE, help="时间范围（天）")
    ap.add_argument("--stats", type=int, default=DEFAULT_STATS, help="统计窗口（天），返回 min/avg/max")
    ap.add_argument("--out", default=OUT_DIR, help="输出目录")
    args = ap.parse_args()

    if not args.asins and not args.keyword:
        ap.error("必须提供 --keyword 或 --asins 之一")

    asins = [a.strip() for a in args.asins.split(",")] if args.asins else \
        discover_asins(args.keyword, args.limit, DOMAIN)
    if not asins:
        sys.exit("未发现任何 ASIN")

    print(f"[拉取] {len(asins)} 个 ASIN: {', '.join(asins[:5])}{' ...' if len(asins) > 5 else ''}")
    data = api_get({"asin": ",".join(asins), "domain": DOMAIN,
                    "range": args.range, "stats": args.stats})

    products = [parse_product(p) for p in data.get("products", [])]
    products = [p for p in products if p["asin"]]

    os.makedirs(os.path.join(args.out, "raw"), exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    raw_path = os.path.join(args.out, "raw", f"keepa_{ts}.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump({"fetched_at": utcnow(), "raw": data, "parsed": products},
                  f, ensure_ascii=False, indent=1)

    print(f"\n[摘要] 成功 {len(products)}/{len(asins)} 个 ASIN")
    print(f"[token] 本次消耗: {data.get('tokensConsumed', '未知（以 Keepa 控制台为准）')}")
    print(f"[存档] {raw_path}")
    print("\n{:<12} {:>10} {:>10} {:>10} {:>8} {:>8} {:>10}  {}".format(
        "ASIN", "现价$", "90d低$", "90d高$", "评分", "评论数", "BSR", "主图"))
    for p in products:
        img = (p["main_image_url"] or "")[:40]
        print("{:<12} {:>10} {:>10} {:>10} {:>8} {:>8} {:>10}  {}".format(
            p["asin"], p["current_price"], p["price_min_90d"], p["price_max_90d"],
            p["rating"], p["review_count"], p["bsr"], img))


if __name__ == "__main__":
    main()
