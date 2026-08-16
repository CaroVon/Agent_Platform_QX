"""
PptDesign Agent —— Presentation DSL → ppt-master SVG 确定性渲染器（v2）
============================================================

v2 升级（阶段 A/B/C）：
1. **页面预算器**：全组件高度预算 → 字号阶梯降级（1.0→0.9→0.8）→
   自适应内容截断 → 溢出标记（不再静默丢内容）
2. **换行校准**：CJK 全角按 1.0em、ASCII 按 0.55em 计宽
3. **图表库扩展**：column/line/pie(donut)/radar/stacked/scatter(象限)，
   数据标签 + 图例 + 网格
4. **原生 chart markers**：`data-pptx-replace-with="chart"` + JSON payload +
   EMU bounds（svg_to_pptx 导出为真 PowerPoint 图表），SVG 视觉为兜底
5. **图标系统**：chunk-filled 图标内联（组件语义映射，缺图自动跳过）
6. **版式脚手架**：封面 Hero 图片槽、标题区配图、页脚页码、章节强调条
7. **图片槽位**：`assets` 参数注入生图（images/*.png）→ Hero/配图/装饰带
"""

from __future__ import annotations

import html
import json
import math
import os
import re
from pathlib import Path

W, H = 1280, 720
PAD = 56
COL_GAP = 24
COL_W = (W - PAD * 2 - COL_GAP) / 2  # 572
BUDGET_Y = 676  # 内容可用高度上限（底部留页码区；文本 shape 行高余量）
EMU = 9525  # 96dpi 下 1px → EMU
FONT = "Noto Sans SC, Source Han Sans SC, PingFang SC, Microsoft YaHei, sans-serif"
_TITLE_FONT = "Noto Serif SC, Source Han Serif SC, Georgia, serif"

_PALETTE_DEFAULTS = {
    "bg": "#f8fafc", "surface": "#ffffff", "primary": "#4f46e5",
    "accent": "#6366f1", "text": "#0f172a", "muted": "#64748b",
}

_ICON_DIR = Path(__file__).resolve().parent / "vendor" / "ppt-master" / "templates" / "icons" / "chunk-filled"

# 组件语义 → 图标名（缺失自动跳过）
_ICON_MAP = {
    "metric": "chart-line",
    "card": "list",
    "table": "chart-bar",
    "timeline": "clock",
    "quote": "lightbulb",
    "chart": "chart-pie",
    "matrix": "layers",
    "text": "file-lines",
    "cover": "crown",
    "summary": "flag",
    "market_overview": "gauge-high",
    "competitor_matrix": "chart-column",
    "user_persona": "users",
    "user_journey": "route",
    "feature_priority": "list-ordered",
    "product_architecture": "layers",
    "roadmap": "clock",
    "conclusion": "target",
}

_icon_cache: dict[str, str | None] = {}


def _icon(name: str, color: str, x: float, y: float, size: float = 22) -> str:
    """内联 chunk-filled 图标（按当前色渲染），缺失返回空串。"""
    if name not in _icon_cache:
        path = _ICON_DIR / f"{name}.svg"
        if path.is_file():
            try:
                content = path.read_text(encoding="utf-8")
                m = re.search(r"<svg[^>]*>(.*?)</svg>", content, re.DOTALL)
                _icon_cache[name] = m.group(1) if m else ""
            except OSError:
                _icon_cache[name] = ""
        else:
            _icon_cache[name] = ""
    inner = _icon_cache.get(name) or ""
    if not inner:
        return ""
    # svg_to_pptx 不支持 currentColor → 替换为实际色值
    inner = inner.replace("currentColor", color)
    return (
        f'<g transform="translate({x:.1f} {y:.1f}) scale({size / 24:.3f})" '
        f'fill="{color}">{inner}</g>'
    )


def _esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def _text(x, y, content, size, fill, weight="normal", anchor="start", italic=False, family=None):
    style = f'font-family="{family or FONT}" font-size="{size}" fill="{fill}" font-weight="{weight}"'
    if italic:
        style += ' font-style="italic"'
    return f'<text x="{x}" y="{y}" text-anchor="{anchor}" {style}>{_esc(content)}</text>'


