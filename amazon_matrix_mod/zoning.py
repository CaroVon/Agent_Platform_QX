"""4 区规则引擎 —— 竞品矩阵分区（对应设计文档 §2.2 与执行前最终方案 §1.2 修订）。

需求热度指标（实测修订）：
  主指标 = est_monthly_sales（Rainforest recent_sales 官方口径 "3K+ bought in past month" 解析；
           缺失时 BSR 分段系数回退），不再使用评论增速（Rainforest 无上架日期字段）。

规则（按优先级依次覆盖，与 P2P3 规划 §3.1 一致）：
  1. price_gap        价格缺口带：价格 ∈ [P50, P75] 且 需求 > P80
  2. value_opportunity 性价比机会：价格 < 同评分段中位数×0.85 且 评论数 < 500
  3. demand_heat      需求热度：需求 > P80 且 非 FBA（is_fba=False 代理 FBM 主导）
  4. red_ocean        红海警示：价格 ∈ [P50×0.9, P50×1.1] 且 评论数 > 1000 且 FBA
"""
from __future__ import annotations

import pandas as pd

ZONES = ("neutral", "price_gap", "value_opportunity", "demand_heat", "red_ocean")
ZONE_LABELS = {
    "price_gap": "价格缺口区",
    "value_opportunity": "性价比机会区",
    "demand_heat": "需求热度区",
    "red_ocean": "红海警示区",
    "neutral": "中性区",
}


def _fill_rating_median_price(df: pd.DataFrame) -> pd.Series:
    """同评分段价格中位数（评分段: 0-3 / 3-4 / 4-4.5 / 4.5-5）。"""
    bins = [0, 3, 4, 4.5, 5.01]
    labels = ["0-3", "3-4", "4-4.5", "4.5-5"]
    group = pd.cut(df["rating"].fillna(0), bins=bins, labels=labels, right=False)
    return df.groupby(group, observed=True)["current_price"].transform("median")


def classify_zones(df: pd.DataFrame) -> pd.DataFrame:
    """输入含 current_price / rating / review_count / est_monthly_sales / is_fba 的 DataFrame，
    输出新增 zone 列（copy，不改原数据）。"""
    df = df.copy()
    if df.empty:
        df["zone"] = pd.Series(dtype=str)
        return df

    # 缺失列兜底（防御：缺 est_monthly_sales / is_fba / review_count 仍可分区）
    for col, default in (("est_monthly_sales", 0), ("is_fba", False), ("review_count", 0)):
        if col not in df.columns:
            df[col] = default

    n = len(df)
    p25, p50, p75 = df["current_price"].quantile([0.25, 0.5, 0.75])
    p80 = df["est_monthly_sales"].fillna(0).quantile(0.80)
    price_median_for_rating = _fill_rating_median_price(df)
    is_fba = df["is_fba"].fillna(False)

    df["zone"] = "neutral"

    # 规则 1：价格缺口带
    mask = (
        df["current_price"].between(p50, p75)
        & (df["est_monthly_sales"].fillna(0) > p80)
    )
    df.loc[mask, "zone"] = "price_gap"

    # 规则 2：性价比机会区
    mask = (
        (df["current_price"] < price_median_for_rating * 0.85)
        & (df["review_count"].fillna(0) < 500)
    )
    df.loc[mask, "zone"] = "value_opportunity"

    # 规则 3：需求热度区（FBM 主导：is_fba=False）
    mask = (
        (df["est_monthly_sales"].fillna(0) > p80)
        & (~is_fba)
    )
    df.loc[mask, "zone"] = "demand_heat"

    # 规则 4：红海警示区
    mask = (
        df["current_price"].between(p50 * 0.9, p50 * 1.1)
        & (df["review_count"].fillna(0) > 1000)
        & is_fba
    )
    df.loc[mask, "zone"] = "red_ocean"

    # 汇总规则阈值（供报告与 LLM 解读上下文）
    df.attrs["zoning_rules"] = {
        "price_gap": {"price_range": [round(p50, 2), round(p75, 2)],
                      "demand_threshold": round(p80, 0), "count": int((df["zone"] == "price_gap").sum())},
        "value_opportunity": {"price_threshold": round(p25, 2), "review_threshold": 500,
                              "count": int((df["zone"] == "value_opportunity").sum())},
        "demand_heat": {"demand_threshold": round(p80, 0), "fbm_ratio_min": 0.5,
                        "count": int((df["zone"] == "demand_heat").sum())},
        "red_ocean": {"price_band": [round(p50 * 0.9, 2), round(p50 * 1.1, 2)],
                      "review_threshold": 1000, "count": int((df["zone"] == "red_ocean").sum())},
    }
    return df


def zone_summary(df: pd.DataFrame) -> dict:
    """分区计数摘要。"""
    counts = df["zone"].value_counts().to_dict()
    return {z: int(counts.get(z, 0)) for z in ZONES}


def zone_samples(df: pd.DataFrame, zone: str, limit: int = 3) -> list[dict]:
    """某区代表竞品（按月销估算降序），供 LLM 解读上下文。"""
    sub = df[df["zone"] == zone].sort_values(
        "est_monthly_sales", ascending=False, na_position="last")
    out = []
    for _, r in sub.head(limit).iterrows():
        out.append({
            "asin": r.get("asin"), "title": str(r.get("title") or "")[:40],
            "price": r.get("current_price"), "rating": r.get("rating"),
            "review_count": r.get("review_count"),
            "est_monthly_sales": r.get("est_monthly_sales"),
        })
    return out
