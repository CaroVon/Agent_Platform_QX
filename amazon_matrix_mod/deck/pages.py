"""deck 页面构建 —— 确定性数据 → 1280×720 页面 SVG（ppt-master 画布契约）。

页面规范与主管线（PptDesignAgent）对齐：
  - 主题：THEME_PRESETS（deck/themes.Theme 注入 ctx["theme"]）
  - 内容页：左上标题 26px 加粗 + 主色强调竖条 + insight 副标题 14px 主色
  - 封面：浅色 hero 风格（image-01 封面图低透明铺底 + 主色条 + 大标题）
  - 页脚/根属性/字号白名单：由 build.write_pages 统一后处理（deck/chrome.py）
所有数值来自真实数据（ctx['df'] 等），缺失显式标注「数据缺失」，禁止编造。
"""
from __future__ import annotations

import base64
import os
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd

from amazon_matrix_mod.svgcharts import charts
from amazon_matrix_mod.svgcharts.svg import el, fmt, svg_document, text
from amazon_matrix_mod.svgcharts.style import FONT_CHAIN, SERIES, ZONE_COLORS
from amazon_matrix_mod import zoning

W, H = 1280, 720
MX = 56          # 左右边距
HEADER_Y = 80    # 标题基线


def _wrap(content: str, width_px: float, size: float, line_h: float = 1.65) -> list[str]:
    """按像素宽度断行（CJK 全宽 / ASCII 0.55 宽估算）。"""
    lines, cur, cur_w = [], "", 0.0
    for ch in content:
        cw = size * (1.0 if ord(ch) > 0x2E7F else 0.55)
        if cur_w + cw > width_px and cur:
            lines.append(cur)
            cur, cur_w = "", 0.0
        cur += ch
        cur_w += cw
    if cur:
        lines.append(cur)
    return lines


def _paragraph(parent, x, y, width, content: str, *, size=13, fill=None,
               line_h=None, max_lines=None) -> float:
    """段落实排。返回下一行基线 y。"""
    from amazon_matrix_mod.svgcharts.style import C
    fill = fill or C.INK
    line_h = line_h or size * 1.65
    lines = _wrap(content or "—", width, size)
    if max_lines:
        lines = lines[:max_lines]
    for i, ln in enumerate(lines):
        text(parent, x, y + i * line_h, ln, size=size, fill=fill, family=FONT_CHAIN)
    return y + len(lines) * line_h


def _page(page_id: str, theme) -> ET.Element:
    root = svg_document(W, H, bg=theme.bg)
    return root


def _header(root, theme, title: str, subtitle: str | None = None) -> None:
    """主管线规范：左上标题 26 加粗 + 主色强调竖条 + insight 14 主色。"""
    # 强调竖条（标题左侧）
    el(root, "rect", x=MX, y=HEADER_Y - 21, width=6, height=28, rx=2,
       fill=theme.primary)
    text(root, MX + 18, HEADER_Y, title, size=26, fill=theme.text,
         weight="bold", family=FONT_CHAIN)
    if subtitle:
        text(root, MX + 18, HEADER_Y + 30, subtitle, size=14,
             fill=theme.primary, family=FONT_CHAIN)


def _provenance_note(root, theme, note: str | None = None) -> None:
    """数据溯源注记（页脚线上方，不占 chrome 页脚位）。"""
    if note:
        text(root, W - MX, 674, note, size=9.5, fill=theme.muted,
             anchor="end", family=FONT_CHAIN)


