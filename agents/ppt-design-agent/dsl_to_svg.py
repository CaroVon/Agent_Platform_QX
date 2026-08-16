"""
PptDesign Agent —— Presentation DSL → ppt-master SVG 确定性渲染器
============================================================

把 Presentation DSL 页面渲染为 ppt-master 约定的逐页 SVG（1280×720）：
- 页面设计闭合：所有可见内容都在 SVG 中（文字/图形/图表/表格），无外部依赖
- 视觉层由 theme.palette 驱动（咨询风 8 套 + 默认）
- 图表（chart/matrix）用原生 SVG 元素绘制（柱/折线/饼/象限散点），
  与 Web 预览同数据、同语义（primary/accent 双色）
- 文本按宽度估算换行（CJK 全角 ≈ 字号 px），禁止溢出画布
"""

from __future__ import annotations

import html
import math
import re

W, H = 1280, 720
PAD = 56
COL_GAP = 24
COL_W = (W - PAD * 2 - COL_GAP) / 2  # 572
FONT = "Noto Sans SC, Source Han Sans SC, PingFang SC, Microsoft YaHei, sans-serif"

_PALETTE_DEFAULTS = {
    "bg": "#f8fafc", "surface": "#ffffff", "primary": "#4f46e5",
    "accent": "#6366f1", "text": "#0f172a", "muted": "#64748b",
}


def _esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def _wrap(text: str, font_size: float, max_width: float) -> list[str]:
    """按估算宽度换行（CJK 全角 ≈ font_size px，ASCII 半角 ≈ font_size*0.55）。"""
    text = re.sub(r"\s+", " ", str(text)).strip()
    if not text:
        return []
    per_line = max(int(max_width / (font_size * 0.62)), 4)
    lines: list[str] = []
    cur = ""
    for ch in text:
        if len(cur) >= per_line:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def _text(x, y, content, size, fill, weight="normal", anchor="start", italic=False, spacing=None):
    style = f'font-family="{FONT}" font-size="{size}" fill="{fill}" font-weight="{weight}"'
    if italic:
        style += ' font-style="italic"'
    if spacing:
        style += f' letter-spacing="{spacing}"'
    return (
        f'<text x="{x}" y="{y}" text-anchor="{anchor}" {style}>'
        f"{_esc(content)}</text>"
    )


def _round_rect(x, y, w, h, r, fill, stroke=None, stroke_w=1):
    stroke_attr = f' stroke="{stroke}" stroke-width="{stroke_w}"' if stroke else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" ry="{r}" fill="{fill}"{stroke_attr}/>'


# ─── 组件渲染 ─────────────────────────────────────────────

def _metric(c, C, x, y):
    data = c.get("data") or {}
    value = str(data.get("value") or "")
    label = str(data.get("label") or "")
    h = 110
    out = [_round_rect(x, y, COL_W, h, 14, C["surface"], C["accent"], 1.5)]
    out.append(_text(x + 20, y + 46, value, 28, C["primary"], "bold"))
    if label:
        out.append(_text(x + 20, y + 78, label, 13, C["muted"]))
    return out, h


def _card(c, C, x, y, max_h=330):
    data = c.get("data") or {}
    title = str(data.get("title") or "")
    items = [str(i) for i in (data.get("items") or []) if str(i).strip()]
    desc = str(data.get("description") or "")
    lines: list[str] = []
    for it in items:
        lines.extend(_wrap(it, 12, COL_W - 40))
    if desc:
        lines.extend(_wrap(desc, 12, COL_W - 40))
    h = 54 + max(len(lines), 1) * 20
    h = min(h, max_h)
    out = [_round_rect(x, y, COL_W, h, 12, C["surface"], C["muted"], 1)]
    if title:
        out.append(_text(x + 20, y + 30, title, 15, C["text"], "bold"))
    ty = y + 54
    for line in lines[: max(1, int((h - 54) / 20))]:
        out.append(_text(x + 20, ty, line, 12, C["muted"]))
        ty += 20
    return out, h


