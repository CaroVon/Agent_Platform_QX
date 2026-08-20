"""第 7 章：评论痛点与差异化机会 —— 确定性关键词聚类 + 可选 LLM 深化。

数据：reviews_raw（分页采集）优先，缺失时用 product 的 top_reviews。
"""
from __future__ import annotations

import re
from collections import Counter

import pandas as pd

from amazon_matrix_mod.chapters.common import BRAND_COLORS, fp, save_chart, setup_style

# 主题词典：关键词 → 主题（痛点/卖点方向）
_TOPICS = [
    ("质量/做工", ["quality", "cheap", "flimsy", "broken", "defect", "quality", "plastic",
                    "材质", "做工", "质量"]),
    ("续航/电池", ["battery", "charge", "battery life", "续航", "充电", "电量"]),
    ("连接/配对", ["connect", "pair", "bluetooth", "lag", "disconnect", "连接", "配对", "延迟", "断连"]),
    ("手感/舒适", ["comfort", "ergonomic", "hand", "wrist", "comfortable", "手感", "舒适", "握感"]),
    ("尺寸/便携", ["small", "large", "size", "portable", "compact", "尺寸", "便携", "大小"]),
    ("噪音/静音", ["noise", "silent", "loud", "click", "声音", "静音", "噪音"]),
    ("物流/包装", ["shipping", "delivery", "package", "arrive", "物流", "包装", "配送"]),
    ("客服/售后", ["customer service", "refund", "return", "support", "客服", "售后", "退款", "退货"]),
    ("兼容性", ["compatible", "mac", "windows", "chromebook", "兼容", "系统"]),
]


def _collect_reviews(reviews_raw: dict, products_raw: dict) -> list[dict]:
    """合并所有评论：分页优先，top_reviews 补充。"""
    out: list[dict] = []
    for asin, rv in (reviews_raw or {}).items():
        out.extend({"asin": asin, **r} for r in rv)
    if not out:
        for asin, raw in (products_raw or {}).items():
            for tr in (raw.get("top_reviews") or []):
                out.append({"asin": asin, "body": tr.get("body"),
                            "title": tr.get("title"), "rating": tr.get("rating")})
    return out


def _classify(body: str) -> list[str]:
    b = (body or "").lower()
    hits = [name for name, kws in _TOPICS if any(k in b for k in kws)]
    return hits


def analyze(df: pd.DataFrame, reviews_raw: dict, products_raw: dict, out_dir: str) -> dict:
    setup_style()
    import matplotlib.pyplot as plt

    reviews = _collect_reviews(reviews_raw, products_raw)
    conclusions: list[str] = []
    images: list[str] = []

    if not reviews:
        return {"title": "评论痛点与差异化机会", "conclusion": ["无评论数据（可加购 reviews 分页）"],
                "images": [], "md": "## 7. 评论痛点与差异化机会\n\n- 无评论数据\n"}

    topic_count: Counter = Counter()
    negative: list[str] = []
    positive: list[str] = []
    for r in reviews:
        body = r.get("body") or ""
        rating = r.get("rating")
        for t in _classify(body):
            topic_count[t] += 1
        if rating is not None and float(rating) <= 3:
            negative.append(body[:200])
        elif rating is not None and float(rating) >= 4 and len(body) > 60:
            positive.append(body[:200])

    total = len(reviews)
    # 主题频次图
    if topic_count:
        fig, ax = plt.subplots(figsize=(10, 4.4))
        items = topic_count.most_common(8)
        ax.barh([t for t, _ in items][::-1], [c for _, c in items][::-1],
                color=BRAND_COLORS["blue"], alpha=0.85)
        for i, (_, c) in enumerate(items[::-1]):
            ax.text(c + total * 0.01, i, str(c), va="center", fontsize=9)
        ax.set_xlabel("提及次数", fontproperties=fp(10))
        ax.set_title(f"评论主题分布（N={total}）", fontproperties=fp(12, "bold"))
        ax.tick_params(labelsize=9)
        fig.tight_layout()
        images.append(save_chart(fig, out_dir, "ch07_topics.png"))
        top_topic = topic_count.most_common(1)[0]
        conclusions.append(
            f"评论最高频主题：{top_topic[0]}（{top_topic[1]} 次提及，{top_topic[1] / total * 100:.0f}%）")

    # 差评痛点
    if negative:
        neg_topics = Counter(t for body in negative for t in _classify(body))
        if neg_topics:
            top_neg = neg_topics.most_common(2)
            conclusions.append(
                "差评核心痛点：" + "；".join(f"{t}（{c} 次）" for t, c in top_neg)
                + " —— 产品改进切入点")
    if positive:
        conclusions.append(f"好评样本 {len(positive)} 条（可用作卖点背书）")

    # 差评率（按评论样本）
    rated = [r for r in reviews if r.get("rating") is not None]
    if rated:
        bad_rate = sum(1 for r in rated if float(r["rating"]) <= 3) / len(rated)
        conclusions.append(f"样本差评率（≤3星）{bad_rate * 100:.0f}%")

    return {"title": "评论痛点与差异化机会", "conclusion": conclusions, "images": images,
            "md": _md(conclusions, reviews)}


def _md(conclusions: list[str], reviews: list[dict]) -> str:
    out = ["## 7. 评论痛点与差异化机会\n"]
    out += [f"- {c}" for c in conclusions]
    if reviews:
        out.append("\n### 评论样本")
        for r in reviews[:6]:
            body = (r.get("body") or "")[:100].replace("\n", " ")
            out.append(f"- [{r.get('asin')} {r.get('rating')}★] {body}")
    return "\n".join(out) + "\n"
