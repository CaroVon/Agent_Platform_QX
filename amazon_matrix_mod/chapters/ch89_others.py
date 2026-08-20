"""第 8/9/10/11 章：Listing 对标 / 变体策略 / 履约结构 / 广告竞争度（SVG 渲染）。"""
from __future__ import annotations

from collections import Counter

import pandas as pd

from amazon_matrix_mod.chapters.common import save_chart
from amazon_matrix_mod.svgcharts import charts
from amazon_matrix_mod.svgcharts.style import C


# ─── 第 8 章：Listing 质量对标 ─────────────────────────────

def _listing_score(product_raw: dict) -> dict:
    p = product_raw or {}
    bullets = p.get("feature_bullets") or []
    images = p.get("images") or []
    specs = p.get("specifications") or []
    a_plus = bool((p.get("a_plus_content") or {}).get("has_a_plus_content"))
    return {
        "bullets": len(bullets),
        "bullet_len": sum(len(b) for b in bullets),
        "images": len(images),
        "a_plus": a_plus,
        "specs": len(specs),
        "videos": p.get("videos_count") or 0,
        "documents": len(p.get("documents") or []),
    }


def _listing_total(product_raw: dict) -> float:
    """综合分（0-100）：卖点/图片/规格/视频/A+ 各 20 分加权（与旧口径一致）。"""
    s = _listing_score(product_raw)
    dims = [("bullets", 5), ("images", 7), ("specs", 20), ("videos", 3)]
    score = sum(min(s[k], cap) / cap * 20 for k, cap in dims)
    score += 20 if s["a_plus"] else 0
    return round(score, 1)


def ch08_listing(df: pd.DataFrame, products_raw: dict, out_dir: str) -> dict:
    rows = []
    for asin in df["asin"]:
        raw = products_raw.get(asin)
        if raw:
            s = _listing_score(raw)
            s["asin"] = asin
            s["brand"] = raw.get("brand") or df[df["asin"] == asin].iloc[0].get("brand")
            s["score"] = _listing_total(raw)
            rows.append(s)
    if not rows:
        return {"title": "Listing 质量对标", "conclusion": ["无原始数据"], "images": [],
                "md": "## 8. Listing 质量对标\n\n- 无原始数据\n"}
    ldf = pd.DataFrame(rows).set_index("asin")
    ranked = ldf.sort_values("score", ascending=False).head(10)

    def _draw(root):
        charts.bar_h(root, 40, 60, 1020, 360,
                     [{"label": str(r["brand"])[:14], "value": float(r["score"]),
                       "display": f"{r['score']:.0f}"}
                      for _, r in ranked.iterrows()],
                     title="竞品 Listing 质量对标（Top10，卖点/图片/规格/视频/A+ 加权）",
                     label_width=150)

    img = save_chart(_draw, out_dir, "ch08_listing_score.svg")
    med = ldf["score"].median()
    conclusions = [
        f"Listing 综合分中位 {med:.0f}/100；"
        f"Top1 {str(ranked.iloc[0]['brand'])[:14]}（{ranked.iloc[0]['score']} 分）",
        f"低分项集中在{'A+ 内容' if (~ldf['a_plus'].astype(bool)).sum() > len(ldf) / 2 else '视频/文档'} "
        f"—— 我方上架可快速建立的内容优势"]
    return {"title": "Listing 质量对标", "conclusion": conclusions, "images": [img],
            "md": _md_simple(8, "Listing 质量对标", conclusions)}


# ─── 第 9 章：变体与规格策略 ─────────────────────────────

