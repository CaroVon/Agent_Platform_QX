"""svgcharts 图表组件库 —— 确定性 SVG 渲染（数据驱动，无 AI 参与）。

所有组件接收父 <g>/svg 元素与区域 (x, y, w, h)，直接绘制。
数值格式化遵循「真实数据 + 显式缺失标注」原则。
"""
from __future__ import annotations

import base64
import math
import os
import xml.etree.ElementTree as ET

import numpy as np

from amazon_matrix_mod.svgcharts.svg import el, fmt, text
from amazon_matrix_mod.svgcharts.style import C, FONT_CHAIN, SERIES, ZONE_COLORS


# ─────────────────────────── 基础工具 ───────────────────────────

def group(parent, x: float = 0, y: float = 0, **attrs) -> ET.Element:
    return el(parent, "g", transform=f"translate({fmt(x)},{fmt(y)})", **attrs)


def _money(v) -> str:
    return "—" if v is None else f"${v:,.2f}"


def _count(v) -> str:
    if v is None:
        return "—"
    if v >= 10000:
        return f"{v / 1000:.0f}k"
    if v >= 1000:
        return f"{v / 1000:.1f}k"
    return f"{int(v)}"


def log_ticks(lo: float, hi: float, max_ticks: int = 8) -> list[float]:
    """对数轴友好刻度（1/2/5 × 10^k）。"""
    ticks, k0, k1 = [], math.floor(math.log10(lo)), math.ceil(math.log10(hi))
    for k in range(k0 - 1, k1 + 2):
        for m in (1, 2, 5):
            v = m * 10 ** k
            if lo <= v <= hi:
                ticks.append(v)
    if len(ticks) > max_ticks:  # 过密时抽稀到 1×10^k
        ticks = [t for t in ticks if abs(math.log10(t) - round(math.log10(t))) < 1e-9]
        step = max(1, len(ticks) // max_ticks)
        ticks = ticks[::step]
    return sorted(set(ticks))


class LogScale:
    def __init__(self, d0: float, d1: float, p0: float, p1: float):
        self.d0, self.d1 = max(d0, 1e-9), max(d1, d0 * 1.0001)
        self.p0, self.p1 = p0, p1

    def __call__(self, v: float) -> float:
        v = min(max(v, self.d0), self.d1)
        t = (math.log10(v) - math.log10(self.d0)) / \
            (math.log10(self.d1) - math.log10(self.d0))
        return self.p0 + t * (self.p1 - self.p0)


class LinScale:
    def __init__(self, d0: float, d1: float, p0: float, p1: float):
        self.d0, self.d1 = d0, d1
        self.p0, self.p1 = p0, p1

    def __call__(self, v: float) -> float:
        t = 0.0 if self.d1 == self.d0 else (v - self.d0) / (self.d1 - self.d0)
        return self.p0 + t * (self.p1 - self.p0)


def axis_frame(parent, x: float, y: float, w: float, h: float, *,
               xs: LinScale | None = None, ys: LinScale | None = None,
               x_ticks: list[float] | None = None, y_ticks: list[float] | None = None,
               x_fmt=lambda v: fmt(v), y_fmt=lambda v: fmt(v),
               x_label: str = "", y_label: str = "") -> None:
    """坐标框架：边框 + 网格 + 刻度标签 + 轴标题。"""
    el(parent, "rect", x=x, y=y, width=w, height=h, fill="none",
       stroke=C.GRID, stroke_width=1)
    if x_ticks and xs:
        for tv in x_ticks:
            px = xs(tv)
            if x <= px <= x + w:
                el(parent, "line", x1=px, y1=y, x2=px, y2=y + h,
                   stroke=C.GRID, stroke_width=0.7, stroke_dasharray="2 3")
                text(parent, px, y + h + 16, x_fmt(tv), size=10.5, fill=C.SUB,
                     anchor="middle", family=FONT_CHAIN)
    if y_ticks and ys:
        for tv in y_ticks:
            py = ys(tv)
            if y <= py <= y + h:
                el(parent, "line", x1=x, y1=py, x2=x + w, y2=py,
                   stroke=C.GRID, stroke_width=0.7, stroke_dasharray="2 3")
                text(parent, x - 8, py + 3.5, y_fmt(tv), size=10.5, fill=C.SUB,
                     anchor="end", family=FONT_CHAIN)
    if x_label:
        text(parent, x + w / 2, y + h + 34, x_label, size=11.5, fill=C.SUB,
             anchor="middle", family=FONT_CHAIN)
    if y_label:
        t = el(parent, "text", x=x - 46, y=y + h / 2, font_size=11.5, fill=C.SUB,
               font_family=FONT_CHAIN,
               transform=f"rotate(-90 {fmt(x - 46)} {fmt(y + h / 2)})",
               text_anchor="middle")
        t.text = y_label


# ─────────────────────────── 图表组件 ───────────────────────────

def histogram(parent, x, y, w, h, values: list[float], *, bins: int = 12,
              quantiles: dict[str, float] | None = None,
              gaps: list[dict] | None = None, unit: str = "$",
              title: str = "", font_scale: float = 1.0) -> None:
    """直方图（线性轴）+ 分位线 + 缺口带 + X/Y 数值刻度。

    font_scale：M3 审图回环的字号修订参数（>1 放大刻度/标注文字）。
    """
    fs = lambda s: s * font_scale  # noqa: E731
    if not values:
        text(parent, x + w / 2, y + h / 2, "数据缺失", size=13, fill=C.SUB,
             anchor="middle", family=FONT_CHAIN)
        return
    hist, edges = np.histogram(values, bins=min(bins, max(6, len(values))))
    vmax = max(1, int(hist.max()))
    sx = LinScale(edges[0], edges[-1], x, x + w)
    if title:
        text(parent, x, y - 10, title, size=fs(12.5), fill=C.NAVY, weight="600",
             family=FONT_CHAIN)
    plot_y, plot_h = y + (24 if title else 0), h - (24 if title else 0) - 20
    # Y 轴频次刻度（左）
    for i in range(1, vmax + 1):
        if vmax > 6 and i % 2 == 1 and i != vmax:
            continue
        gy = plot_y + plot_h - plot_h * i / vmax
        el(parent, "line", x1=x, y1=gy, x2=x + w, y2=gy,
           stroke=C.GRID, stroke_width=0.6, stroke_dasharray="2 3")
        text(parent, x - 8, gy + 3.5, str(i), size=fs(9.5), fill=C.SUB,
             anchor="end", family=FONT_CHAIN)
    # X 轴价格刻度（bin 边界抽稀）
    step = max(1, len(edges) // 8)
    for e in edges[::step]:
        px = sx(e)
        text(parent, px, plot_y + plot_h + 14, f"{unit}{e:,.0f}", size=fs(9.5),
             fill=C.SUB, anchor="middle", family=FONT_CHAIN)
    for gaps_i, g in enumerate(gaps or []):
        gx0, gx1 = sx(g["low"]), sx(min(g["high"], edges[-1]))
        if gx1 > gx0:
            el(parent, "rect", x=gx0, y=plot_y, width=gx1 - gx0, height=plot_h,
               fill=C.AMBER, opacity=0.16)
            text(parent, (gx0 + gx1) / 2, plot_y + plot_h / 2,
                 f"缺口 {unit}{g['low']:,.0f}-{g['high']:,.0f}", size=10,
                 fill="#8a6d00", anchor="middle", family=FONT_CHAIN)
    bw = (x + w - x) / len(hist) * 0.88
    for cnt, (v0, v1) in zip(hist, zip(edges[:-1], edges[1:])):
        px, ph = sx((v0 + v1) / 2), plot_h * cnt / vmax
        el(parent, "rect", x=px - bw / 2, y=plot_y + plot_h - ph, width=bw,
           height=ph, fill=C.LIGHT_BLUE, stroke=C.BLUE, stroke_width=1, rx=2)
    for label, color in (("P25", C.AMBER), ("P50", C.GREEN), ("P75", C.RED)):
        v = (quantiles or {}).get(label)
        if v is None:
            continue
        px = sx(v)
        el(parent, "line", x1=px, y1=plot_y, x2=px, y2=plot_y + plot_h,
           stroke=color, stroke_width=1.4, stroke_dasharray="5 4")
        text(parent, px, plot_y - 6, f"{label} {unit}{v:,.2f}", size=10,
             fill=color, anchor="middle", family=FONT_CHAIN)
    for i in range(1, 4):
        el(parent, "line", x1=x, y1=plot_y + plot_h * i / 4, x2=x + w,
           y2=plot_y + plot_h * i / 4, stroke=C.GRID, stroke_width=0.6)


def bar_h(parent, x, y, w, h, items: list[dict], *, unit: str = "",
          title: str = "", label_width: float = 150,
          value_fmt=lambda v: fmt(v)) -> None:
    """水平条形图。items: [{label, value, color?, display?}]（按给定顺序绘制）。"""
    if not items:
        text(parent, x + w / 2, y + h / 2, "数据缺失", size=13, fill=C.SUB,
             anchor="middle", family=FONT_CHAIN)
        return
    vmax = max(i["value"] for i in items) or 1
    top = y + (26 if title else 0)
    row_h = min(30, (h - (26 if title else 0)) / max(1, len(items)))
    if title:
        text(parent, x, y - 8, title, size=12.5, fill=C.NAVY, weight="600",
             family=FONT_CHAIN)
    bar_x = x + label_width
    bar_w = w - label_width - 64
    for i, item in enumerate(items):
        cy = top + row_h * (i + 0.5)
        text(parent, x, cy + 4, str(item["label"])[:16], size=11, fill=C.INK,
             family=FONT_CHAIN)
        bw = bar_w * item["value"] / vmax
        el(parent, "rect", x=bar_x, y=cy - row_h * 0.30, width=max(bw, 1.5),
           height=row_h * 0.60, fill=item.get("color") or C.BLUE, rx=3)
        text(parent, bar_x + max(bw, 1.5) + 8, cy + 4,
             item.get("display") or (unit + value_fmt(item["value"])),
             size=10.5, fill=C.SUB, family=FONT_CHAIN)


def donut(parent, cx, cy, r, slices: list[dict], *, center_total: str = "",
          center_label: str = "", legend_x: float | None = None,
          legend_y: float | None = None) -> None:
    """环图。slices: [{label, value, color}]。图例画在 (legend_x, legend_y) 起始处。"""
    total = sum(s["value"] for s in slices) or 1
    a0 = -90.0
    for s in slices:
        frac = s["value"] / total
        a1 = a0 + frac * 360
        large = 1 if (a1 - a0) > 180 else 0
        r_in = r * 0.62
        p = []
        for angle, radius in ((a0, r), (a1, r), (a1, r_in), (a0, r_in)):
            rad = math.radians(angle)
            p.append((cx + radius * math.cos(rad), cy + radius * math.sin(rad)))
        if frac >= 0.999:
            el(parent, "circle", cx=cx, cy=cy, r=r, fill=s["color"])
            el(parent, "circle", cx=cx, cy=cy, r=r_in, fill=C.BG)
        else:
            el(parent, "path",
               d=f"M {fmt(p[0][0])} {fmt(p[0][1])} A {fmt(r)} {fmt(r)} 0 "
                 f"{large} 1 {fmt(p[1][0])} {fmt(p[1][1])} "
                 f"L {fmt(p[2][0])} {fmt(p[2][1])} "
                 f"A {fmt(r_in)} {fmt(r_in)} 0 {large} 0 "
                 f"{fmt(p[3][0])} {fmt(p[3][1])} Z",
               fill=s["color"], stroke=C.BG, stroke_width=1.5)
        a0 = a1
    if center_total:
        text(parent, cx, cy - 2, center_total, size=20, fill=C.NAVY,
             weight="600", anchor="middle", family=FONT_CHAIN)
        if center_label:
            text(parent, cx, cy + 18, center_label, size=10.5, fill=C.SUB,
                 anchor="middle", family=FONT_CHAIN)
    if legend_x is not None and legend_y is not None:
        for i, s in enumerate(slices):
            ly = legend_y + i * 22
            el(parent, "rect", x=legend_x, y=ly - 8, width=11, height=11,
               fill=s["color"], rx=2)
            text(parent, legend_x + 18, ly + 2,
                 f"{s['label']}  {fmt(s['value'] / total * 100)}%",
                 size=11, fill=C.INK, family=FONT_CHAIN)


def scatter_fit(parent, x, y, w, h, points: list[tuple[float, float]],
                *, x_label: str = "", y_label: str = "",
                fit: bool = True, fit_note: str = "",
                title: str = "") -> None:
    """log-log 散点 + OLS 弹性拟合线（ch04 价格-销量弹性）。"""
    if title:
        text(parent, x, y - 10, title, size=12.5, fill=C.NAVY, weight="600",
             family=FONT_CHAIN)
    pts = [(px, py) for px, py in points if px > 0 and py > 0]
    if not pts:
        text(parent, x + w / 2, y + h / 2, "数据缺失", size=13, fill=C.SUB,
             anchor="middle", family=FONT_CHAIN)
        return
    xs_v = [p[0] for p in pts]
    ys_v = [p[1] for p in pts]
    x0, x1 = min(xs_v) * 0.8, max(xs_v) * 1.25
    y0, y1 = min(ys_v) * 0.7, max(ys_v) * 1.5
    sx = LogScale(x0, x1, x, x + w)
    sy = LogScale(y0, y1, y + h, y)
    axis_frame(parent, x, y, w, h, xs=sx, ys=sy,
               x_ticks=log_ticks(x0, x1), y_ticks=log_ticks(y0, y1),
               x_fmt=lambda v: f"${fmt(v)}", y_fmt=lambda v: _count(v),
               x_label=x_label, y_label=y_label)
    if fit and len(pts) >= 3:
        lx = np.log10(xs_v)
        ly = np.log10(ys_v)
        k, b = np.polyfit(lx, ly, 1)
        fx0, fx1 = sx(x0), sx(x1)
        fy0, fy1 = sy(10 ** (k * math.log10(x0) + b)), sy(10 ** (k * math.log10(x1) + b))
        el(parent, "line", x1=fx0, y1=fy0, x2=fx1, y2=fy1,
           stroke=C.RED, stroke_width=1.8)
        if fit_note:
            text(parent, x + w - 8, y + 18, fit_note.format(slope=k),
                 size=10.5, fill=C.RED, anchor="end", family=FONT_CHAIN)
    for px_v, py_v in pts:
        el(parent, "circle", cx=sx(px_v), cy=sy(py_v), r=4.5,
           fill=C.BLUE, fill_opacity=0.78, stroke="white", stroke_width=0.8)


def interval_bars(parent, x, y, w, h, items: list[dict], *, unit: str = "$",
                  title: str = "", label_width: float = 130) -> None:
    """区间条（品牌价格 min–max + 中位圆点）。items: [{label, lo, hi, mid}]。"""
    if not items:
        text(parent, x + w / 2, y + h / 2, "数据缺失", size=13, fill=C.SUB,
             anchor="middle", family=FONT_CHAIN)
        return
    lo_all = min(i["lo"] for i in items)
    hi_all = max(i["hi"] for i in items)
    sx = LinScale(lo_all * 0.92, hi_all * 1.08, x + label_width, x + w - 70)
    top = y + (26 if title else 0)
    row_h = min(30, (h - (26 if title else 0)) / max(1, len(items)))
    if title:
        text(parent, x, y - 8, title, size=12.5, fill=C.NAVY, weight="600",
             family=FONT_CHAIN)
    for idx, item in enumerate(items):
        cy = top + row_h * (idx + 0.5)
        text(parent, x, cy + 4, str(item["label"])[:14], size=11, fill=C.INK,
             family=FONT_CHAIN)
        bx0, bx1 = sx(item["lo"]), sx(item["hi"])
        el(parent, "rect", x=bx0, y=cy - 4, width=max(bx1 - bx0, 2), height=8,
           fill=C.LIGHT_BLUE, stroke=C.BLUE, stroke_width=0.8, rx=4)
        mx = sx(item["mid"])
        el(parent, "circle", cx=mx, cy=cy, r=4.2, fill=C.NAVY)
        text(parent, x + w - 66, cy + 4,
             f"{unit}{item['lo']:,.0f}-{item['hi']:,.0f}",
             size=9.5, fill=C.SUB, family=FONT_CHAIN)


def table(parent, x, y, w, headers: list[str], rows: list[list[str]],
          *, col_align: list[str] | None = None, row_h: float = 23,
          font_size: float = 10.5, max_rows: int = 12) -> float:
    """数据表（斑马纹）。返回底部 y。列宽均分或按内容加权。"""
    n = len(headers)
    col_align = col_align or (["start"] + ["end"] * (n - 1))
    chars = [max(len(str(headers[c])), *(len(str(r[c])) for r in rows[:20]))
             for c in range(n)] if rows else [len(h) for h in headers]
    weights = [min(c, 30) + 2 for c in chars]
    total = sum(weights)
    widths = [w * wt / total for wt in weights]
    # 表头
    el(parent, "rect", x=x, y=y, width=w, height=row_h, fill=C.NAVY, rx=3)
    cx = x
    for c, head in enumerate(headers):
        text(parent, cx + (8 if col_align[c] == "start" else widths[c] - 8),
             y + row_h - 7, head, size=font_size, fill="white", weight="600",
             anchor=col_align[c], family=FONT_CHAIN)
        cx += widths[c]
    # 行
    for r_i, row in enumerate(rows[:max_rows]):
        ry = y + row_h * (r_i + 1)
        if r_i % 2 == 1:
            el(parent, "rect", x=x, y=ry, width=w, height=row_h,
               fill="#EFEDE4", opacity=0.55)
        cx = x
        for c, cell in enumerate(row):
            text(parent, cx + (8 if col_align[c] == "start" else widths[c] - 8),
                 ry + row_h - 7, str(cell), size=font_size, fill=C.INK,
                 anchor=col_align[c], family=FONT_CHAIN)
            cx += widths[c]
    bottom = y + row_h * (min(len(rows), max_rows) + 1)
    if len(rows) > max_rows:
        text(parent, x + w, bottom + 14, f"…共 {len(rows)} 行，全量见 data.csv",
             size=9.5, fill=C.SUB, anchor="end", family=FONT_CHAIN)
    return bottom


def kpi_cards(parent, x, y, w, h, cards: list[dict],
              gap: float = 12) -> None:
    """KPI 卡片行。cards: [{value, label, sub?, color?}]。"""
    n = len(cards)
    if not n:
        return
    cw = (w - gap * (n - 1)) / n
    for i, card in enumerate(cards):
        cx = x + i * (cw + gap)
        el(parent, "rect", x=cx, y=y, width=cw, height=h, fill=C.CARD, rx=8,
           stroke=C.GRID, stroke_width=1)
        el(parent, "rect", x=cx, y=y, width=4, height=h,
           fill=card.get("color") or C.BLUE, rx=2)
        text(parent, cx + 16, y + h * 0.44, str(card["value"]), size=21,
             fill=card.get("color") or C.NAVY, weight="700", family=FONT_CHAIN)
        text(parent, cx + 16, y + h * 0.72, card["label"], size=11,
             fill=C.SUB, family=FONT_CHAIN)
        if card.get("sub"):
            text(parent, cx + 16, y + h - 9, card["sub"], size=9.5,
                 fill=C.GREY, family=FONT_CHAIN)


# ─────────────────────────── 核心矩阵图（需求 2） ───────────────────────────

def _image_data_uri(path: str | None) -> str | None:
    if not path or not os.path.isfile(path) or os.path.getsize(path) < 1000:
        return None
    mime = "image/png" if path.lower().endswith(".png") else "image/jpeg"
    with open(path, "rb") as f:
        return f"data:{mime};base64,{base64.b64encode(f.read()).decode()}"


def _num(v) -> float | None:
    """NaN/None → None（pandas NaN 是 truthy，必须显式判）。"""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return float(v)


def matrix_chart(parent, x, y, w, h, *, df, our_asin: str | None = None,
                 image_cache_dir: str | None = None,
                 show_price_band: bool = True, uid: str = "mx",
                 max_labels: int = 60,
                 thumb_cap: float | None = None) -> dict:
    """价格 × 月销竞品矩阵（hero 图）。

    - x=价格（log），y=预估月销（log）；缩略图=竞品主图（image_cache）
    - 缩略图边框=分区色；我方=金框 + ★ 徽标；尺寸 ∝ √评论数（40-88px）
    - 防重叠：layout.resolve_collisions；被挤开的缩略图画引出线锚回真实坐标
    返回绘图元信息（含无销量计数，供脚注如实标注）。
    """
    from amazon_matrix_mod.svgcharts.layout import Node, resolve_collisions

    rows = [r for r in df.to_dict("records")
            if (_num(r.get("current_price")) or 0) > 0]
    if not rows:
        text(parent, x + w / 2, y + h / 2, "数据缺失（无有效价格样本）", size=13,
             fill=C.SUB, anchor="middle", family=FONT_CHAIN)
        return {"n": 0, "no_sales": 0}

    prices = [_num(r["current_price"]) for r in rows]
    sales = [_num(r.get("est_monthly_sales")) or 0.0 for r in rows]
    pos_sales = [s for s in sales if s > 0]
    max_sales = max(pos_sales) if pos_sales else 1.0
    no_sales_n = len(sales) - len(pos_sales)

    x0, x1 = min(prices) * 0.8, max(prices) * 1.3
    y_floor = max(1.0, (min(pos_sales) * 0.6) if pos_sales else 1.0)
    y1 = max_sales * 2.0
    sx = LogScale(x0, x1, x + 52, x + w - 14)
    sy = LogScale(y_floor, y1, y + h - 40, y + 26)

    axis_frame(parent, x + 52, y + 26, w - 66, h - 66, xs=sx, ys=sy,
               x_ticks=log_ticks(x0, x1), y_ticks=log_ticks(y_floor, y1),
               x_fmt=lambda v: f"${fmt(v)}", y_fmt=lambda v: _count(v),
               x_label="价格 $（对数轴）", y_label="预估月销（对数轴）")

    # 价格参考带：P25-P75 + 中位线（真实分位数）
    if show_price_band and len(prices) >= 4:
        p25, p50, p75 = np.quantile(prices, [0.25, 0.5, 0.75])
        bx0, bx1 = sx(p25), sx(min(p75, x1))
        if bx1 > bx0:
            el(parent, "rect", x=bx0, y=y + 26, width=bx1 - bx0, height=h - 66,
               fill=C.NAVY, opacity=0.06)
            text(parent, (bx0 + bx1) / 2, y + 40,
                 f"P25-P75 主流价格带 ${p25:,.0f}-${p75:,.0f}", size=10,
                 fill=C.NAVY, anchor="middle", opacity=0.75, family=FONT_CHAIN)
        for v, lab in ((p50, "P50"),):
            px = sx(v)
            el(parent, "line", x1=px, y1=y + 26, x2=px, y2=y + h - 40,
               stroke=C.GREEN, stroke_width=1.2, stroke_dasharray="6 5")

    # 节点：尺寸 ∝ √评论数，权重 ∝ 月销（高销量者原位优先）；
    # 密度感知：缩略图占绘图区面积 >40% 时按比例缩到 34px 下限（防重叠前提）
    from amazon_matrix_mod import storage
    plot_area = (w - 66) * (h - 66)
    density_cap = math.sqrt(plot_area * 0.40 / max(len(rows), 1)) - 10
    nodes, meta = [], []
    for r in rows:
        price = _num(r["current_price"]) or 0.0
        s = _num(r.get("est_monthly_sales")) or 0.0
        rc = _num(r.get("review_count")) or 0.0
        size = 40 + math.sqrt(max(rc, 0)) * 1.1
        size = max(42, min(88, size))
        if thumb_cap:
            size = max(34, min(size, thumb_cap))
        if density_cap < size:
            size = max(34, density_cap)
        px = sx(price)
        py = sy(s if s > 0 else y_floor * 1.15)
        is_ours = bool(our_asin and r.get("asin") == our_asin)
        label = f"${price:,.2f}" + ("" if s > 0 else " †")
        node = Node(x=px, y=py - 8, w=size + 8, h=size + 26,
                    anchor_x=px, anchor_y=py - 8,
                    weight=1.0 + math.log10(1 + s))
        nodes.append(node)
        img_path = None
        if image_cache_dir:
            img_path = storage.cache_image_url(image_cache_dir, r.get("asin") or "")
        meta.append({
            "asin": r.get("asin"), "zone": r.get("zone") or "neutral",
            "is_ours": is_ours, "size": size, "label": label,
            "uri": _image_data_uri(img_path), "no_sales": s <= 0,
        })

    resolve_collisions(nodes, (x + 58, y + 30, x + w - 18, y + h - 46))

    # 引出线（先画，垫底）
    for node, m in zip(nodes, meta):
        if node.displaced:
            el(parent, "line", x1=node.anchor_x, y1=node.anchor_y,
               x2=node.x, y2=node.y - m["size"] / 2 - 2,
               stroke=C.GREY, stroke_width=1, stroke_dasharray="3 3")
            el(parent, "circle", cx=node.anchor_x, cy=node.anchor_y, r=3,
               fill=C.GREY)

    # 缩略图 + 价格标签（clipPath 统一放 <defs>——svg_to_pptx 契约）
    defs = el(parent, "defs")
    shown = 0
    for node, m in zip(nodes, meta):
        if shown >= max_labels:
            break
        shown += 1
        s = m["size"]
        tx, ty = node.x - s / 2, node.y - s / 2
        border = C.GOLD if m["is_ours"] else ZONE_COLORS.get(m["zone"], C.GREY)
        bw = 4 if m["is_ours"] else 2.5
        clip_id = f"{uid}-clip-{m['asin']}"
        clip = el(defs, "clipPath", id=clip_id)
        el(clip, "rect", x=tx, y=ty, width=s, height=s, rx=7)
        if m["uri"]:
            el(parent, "image", x=tx, y=ty, width=s, height=s,
               preserveAspectRatio="xMidYMid slice", href=m["uri"],
               clip_path=f"url(#{clip_id})")
        else:
            el(parent, "rect", x=tx, y=ty, width=s, height=s, rx=7,
               fill="#DDD9CC", stroke=border, stroke_width=1)
            text(parent, node.x, node.y + 4, "无图", size=9, fill=C.SUB,
                 anchor="middle", family=FONT_CHAIN)
        el(parent, "rect", x=tx, y=ty, width=s, height=s, rx=7, fill="none",
           stroke=border, stroke_width=bw)
        if m["is_ours"]:
            badge = el(parent, "g")
            el(badge, "rect", x=node.x - 26, y=ty - 15, width=52, height=17,
               rx=8.5, fill=C.GOLD)
            text(badge, node.x, ty - 3, "★ 我方", size=10, fill="white",
                 weight="700", anchor="middle", family=FONT_CHAIN)
        text(parent, node.x, ty + s + 14, m["label"], size=10.5,
             fill=C.INK if not m["no_sales"] else C.SUB,
             anchor="middle", family=FONT_CHAIN)

    # 图例
    lg_x, lg_y = x + w - 14, y + h - 44
    legend_items = [("price_gap", "价格缺口"), ("value_opportunity", "性价比"),
                    ("demand_heat", "需求热度"), ("red_ocean", "红海")]
    text(parent, lg_x, lg_y, "分区", size=10, fill=C.SUB, anchor="end",
         family=FONT_CHAIN)
    lx = lg_x - 30
    for zone, lab in reversed(legend_items):
        el(parent, "rect", x=lx - 10, y=lg_y - 9, width=10, height=10,
           fill=ZONE_COLORS[zone], rx=2)
        text(parent, lx + 2, lg_y, lab, size=9.5, fill=C.SUB, family=FONT_CHAIN)
        lx -= 78
    return {"n": len(rows), "no_sales": no_sales_n, "shown": shown}