def _embed_image(parent, path: str | None, x, y, w, h, rounded: float = 10,
                 uid: str = "img", opacity: float | None = None) -> bool:
    """嵌入位图（等比 contain，圆角裁剪）。失败返回 False。

    clipPath 放 <defs> 直接子元素（svg_to_pptx 契约）。
    """
    if not path or not os.path.isfile(path) or os.path.getsize(path) < 1000:
        return False
    mime = "image/png" if path.lower().endswith(".png") else "image/jpeg"
    with open(path, "rb") as f:
        uri = f"data:{mime};base64,{base64.b64encode(f.read()).decode()}"
    defs = el(parent, "defs")
    clip = el(defs, "clipPath", id=f"{uid}-clip")
    el(clip, "rect", x=x, y=y, width=w, height=h, rx=rounded)
    img = el(parent, "image", x=x, y=y, width=w, height=h,
             preserveAspectRatio="xMidYMid meet", href=uri,
             clip_path=f"url(#{uid}-clip)")
    if opacity is not None:
        img.set("opacity", fmt(opacity))
    return True


def _safe(f, digits=2, prefix="", suffix=""):
    if f is None or (isinstance(f, float) and np.isnan(f)):
        return "数据缺失"
    return f"{prefix}{f:,.{digits}f}{suffix}"


def _val(record: dict, key: str):
    """pandas 行取值：NaN → None（NaN 是 truthy，直接 get 会漏判）。"""
    v = record.get(key)
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    return v


def _th(ctx: dict):
    from amazon_matrix_mod.deck.themes import Theme
    return ctx.get("theme") or Theme("cyber-ivory-navy")


# ─────────────────────────── 页面构建器 ───────────────────────────
# ctx 结构：{df, interpretation, rules, chapters(list), exec_summary,
#           m3_insights, visuals, keyword, marketplace, fetched_at,
#           credits, our_asin, image_cache_dir, zone_summary, search_raw,
#           theme(Theme)}

def page_cover(ctx: dict, rev: dict | None = None) -> ET.Element:
    """封面：浅色 hero 风格（与主 deck 封面同构）。"""
    th = _th(ctx)
    root = _page("cover", th)
    vis = ctx.get("visuals") or {}
    # hero 低透明铺底（主管线封面惯例）
    if vis.get("cover"):
        if _embed_image(root, vis["cover"], 0, 0, W, H, rounded=0,
                        uid="coverbg", opacity=0.35):
            # 铺底后加同色系浅遮罩保证文字可读
            el(root, "rect", x=0, y=0, width=W, height=H, fill=th.bg,
               opacity=0.45)
    el(root, "rect", x=MX, y=252, width=72, height=8, rx=4, fill=th.primary)
    text(root, MX, 330, "亚马逊竞品矩阵 MOD 分析", size=48, fill=th.text,
         weight="bold", family=FONT_CHAIN)
    text(root, MX, 396, ctx.get("keyword", ""), size=30, fill=th.primary,
         family=FONT_CHAIN)
    df = ctx.get("df")
    meta = (f"站点 {ctx.get('marketplace', '—')} ｜ "
            f"{len(df) if df is not None else 0} 个竞品样本 ｜ "
            f"数据源 Rainforest API ｜ 抓取 {ctx.get('fetched_at', '—')}")
    text(root, MX, 458, meta, size=15, fill=th.muted, family=FONT_CHAIN)
    if ctx.get("our_asin"):
        text(root, MX, 488, f"我方 ASIN：{ctx['our_asin']}", size=14,
             fill=th.muted, family=FONT_CHAIN)
    el(root, "rect", x=MX, y=620, width=W - 2 * MX, height=1,
       fill=th.muted, opacity=0.4)
    text(root, MX, 648, "价格 × 销量四区矩阵 ｜ 14 章数据驱动分析 ｜ M3 增强审校",
         size=13, fill=th.muted, family=FONT_CHAIN)
    return root


