"""MOD 确定性组件库 —— 主 deck「竞品矩阵章节」的图表资产（P2.2）。

设计口径（源自 Desktop\\MOD 参考 + svg_final 质量基线）：
  - 每个组件为独立 SVG（1280×560 或 1280×620），落 {out_dir}/charts/；
    经光栅化 PNG 后作为页面图片组件嵌入主 deck（LLM 页面排版引用）。
  - chrome 色（底/卡面/文字/主色/网格）跟随 deck 主题（apply_theme）；
    分区语义色（绿/蓝/琥珀/红）保留在图表内部 —— 数据语义不随主题漂移，
    且作为图片嵌入不进入页面 SVG 的色板纪律检查。
  - 全部数据来自共享数据层（df 派生指标 + 分区），禁止编造；占位用 TBD。

组件清单（charts_index.json kind ↔ 主 deck 页型）：
  market_donut      → mod_overview   品牌份额环形 + ASP 气泡 + KPI 条
  demand_bars       → mod_overview   Top 销量竞品条形（含价格标注）
  price_bands       → mod_overview   价格带直方图（P25/P75 标注）
  zone_grid         → mod_overview   四分区卡片（计数 + 阈值）
  matrix_scatter    → mod_matrix     价格×月销对数散点（分区着色，缩略图省略版）
  spec_matrix       → mod_spec_comparison  参数对比矩阵（hero 先列 + 优势高亮）
  sku_channels      → mod_sku_analysis    FBA/卖家类型结构 + 分区交叉表
"""
from __future__ import annotations

import json
import math
import os

import pandas as pd

from amazon_matrix_mod.svgcharts import style
from amazon_matrix_mod.svgcharts.svg import el, fmt, save, svg_document, text
from amazon_matrix_mod.svgcharts.style import C, FONT_CHAIN, ZONE_COLORS

_W = 1280
_H = 560


def _norm_money(v) -> str:
    try:
        return f"${float(v):,.2f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return "TBD"


def _norm_count(v) -> str:
    try:
        v = float(v)
        if v >= 10000:
            return f"{v / 1000:.0f}k"
        if v >= 1000:
            return f"{v / 1000:.1f}k"
        return f"{v:.0f}"
    except (TypeError, ValueError):
        return "TBD"


def _card(root, x, y, w, h, *, fill=None, stroke=None, rx=6, opacity=None, stroke_width=1):
    return el(root, "rect", x=x, y=y, width=w, height=h,
              fill=fill or C.CARD, stroke=stroke or C.GRID, rx=rx,
              opacity=opacity, stroke_width=stroke_width)


def _label(root, x, y, content, size=11, fill=None, weight=None, anchor=None,
           spacing=None, opacity=None):
    return text(root, x, y, content, size=size, fill=fill or C.SUB,
                weight=weight, family=FONT_CHAIN, anchor=anchor,
                letter_spacing=spacing, opacity=opacity)