def _round_rect(x, y, w, h, r, fill, stroke=None, stroke_w=1, opacity=None):
    stroke_attr = f' stroke="{stroke}" stroke-width="{stroke_w}"' if stroke else ""
    op = f' opacity="{opacity}"' if opacity is not None else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" ry="{r}" fill="{fill}"{stroke_attr}{op}/>'


def _lighten(hex_color: str) -> str:
    try:
        hx = hex_color.lstrip("#")
        r, g, b = (int(hx[i : i + 2], 16) for i in (0, 2, 4))
        return f"#{(min(255, r + 14)):02x}{(min(255, g + 14)):02x}{(min(255, b + 14)):02x}"
    except Exception:
        return "#f1f5f9"


# ─── 换行（校准：CJK 全角=1.0em，ASCII=0.55em） ──────────────

_CJK_RE = re.compile(r"[\u2e80-\u9fff\uf900-\ufaff\uff00-\uffef]")


def _wrap(text: str, font_size: float, max_width: float) -> list[str]:
    s = re.sub(r"\s+", " ", str(text)).strip()
    if not s:
        return []
    em = font_size
    width_so_far = 0.0
    line: list[str] = []
    lines: list[str] = []
    for ch in s:
        w = em if _CJK_RE.match(ch) else em * 0.55
        if width_so_far + w > max_width and line:
            lines.append("".join(line))
            line, width_so_far = [], 0.0
        line.append(ch)
        width_so_far += w
    if line:
        lines.append("".join(line))
    return lines


def _clip_lines(text: str, font_size: float, max_width: float, max_lines: int) -> list[str]:
    """按行数截断，末行加省略号（以容纳省略号的换行为准）。"""
    lines = _wrap(text, font_size, max_width)
    if len(lines) <= max_lines:
        return lines
    out = lines[: max_lines - 1]
    last = lines[max_lines - 1]
    while last:
        candidate = _wrap(last + "…", font_size, max_width)
        if len(candidate) == 1 and candidate[0] == last + "…":
            break
        last = last[:-1]
        if not last:
            break
    out.append((last + "…") if last else "…")
    return out


# ─── 原生 chart marker 辅助 ────────────────────────────────

def _native_chart_marker(comp_id: str, x: float, y: float, w: float, h: float, payload: dict, fallback: list[str]) -> str:
    """chart 组件 → <g data-pptx-replace-with="chart"> 原生标记（SVG 兜底在内）。"""
    bounds = f"{x * EMU:.0f},{y * EMU:.0f},{w * EMU:.0f},{h * EMU:.0f}"
    json_data = json.dumps(payload, ensure_ascii=False)
    return (
        f'<g id="{comp_id}" data-pptx-replace-with="chart" data-pptx-id="{comp_id}" '
        f'data-pptx-bounds="{bounds}" data-pptx-json=\'{_esc(json_data)}\'>'
        + "".join(fallback)
        + "</g>"
    )


def _chart_payload(kind: str, categories: list[str], values: list[float], title: str = "", extra: dict | None = None) -> dict:
    payload: dict = {
        "type": kind,
        "categories": categories,
        "series": [{"name": title or "数值", "values": values}],
        "data_labels": True,
    }
    if extra:
        payload.update(extra)
    return payload


# ─── 组件渲染（font_scale 参与） ───────────────────────────

def _metric(c, C, x, y, fs=1.0, avail=400):
    data = c.get("data") or {}
    value = str(data.get("value") or "")
    label = str(data.get("label") or "")
    h = 104
    out = [
        _round_rect(x, y, COL_W, h, 14, C["surface"], C["accent"], 1.5),
        _icon(_ICON_MAP.get("metric", ""), C["accent"], x + COL_W - 34, y + 12, 20),
        _text(x + 20, y + 44, value, int(28 * fs), C["primary"], "bold"),
    ]
    if label:
        out.append(_text(x + 20, y + 76, label, 12, C["muted"]))
    return out, h


