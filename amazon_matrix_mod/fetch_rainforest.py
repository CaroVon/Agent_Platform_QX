#!/usr/bin/env python3
"""P1: Rainforest API 适配器 — 关键词→ASIN 发现 / 指定 ASIN → 详情快照拉取。

接口（官方文档 docs.trajectdata.com/rainforestapi）:
    GET https://api.rainforestapi.com/request
        ?api_key=KEY & type=product & amazon_domain=amazon.com & asin=B0XXX
        ?api_key=KEY & type=search  & amazon_domain=amazon.com & search_term=KEYWORD

用法:
    export RAINFOREST_API_KEY=...
    python fetch_rainforest.py --keyword "yoga mat" --limit 10
    python fetch_rainforest.py --asins B0XXXXXXXX,B0YYYYYYYY

输出:
    outputs/raw/rainforest_<ts>.json   原始响应存档 + parsed 归一化字段
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import requests

BASE = "https://api.rainforestapi.com/request"
DEFAULT_KEYWORD = "yoga mat"
DEFAULT_LIMIT = 10
OUT_DIR = "outputs"
AMAZON_DOMAIN = "amazon.com"  # 美亚


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_key() -> str:
    key = os.environ.get("RAINFOREST_API_KEY", "")
    if not key:
        sys.exit("缺少 RAINFOREST_API_KEY 环境变量（Rainforest 注册后获取，见 README）")
    return key


def call(params: dict) -> dict:
    params["api_key"] = get_key()
    for attempt in range(3):
        try:
            r = requests.get(BASE, params=params, timeout=30)
            if r.status_code == 429:
                wait = 30 * (attempt + 1)
                print(f"[限流 429] 等待 {wait}s ...")
                time.sleep(wait)
                continue
            r.raise_for_status()
            data = r.json()
            req_info = data.get("request_info") or {}
            if req_info.get("success") is False:
                sys.exit(f"Rainforest 错误: {req_info.get('message')}")
            return data
        except requests.RequestException as e:
            print(f"[重试 {attempt + 1}/3] {e}")
            time.sleep(5 * (attempt + 1))
    sys.exit("Rainforest 连续失败，请检查网络与 key")


def discover_asins(keyword: str, limit: int, sort_by: str = None,
                   exclude_sponsored: bool = True) -> list:
    """type=search: 按关键词搜索竞品（核心入口，实测 1 页 = 1 credit）。

    参数见 Rainforest 文档（docs.trajectdata.com/rainforestapi）:
      sort_by: price_low_to_high / price_high_to_low / rating / featured...
      max_page: 一次取 N 页（每页 1 credit）
      exclude_sponsored: 去掉广告位
    """
    params = {"type": "search", "amazon_domain": AMAZON_DOMAIN,
              "search_term": keyword, "exclude_sponsored": "true" if exclude_sponsored else "false"}
    if sort_by:
        params["sort_by"] = sort_by
    data = call(params)
    results = data.get("search_results") or []
    print(f"[搜索] '{keyword}' 本页 {len(results)} 个结果"
          f"（credits: {data.get('request_info', {}).get('credits_used_this_request', '?')}）")
    return results[:limit]


def parse_rating(v):
    """Rainforest rating 形如 '4.5 out of 5 stars' 或数字。"""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    try:
        return round(float(str(v).split()[0]), 2)
    except (ValueError, IndexError):
        return None


def parse_recent_sales(v) -> int:
    """解析 recent_sales 官方销量口径："3K+ bought in past month" / "500+ bought" / "Bought 1K+ times"。
    返回区间中位数估算；无法解析返回 None。"""
    if not v:
        return None
    s = str(v)
    import re
    m = re.search(r"([\d.]+)\s*([KkMm])?", s)
    if not m:
        return None
    n = float(m.group(1))
    mult = {"k": 1000, "m": 1000000}.get((m.group(2) or "").lower(), 1)
    return int(n * mult)  # "3K+" → 3000


def parse_product(p: dict) -> dict:
    """防御性解析 Rainforest product 对象 → 归一化字段（实测契约，2026-08-19 冻结）。"""
    images = p.get("images") or []
    main_image = None
    for img in images:
        if isinstance(img, dict):
            main_image = img.get("link") or img.get("large") or img.get("medium")
        elif isinstance(img, str):
            main_image = img
        if main_image:
            break
    # 实测：product.main_image.link 优先（原图），images[] 次之
    mi = p.get("main_image") or {}
    if isinstance(mi, dict) and mi.get("link"):
        main_image = mi["link"]

    review_count = p.get("ratings_total") or p.get("reviews_total")

    # Buy Box 价格优先（实测 buybox_winner.price.value），回退 product.price
    bb = p.get("buybox_winner") or {}
    price = (bb.get("price") or {}).get("value") if isinstance(bb, dict) else None
    if price is None:
        price = (p.get("price") or {}).get("value") if isinstance(p.get("price"), dict) else p.get("price")

    # BSR: 实测为数组 [{'rank': 55, 'category': 'Computer Mice'}, ...]
    bsr, bsr_cat = None, None
    ranks = p.get("bestsellers_rank") or []
    if ranks and isinstance(ranks, list):
        first = ranks[0]
        if isinstance(first, dict):
            bsr, bsr_cat = first.get("rank"), first.get("category")
    elif isinstance(ranks, str):
        head = ranks.split(" in ")[0].lstrip("#").replace(",", "")
        try:
            bsr = int(head.split()[0])
        except (ValueError, IndexError):
            bsr = None

    # 卖家/发货：buybox is_prime 作 FBA 代理（offers 接口可精确化，成本 +1/个）
    is_prime = (bb.get("is_prime")) if isinstance(bb, dict) else None

    return {
        "asin": p.get("asin"),
        "title": p.get("title"),
        "brand": p.get("brand"),
        "main_image_url": main_image,
        "current_price": price,
        "rating": parse_rating(p.get("rating")),
        "review_count": review_count,
        "recent_sales_raw": p.get("recent_sales"),          # "3K+ bought in past month"
        "est_monthly_sales": parse_recent_sales(p.get("recent_sales")),
        "bsr": bsr,
        "bsr_category": bsr_cat,
        "is_prime": is_prime,                               # FBA 代理
        "seller_type": None,                                # 需 type=offers（可选抽查）
        "is_fba": is_prime,
        "url": p.get("link") or p.get("url"),
        "fetched_at": utcnow(),
    }


def main():
    ap = argparse.ArgumentParser(description="P1: Rainforest 竞品数据拉取")
    ap.add_argument("--keyword", help="方式A：搜索关键词（核心：关键词→竞品）")
    ap.add_argument("--asins", help="方式B：逗号分隔 ASIN 列表")
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    ap.add_argument("--sort-by", default=None,
                    help="search 排序: price_low_to_high / price_high_to_low / rating / featured")
    ap.add_argument("--include-sponsored", action="store_true", help="不过滤广告位（默认过滤）")
    ap.add_argument("--out", default=OUT_DIR)
    args = ap.parse_args()
    if not args.asins and not args.keyword:
        ap.error("必须提供 --keyword 或 --asins 之一")

    if args.asins:
        asins = [a.strip() for a in args.asins.split(",")]
        results = [{"asin": a} for a in asins]
        print(f"[拉取] {len(asins)} 个 ASIN 详情")
    else:
        results = discover_asins(args.keyword, args.limit,
                                 sort_by=args.sort_by,
                                 exclude_sponsored=not args.include_sponsored)

    products = []
    for i, item in enumerate(results, 1):
        asin = item.get("asin")
        if not asin:
            continue
        print(f"  [{i}/{len(results)}] {asin} ...")
        data = call({"type": "product", "amazon_domain": AMAZON_DOMAIN, "asin": asin})
        p = data.get("product") or {}
        parsed = parse_product(p)
        if not parsed["asin"]:
            parsed["asin"] = asin
        products.append(parsed)
        time.sleep(0.5)  # 温和限速

    os.makedirs(os.path.join(args.out, "raw"), exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    raw_path = os.path.join(args.out, "raw", f"rainforest_{ts}.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump({"fetched_at": utcnow(), "source": "rainforest",
                   "parsed": products}, f, ensure_ascii=False, indent=1)

    print(f"\n[摘要] 成功 {len(products)} 个 ASIN")
    print(f"[存档] {raw_path}")
    print("\n{:<12} {:>10} {:>8} {:>10} {:>8} {:>8}  {}".format(
        "ASIN", "现价$", "评分", "评论数", "月销估", "BSR", "主图"))
    for p in products:
        f = lambda v: "-" if v is None else v  # noqa: E731
        print("{:<12} {:>10} {:>8} {:>10} {:>8} {:>8}  {}".format(
            p["asin"], f(p["current_price"]), f(p["rating"]), f(p["review_count"]),
            f(p["est_monthly_sales"]), f(p["bsr"]), (p["main_image_url"] or "")[:44]))


if __name__ == "__main__":
    main()