def ch09_variants(df: pd.DataFrame, products_raw: dict, out_dir: str) -> dict:
    rows = []
    for asin in df["asin"]:
        raw = products_raw.get(asin) or {}
        variants = raw.get("variants") or []
        rows.append({"asin": asin,
                     "brand": raw.get("brand") or df[df["asin"] == asin].iloc[0].get("brand"),
                     "variants": len(variants),
                     "color": raw.get("color") or ""})
    vdf = pd.DataFrame(rows)
    top = vdf.nlargest(8, "variants")

    def _draw(root):
        charts.bar_h(root, 40, 60, 1020, 340,
                     [{"label": str(b)[:14], "value": int(v), "color": C.AMBER}
                      for b, v in zip(top["brand"], top["variants"])],
                     title="竞品变体策略（Top8，颜色/规格数）",
                     label_width=150)

    img = save_chart(_draw, out_dir, "ch09_variants.svg")
    med = vdf["variants"].median()
    conclusions = [
        f"竞品变体数中位 {med:.0f}；"
        f"{'多变体覆盖为主流策略' if med >= 3 else '市场以单变体为主，多变体是差异化空间'}"]
    return {"title": "变体与规格策略", "conclusion": conclusions, "images": [img],
            "md": _md_simple(9, "变体与规格策略", conclusions)}


# ─── 第 10 章：履约与卖家结构 ────────────────────────────

def ch10_fulfillment(df: pd.DataFrame, out_dir: str) -> dict:
    fba = int(df["is_fba"].fillna(False).sum())
    fbm = len(df) - fba

    def _draw(root):
        charts.donut(root, 300, 240, 120,
                     [{"label": f"FBA/Prime {fba}", "value": fba, "color": C.GREEN},
                      {"label": f"FBM {fbm}", "value": fbm, "color": C.GREY}],
                     center_total=f"{fba / max(len(df), 1) * 100:.0f}%",
                     center_label="FBA 占比",
                     legend_x=640, legend_y=200)

    img = save_chart(_draw, out_dir, "ch10_fulfillment.svg")
    ratio = fba / len(df) if len(df) else 0
    conclusions = [
        f"FBA/Prime 占比 {ratio * 100:.0f}%"
        f"（{'履约高度标准化，价格与内容竞争' if ratio > 0.7 else 'FBM 占比可观，物流体验是差异化点'}）"]
    return {"title": "履约与卖家结构", "conclusion": conclusions, "images": [img],
            "md": _md_simple(10, "履约与卖家结构", conclusions)}


# ─── 第 11 章：广告与流量竞争度 ──────────────────────────

def ch11_ads(search_raw: dict | None, out_dir: str) -> dict:
    if not search_raw:
        return {"title": "广告与流量竞争度", "conclusion": ["无 search 原始数据"],
                "images": [], "md": "## 11. 广告与流量竞争度\n\n- 无 search 原始数据\n"}
    results = search_raw.get("search_results") or []
    sponsored = [r for r in results if r.get("sponsored")]
    n = len(results)
    if not n:
        return {"title": "广告与流量竞争度", "conclusion": ["无搜索结果"], "images": [],
                "md": "## 11. 广告与流量竞争度\n\n- 无搜索结果\n"}
    # 广告位品牌
    ad_brands = Counter()
    for r in sponsored:
        t = r.get("title") or ""
        ad_brands[t.split()[0] if t else "?"] += 1

    def _draw(root):
        charts.bar_h(root, 40, 60, 1020, 260,
                     [{"label": "自然位", "value": n - len(sponsored), "color": C.BLUE},
                      {"label": "广告位", "value": len(sponsored), "color": C.AMBER}],
                     title=f"搜索首页广告密度（广告占比 {len(sponsored) / n * 100:.0f}%",
                     label_width=150)

    img = save_chart(_draw, out_dir, "ch11_ads_density.svg")
    ratio = len(sponsored) / n
    ad_brand_desc = "、".join(f"{b}({c})" for b, c in ad_brands.most_common(3))
    conclusions = [
        f"首页广告占比 {ratio * 100:.0f}%"
        f"（{'广告竞争激烈，需高预算或差异化' if ratio > 0.4 else '广告竞争温和'}）",
        f"广告位主力品牌：{ad_brand_desc or '无'}"]
    return {"title": "广告与流量竞争度", "conclusion": conclusions, "images": [img],
            "md": _md_simple(11, "广告与流量竞争度", conclusions)}


def _md_simple(num: int, title: str, conclusions: list[str]) -> str:
    return f"## {num}. {title}\n\n" + "\n".join(f"- {c}" for c in conclusions) + "\n"