def _card(c, C, x, y, fs=1.0, avail=400):
    data = c.get("data") or {}
    title = str(data.get("title") or "")
    items = [str(i) for i in (data.get("items") or []) if str(i).strip()]
    desc = str(data.get("description") or "")
    fs_s = 12 * fs
    lines: list[str] = []
    for it in items:
        lines.extend(_wrap(it, fs_s, COL_W - 44))
    if desc:
        lines.extend(_wrap(desc, fs_s, COL_W - 44))
    line_h = 19 * fs
    h = 52 + len(lines) * line_h
    max_h = min(avail, 380)
    h = min(h, max_h)
    out = [
        _round_rect(x, y, COL_W, h, 12, C["surface"], C["muted"], 1),
        _icon(_ICON_MAP.get("card", ""), C["accent"], x + 16, y + 12, 18),
    ]
    if title:
        out.append(_text(x + 42, y + 29, title, int(15 * fs), C["text"], "bold"))
    ty = y + 52
    # 底部余量 12px：文本 shape 行高会超出盒底，防越界
    max_lines = max(1, int((h - 52 - 12) / line_h))
    for line in _clip_lines("\n".join(lines) if False else ("\n".join(lines)), fs_s, COL_W - 44, max_lines):
        out.append(_text(x + 20, ty, line, fs_s, C["muted"]))
        ty += line_h
    return out, h


def _table(c, C, x, y, fs=1.0, avail=460):
    data = c.get("data") or {}
    columns = [str(c0) for c0 in (data.get("columns") or [])]
    rows = [[str(cell) for cell in (r or [])] for r in (data.get("rows") or [])]
    if not columns and not rows:
        return [_text(x, y + 24, "（表格数据为空）", 13, C["muted"])], 40
    # 表格独立最小缩放（避免随页降级到 <8.5pt）+ 行数按剩余空间封顶
    fs_t = max(fs, 0.92)
    ncols = max(len(columns), max((len(r) for r in rows), default=1))
    col_w = (W - PAD * 2) / ncols
    row_h, head_h = int(30 * fs_t), int(36 * fs_t)
    max_rows = max(1, int((avail - head_h) / row_h))
    show_rows = min(len(rows), max_rows, 12)
    h = head_h + show_rows * row_h
    out = []
    for i in range(ncols):
        label = columns[i] if i < len(columns) else ""
        out.append(_round_rect(PAD + i * col_w, y, col_w, head_h, 0, C["primary"]))
        out.append(_text(PAD + i * col_w + 10, y + head_h * 0.66, label, int(13 * fs_t), C["surface"], "bold"))
    for ri, row in enumerate(rows[:show_rows]):
        ry = y + head_h + ri * row_h
        for i in range(ncols):
            cell = row[i] if i < len(row) else ""
            fill = C["surface"] if ri % 2 == 0 else _lighten(C["bg"])
            out.append(_round_rect(PAD + i * col_w, ry, col_w, row_h, 0, fill))
            line = _wrap(cell, 11 * fs_t, col_w - 14)
            out.append(_text(PAD + i * col_w + 10, ry + row_h * 0.66, line[0] if line else "", int(11 * fs_t), C["text"]))
    if show_rows < len(rows):
        out.append(_text(PAD + 10, y + h - int(10 * fs_t), f"…其余 {len(rows) - show_rows} 行见详细报告", int(10 * fs_t), C["muted"]))
    return out, h


def _timeline(c, C, x, y, fs=1.0, avail=460):
    data = c.get("data") or {}
    phases = data.get("phases") or []
    out: list[str] = []
    ty = y
    per = 0
    per = 0
    for ph in phases[:6]:
        name = str(ph.get("name") or ph.get("phase") or "")
        period = str(ph.get("period") or "")
        ms = [str(m) for m in (ph.get("milestones") or [])[:5]]
        if ty - y > avail - 44:  # 绘制前余量检查（防越界）
            break
        out.append(_round_rect(x, ty, W - PAD * 2, 4, 2, C["accent"]))
        out.append(_text(x, ty + 26, f"▍{name}", int(16 * fs), C["primary"], "bold"))
        if period:
            out.append(_text(x + 14, ty + 50, period, int(12 * fs), C["muted"]))
        ty += int(34 * fs)
        for m in ms:
            if ty - y > avail - 22:
                break
            for line in _wrap(m, 12 * fs, W - PAD * 2 - 40)[:2]:
                out.append(_text(x + 26, ty + 24, f"· {line}", int(12 * fs), C["muted"]))
                ty += int(20 * fs)
        ty += int(22 * fs)
        per = ty - y
    return out, min(per if per else avail, avail)