def page_exec_summary(ctx: dict, rev: dict | None = None) -> ET.Element:
    from amazon_matrix_mod.svgcharts.style import C
    th = _th(ctx)
    root = _page("executive_summary", th)
    _header(root, th, "执行摘要", ctx.get("keyword", ""))
    df: pd.DataFrame = ctx["df"]
    prices = df["current_price"].dropna()
    sales = df["est_monthly_sales"].dropna()
    ratings = df["rating"].dropna()
    cards = [
        {"value": str(len(df)), "label": "竞品样本", "color": th.primary},
        {"value": _safe(prices.median(), 2, "$"), "label": "价格中位数",
         "color": th.accent},
        {"value": _safe(sales.median(), 0), "label": "月销中位数",
         "color": ZONE_COLORS["price_gap"]},
        {"value": _safe(ratings.mean(), 2), "label": "平均评分",
         "color": ZONE_COLORS["demand_heat"]},
    ]
    if len(prices) >= 4:
        p25, p75 = prices.quantile([0.25, 0.75])
        cards.append({"value": f"${p25:,.0f}-${p75:,.0f}", "label": "主流价格带",
                      "color": ZONE_COLORS["red_ocean"]})
    charts.kpi_cards(root, MX, 140, W - 2 * MX, 92, cards)

    y = 280
    text(root, MX, y, "核心结论", size=16, fill=th.primary, weight="600",
         family=FONT_CHAIN)
    y += 24
    summary = ctx.get("exec_summary") or ""
    for ch in (ctx.get("chapters") or []):
        if ch.get("num") == 1 and ch.get("conclusion"):
            summary = summary or ch["conclusion"][0]
    if summary:
        y = _paragraph(root, MX, y, W - 2 * MX, summary, size=14)
    else:
        y = _paragraph(root, MX, y, W - 2 * MX, "（执行摘要生成中/缺失）", size=14,
                       fill=th.muted)
    interp = ctx.get("interpretation") or {}
    if interp.get("verdict"):
        el(root, "rect", x=MX, y=y + 16, width=W - 2 * MX, height=64, rx=10,
           fill=th.surface, stroke=th.accent, stroke_width=1.5)
        el(root, "rect", x=MX, y=y + 16, width=5, height=64, rx=2,
           fill=th.accent)
        text(root, MX + 20, y + 42, "我方定位建议", size=12, fill=th.muted,
             family=FONT_CHAIN)
        text(root, MX + 20, y + 66, interp["verdict"], size=15, fill=th.text,
             weight="600", family=FONT_CHAIN)
    m3 = ctx.get("m3_insights") or {}
    if m3.get("insights"):
        yi = 560
        text(root, MX, yi, "M3 图审洞察", size=14, fill=th.primary, weight="600",
             family=FONT_CHAIN)
        for i, ins in enumerate(m3["insights"][:3]):
            text(root, MX, yi + 24 + i * 24, f"• {ins}", size=12.5, fill=th.text,
                 family=FONT_CHAIN)
    _provenance_note(root, th, f"N={len(df)}")
    return root


