"""Rainforest 适配器 —— 关键词 → 竞品 ASIN（search，1 credit/页）→ 详情（product，1 credit/个）。

实测契约（2026-08-19 冻结，见执行前最终方案 §1.2）：
  search_results[]: asin/title/price.value/rating/ratings_total/recent_sales/image/link/is_prime
  product:          title/brand/main_image.link/buybox_winner.price.value/rating/ratings_total/
                    recent_sales/bestsellers_rank[0].{rank,category}/is_prime(buybox)/link
"""
from __future__ import annotations

import os
import re
import sys
import time
from datetime import datetime, timezone

import requests

from amazon_matrix_mod.metrics import parse_recent_sales

BASE = "https://api.rainforestapi.com/request"
DEFAULT_DOMAIN = "amazon.com"

# 请求间最小间隔（秒）—— 实测单请求 7-9s，避免叠加限流
RATE_LIMIT_SLEEP = 0.6


def get_key() -> str:
    key = os.environ.get("RAINFOREST_API_KEY", "")
    if not key:
        raise RuntimeError("缺少 RAINFOREST_API_KEY 环境变量（Rainforest 注册后获取，见 README）")
    return key


def _call(params: dict) -> dict:
    params["api_key"] = get_key()
    for attempt in range(3):
        try:
            r = requests.get(BASE, params=params, timeout=60)
            if r.status_code == 429:
                time.sleep(30 * (attempt + 1))
                continue
            if r.status_code >= 500:
                # 服务端暂不可用（实测 reviews 偶发 503）→ 退避重试
                time.sleep(10 * (attempt + 1))
                continue
            r.raise_for_status()
            data = r.json()
            info = data.get("request_info") or {}
            if info.get("success") is False:
                raise RuntimeError(f"Rainforest 错误: {info.get('message')}")
            return data
        except requests.RequestException as e:
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))


def _parse_rating(v) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    try:
        return round(float(str(v).split()[0]), 2)
    except (ValueError, IndexError):
        return None


def _parse_bsr(p: dict) -> tuple[int | None, str | None]:
    ranks = p.get("bestsellers_rank") or []
    if ranks and isinstance(ranks, list) and isinstance(ranks[0], dict):
        return ranks[0].get("rank"), ranks[0].get("category")
    if isinstance(ranks, str):
        head = ranks.split(" in ")[0].lstrip("#").replace(",", "")
        m = re.search(r"\d+", head)
        if m:
            return int(m.group()), None
    return None, None


def search(keyword: str, limit: int = 50, sort_by: str | None = None,
           exclude_sponsored: bool = True, max_page: int = 1) -> list[dict]:
    """关键词搜索 → 竞品列表（每页 1 credit）。"""
    params = {"type": "search", "amazon_domain": DEFAULT_DOMAIN,
              "search_term": keyword,
              "exclude_sponsored": "true" if exclude_sponsored else "false"}
    if sort_by:
        params["sort_by"] = sort_by
    if max_page and max_page > 1:
        params["max_page"] = max_page
    data = _call(params)
    results = data.get("search_results") or []
    out = []
    for r in results:
        price = (r.get("price") or {})
        out.append({
            "asin": r.get("asin"),
            "title": r.get("title"),
            "current_price": price.get("value"),
            "rating": _parse_rating(r.get("rating")),
            "review_count": r.get("ratings_total"),
            "recent_sales_raw": r.get("recent_sales"),
            "main_image_url": r.get("image"),
            "url": r.get("link"),
            "is_prime": bool(r.get("is_prime")),
            "sponsored": bool(r.get("sponsored")),
        })
        if len(out) >= limit:
            break
    return out