def _quote(c, C, x, y, fs=1.0, avail=460):
    data = c.get("data") or {}
    text = str(data.get("quote") or data.get("text") or "")
    lines = _wrap(text, 16 * fs, W - PAD * 2 - 60)
    h = max(len(lines[:6]) * 26 * fs, 50)
    out = [f'<rect x="{x}" y="{y}" width="6" height="{h}" fill="{C["accent"]}"/>']
    ty = y + 26 * fs
    for line in lines[:6]:
        out.append(_text(x + 24, ty, line, int(16 * fs), C["text"], italic=True))
        ty += 26 * fs
    return out, h


def _chart(c, C, x, y, fs=1.0, avail=460):
    """chart/matrix → SVG 图表（column/line/pie/radar/scatter）+ 原生 marker。"""
    data = c.get("data") or {}
    kind = data.get("chart_type") or "bar"
    comp_id = str(c.get("id") or f"chart-{int(x)}-{int(y)}")
    # 高度随剩余空间收缩（预算器联动），避免堆叠溢出
    h = min(int(300 * fs), max(int(avail - 12), 150))
    cw = W - PAD * 2
    ch = max(h - int(80 * fs), 120)
    cx, cy = x, y + int(40 * fs)

    if c.get("type") == "matrix" or kind == "quadrant":
        fallback, h = _quadrant_svg(data, C, x, y, fs)
        return fallback, h  # 象限暂用 SVG（scatter 原生后续可加）

    items = [
        {"label": str(it.get("label") or it.get("name") or ""), "value": float(it.get("value") or 0)}
        for it in (data.get("items") or [])
        if it and (it.get("label") or it.get("name"))
    ]
    if not items:
        return [_text(x, y + 30, "（图表数据为空）", 13, C["muted"])], h
    vmax = max(i["value"] for i in items) or 1
    n = len(items)
    cats = [i["label"] for i in items]
    vals = [i["value"] for i in items]

    out = [_round_rect(x, y, cw, h, 12, C["surface"], C["muted"], 1)]

    if kind == "pie":
        cx0, cy0, radius = x + int(240 * fs), y + int(160 * fs), int(86 * fs)
        total = sum(vals) or 1
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
            out.append(
                f'<path d="M {cx0} {cy0} L {x1:.1f} {y1:.1f} A {radius} {radius} 0 {large} 1 {x2:.1f} {y2:.1f} Z" '
                f'fill="{colors[idx % len(colors)]}" stroke="{C["surface"]}" stroke-width="2"/>'
            )
            start = end
        ly = y + int(30 * fs)
        for idx, it in enumerate(items[:8]):
            color = colors[idx % len(colors)]
            out.append(f'<circle cx="{x + 40}" cy="{ly}" r="5" fill="{color}"/>')
            out.append(_text(x + 54, ly + 5, f"{it['label']} {it['value']:g}", int(12 * fs), C["text"]))
            ly += int(24 * fs)
        payload = _chart_payload("pie", cats, vals, str(data.get("title") or ""))
    elif kind == "radar":
        radar_h = int(180 * fs)
        cx0, cy0, radius = x + int(220 * fs), y + int(160 * fs), int(120 * fs)
        n_axes = max(n, 3)
        max_v = max(vals + [100.0])
        for i in range(n_axes):
            a = math.radians(90 - 360 * i / n_axes)
            out.append(f'<line x1="{cx0}" y1="{cy0}" x2="{cx0 + radius * math.cos(a):.1f}" y2="{cy0 - radius * math.sin(a):.1f}" stroke="#e2e8f0" stroke-width="1"/>')
        pts = []
        for i, v in enumerate(vals):
            a = math.radians(90 - 360 * i / n_axes)
            pts.append(f"{cx0 + radius * v / max_v * math.cos(a):.1f},{cy0 - radius * v / max_v * math.sin(a):.1f}")
        poly = " ".join(pts)
        out.append(f'<polygon points="{poly}" fill="{C["primary"]}" fill-opacity="0.22" stroke="{C["primary"]}" stroke-width="2"/>')
        for i, it in enumerate(items):
            a = math.radians(90 - 360 * i / n_axes)
            lx, ly2 = cx0 + (radius + 16) * math.cos(a), cy0 - (radius + 16) * math.sin(a)
            out.append(_text(lx, ly2 + 4, it["label"], int(10 * fs), C["muted"], anchor="middle"))
        payload = _chart_payload("radar", cats, vals, str(data.get("title") or ""))
    else:
        # column / line / stacked（多系列）
        series_raw = data.get("series")
        multi = isinstance(series_raw, list) and series_raw and isinstance(series_raw[0], dict)
        if multi:
            series = [
                {"name": str(s.get("name") or f"系列{i+1}"),
                 "values": [float(v) for v in (s.get("values") or s.get("items") or [])]}
                for i, s in enumerate(series_raw[:3])
            ]
            stacked = bool(data.get("stacked"))
        else:
            series = [{"name": "数值", "values": vals}]
            stacked = False
        all_vals = [v for s in series for v in s["values"]] or [1]
        vmax = max(all_vals) or 1
        colors = [C["primary"], C["accent"], "#0ea5e9", "#10b981"]
        bw = cw / max(n, 1)
        if kind == "line":
            for si, s in enumerate(series):
                pts = [
                    (cx + bw * (i + 0.5), cy + ch - ch * v / vmax)
                    for i, v in enumerate(s["values"])
                ]
                poly = " ".join(f"{p[0]:.1f},{p[1]:.1f}" for p in pts)
                out.append(f'<polyline points="{poly}" fill="none" stroke="{colors[si % len(colors)]}" stroke-width="3"/>')
                for px, py in pts:
                    out.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="5" fill="{colors[si % len(colors)]}"/>')
            for i, it in enumerate(items):
                out.append(_text(cx + bw * (i + 0.5), cy + ch + 18, it["label"], int(11 * fs), C["muted"], anchor="middle"))
            payload = _chart_payload("line", cats, vals, str(data.get("title") or ""))
        else:
            base = [0.0] * n
            for si, s in enumerate(series):
                color = colors[si % len(colors)]
                for i, v in enumerate(s["values"]):
                    bh = max(ch * v / vmax, 3)
                    bx = cx + bw * i + bw * 0.18
                    by = cy + ch - bh - (base[i] * ch / vmax if stacked else 0)
                    out.append(_round_rect(bx, by, bw * 0.64, bh, 4, color))
                    if not stacked and si == 0:
                        out.append(_text(bx + bw * 0.32, by - 8, f"{v:g}", int(10 * fs), C["text"], anchor="middle"))
                    if stacked:
                        base[i] += v
                if si == 0:
                    for i, it in enumerate(items):
                        out.append(_text(cx + bw * (i + 0.5), cy + ch + 18, it["label"], int(11 * fs), C["muted"], anchor="middle"))
            if len(series) > 1:
                lx = x + 20
                for si, s in enumerate(series):
                    out.append(f'<rect x="{lx}" y="{y + 12}" width="10" height="10" fill="{colors[si % len(colors)]}"/>')
                    out.append(_text(lx + 14, y + 21, s["name"], int(10 * fs), C["muted"]))
                    lx += 20 + len(s["name"]) * 11 * fs + 18
            payload = _chart_payload("column", cats, vals, str(data.get("title") or ""))
            if stacked:
                payload.update({"stacked": True})
    out.append(f'<line x1="{cx}" y1="{cy + ch}" x2="{cx + cw}" y2="{cy + ch}" stroke="{C["muted"]}" stroke-width="1"/>')

    marker = _native_chart_marker(comp_id, x, y, cw, h, payload, out)
    return [marker], h