def _table(c, C, x, y):
    data = c.get("data") or {}
    columns = [str(c0) for c0 in (data.get("columns") or [])]
    rows = [[str(cell) for cell in (r or [])] for r in (data.get("rows") or [])]
    if not columns and not rows:
        return [_text(x, y + 24, "（表格数据为空）", 13, C["muted"])], 40
    ncols = max(len(columns), max((len(r) for r in rows), default=1))
    col_w = (W - PAD * 2) / ncols
    row_h, head_h = 30, 36
    h = head_h + min(len(rows), 12) * row_h
    out = []
    for i in range(ncols):
        label = columns[i] if i < len(columns) else ""
        out.append(_round_rect(PAD + i * col_w, y, col_w, head_h, 0, C["primary"]))
        out.append(_text(PAD + i * col_w + 10, y + 24, label, 13, C["surface"], "bold"))
    for ri, row in enumerate(rows[:12]):
        ry = y + head_h + ri * row_h
        for i in range(ncols):
            cell = row[i] if i < len(row) else ""
            fill = C["surface"] if ri % 2 == 0 else _lighten(C["bg"])
            out.append(_round_rect(PAD + i * col_w, ry, col_w, row_h, 0, fill))
            for line in _wrap(cell, 11, col_w - 14)[:1]:
                out.append(_text(PAD + i * col_w + 10, ry + 21, line, 11, C["text"]))
    return out, h


def _lighten(hex_color: str) -> str:
    try:
        hx = hex_color.lstrip("#")
        r, g, b = (int(hx[i : i + 2], 16) for i in (0, 2, 4))
        return f"#{(min(255, r + 14)):02x}{(min(255, g + 14)):02x}{(min(255, b + 14)):02x}"
    except Exception:
        return "#f1f5f9"


def _timeline(c, C, x, y):
    data = c.get("data") or {}
    phases = data.get("phases") or []
    out: list[str] = []
    ty = y
    for ph in phases[:6]:
        name = str(ph.get("name") or ph.get("phase") or "")
        period = str(ph.get("period") or "")
        ms = [str(m) for m in (ph.get("milestones") or [])[:5]]
        out.append(_round_rect(x, ty, W - PAD * 2, 4, 2, C["accent"]))
        out.append(_text(x, ty + 26, f"▍{name}", 16, C["primary"], "bold"))
        if period:
            out.append(_text(x + 14, ty + 50, period, 12, C["muted"]))
        ty += 34
        for m in ms:
            for line in _wrap(m, 12, W - PAD * 2 - 40)[:2]:
                out.append(_text(x + 26, ty + 24, f"· {line}", 12, C["muted"]))
                ty += 20
        ty += 22
    return out, ty - y + 10


def _quote(c, C, x, y):
    data = c.get("data") or {}
    text = str(data.get("quote") or data.get("text") or "")
    lines = _wrap(text, 16, W - PAD * 2 - 60)
    h = max(len(lines) * 26, 50)
    out = [f'<rect x="{x}" y="{y}" width="6" height="{h}" fill="{C["accent"]}"/>']
    ty = y + 26
    for line in lines[:6]:
        out.append(_text(x + 24, ty, line, 16, C["text"], "normal", italic=True))
        ty += 26
    return out, h