# ─────────────────────────────────────────────────────────────
# 1. 品牌份额环形 + ASP 气泡 + KPI 条（mod_overview）
# ─────────────────────────────────────────────────────────────
def market_donut(df: pd.DataFrame, root, meta: dict) -> None:
    topn = 6
    counts = df["brand"].fillna("其他").value_counts().head(topn)
    other = len(df) - int(counts.sum())
    shares = list(counts.items()) + ([("其他品牌", other)] if other > 0 else [])
    total = float(sum(v for _, v in shares)) or 1.0

    cx, cy, r_out, r_in = 300, 300, 190, 108
    angle = -math.pi / 2
    for i, (name, n) in enumerate(shares):
        frac = n / total
        a0, a1 = angle, angle + frac * 2 * math.pi
        angle = a1
        color = style.SERIES[i % len(style.SERIES)]
        large = 1 if frac > 0.5 else 0
        x0o, y0o = cx + r_out * math.cos(a0), cy + r_out * math.sin(a0)
        x1o, y1o = cx + r_out * math.cos(a1), cy + r_out * math.sin(a1)
        x1i, y1i = cx + r_in * math.cos(a1), cy + r_in * math.sin(a1)
        x0i, y0i = cx + r_in * math.cos(a0), cy + r_in * math.sin(a0)
        el(root, "path",
           d=f"M {fmt(x0o)} {fmt(y0o)} A {r_out} {r_out} 0 {large} 1 {fmt(x1o)} {fmt(y1o)} "
             f"L {fmt(x1i)} {fmt(y1i)} A {r_in} {r_in} 0 {large} 0 {fmt(x0i)} {fmt(y0i)} Z",
           fill=color, stroke=C.CARD, stroke_width=2)
        mid = (a0 + a1) / 2
        lx, ly = cx + (r_out + 26) * math.cos(mid), cy + (r_out + 26) * math.sin(mid)
        anchor = "start" if math.cos(mid) >= 0 else "end"
        _label(root, lx, ly, f"{name} {n / total * 100:.0f}%", size=13,
               fill=C.INK, weight="bold", anchor=anchor)
    text(root, cx, cy - 4, f"{len(df)}", size=44, fill=C.NAVY, weight="bold",
         family=FONT_CHAIN, anchor="middle")
    text(root, cx, cy + 24, "竞品 ASIN", size=12, fill=C.SUB, family=FONT_CHAIN, anchor="middle")

    # ASP 价格气泡（均价锚点，参考 MOD 市场总览的 ASP callout）
    prices = [p for p in df["current_price"].dropna().tolist() if p > 0]
    asps = sorted({round(p / 10) * 10 for p in prices})[:6] or [int(sum(prices) / len(prices))] if prices else []
    bx = 560
    _label(root, bx, 150, "ASP 价格锚点（真实挂牌价聚类）", size=13, fill=C.INK, weight="bold")
    for i, asp in enumerate(asps):
        n_near = sum(1 for p in prices if abs(p - asp) <= 5)
        r = 10 + min(18, n_near * 2)
        color = style.SERIES[i % len(style.SERIES)]
        el(root, "circle", cx=bx + 40 + i * 105, cy=230, r=r, fill=color, opacity=0.8)
        text(root, bx + 40 + i * 105, 230 + r + 20, f"${asp}", size=13, fill=C.INK,
             weight="bold", family=FONT_CHAIN, anchor="middle")
        _label(root, bx + 40 + i * 105, 230 + r + 36, f"{n_near} 款", size=10, anchor="middle")

    # KPI 条（样本/均价/均分/评论量）
    kpis = meta.get("kpis") or []
    kx, ky, kw, kh = 560, 320, 660, 84
    for i, (label, value) in enumerate(kpis[:4]):
        x = kx + i * (kw / 4)
        _card(root, x, ky, kw / 4 - 12, kh)
        el(root, "rect", x=x, y=ky, width=3, height=kh, fill=C.NAVY)
        _label(root, x + 16, ky + 24, label, size=11, spacing=2)
        text(root, x + 16, ky + 60, str(value), size=26, fill=C.NAVY, weight="bold",
             family=FONT_CHAIN)
    _label(root, 560, 440, "*Rainforest data · " + (meta.get("fetched_at") or ""), size=10, opacity=0.8)