def _quadrant_svg(data, C, x, y, fs=1.0):
    points = [
        p for p in (data.get("points") or [])
        if p and isinstance(p.get("x"), (int, float)) and isinstance(p.get("y"), (int, float))
    ]
    h = int(340 * fs)
    out = [_round_rect(x, y, W - PAD * 2, h, 12, C["surface"], C["muted"], 1)]
    gx, gy, gw, gh = x + 60, y + int(40 * fs), W - PAD * 2 - 120, int(230 * fs)
    mid_x, mid_y = gx + gw / 2, gy + gh / 2
    out.append(f'<line x1="{mid_x}" y1="{gy}" x2="{mid_x}" y2="{gy + gh}" stroke="{C["muted"]}" stroke-width="1" stroke-dasharray="6 6"/>')
    out.append(f'<line x1="{gx}" y1="{mid_y}" x2="{gx + gw}" y2="{mid_y}" stroke="{C["muted"]}" stroke-width="1" stroke-dasharray="6 6"/>')
    out.append(_text(gx + gw / 2, gy + gh + 28, str(data.get("x_axis") or "x"), int(12 * fs), C["muted"], anchor="middle"))
    out.append(_text(gx - 40, gy + gh / 2, str(data.get("y_axis") or "y"), int(12 * fs), C["muted"], anchor="middle"))
    for p in points:
        px = gx + float(p["x"]) * gw
        py = gy + gh - float(p["y"]) * gh
        ours = p.get("kind") in ("product", "ours")
        color = C["primary"] if ours else "#94a3b8"
        out.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="7" fill="{color}"/>')
        out.append(_text(px, py - 12, str(p.get("name") or ""), int(11 * fs), C["text"], anchor="middle"))
    return out, h


