"""第 8/9/10/11 章：Listing 对标 / 变体策略 / 履约结构 / 广告竞争度。"""
from __future__ import annotations

import pandas as pd

from amazon_matrix_mod.chapters.common import BRAND_COLORS, fp, save_chart, setup_style


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


def ch08_listing(df: pd.DataFrame, products_raw: dict, out_dir: str) -> dict:
    setup_style()
    import matplotlib.pyplot as plt

    rows = []
    for asin in df["asin"]:
        raw = products_raw.get(asin)
        if raw:
            s = _listing_score(raw)
            s["asin"] = asin
            s["brand"] = raw.get("brand") or df[df["asin"] == asin].iloc[0].get("brand")
            rows.append(s)
    if not rows:
        return {"title": "Listing 质量对标", "conclusion": ["无原始数据"], "images": [],
                "md": "## 8. Listing 质量对标\n\n- 无原始数据\n"}
    ldf = pd.DataFrame(rows).set_index("asin")
    dims = [("bullets", "卖点数", 5), ("images", "图片数", 7), ("specs", "规格项", 20),
            ("videos", "视频数", 3), ("documents", "文档数", 3)]
    # 综合分（0-100）
    ldf = ldf.copy()
    score = 0
    for col, _label, _max in dims:
        score += (ldf[col].clip(upper=_max) / _max) * 20
    if "a_plus" in ldf:
        score += ldf["a_plus"].astype(int) * 20
    ldf["score"] = score.round(1)

    fig, ax = plt.subplots(figsize=(10, 5))
    ranked = ldf.sort_values("score", ascending=False).head(10)
    labels = [f"{str(r['brand'])[:12]}" for _, r in ranked.iterrows()]
    bars = ax.barh(labels[::-1], ranked["score"][::-1], color=BRAND_COLORS["blue"], alpha=0.85)
    for i, b in enumerate(bars):
        ax.text(b.get_width() + 1, b.get_y() + b.get_height() / 2,
                f"{ranked['score'][::-1].iloc[i]:.0f}", va="center", fontsize=9)
    ax.set_xlabel("Listing 综合分（卖点/图片/规格/视频/A+ 加权）", fontproperties=fp(10))
    ax.set_title("竞品 Listing 质量对标（Top10）", fontproperties=fp(12, "bold"))
    ax.tick_params(labelsize=9)
    fig.tight_layout()
    img = save_chart(fig, out_dir, "ch08_listing_score.png")
    med = ldf["score"].median()
    conclusions = [
        f"Listing 综合分中位 {med:.0f}/100；"
        f"Top1 {str(ranked.iloc[0]['brand'])[:14]}（{ranked.iloc[0]['score']} 分）",
        f"低分项集中在{'A+ 内容' if (ldf['a_plus'] == False).sum() > len(ldf) / 2 else '视频/文档'} "
        f"—— 我方上架可快速建立的内容优势"]
    return {"title": "Listing 质量对标", "conclusion": conclusions, "images": [img],
            "md": _md_simple(8, "Listing 质量对标", conclusions)}


# ─── 第 9 章：变体与规格策略 ─────────────────────────────

def ch09_variants(df: pd.DataFrame, products_raw: dict, out_dir: str) -> dict:
    setup_style()
    import matplotlib.pyplot as plt

    rows = []
    for asin in df["asin"]:
        raw = products_raw.get(asin) or {}
        variants = raw.get("variants") or []
        rows.append({"asin": asin,
                     "brand": raw.get("brand") or df[df["asin"] == asin].iloc[0].get("brand"),
                     "variants": len(variants),
                     "color": raw.get("color") or ""})
    vdf = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(10, 4.6))
    top = vdf.nlargest(8, "variants")
    ax.bar([str(b)[:14] for b in top["brand"]], top["variants"],
           color=BRAND_COLORS["amber"], alpha=0.9)
    for i, v in enumerate(top["variants"]):
        ax.text(i, v + 0.2, str(v), ha="center", fontsize=9)
    ax.set_ylabel("变体数（颜色/规格）", fontproperties=fp(10))
    ax.set_title("竞品变体策略（Top8）", fontproperties=fp(12, "bold"))
    ax.tick_params(labelsize=8.5)
    fig.tight_layout()
    img = save_chart(fig, out_dir, "ch09_variants.png")
    med = vdf["variants"].median()
    conclusions = [
        f"竞品变体数中位 {med:.0f}；{'多变体覆盖为主流策略' if med >= 3 else '市场以单变体为主，多变体是差异化空间'}"]
    return {"title": "变体与规格策略", "conclusion": conclusions, "images": [img],
            "md": _md_simple(9, "变体与规格策略", conclusions)}


# ─── 第 10 章：履约与卖家结构 ────────────────────────────

def ch10_fulfillment(df: pd.DataFrame, out_dir: str) -> dict:
    setup_style()
    import matplotlib.pyplot as plt

    fba = int(df["is_fba"].fillna(False).sum())
    fbm = len(df) - fba
    fig, ax = plt.subplots(figsize=(6.5, 4.6))
    ax.pie([fba, fbm], labels=[f"FBA/Prime {fba}", f"FBM {fbm}"],
           colors=[BRAND_COLORS["green"], BRAND_COLORS["grey"]],
           autopct="%1.0f%%", startangle=90,
           textprops={"fontproperties": fp(10)})
    ax.set_title("履约结构（FBA vs FBM）", fontproperties=fp(12, "bold"))
    fig.tight_layout()
    img = save_chart(fig, out_dir, "ch10_fulfillment.png")
    ratio = fba / len(df) if len(df) else 0
    conclusions = [
        f"FBA/Prime 占比 {ratio * 100:.0f}%"
        f"（{'履约高度标准化，价格与内容竞争' if ratio > 0.7 else 'FBM 占比可观，物流体验是差异化点'}）"]
    return {"title": "履约与卖家结构", "conclusion": conclusions, "images": [img],
            "md": _md_simple(10, "履约与卖家结构", conclusions)}


# ─── 第 11 章：广告与流量竞争度 ──────────────────────────

def ch11_ads(search_raw: dict | None, out_dir: str) -> dict:
    setup_style()
    import matplotlib.pyplot as plt

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
    from collections import Counter
    ad_brands = Counter()
    for r in sponsored:
        t = r.get("title") or ""
        ad_brands[t.split()[0] if t else "?"] += 1
    fig, ax = plt.subplots(figsize=(10, 4.4))
    ax.bar(["自然位", "广告位"], [n - len(sponsored), len(sponsored)],
           color=[BRAND_COLORS["blue"], BRAND_COLORS["amber"]], alpha=0.9)
    for i, v in enumerate([n - len(sponsored), len(sponsored)]):
        ax.text(i, v + 0.1, str(v), ha="center", fontsize=10)
    ax.set_ylabel("首页结果数", fontproperties=fp(10))
    ax.set_title(f"搜索首页广告密度（广告占比 {len(sponsored) / n * 100:.0f}%）",
                 fontproperties=fp(12, "bold"))
    ax.tick_params(labelsize=9)
    fig.tight_layout()
    img = save_chart(fig, out_dir, "ch11_ads_density.png")
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