# ─────────────────────────────────────────────────────────────
# 2. Top 销量条形（mod_overview）
# ─────────────────────────────────────────────────────────────
def demand_bars(df: pd.DataFrame, root, meta: dict) -> None:
    rows = df.sort_values("est_monthly_sales", ascending=False).head(8)
    max_sales = float(rows["est_monthly_sales"].max() or 1) or 1.0
    x0, y0, w = 420, 90, 720
    for i, (_, r) in enumerate(rows.iterrows()):
        y = y0 + i * 56
        title = str(r.get("title") or "")[:34]
        _label(root, 60, y + 18, title, size=13, fill=C.INK)
        _label(root, 60, y + 36, f"{r.get('brand') or '—'} · {r.get('asin')}", size=10)
        sales = float(r.get("est_monthly_sales") or 0)
        bw = max(4.0, sales / max_sales * (w - 200))
        el(root, "rect", x=x0, y=y, width=bw, height=30,
           fill=ZONE_COLORS.get(r.get("zone"), C.GREY), opacity=0.88, rx=3)
        text(root, x0 + bw + 10, y + 21, f"{_norm_count(sales)}/月", size=13,
             fill=C.INK, weight="bold", family=FONT_CHAIN)
        _label(root, x0 + 12, y + 21, _norm_money(r.get("current_price")), size=12,
               fill="#FFFFFF", weight="bold")
    _label(root, 60, y0 + 8 * 56 + 10, "*est_monthly_sales：Amazon 官方 recent_sales 口径（缺失回退 BSR 系数）",
           size=10, opacity=0.8)