# ─── 版式脚手架（页脚/页码/图片槽位） ─────────────────────

def _footer(C, index: int, page_type: str) -> list[str]:
    if page_type in ("cover", "conclusion"):
        return []
    out = [
        f'<line x1="{PAD}" y1="692" x2="{W - PAD}" y2="692" stroke="{C["muted"]}" stroke-width="0.8" opacity="0.4"/>',
        _text(PAD, 700, f"{index + 1:02d}", 11, C["muted"]),
    ]
    return out


def _image_slot(src: str, x: float, y: float, w: float, h: float, radius: float = 10, opacity: float = 1.0) -> list[str]:
    """图片槽位：文件存在时 <image> 内嵌（finalize embed-images 会展开）。"""
    if not src:
        return []
    return [
        _round_rect(x, y, w, h, radius, "#FFFFFF", "#E2E8F0", 1),
        f'<image href="{_esc(src)}" x="{x}" y="{y}" width="{w}" height="{h}" '
        f'preserveAspectRatio="xMidYMid slice" opacity="{opacity}"/>',
    ]


# ─── 页面组装（预算器） ────────────────────────────────────

def render_page_svg(page: dict, theme: dict | None, index: int, assets: dict | None = None) -> dict:
    """渲染页面 SVG；返回 {svg, overflow, max_y, font_scale}。"""
    palette = dict(_PALETTE_DEFAULTS)
    if theme and isinstance(theme.get("palette"), dict):
        palette.update({k: v for k, v in theme["palette"].items() if v})
    C = palette
    page_type = page.get("type", "content")
    title = str(page.get("title") or "")
    subtitle = str(page.get("subtitle") or "")
    insight = str(page.get("insight") or "")
    comps = page.get("components") or []
    assets = assets or {}

    hero = assets.get("hero") if page_type in ("cover", "conclusion") else None
    page_img = assets.get("pages", {}).get(f"{index + 1:02d}")

    def build(fs: float) -> tuple[list[str], float, float]:
        """返回 (fragments, max_y, 是否溢出)。"""
        out: list[str] = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
            f'<rect width="{W}" height="{H}" fill="{C["bg"]}"/>',
        ]
        if hero:
            out.extend(_image_slot(hero, 0, 0, W, H, 0, 0.32))
        if page_type in ("cover", "conclusion"):
            out.append(f'<rect x="{W / 2 - 140}" y="288" width="280" height="8" fill="{C["accent"]}"/>')
            # 标题自适应：36px、最多两行（防超宽/负坐标）
            tsize = 36
            lines = _wrap(title, tsize, W - 260)
            ty = 360
            for line in lines[:2]:
                out.append(_text(W / 2, ty, line, tsize, C["text"], "bold", anchor="middle", family=_TITLE_FONT))
                ty += 46
            if subtitle:
                out.append(_text(W / 2, 470, subtitle, 20, C["muted"], anchor="middle"))
            out.extend(_footer(C, index, page_type))
            out.append("</svg>")
            return out, 500, False

        # 标题区（+ 可选配图）
        out.append(f'<rect x="{PAD}" y="52" width="10" height="34" fill="{C["accent"]}"/>')
        out.append(_text(PAD + 26, 80, title, int(26 * fs), C["text"], "bold", family=_TITLE_FONT))
        if page_img:
            out.extend(_image_slot(page_img, W - 240, 44, 184, 104, 10))
        if insight:
            out.append(_text(PAD, 118, insight, int(14 * fs), C["primary"]))

        y0 = int(150 * fs)
        col_heights = [y0, y0]
        max_y = y0
        for c in comps:
            ctype = c.get("type")
            wide = ctype in ("table", "timeline", "quote", "text", "chart", "matrix")
            col = 0 if col_heights[0] <= col_heights[1] else 1
            cx = PAD + col * (COL_W + COL_GAP) if not wide else PAD
            cy = col_heights[col] if not wide else max(col_heights)
            avail = BUDGET_Y - cy
            if avail < 60:
                break
            builder = {
                "metric": _metric, "card": _card, "table": _table,
                "timeline": _timeline, "quote": _quote,
                "chart": _chart, "matrix": _chart,
            }.get(ctype)
            if builder is None:
                data = c.get("data") or {}
                t_title = str(data.get("title") or "")
                body = str(data.get("text") or data.get("content") or "")
                lines = _wrap(body, int(14 * fs), W - PAD * 2)
                h = int(40 * fs) + len(lines) * int(26 * fs)
                if t_title:
                    out.append(_text(cx, cy + int(26 * fs), t_title, int(15 * fs), C["text"], "bold"))
                ty = cy + int(54 * fs)
                max_lines = max(1, int(avail / (26 * fs)))
                for line in _clip_lines(body, int(14 * fs), W - PAD * 2, max_lines):
                    out.append(_text(cx, ty, line, int(14 * fs), C["text"]))
                    ty += int(26 * fs)
                h = ty - cy
            else:
                frags, h = builder(c, C, cx, cy, fs=fs, avail=avail)
                out.extend(frags)
            if wide:
                col_heights = [cy + h + 18, cy + h + 18]
            else:
                col_heights[col] = cy + h + 18
            max_y = max(max_y, cy + h)
            if max(col_heights) > BUDGET_Y:
                break

        out.extend(_footer(C, index, page_type))
        out.append("</svg>")
        return out, max_y, max_y > BUDGET_Y

    # 字号阶梯降级（预算器）
    chosen = None
    for fs in (1.0, 0.9, 0.8):
        frags, max_y, overflow = build(fs)
        if not overflow:
            chosen = (frags, max_y, fs, False)
            break
        chosen = (frags, max_y, fs, overflow)
    frags, max_y, fs, overflow = chosen or build(0.8)
    return {"svg": "\n".join(frags), "overflow": max_y > 700, "max_y": max_y, "font_scale": fs}


def render_project_svgs(presentation: dict, project_dir: str, assets: dict | None = None) -> dict:
    """渲染全部页面 SVG 到 svg_output/；返回 {files, overflow_pages, max_y_by_page}。"""
    svg_dir = os.path.join(project_dir, "svg_output")
    os.makedirs(svg_dir, exist_ok=True)
    pages = presentation.get("pages") or []
    theme = presentation.get("theme")
    files: list[str] = []
    overflow_pages: list[int] = []
    max_y_by_page: dict[int, float] = {}
    for i, page in enumerate(pages):
        result = render_page_svg(page, theme, i, assets=assets)
        name = f"slide_{i + 1:02d}_{page.get('type', 'page')}.svg"
        with open(os.path.join(svg_dir, name), "w", encoding="utf-8") as f:
            f.write(result["svg"])
        files.append(name)
        max_y_by_page[i + 1] = round(result["max_y"], 1)
        if result["overflow"]:
            overflow_pages.append(i + 1)
    return {"files": files, "overflow_pages": overflow_pages, "max_y_by_page": max_y_by_page}