def page_market_overview(ctx: dict, rev: dict | None = None) -> ET.Element:
    from amazon_matrix_mod.svgcharts.style import C
    th = _th(ctx)
    root = _page("market_overview", th)
    _header(root, th, "市场概览：品牌集中度与广告强度",
            f"关键词：{ctx.get('keyword', '')}")
    df: pd.DataFrame = ctx["df"]
    by_brand = (df.groupby(df["brand"].fillna("未知"))
                .agg(sales=("est_monthly_sales", "sum"),
                     reviews=("review_count", "sum")).reset_index())
    by_brand["sales"] = by_brand["sales"].fillna(0)
    by_brand = by_brand.sort_values("sales", ascending=False)
    total_sales = by_brand["sales"].sum() or 1
    top = by_brand.head(8)
    items = [{"label": str(b["brand"])[:14],
              "value": float(b["sales"] or 0),
              "color": SERIES[i % len(SERIES)]}
             for i, (_, b) in enumerate(top.iterrows())]
    g1 = el(root, "g")
    charts.bar_h(g1, MX, 160, 700, 420, items, title="品牌预估月销份额（Top8）",
                 label_width=170)

    # HHI（0-1 归一化口径，与 ch02 一致：Σ份额²）
    from amazon_matrix_mod.chapters.ch02_market import hhi as _hhi
    h = _hhi([float(v) / total_sales for v in by_brand["sales"]]) \
        if total_sales else None
    hhi_txt = f"{h:.3f}" if h is not None else "数据缺失"
    conc = "高集中（寡头）" if h and h > 0.25 else \
        ("中等集中" if h and h > 0.15 else "低集中（分散）")
    el(root, "rect", x=800, y=160, width=W - MX - 800, height=130, rx=10,
       fill=th.surface, stroke=C.GRID)
    text(root, 820, 200, "品牌集中度 HHI", size=13, fill=th.muted, family=FONT_CHAIN)
    text(root, 820, 240, hhi_txt, size=30, fill=th.primary, weight="700",
         family=FONT_CHAIN)
    text(root, 820, 268, conc, size=12.5, fill=th.text, family=FONT_CHAIN)

    # 广告位占比（search_raw sponsored）
    sr = ctx.get("search_raw") or {}
    results = sr.get("search_results") or []
    if results:
        sponsored = sum(1 for r in results if r.get("sponsored"))
        nons = len(results) - sponsored
        charts.donut(root, 880, 460, 80,
                     [{"label": "自然位", "value": nons, "color": th.primary},
                      {"label": "广告位", "value": sponsored,
                       "color": ZONE_COLORS["red_ocean"]}],
                     center_total=f"{nons / max(len(results), 1) * 100:.0f}%",
                     center_label="自然位占比",
                     legend_x=830, legend_y=580)
    else:
        text(root, 880, 460, "广告占比：数据缺失（无 search_raw）", size=12,
             fill=th.muted, family=FONT_CHAIN)
    _provenance_note(root, th, f"N={len(df)} ｜ HHI 基于预估月销份额")
    return root


def page_price_bands(ctx: dict, rev: dict | None = None) -> ET.Element:
    th = _th(ctx)
    root = _page("price_bands", th)
    _header(root, th, "价格带结构：分位与缺口检测", ctx.get("keyword", ""))
    df: pd.DataFrame = ctx["df"]
    prices = [float(v) for v in df["current_price"].dropna() if v and v > 0]
    from amazon_matrix_mod.chapters.ch03_price import find_price_gaps
    if len(prices) >= 4:
        p25, p50, p75 = np.quantile(prices, [0.25, 0.5, 0.75])
        gaps = find_price_gaps(prices)
        charts.histogram(root, MX, 170, W - 2 * MX, 380, prices,
                         bins=12, quantiles={"P25": p25, "P50": p50, "P75": p75},
                         gaps=gaps,
                         title=f"价格分布（N={len(prices)}）",
                         font_scale=float((rev or {}).get("font_scale") or 1.0))
        y = 600
        concl = [f"中位价 ${p50:,.2f}，主流带 P25-P75 = ${p25:,.2f}-${p75:,.2f}"]
        if gaps:
            concl.append("价格缺口带：" + "、".join(
                f"${g['low']:,.0f}-${g['high']:,.0f}" for g in gaps[:3])
                + "（差异化切入价位）")
        else:
            concl.append("未检测到显著价格空档（≥8% 价程连续空 bin）")
        for i, c in enumerate(concl):
            text(root, MX, y + i * 26, f"• {c}", size=13.5, fill=th.text,
                 family=FONT_CHAIN)
    else:
        text(root, W / 2, 380, "数据缺失（有效价格样本 < 4）", size=14,
             fill=th.muted, anchor="middle", family=FONT_CHAIN)
    _provenance_note(root, th, "缺口判定：连续空 bin 跨度 ≥ 总价程 8%")
    return root