# ─────────────────────────────────────────────────────────────
# 3. 价格带直方图（mod_overview）
# ─────────────────────────────────────────────────────────────
def price_bands(df: pd.DataFrame, root, meta: dict) -> None:
    prices = [p for p in df["current_price"].dropna().tolist() if p > 0]
    if not prices:
        _label(root, 640, 300, "无价格数据", size=16, anchor="middle")
        return
    p25 = float(pd.Series(prices).quantile(0.25))
    p75 = float(pd.Series(prices).quantile(0.75))
    lo = math.floor(min(prices) / 10) * 10
    hi = math.ceil(max(prices) / 10) * 10
    step = max(5, (hi - lo) / 14 or 5)
    edges = [lo + i * step for i in range(int((hi - lo) / step) + 2)]
    hist = {}
    for p in prices:
        for e0, e1 in zip(edges, edges[1:]):
            if e0 <= p < e1:
                hist[(e0, e1)] = hist.get((e0, e1), 0) + 1
                break
    peak = max(hist.values() or [1]) or 1
    x0, y0, h = 120, 440, 280
    bw = 1000 / max(1, len(edges) - 1)
    for (e0, e1), n in sorted(hist.items()):
        i = edges.index(e0)
        bh = n / peak * h
        in_band = p25 <= (e0 + e1) / 2 <= p75
        el(root, "rect", x=x0 + i * bw + 2, y=y0 - bh, width=bw - 4, height=bh,
           fill=C.NAVY if in_band else C.GREY, opacity=0.85 if in_band else 0.55, rx=3)
        if n == peak:
            _label(root, x0 + i * bw + bw / 2, y0 - bh - 10, f"{n} 款", size=12,
                   fill=C.INK, weight="bold", anchor="middle")
    el(root, "line", x1=x0, y1=y0, x2=x0 + 1000, y2=y0, stroke=C.SUB, stroke_width=1)
    for e in edges[:: max(1, len(edges) // 8)]:
        _label(root, x0 + edges.index(e) * bw + bw / 2, y0 + 22, f"${e:.0f}", size=11, anchor="middle")
    # P25-P75 参考带
    band_x0 = x0 + (p25 - lo) / (hi - lo + step) * 1000
    band_x1 = x0 + (p75 - lo) / (hi - lo + step) * 1000
    el(root, "rect", x=band_x0, y=y0 - h, width=max(2.0, band_x1 - band_x0), height=h,
       fill=C.NAVY, opacity=0.08)
    _label(root, 120, 90, f"P25–P75 主流价格带：{_norm_money(p25)} – {_norm_money(p75)}",
           size=18, fill=C.INK, weight="bold")
    _label(root, 120, 118, f"样本 {len(prices)} 个在售 ASIN · 均价 {_norm_money(sum(prices) / len(prices))}",
           size=12)


# ─────────────────────────────────────────────────────────────
# 4. 四分区卡片（mod_overview）
# ─────────────────────────────────────────────────────────────
def zone_grid(df: pd.DataFrame, root, meta: dict) -> None:
    from amazon_matrix_mod.svgcharts.style import ZONE_LABELS
    interp = meta.get("interpretation") or {}
    counts = df["zone"].value_counts().to_dict()
    rules = meta.get("rules") or {}
    zones = [("price_gap", "value_opportunity", "demand_heat", "red_ocean")]
    for i, zone in enumerate(zones[0]):
        x, y, w, h = 60 + (i % 2) * 590, 80 + (i // 2) * 220, 570, 200
        color = ZONE_COLORS[zone]
        _card(root, x, y, w, h, stroke=C.GRID)
        el(root, "rect", x=x, y=y, width=4, height=h, fill=color)
        text(root, x + 24, y + 44, str(counts.get(zone, 0)), size=40, fill=color,
             weight="bold", family=FONT_CHAIN)
        _label(root, x + 90, y + 32, ZONE_LABELS.get(zone, zone), size=16, fill=C.INK, weight="bold")
        rule = rules.get(zone)
        _label(root, x + 90, y + 54, (rule if isinstance(rule, str) else json.dumps(rule, ensure_ascii=False))[:52],
               size=10, opacity=0.9)
        words = str(interp.get(zone) or "TBD")
        _label(root, x + 24, y + 96, words[:56], size=15, fill=C.INK)
        sample = df[df["zone"] == zone].sort_values("est_monthly_sales", ascending=False)
        for j, (_, r) in enumerate(sample.head(3).iterrows()):
            _label(root, x + 24, y + 130 + j * 22,
                   f"[A] {str(r.get('title') or '')[:36]} · {_norm_money(r.get('current_price'))} · "
                   f"月销{_norm_count(r.get('est_monthly_sales'))}", size=11)
        if len(sample) == 0:
            _label(root, x + 24, y + 130, "（本批次无该区样本）", size=11, opacity=0.7)
    _label(root, 60, 520, "verdict：" + str(interp.get("verdict") or "TBD"), size=15,
           fill=C.NAVY, weight="bold")


# ─────────────────────────────────────────────────────────────
# 5. 价格×月销对数散点（mod_matrix；缩略图省略版，页面内高密度呈现）
# ─────────────────────────────────────────────────────────────
def matrix_scatter(df: pd.DataFrame, root, meta: dict) -> None:
    x0, y0, w, h = 110, 80, 880, 400
    ys = [max(s, 1) for s in df["est_monthly_sales"].dropna().tolist()] or [1]
    xs = [p for p in df["current_price"].dropna().tolist() if p > 0] or [1]

    def lx(p):
        return x0 + (math.log10(max(p, 1)) - math.log10(max(min(xs), 1))) / \
            max(1e-6, math.log10(max(max(xs), 2)) - math.log10(max(min(xs), 1))) * w

    def ly(s):
        return y0 + h - (math.log10(max(s, 1)) - math.log10(1)) / \
            max(1e-6, math.log10(max(max(ys), 10))) * h

    for gx in range(5):
        yy = y0 + gx * h / 4
        el(root, "line", x1=x0, y1=yy, x2=x0 + w, y2=yy, stroke=C.GRID, stroke_width=1)
    # P25-P75 竖带
    if len(xs) >= 4:
        p25, p75 = pd.Series(xs).quantile([0.25, 0.75])
        el(root, "rect", x=lx(p25), y=y0, width=max(2.0, lx(p75) - lx(p25)), height=h,
           fill=C.NAVY, opacity=0.06)
        _label(root, (lx(p25) + lx(p75)) / 2, y0 - 8, f"P25–P75 {_norm_money(p25)}–{_norm_money(p75)}",
               size=11, fill=C.NAVY, anchor="middle")
    max_rev = float(df["review_count"].max() or 1) or 1.0
    hero = meta.get("our_asin")
    for _, r in df.iterrows():
        p, s = r.get("current_price"), r.get("est_monthly_sales")
        if not p or not s or p <= 0 or s <= 0:
            continue
        radius = 5 + (float(r.get("review_count") or 0) / max_rev) * 11
        is_hero = hero and r.get("asin") == hero
        el(root, "circle", cx=lx(p), cy=ly(s), r=radius,
           fill=ZONE_COLORS.get(r.get("zone"), C.GREY), opacity=0.85,
           stroke=C.GOLD if is_hero else None, stroke_width=2 if is_hero else None)
        if r.get("zone") == "red_ocean" or is_hero:
            _label(root, lx(p) + radius + 3, ly(s) + 4, str(r.get("asin")), size=9, fill=C.INK)
    for i, v in enumerate(sorted({max(1, min(xs)), 10, 50, 100, max(2, int(max(xs)))})):
        _label(root, lx(v), y0 + h + 22, f"${v}", size=11, anchor="middle")
    _label(root, x0 + w + 16, y0 + h, "月销→", size=11)
    _label(root, x0 + w / 2, y0 + h + 48, "价格（对数轴）", size=12, anchor="middle")
    # 图例
    from amazon_matrix_mod.svgcharts.style import ZONE_LABELS
    for i, zone in enumerate(("price_gap", "value_opportunity", "demand_heat", "red_ocean")):
        yy = 100 + i * 30
        el(root, "circle", cx=1030, cy=yy - 4, r=7, fill=ZONE_COLORS[zone])
        _label(root, 1044, yy, ZONE_LABELS[zone], size=12, fill=C.INK)
        _label(root, 1044, yy + 14, f"{int((df['zone'] == zone).sum())} 款", size=10)
    _label(root, 110, 545, f"N={len(df)} · 边框色=分区 · 尺寸∝评论数 · {meta.get('fetched_at') or ''}", size=10, opacity=0.8)


# ─────────────────────────────────────────────────────────────
# 6. 参数对比矩阵（mod_spec_comparison；hero 先列 + 优势高亮）
# ─────────────────────────────────────────────────────────────
def spec_matrix(df: pd.DataFrame, root, meta: dict) -> None:
    rows = df.sort_values("est_monthly_sales", ascending=False).head(7)
    hero = meta.get("our_asin")
    if hero:
        hero_row = df[df["asin"] == hero]
        if len(hero_row):
            rows = pd.concat([hero_row, rows[rows["asin"] != hero]]).head(7)
    attrs = [
        ("价格", lambda r: _norm_money(r.get("current_price"))),
        ("评分", lambda r: f"{r.get('rating') or 'TBD'}"),
        ("评论数", lambda r: _norm_count(r.get("review_count"))),
        ("月销估算", lambda r: _norm_count(r.get("est_monthly_sales"))),
        ("BSR", lambda r: _norm_count(r.get("bsr"))),
        ("配送", lambda r: "FBA" if r.get("is_fba") else "自发货"),
        ("卖家", lambda r: str(r.get("seller_type") or "TBD")[:10]),
        ("分区", lambda r: str(r.get("zone") or "neutral")),
    ]
    x0, y0, cw, rh = 60, 130, 160, 48
    # 表头：产品卡片（标题 + ASIN）
    for j, (_, r) in enumerate(rows.iterrows()):
        x = x0 + 140 + j * cw
        _card(root, x, 56, cw - 8, 66, fill=C.NAVY if r.get("asin") == hero else C.CARD,
              stroke=C.NAVY)
        _label(root, x + 10, 78, str(r.get("title") or "")[:18], size=11,
               fill="#FFFFFF" if r.get("asin") == hero else C.INK, weight="bold")
        _label(root, x + 10, 100, f"{r.get('brand') or '—'} · {r.get('asin')}", size=9,
               fill="#FFFFFFCC" if r.get("asin") == hero else C.SUB)
    # 价格最优/评分最高列高亮依据
    best_price = pd.to_numeric(rows["current_price"], errors="coerce").idxmin()
    best_rating = pd.to_numeric(rows["rating"], errors="coerce").idxmax()
    for i, (attr, fn) in enumerate(attrs):
        y = y0 + i * rh
        if i % 2 == 0:
            el(root, "rect", x=x0, y=y - 18, width=140 + len(rows) * cw, height=rh - 4,
               fill=C.CARD, opacity=0.6)
        _label(root, x0 + 8, y, attr, size=13, fill=C.INK, weight="bold")
        for j, (idx, r) in enumerate(rows.iterrows()):
            x = x0 + 148 + j * cw
            win = (attr == "价格" and idx == best_price) or (attr == "评分" and idx == best_rating)
            if win:
                el(root, "rect", x=x - 6, y=y - 18, width=cw - 8, height=rh - 4,
                   fill=C.NAVY, opacity=0.1, rx=4)
            _label(root, x, y, fn(r), size=13,
                   fill=C.NAVY if win else C.INK, weight="bold" if win else None)
    _label(root, 60, y0 + len(attrs) * rh + 6,
           f"*优势高亮=最优价格/评分 · hero={hero or '未指定'} · {meta.get('fetched_at') or ''}",
           size=10, opacity=0.8)


# ─────────────────────────────────────────────────────────────
# 7. SKU/渠道结构（mod_sku_analysis）
# ─────────────────────────────────────────────────────────────
def sku_channels(df: pd.DataFrame, root, meta: dict) -> None:
    # 左：FBA × 卖家类型堆叠
    fba = int(df["is_fba"].fillna(False).sum())
    non_fba = len(df) - fba
    sellers = df["seller_type"].fillna("unknown").value_counts().head(4)
    _label(root, 60, 90, "配送结构", size=16, fill=C.INK, weight="bold")
    total = max(1, len(df))
    for i, (name, n, color) in enumerate([("FBA", fba, C.NAVY), ("自发货", non_fba, C.GREY)]):
        y = 130 + i * 70
        el(root, "rect", x=60, y=y, width=n / total * 480, height=40, fill=color, opacity=0.88, rx=4)
        text(root, 72, y + 26, f"{name} {n}（{n / total * 100:.0f}%）", size=14,
             fill="#FFFFFF", weight="bold", family=FONT_CHAIN)
    _label(root, 60, 300, "卖家类型分布", size=16, fill=C.INK, weight="bold")
    for i, (name, n) in enumerate(sellers.items()):
        y = 336 + i * 44
        _label(root, 60, y + 16, str(name)[:16], size=12, fill=C.INK)
        el(root, "rect", x=200, y=y, width=n / total * 340, height=24,
           fill=style.SERIES[i % len(style.SERIES)], opacity=0.85, rx=3)
        _label(root, 200 + n / total * 340 + 8, y + 16, f"{n}", size=12)
    # 右：分区 × 交叉表
    _label(root, 640, 90, "分区 × 渠道交叉", size=16, fill=C.INK, weight="bold")
    zones = ("price_gap", "value_opportunity", "demand_heat", "red_ocean", "neutral")
    from amazon_matrix_mod.svgcharts.style import ZONE_LABELS
    for i, zone in enumerate(zones):
        sub = df[df["zone"] == zone]
        y = 130 + i * 62
        color = ZONE_COLORS.get(zone, C.GREY)
        el(root, "rect", x=640, y=y, width=6, height=46, fill=color)
        _label(root, 660, y + 18, ZONE_LABELS.get(zone, zone), size=13, fill=C.INK, weight="bold")
        fba_n = int(sub["is_fba"].fillna(False).sum())
        _label(root, 660, y + 38, f"{len(sub)} 款 · FBA {fba_n} · 均价 "
               f"{_norm_money(sub['current_price'].mean() if len(sub) else None)} · "
               f"月销中位 {_norm_count(sub['est_monthly_sales'].median() if len(sub) else None)}",
               size=11, opacity=0.9)
    _label(root, 640, 480, "*口径：Rainforest 实时字段（is_fba / seller_type / zone）", size=10, opacity=0.8)


# ─────────────────────────────────────────────────────────────
# 编排入口
# ─────────────────────────────────────────────────────────────
def render_mod_charts(out_dir: str, df: pd.DataFrame, *, keyword: str = "",
                      marketplace: str = "", fetched_at: str = "",
                      our_asin: str | None = None, theme=None,
                      interpretation: dict | None = None,
                      rules: dict | None = None) -> dict:
    """渲染 MOD 组件到 {out_dir}/charts/，返回 charts_index（相对路径）。

    任何单组件失败仅跳过该组件（增强层，不阻塞主流程）。
    """
    from amazon_matrix_mod.svgcharts import rasterize

    if theme is not None:
        style.apply_theme(theme)
    charts_dir = os.path.join(out_dir, "charts")
    os.makedirs(charts_dir, exist_ok=True)
    prices = [p for p in df["current_price"].dropna().tolist() if p > 0]
    ratings = [r for r in df["rating"].dropna().tolist() if r]
    meta = {
        "keyword": keyword, "fetched_at": fetched_at, "our_asin": our_asin,
        "interpretation": interpretation or {}, "rules": rules or {},
        "kpis": [
            ("均价 ASP", _norm_money(sum(prices) / len(prices)) if prices else "TBD"),
            ("平均评分", f"{sum(ratings) / len(ratings):.2f}" if ratings else "TBD"),
            ("价格带", f"{_norm_money(min(prices))}–{_norm_money(max(prices))}" if prices else "TBD"),
            ("样本 ASIN", str(len(df))),
        ],
    }
    builders = {
        "market_donut": (market_donut, "市场总览 · 品牌份额与 ASP", "mod_overview"),
        "demand_bars": (demand_bars, "需求分布 · Top 销量竞品", "mod_overview"),
        "price_bands": (price_bands, "价格带分布", "mod_overview"),
        "zone_grid": (zone_grid, "四分区格局", "mod_overview"),
        "matrix_scatter": (matrix_scatter, "价格 × 月销矩阵", "mod_matrix"),
        "spec_matrix": (spec_matrix, "参数对比矩阵", "mod_spec_comparison"),
        "sku_channels": (sku_channels, "SKU 与渠道结构", "mod_sku_analysis"),
    }
    index: dict = {}
    for name, (fn, title, kind) in builders.items():
        try:
            root = svg_document(_W, _H, bg=C.BG)
            fn(df, root, meta)
            svg_path = os.path.join(charts_dir, f"{name}.svg")
            save(root, svg_path)
            png_path = None
            try:
                png_path = rasterize.svg_to_png(svg_path, svg_path[:-4] + ".png", width=1280)
            except Exception:  # noqa: BLE001 —— 无 Playwright 时保留 SVG
                png_path = None
            index[name] = {
                "title": title, "kind": kind,
                "svg": os.path.relpath(svg_path, out_dir),
                "png": os.path.relpath(png_path, out_dir) if png_path else None,
            }
        except Exception as exc:  # noqa: BLE001 —— 单组件失败跳过
            print(f"[charts] {name} 渲染失败（跳过）: {str(exc)[:100]}")
    with open(os.path.join(charts_dir, "charts_index.json"), "w", encoding="utf-8") as f:
        json.dump({"keyword": keyword, "marketplace": marketplace,
                   "fetched_at": fetched_at, "charts": index}, f, ensure_ascii=False, indent=1)
    print(f"[charts] MOD 组件 {len(index)}/{len(builders)} 渲染完成 → {charts_dir}")
    return index
