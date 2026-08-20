"""派生指标 —— 竞品数据归一化与派生（对应执行前最终方案 §1.2 字段契约）。"""
from __future__ import annotations

import re

# BSR → 月销量粗估（分段经验系数；仅 recent_sales 缺失时回退）
_BSR_TIERS = [
    (50, 3000), (200, 1500), (500, 800), (1000, 450),
    (3000, 200), (10000, 80), (float("inf"), 20),
]


def parse_recent_sales(raw) -> int | None:
    """解析 Amazon 官方销量口径 "3K+ bought in past month" / "Bought 500+ times"。
    "3K+" → 3000（区间下限，保守估算）。无法解析返回 None。"""
    if not raw:
        return None
    m = re.search(r"([\d.]+)\s*([KkMm])?", str(raw))
    if not m:
        return None
    n = float(m.group(1))
    mult = {"k": 1000, "m": 1000000}.get((m.group(2) or "").lower(), 1)
    return int(n * mult)


def est_sales_from_bsr(bsr) -> int | None:
    """BSR → 月销量粗估（recent_sales 缺失回退）。"""
    if not bsr or bsr <= 0:
        return None
    for limit, sales in _BSR_TIERS:
        if bsr <= limit:
            return sales
    return 20


def normalize_rating(v) -> float | None:
    """评分归一化为 0-5（防御 Keepa 百分制/千分制等变体）。"""
    if v is None or v <= 0:
        return None
    if v > 1000:
        return round(v / 1000.0, 2)
    if v > 100:
        return round(v / 100.0, 2)
    return round(v, 2)


def cents_to_dollars(v) -> float | None:
    """美分 → 美元（Keepa 口径）；-1/None 无数据。"""
    if v is None or v == -1:
        return None
    return round(v / 100.0, 2)


def derive_metrics(row: dict) -> dict:
    """补全派生字段（幂等，可直接作用于适配器输出行）：
    - est_monthly_sales：recent_sales 解析优先，BSR 粗估回退
    - is_fba 缺省 False
    - zone 由 zoning 引擎负责，不在此处
    """
    row = dict(row)
    sales = parse_recent_sales(row.get("recent_sales_raw") or row.get("recent_sales"))
    if sales is None:
        sales = est_sales_from_bsr(row.get("bsr"))
    row["est_monthly_sales"] = sales
    row.setdefault("is_fba", False)
    row.setdefault("seller_type", None)
    return row