def _chart(c, C, x, y):
    """chart / matrix → 原生 SVG 图表（柱/折线/饼/象限散点）。"""
    data = c.get("data") or {}
    kind = data.get("chart_type") or "bar"
    if c.get("type") == "matrix" or kind == "quadrant":
        return _quadrant(data, C, x, y)
    items = [
        {"label": str(it.get("label") or it.get("name") or ""), "value": float(it.get("value") or 0)}
        for it in (data.get("items") or [])
        if it and (it.get("label") or it.get("name"))
    ]
    h = 300
    if not items:
        return [_text(x, y + 30, "（图表数据为空）", 13, C["muted"])], h
    cw, ch = W - PAD * 2, 220
    cx, cy = x, y + 40
    out = [_round_rect(x, y, cw, h, 12, C["surface"], C["muted"], 1)]
    vmax = max(i["value"] for i in items) or 1
    n = len(items)
    if kind == "pie":
        total = sum(i["value"] for i in items) or 1
        cx0, cy0, radius = x + 260, y + 170, 90
        start = -90.0
        colors = [C["primary"], C["accent"], "#0ea5e9", "#10b981", "#f59e0b", "#94a3b8"]
        for idx, it in enumerate(items):
            ang = 360.0 * it["value"] / total
            end = start + ang
            large = 1 if ang > 180 else 0
            x1 = cx0 + radius * math.cos(math.radians(start))
            y1 = cy0 + radius * math.sin(math.radians(start))
            x2 = cx0 + radius * math.cos(math.radians(end))
            y2 = cy0 + radius * math.sin(math.radians(end))
            color = colors[idx % len(colors)]
            out.append(
                f'<path d="M {cx0} {cy0} L {x1:.1f} {y1:.1f} A {radius} {radius} 0 {large} 1 {x2:.1f} {y2:.1f} Z" '
                f'fill="{color}" stroke="{C["surface"]}" stroke-width="2"/>'
            )
            start = end
        ly = y + 40
        for idx, it in enumerate(items[:8]):
            color = colors[idx % len(colors)]
            out.append(f'<circle cx="{x + 40}" cy="{ly}" r="5" fill="{color}"/>')
            out.append(_text(x + 54, ly + 5, f"{it['label']} {it['value']:g}", 12, C["text"]))
            ly += 24
    elif kind == "line":
        bw = cw / max(n, 1)
        pts = [
            (cx + bw * (i + 0.5), cy + ch - ch * it["value"] / vmax)
            for i, it in enumerate(items)
        ]
        poly = " ".join(f"{p[0]:.1f},{p[1]:.1f}" for p in pts)
        out.append(f'<polyline points="{poly}" fill="none" stroke="{C["primary"]}" stroke-width="3"/>')
        for i, (px, py) in enumerate(pts):
            out.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="5" fill="{C["primary"]}"/>')
            out.append(_text(px, py - 10, f"{items[i]['value']:g}", 11, C["text"], anchor="middle"))
            out.append(_text(px, cy + ch + 18, items[i]["label"], 11, C["muted"], anchor="middle"))
    else:  # bar / radar→bar
        bw = cw / max(n, 1)
        for i, it in enumerate(items):
            bh = max(ch * it["value"] / vmax, 4)
            bx = cx + bw * i + bw * 0.18
            out.append(_round_rect(bx, cy + ch - bh, bw * 0.64, bh, 4, C["primary"]))
            out.append(_text(bx + bw * 0.32, cy + ch - bh - 8, f"{it['value']:g}", 11, C["text"], anchor="middle"))
            out.append(_text(bx + bw * 0.32, cy + ch + 18, it["label"], 11, C["muted"], anchor="middle"))
    out.append(f'<line x1="{cx}" y1="{cy + ch}" x2="{cx + cw}" y2="{cy + ch}" stroke="{C["muted"]}" stroke-width="1"/>')
    return out, h


def _quadrant(data, C, x, y):
    points = [
        p for p in (data.get("points") or [])
        if p and isinstance(p.get("x"), (int, float)) and isinstance(p.get("y"), (int, float))
    ]
    h = 340
    out = [_round_rect(x, y, W - PAD * 2, h, 12, C["surface"], C["muted"], 1)]
    gx, gy, gw, gh = x + 60, y + 40, W - PAD * 2 - 120, 230
    mid_x, mid_y = gx + gw / 2, gy + gh / 2
    out.append(f'<line x1="{mid_x}" y1="{gy}" x2="{mid_x}" y2="{gy + gh}" stroke="{C["muted"]}" stroke-width="1" stroke-dasharray="6 6"/>')
    out.append(f'<line x1="{gx}" y1="{mid_y}" x2="{gx + gw}" y2="{mid_y}" stroke="{C["muted"]}" stroke-width="1" stroke-dasharray="6 6"/>')
    out.append(_text(gx + gw / 2, gy + gh + 28, str(data.get("x_axis") or "x"), 12, C["muted"], anchor="middle"))
    out.append(_text(gx - 40, gy + gh / 2, str(data.get("y_axis") or "y"), 12, C["muted"], anchor="middle"))
    for p in points:
        px = gx + float(p["x"]) * gw
        py = gy + gh - float(p["y"]) * gh
        ours = p.get("kind") in ("product", "ours")
        color = C["primary"] if ours else "#94a3b8"
        out.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="7" fill="{color}"/>')
        out.append(_text(px, py - 12, str(p.get("name") or ""), 11, C["text"], anchor="middle"))
    return out, h