def page_demand(ctx: dict, rev: dict | None = None) -> ET.Element:
    from amazon_matrix_mod.svgcharts.style import C
    th = _th(ctx)
    root = _page("demand", th)
    _header(root, th, "需求结构：价格-销量弹性", ctx.get("keyword", ""))
    df: pd.DataFrame = ctx["df"]
    pts = [(float(r["current_price"]), float(r["est_monthly_sales"]))
           for _, r in df.iterrows()
           if pd.notna(r.get("current_price")) and pd.notna(r.get("est_monthly_sales"))]
    charts.scatter_fit(
        root, MX, 170, 700, 440, pts,
        x_label="价格 $", y_label="预估月销",
        fit_note="log-log OLS 弹性斜率 = {slope:.2f}",
        title=f"价格-销量弹性（有效样本 {len(pts)}）")
    # Top 销量榜（真实数据）
    top = df.dropna(subset=["est_monthly_sales"]) \
        .sort_values("est_monthly_sales", ascending=False).head(8)
    rows = [[str(r["asin"]), str(_val(r, "brand") or "—")[:10],
             _safe(_val(r, "current_price"), 2, "$"),
             f"{int(r['est_monthly_sales']):,}",
             _safe(_val(r, "rating"), 1, "", "★")]
            for _, r in top.iterrows()]
    text(root, 800, 190, "月销 Top 榜", size=15, fill=th.primary, weight="600",
         family=FONT_CHAIN)
    charts.table(root, 800, 210, W - MX - 800,
                 ["ASIN", "品牌", "价格", "月销", "评分"], rows,
                 row_h=30, font_size=11, max_rows=8,
                 col_align=["start", "start", "end", "end", "end"])
    sales = df["est_monthly_sales"].dropna()
    if len(sales):
        text(root, 800, 500,
             f"月销合计 ≈ {sales.sum():,.0f} ｜ 中位 {sales.median():,.0f}",
             size=12.5, fill=th.text, family=FONT_CHAIN)
    no_sales = int(df["est_monthly_sales"].isna().sum())
    if no_sales:
        text(root, 800, 526, f"（{no_sales} 个样本无销量数据，未计入）",
             size=11, fill=th.muted, family=FONT_CHAIN)
    _provenance_note(root, th, "月销=recent_sales 官方口径，缺失回退 BSR 系数估算")
    return root


def page_matrix(ctx: dict, rev: dict | None = None) -> ET.Element:
    """★ 核心主图页：价格×月销矩阵，缩略图=竞品主图（需求 2）。"""
    th = _th(ctx)
    root = _page("matrix", th)
    rev = rev or {}
    _header(root, th, "价格 × 月销竞品矩阵",
            f"{ctx.get('keyword', '')} ｜ 缩略图=竞品主图，边框色=分区，尺寸∝评论数")
    g = el(root, "g")
    cap = 88.0
    if rev.get("thumb_scale"):
        cap = 88.0 * float(rev["thumb_scale"])
    meta = charts.matrix_chart(
        g, MX - 16, 140, W - 2 * MX + 32, 520, df=ctx["df"],
        our_asin=ctx.get("our_asin"), image_cache_dir=ctx.get("image_cache_dir"),
        uid="deck-mx", thumb_cap=cap)
    notes = [f"N={meta.get('n', 0)}"]
    if meta.get("no_sales"):
        notes.append(f"† {meta['no_sales']} 个竞品无销量数据（置于底部低销区）")
    if meta.get("shown", 99) < meta.get("n", 0):
        notes.append(f"仅展示销量 Top{meta['shown']}")
    notes.append("虚线=被挤开缩略图的引出锚点")
    _provenance_note(root, th, " ｜ ".join(notes))
    return root


def _fmt_rule(rule) -> str:
    """分区规则 → 可读文本（numpy 数值转普通数字，隐藏 count）。"""
    if isinstance(rule, dict):
        parts = []
        for k, v in rule.items():
            if k == "count":
                continue
            if isinstance(v, (list, tuple)):
                v = "-".join(f"{float(x):g}" for x in v)
            elif isinstance(v, (int, float, np.floating)):
                v = f"{float(v):g}"
            parts.append(f"{k}={v}")
        return ", ".join(parts)
    return str(rule)


