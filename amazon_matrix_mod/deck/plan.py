"""deck 页面规划 —— 按数据可得性自适应选择页面与顺序。"""
from __future__ import annotations

from amazon_matrix_mod.deck import pages


def plan_pages(ctx: dict) -> list[tuple[str, object]]:
    """返回 [(文件名, 构建器)]，文件名数字前缀决定 pptx 页序。"""
    df = ctx.get("df")
    has_price = bool(df is not None and df["current_price"].notna().sum() >= 4)
    has_sales = bool(df is not None and df["est_monthly_sales"].notna().sum() >= 3)
    ch7 = next((c for c in (ctx.get("chapters") or []) if c.get("num") == 7), None)
    has_reviews = bool(ch7 and ch7.get("conclusion")
                       and "无评论数据" not in ch7["conclusion"][0])
    has_products_raw = bool(ctx.get("products_raw"))

    plan: list[tuple[str, object]] = [
        ("slide_01_cover.svg", pages.page_cover),
        ("slide_02_executive_summary.svg", pages.page_exec_summary),
        ("slide_03_market_overview.svg", pages.page_market_overview),
    ]
    seq = 4
    if has_price:
        plan.append((f"slide_{seq:02d}_price_bands.svg", pages.page_price_bands))
        seq += 1
    if has_sales:
        plan.append((f"slide_{seq:02d}_demand.svg", pages.page_demand))
        seq += 1
    # 核心主图页（需求 2）——恒在有数据时包含
    if df is not None and len(df):
        plan.append((f"slide_{seq:02d}_matrix.svg", pages.page_matrix))
        seq += 1
    plan.append((f"slide_{seq:02d}_zones.svg", pages.page_zones))
    seq += 1
    if has_reviews:
        plan.append((f"slide_{seq:02d}_reviews.svg", pages.page_reviews))
        seq += 1
    if has_products_raw:
        plan.append((f"slide_{seq:02d}_listing_fulfillment.svg",
                     pages.page_listing_fulfillment))
        seq += 1
    plan.append((f"slide_{seq:02d}_strategy.svg", pages.page_strategy))
    seq += 1
    plan.append((f"slide_{seq:02d}_appendix.svg", pages.page_appendix))
    return plan