def product(asin: str) -> dict:
    """单个 ASIN 详情（1 credit）。"""
    data = _call({"type": "product", "amazon_domain": DEFAULT_DOMAIN, "asin": asin})
    p = data.get("product") or {}
    bb = p.get("buybox_winner") or {}
    price = (bb.get("price") or {}).get("value")
    if price is None and isinstance(p.get("price"), dict):
        price = p["price"].get("value")
    mi = p.get("main_image") or {}
    bsr, bsr_cat = _parse_bsr(p)
    return {
        "asin": p.get("asin") or asin,
        "title": p.get("title"),
        "brand": p.get("brand"),
        "main_image_url": mi.get("link") if isinstance(mi, dict) else None,
        "current_price": price,
        "rating": _parse_rating(p.get("rating")),
        "review_count": p.get("ratings_total"),
        "recent_sales_raw": p.get("recent_sales"),
        "est_monthly_sales": parse_recent_sales(p.get("recent_sales")),
        "bsr": bsr,
        "bsr_category": bsr_cat,
        "is_fba": bool(bb.get("is_prime")) if isinstance(bb, dict) else None,
        "is_prime": bool(bb.get("is_prime")) if isinstance(bb, dict) else None,
        "seller_type": None,
        "url": p.get("link"),
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def fetch_competitors(keyword: str, limit: int = 50, sort_by: str | None = None,
                      exclude_sponsored: bool = True, asins: list[str] | None = None,
                      progress=None) -> list[dict]:
    """完整采集：关键词 → ASIN 池 → 逐个详情（可指定 --asins 跳过搜索）。

    返回归一化 CompetitorRow 列表；单个详情失败仅跳过（不中断整批）。
    """
    rows = []
    for item, raw in _iter_products(keyword, limit, sort_by, exclude_sponsored, asins, progress):
        rows.append(raw)
    return rows


def _iter_products(keyword: str, limit: int, sort_by: str | None,
                   exclude_sponsored: bool, asins: list[str] | None,
                   progress=None):
    """采集生成器：yield (归一化行, 原始 product dict)。"""
    if asins:
        candidates = [{"asin": a} for a in asins]
    else:
        candidates = search(keyword, limit=limit, sort_by=sort_by,
                            exclude_sponsored=exclude_sponsored)
    for i, item in enumerate(candidates, 1):
        asin = item.get("asin")
        if not asin:
            continue
        if progress:
            progress(i, len(candidates), asin)
        try:
            data = _call({"type": "product", "amazon_domain": DEFAULT_DOMAIN, "asin": asin})
            p = data.get("product") or {}
            yield product_from_raw(p, asin), p
        except Exception as exc:  # noqa: BLE001 —— 单点失败跳过
            if progress:
                progress(i, len(candidates), asin, error=str(exc)[:100])
        time.sleep(RATE_LIMIT_SLEEP)


def product_from_raw(p: dict, fallback_asin: str | None = None) -> dict:
    """原始 product dict → 归一化行（与 product() 同逻辑，供批量采集复用）。"""
    bb = p.get("buybox_winner") or {}
    price = (bb.get("price") or {}).get("value")
    if price is None and isinstance(p.get("price"), dict):
        price = p["price"].get("value")
    mi = p.get("main_image") or {}
    bsr, bsr_cat = _parse_bsr(p)
    return {
        "asin": p.get("asin") or fallback_asin,
        "title": p.get("title"),
        "brand": p.get("brand"),
        "main_image_url": mi.get("link") if isinstance(mi, dict) else None,
        "current_price": price,
        "rating": _parse_rating(p.get("rating")),
        "review_count": p.get("ratings_total"),
        "recent_sales_raw": p.get("recent_sales"),
        "est_monthly_sales": parse_recent_sales(p.get("recent_sales")),
        "bsr": bsr,
        "bsr_category": bsr_cat,
        "is_fba": bool(bb.get("is_prime")) if isinstance(bb, dict) else None,
        "is_prime": bool(bb.get("is_prime")) if isinstance(bb, dict) else None,
        "seller_type": None,
        "url": p.get("link"),
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def fetch_reviews(asin: str, pages: int = 2, progress=None) -> list[dict]:
    """评论分页采集（每页 1 credit）。返回归一化评论列表。"""
    reviews: list[dict] = []
    for page in range(1, pages + 1):
        data = _call({"type": "reviews", "amazon_domain": DEFAULT_DOMAIN,
                      "asin": asin, "page": page})
        for r in (data.get("reviews") or []):
            if not isinstance(r, dict):
                continue
            reviews.append({
                "asin": asin,
                "title": r.get("title"),
                "body": r.get("body"),
                "rating": r.get("rating"),
                "date": (r.get("date") or {}).get("raw"),
                "date_utc": (r.get("date") or {}).get("utc"),
                "verified_purchase": bool(r.get("verified_purchase")),
                "helpful_votes": r.get("helpful_votes"),
                "review_country": r.get("review_country"),
            })
        time.sleep(RATE_LIMIT_SLEEP)
    return reviews