# ─── 页面组装 ─────────────────────────────────────────────

def render_page_svg(page: dict, theme: dict | None, index: int) -> str:
    """Presentation DSL 页 → ppt-master 页 SVG 字符串。"""
    palette = dict(_PALETTE_DEFAULTS)
    if theme and isinstance(theme.get("palette"), dict):
        palette.update({k: v for k, v in theme["palette"].items() if v})
    C = palette
    page_type = page.get("type", "content")
    title = str(page.get("title") or "")
    subtitle = str(page.get("subtitle") or "")
    insight = str(page.get("insight") or "")
    comps = page.get("components") or []

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        f'<rect width="{W}" height="{H}" fill="{C["bg"]}"/>',
    ]

    # 封面 / 结尾
    if page_type in ("cover", "conclusion"):
        out.append(f'<rect x="{W/2-140}" y="292" width="280" height="8" fill="{C["accent"]}"/>')
        for line in _wrap(title, 44, W - 200):
            pass
        out.append(_text(W / 2, 380, title, 44, C["text"], "bold", anchor="middle"))
        if subtitle:
            out.append(_text(W / 2, 448, subtitle, 20, C["muted"], anchor="middle"))
        out.append("</svg>")
        return "\n".join(out)

    # 内容页：标题 + 强调条 + insight
    out.append(f'<rect x="{PAD}" y="56" width="10" height="34" fill="{C["accent"]}"/>')
    out.append(_text(PAD + 26, 82, title, 26, C["text"], "bold"))
    if insight:
        out.append(_text(PAD, 120, insight, 14, C["primary"]))

    # 组件流式布局（两列网格；宽组件跨列）
    y = 160
    col_heights = [y, y]
    idx = 0
    for c in comps:
        ctype = c.get("type")
        wide = ctype in ("table", "timeline", "quote", "text", "chart", "matrix")
        col = 0 if col_heights[0] <= col_heights[1] else 1
        cx = PAD + col * (COL_W + COL_GAP) if not wide else PAD
        cy = col_heights[col] if not wide else max(col_heights)
        builder = {
            "metric": _metric, "card": _card, "table": _table,
            "timeline": _timeline, "quote": _quote,
            "chart": _chart, "matrix": _chart,
        }.get(ctype)
        if builder is None:
            # text 组件
            data = c.get("data") or {}
            t_title = str(data.get("title") or "")
            body = str(data.get("text") or data.get("content") or "")
            lines = _wrap(body, 14, W - PAD * 2)
            h = 40 + len(lines) * 26
            if t_title:
                out.append(_text(cx, cy + 26, t_title, 15, C["text"], "bold"))
            ty = cy + 54
            for line in lines[:12]:
                out.append(_text(cx, ty, line, 14, C["text"]))
                ty += 26
            h = ty - cy
        else:
            frags, h = builder(c, C, cx, cy)
            out.extend(frags)
        if wide:
            col_heights = [cy + h + 18, cy + h + 18]
        else:
            col_heights[col] = cy + h + 18
        idx += 1
        if max(col_heights) > H - 24:
            break  # 超出画布即止（页面设计闭合：宁可截断不可溢出）

    out.append("</svg>")
    return "\n".join(out)


def render_project_svgs(presentation: dict, project_dir, page_prefix="slide") -> list[str]:
    """渲染全部页面 SVG 到 project_dir/svg_output/，返回文件名列表。"""
    import os

    svg_dir = os.path.join(project_dir, "svg_output")
    os.makedirs(svg_dir, exist_ok=True)
    pages = presentation.get("pages") or []
    theme = presentation.get("theme")
    files: list[str] = []
    for i, page in enumerate(pages):
        svg = render_page_svg(page, theme, i)
        name = f"{page_prefix}_{i + 1:02d}_{page.get('type', 'page')}.svg"
        with open(os.path.join(svg_dir, name), "w", encoding="utf-8") as f:
            f.write(svg)
        files.append(name)
    return files