def page_zones(ctx: dict, rev: dict | None = None) -> ET.Element:
    from amazon_matrix_mod.svgcharts.style import C
    th = _th(ctx)
    root = _page("zones", th)
    _header(root, th, "四区解读：机会与风险", ctx.get("keyword", ""))
    interp = ctx.get("interpretation") or {}
    rules = ctx.get("rules") or {}
    df: pd.DataFrame = ctx["df"]
    vis = ctx.get("visuals") or {}
    counts = df["zone"].value_counts().to_dict() if "zone" in df else {}
    neutral_n = int(counts.get("neutral", 0))
    cw, ch = (W - 2 * MX - 24) / 2, 240
    for i, (zone, label) in enumerate(zoning.ZONE_LABELS.items()):
        if zone == "neutral":
            continue
        cx = MX + (i % 2) * (cw + 24)
        cy = 150 + (i // 2) * (ch + 20)
        color = ZONE_COLORS[zone]
        el(root, "rect", x=cx, y=cy, width=cw, height=ch, rx=12, fill=th.surface,
           stroke=C.GRID)
        el(root, "rect", x=cx, y=cy, width=cw, height=6, rx=3, fill=color)
        text(root, cx + 20, cy + 38, label, size=17, fill=color, weight="700",
             family=FONT_CHAIN)
        text(root, cx + cw - 20, cy + 38, f"{counts.get(zone, 0)} 个竞品",
             size=13, fill=th.muted, anchor="end", family=FONT_CHAIN)
        ix = cx + 20
        if vis.get("zones", {}).get(zone):
            if _embed_image(root, vis["zones"][zone], cx + cw - 120, cy + 56,
                            96, 96, rounded=12, uid=f"zone-{zone}"):
                ix = cx + 20  # 图占右上，文字左移受限
        _paragraph(root, ix, cy + 74, cw - 150 if vis.get("zones", {}).get(zone)
                   else cw - 40, interp.get(zone) or "（LLM 解读缺失）",
                   size=13, fill=th.text)
        if rules.get(zone):
            text(root, cx + 20, cy + ch - 18, f"规则：{_fmt_rule(rules[zone])}",
                 size=10.5, fill=th.muted, family=FONT_CHAIN)
    if neutral_n:
        text(root, W / 2, 668,
             f"※ {neutral_n} 个竞品未落入任何分区（阈值见上；小样本下建议扩充至 ≥20 再评估分区结论）",
             size=11.5, fill=th.muted, anchor="middle", family=FONT_CHAIN)
    _provenance_note(root, th, "分区=确定性规则引擎；解读=DeepSeek 4 区解读")
    return root


def page_reviews(ctx: dict, rev: dict | None = None) -> ET.Element:
    th = _th(ctx)
    root = _page("reviews", th)
    _header(root, th, "评论洞察：主题与痛点", ctx.get("keyword", ""))
    ch7 = next((c for c in (ctx.get("chapters") or []) if c.get("num") == 7), None)
    concl = (ch7 or {}).get("conclusion") or []
    y = 170
    if concl:
        for c in concl[:8]:
            y = _paragraph(root, MX, y, W - 2 * MX, f"• {c}", size=14) + 8
    else:
        text(root, MX, y, "无评论数据", size=14, fill=th.muted, family=FONT_CHAIN)
    _provenance_note(root, th, "词典聚类 + MiniMax-M3 深化（失败降级词典口径）")
    return root


def page_listing_fulfillment(ctx: dict, rev: dict | None = None) -> ET.Element:
    from amazon_matrix_mod.svgcharts.style import C
    th = _th(ctx)
    root = _page("listing_fulfillment", th)
    _header(root, th, "Listing 质量与履约结构", ctx.get("keyword", ""))
    df: pd.DataFrame = ctx["df"]
    products_raw = ctx.get("products_raw") or {}
    from amazon_matrix_mod.chapters.ch89_others import _listing_total
    items = []
    for _, r in df.head(8).iterrows():
        raw = products_raw.get(r["asin"]) or {}
        score = _listing_total(raw)
        items.append({"label": str(r.get("brand") or r["asin"])[-12:],
                      "value": float(score),
                      "display": f"{score:.0f}/100",
                      "color": th.primary if score >= 60 else ZONE_COLORS["demand_heat"]})
    g = el(root, "g")
    charts.bar_h(g, MX, 170, 640, 420, items, title="Listing 质量分（Top8）",
                 label_width=130)
    fba = df["is_fba"].dropna()
    if len(fba):
        charts.donut(root, 880, 300, 90,
                     [{"label": "FBA/Prime", "value": int(fba.sum()),
                       "color": th.primary},
                      {"label": "非 FBA", "value": int(len(fba) - fba.sum()),
                       "color": C.GREY}],
                     center_total=f"{fba.mean() * 100:.0f}%",
                     center_label="FBA 占比", legend_x=830, legend_y=430)
        text(root, 830, 500, "履约判定=buybox is_prime 代理口径", size=10.5,
             fill=th.muted, family=FONT_CHAIN)
    ch10 = next((c for c in (ctx.get("chapters") or []) if c.get("num") == 10), None)
    if ch10:
        for i, c in enumerate((ch10.get("conclusion") or [])[:3]):
            text(root, 830, 540 + i * 24, f"• {c}", size=12, fill=th.text,
                 family=FONT_CHAIN)
    _provenance_note(root, th, "")
    return root


def page_strategy(ctx: dict, rev: dict | None = None) -> ET.Element:
    th = _th(ctx)
    root = _page("strategy", th)
    _header(root, th, "战略建议：四区机会与定位", ctx.get("keyword", ""))
    interp = ctx.get("interpretation") or {}
    y = 180
    for zone, label in zoning.ZONE_LABELS.items():
        if zone == "neutral":
            continue
        color = ZONE_COLORS[zone]
        el(root, "rect", x=MX, y=y - 20, width=8, height=44, rx=4, fill=color)
        text(root, MX + 24, y, label, size=15.5, fill=color, weight="700",
             family=FONT_CHAIN)
        y = _paragraph(root, MX + 180, y, W - 2 * MX - 200,
                       interp.get(zone) or "（解读缺失）", size=13.5, max_lines=2) + 26
    if interp.get("verdict"):
        el(root, "rect", x=MX, y=560, width=W - 2 * MX, height=90, rx=12,
           fill=th.primary)
        text(root, MX + 24, 596, "我方定位建议", size=13, fill=th.bg,
             family=FONT_CHAIN)
        text(root, MX + 24, 630, interp["verdict"], size=18, fill="#FFFFFF",
             weight="600", family=FONT_CHAIN)
    return root


def page_appendix(ctx: dict, rev: dict | None = None) -> ET.Element:
    th = _th(ctx)
    root = _page("appendix", th)
    _header(root, th, "数据附录",
            f"{ctx.get('keyword', '')} ｜ 全量明细见 data.csv / data/")
    df: pd.DataFrame = ctx["df"]
    top = df.sort_values("est_monthly_sales", ascending=False,
                         na_position="last").head(12)
    rows = [[str(r["asin"]), str(_val(r, "title") or "")[:34],
             _safe(_val(r, "current_price"), 2, "$"),
             _safe(_val(r, "rating"), 1),
             f"{int(v):,}" if (v := _val(r, "review_count")) is not None else "—",
             f"{int(v2):,}" if (v2 := _val(r, "est_monthly_sales")) is not None else "—",
             zoning.ZONE_LABELS.get(r.get("zone"), r.get("zone") or "—")]
            for _, r in top.iterrows()]
    charts.table(root, MX, 150, W - 2 * MX,
                 ["ASIN", "标题", "价格", "评分", "评论数", "月销", "分区"], rows,
                 row_h=30, font_size=11, max_rows=12,
                 col_align=["start", "start", "end", "end", "end", "end", "start"])
    _provenance_note(root, th,
                     f"抓取 {ctx.get('fetched_at', '—')} ｜ credits≈{ctx.get('credits') or '—'}")
    return root
