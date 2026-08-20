"""zoning 4 区规则单测。"""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from amazon_matrix_mod import zoning  # noqa: E402


def _df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _base_rows(n: int = 40) -> list[dict]:
    """50 个竞品样本：价格 5-120，评分 3.5-4.8，评论 0-80000，销量 100-10000，FBA 为主。"""
    import random
    random.seed(42)
    rows = []
    for i in range(n):
        price = round(random.uniform(5, 120), 2)
        rows.append({
            "asin": f"B0TEST{i:03d}",
            "title": f"Test Product {i}",
            "current_price": price,
            "rating": round(random.uniform(3.5, 4.8), 2),
            "review_count": int(random.uniform(0, 80000)),
            "est_monthly_sales": int(random.uniform(100, 10000)),
            "is_fba": i % 3 != 0,  # 1/3 FBM
        })
    return rows


def test_price_gap_zone_exists():
    df = zoning.classify_zones(_df(_base_rows()))
    assert set(df["zone"]).issubset(set(zoning.ZONES))
    assert "zone" in df.columns


def test_value_opportunity():
    """低价（低于同评分段中位数×0.85）+ 低评论（<500）必须进性价比区。"""
    rows = _base_rows()
    rows.append({"asin": "B0CHEAP", "title": "Cheap New", "current_price": 3.99,
                 "rating": 4.4, "review_count": 10, "est_monthly_sales": 300,
                 "is_fba": False})
    df = zoning.classify_zones(_df(rows))
    row = df[df["asin"] == "B0CHEAP"].iloc[0]
    assert row["zone"] == "value_opportunity"


def test_demand_heat():
    """高销量（>P80）+ 非 FBA → 需求热度区。"""
    rows = _base_rows()
    rows.append({"asin": "B0HOT", "title": "Hot FBM", "current_price": 30.0,
                 "rating": 4.2, "review_count": 300, "est_monthly_sales": 99999,
                 "is_fba": False})
    df = zoning.classify_zones(_df(rows))
    assert df[df["asin"] == "B0HOT"].iloc[0]["zone"] == "demand_heat"


def test_red_ocean():
    """价格 P50±10% + 评论>1000 + FBA → 红海警示区。"""
    rows = _base_rows()
    df0 = zoning.classify_zones(_df(rows))
    p50 = df0["current_price"].quantile(0.5)
    rows.append({"asin": "B0RED", "title": "Crowded", "current_price": p50,
                 "rating": 4.5, "review_count": 50000, "est_monthly_sales": 5000,
                 "is_fba": True})
    df = zoning.classify_zones(_df(rows))
    assert df[df["asin"] == "B0RED"].iloc[0]["zone"] == "red_ocean"


def test_neutral_default():
    """中价位 + 中评论 + FBA 的普通样本保持 neutral（不被红海误判）。"""
    rows = _base_rows()
    df0 = zoning.classify_zones(_df(rows))
    p50 = df0["current_price"].quantile(0.5)
    rows.append({"asin": "B0NORM", "title": "Normal", "current_price": p50,
                 "rating": 4.0, "review_count": 600, "est_monthly_sales": 800,
                 "is_fba": True})
    df = zoning.classify_zones(_df(rows))
    # 评论 600 < 1000 → 不进红海；销量低 → 不进缺口/热度
    assert df[df["asin"] == "B0NORM"].iloc[0]["zone"] == "neutral"


def test_quantile_boundaries():
    df = _df(_base_rows(40))
    df = zoning.classify_zones(df)
    rules = df.attrs["zoning_rules"]
    assert rules["price_gap"]["price_range"][0] <= rules["price_gap"]["price_range"][1]
    assert all(k in rules for k in ("price_gap", "value_opportunity", "demand_heat", "red_ocean"))


def test_empty_df():
    df = zoning.classify_zones(_df([]))
    assert len(df) == 0 or "zone" in df.columns


def test_missing_fields_do_not_crash():
    """缺 est_monthly_sales / is_fba 时仍可分区（fillna 兜底）。"""
    rows = [{"asin": "B0A", "title": "A", "current_price": 10.0,
             "rating": 4.0, "review_count": 100},
            {"asin": "B0B", "title": "B", "current_price": 20.0,
             "rating": 4.0, "review_count": 200}]
    df = zoning.classify_zones(_df(rows))
    assert set(df["zone"]).issubset(set(zoning.ZONES))
