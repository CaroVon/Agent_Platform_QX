"""合成器（P3.5）—— 3840×2160 主海报 + 封面 + 洞察页 + 多页 PDF。

核心要求：准确度（数据图精确叠加）+ 信息量（执行摘要/4区解读/M3洞察/溯源）+ 美观性（image-01 背景 + 排版）。
"""
from __future__ import annotations

import logging
import os

from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger(__name__)

W, H = 3840, 2160
NAVY = (18, 53, 91)
GOLD = (200, 126, 79)
WHITE = (255, 255, 255)
DARK = (15, 27, 45)
GREY = (120, 130, 145)

# 4 区配色
ZONE_COLORS = {
    "price_gap": (46, 125, 50), "value_opportunity": (21, 101, 192),
    "demand_heat": (249, 168, 37), "red_ocean": (198, 40, 40),
}
ZONE_LABELS = {
    "price_gap": "价格缺口区", "value_opportunity": "性价比机会区",
    "demand_heat": "需求热度区", "red_ocean": "红海警示区",
}


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", 0),
        ("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", 0),
    ]
    for path, idx in candidates:
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size, index=idx)
            except Exception:  # noqa: BLE001
                continue
    return ImageFont.load_default()


def _text(draw: ImageDraw.ImageDraw, xy, text, font, fill, anchor="la", max_w=None):
    """安全文本绘制（超宽自动截断）。"""
    if max_w and draw.textlength(text, font=font) > max_w:
        while text and draw.textlength(text + "…", font=font) > max_w:
            text = text[:-1]
        text += "…"
    draw.text(xy, text, font=font, fill=fill, anchor=anchor)


def _wrap(draw, text, font, max_w) -> list[str]:
    text = (text or "").replace("\n", " ").replace("\r", " ")
    lines, cur = [], ""
    for ch in text:
        if draw.textlength(cur + ch, font=font) > max_w:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def compose_poster(chart_path: str, interpretation: dict, m3_insights: dict,
                   executive_summary: str, keyword: str, marketplace: str,
                   fetched_at: str, n_comp: int, credits: int | None,
                   background_path: str | None, out_path: str,
                   zone_icons: dict | None = None) -> str:
    """3840×2160 主海报合成。"""
    canvas = Image.new("RGB", (W, H), DARK)
    if background_path and os.path.isfile(background_path):
        try:
            bg = Image.open(background_path).convert("RGB").resize((W, H), Image.LANCZOS)
            canvas = bg
        except Exception:  # noqa: BLE001
            pass
    draw = ImageDraw.Draw(canvas, "RGBA")

    # 顶部标题区（半透明遮罩保证可读）
    draw.rectangle([0, 0, W, 210], fill=(10, 20, 35, 200))
    f_title = _font(84, bold=True)
    f_sub = _font(34)
    _text(draw, (80, 52), f"MOD 报告 — {keyword}", f_title, WHITE)
    sub = f"{marketplace}（Rainforest API）｜ N={n_comp} 竞品 ｜ 抓取 {fetched_at[:10]}"
    if credits:
        sub += f" ｜ credits≈{credits}"
    _text(draw, (84, 148), sub, f_sub, (200, 210, 225, 255))

    # 中央坐标图（白底卡片）
    card_top, card_h = 240, 1330
    draw.rounded_rectangle([60, card_top, W - 60, card_top + card_h], radius=24,
                           fill=(255, 255, 255, 246), outline=(255, 255, 255, 120), width=2)
    if os.path.isfile(chart_path):
        chart = Image.open(chart_path).convert("RGBA")
        # 等比适配卡片
        scale = min((W - 160) / chart.width, (card_h - 40) / chart.height)
        chart = chart.resize((int(chart.width * scale), int(chart.height * scale)),
                             Image.LANCZOS)
        cx = 60 + (W - 120 - chart.width) // 2
        cy = card_top + 20 + (card_h - 40 - chart.height) // 2
        canvas.paste(chart, (cx, cy), chart)

    # 底部信息区
    y = card_top + card_h + 30
    f_zone_t = _font(34, bold=True)
    f_zone_b = _font(27)
    f_small = _font(24)
    zone_w = (W - 180) // 4
    # 执行摘要条
    draw.rounded_rectangle([60, y, W - 60, y + 118], radius=18, fill=(255, 255, 255, 235))
    if executive_summary:
        _text(draw, (90, y + 20), "执行摘要", f_zone_t, NAVY)
        lines = _wrap(draw, executive_summary, f_zone_b, W - 420)
        for i, ln in enumerate(lines[:3]):
            _text(draw, (340, y + 20 + i * 34), ln, f_zone_b, (60, 70, 90))
    y += 140

    # 4 区解读卡
    for i, zone in enumerate(("price_gap", "value_opportunity", "demand_heat", "red_ocean")):
        x0 = 60 + i * (zone_w + 20)
        color = ZONE_COLORS[zone]
        draw.rounded_rectangle([x0, y, x0 + zone_w, y + 190], radius=20,
                               fill=(255, 255, 255, 240))
        draw.rectangle([x0, y, x0 + 12, y + 190], fill=color)
        txt = interpretation.get(zone, "—")
        # 分区图标（若有）
        icon_y = y + 16
        if zone_icons and zone_icons.get(zone) and os.path.isfile(zone_icons[zone]):
            try:
                icon = Image.open(zone_icons[zone]).convert("RGBA").resize((64, 64), Image.LANCZOS)
                canvas.paste(icon, (x0 + 22, icon_y), icon)
            except Exception:  # noqa: BLE001
                pass
        _text(draw, (x0 + 100, icon_y + 8), ZONE_LABELS[zone], f_zone_t, color)
        lines = _wrap(draw, txt, f_zone_b, zone_w - 60)
        for j, ln in enumerate(lines[:3]):
            _text(draw, (x0 + 30, icon_y + 78 + j * 34), ln, f_zone_b, (60, 70, 90))
    y += 212

    # M3 洞察条
    insights = m3_insights.get("insights") or []
    if insights:
        draw.rounded_rectangle([60, y, W - 60, y + 168], radius=18,
                               fill=(240, 246, 255, 245))
        _text(draw, (90, y + 18), "M3 数据洞察", f_zone_t, GOLD)
        for i, ins in enumerate(insights[:4]):
            _text(draw, (90, y + 66 + i * 26), f"· {ins[:80]}", f_small, (50, 60, 80))
        y += 190

    # 溯源
    _text(draw, (60, H - 52), f"数据源：Rainforest API @ {fetched_at} ｜ "
          "月销=官方 recent_sales 口径 ｜ 主图来自亚马逊", f_small, (170, 180, 195))

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    canvas.save(out_path, "PNG")
    return out_path


def compose_cover(keyword: str, cover_path: str | None, out_path: str,
                  marketplace: str = "amazon.com") -> str:
    """封面：image-01 视觉 + 标题排版（若视觉缺失用纯色渐变底）。"""
    canvas = Image.new("RGB", (W, H), DARK)
    if cover_path and os.path.isfile(cover_path):
        try:
            cv = Image.open(cover_path).convert("RGB").resize((W, H), Image.LANCZOS)
            canvas = cv
        except Exception:  # noqa: BLE001
            pass
    draw = ImageDraw.Draw(canvas, "RGBA")
    draw.rectangle([0, H - 560, W, H], fill=(8, 16, 30, 210))
    draw.rectangle([0, 0, W, 300], fill=(8, 16, 30, 170))
    _text(draw, (W // 2, 120), "AMAZON MARKET OPPORTUNITY DASHBOARD",
          _font(44), (180, 195, 215, 255), anchor="ma")
    _text(draw, (W // 2, H - 420), f"{keyword} 竞品矩阵 MOD 报告",
          _font(110, bold=True), WHITE, anchor="ma")
    _text(draw, (W // 2, H - 260), f"数据驱动 · 4 区机会分析 · {marketplace}",
          _font(44), (215, 195, 160, 255), anchor="ma")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    canvas.save(out_path, "PNG")
    return out_path


def compose_insights_page(m3_insights: dict, out_path: str, keyword: str) -> str:
    """M3 洞察页。"""
    canvas = Image.new("RGB", (W, H), (245, 247, 250))
    draw = ImageDraw.Draw(canvas)
    f_t = _font(64, bold=True)
    f_h = _font(36, bold=True)
    f_b = _font(28)
    _text(draw, (80, 60), f"M3 数据洞察 — {keyword}", f_t, NAVY)
    y = 190
    assess = m3_insights.get("assess")
    if assess:
        draw.rounded_rectangle([80, y, W - 80, y + 120], radius=18, fill=WHITE)
        _text(draw, (110, y + 16), "图表质量评估", f_h, GOLD)
        _text(draw, (110, y + 70), assess[:150], f_b, (60, 70, 90))
        y += 150
    insights = m3_insights.get("insights") or []
    if insights:
        draw.rounded_rectangle([80, y, W - 80, y + 40 + 74 * len(insights)], radius=18, fill=WHITE)
        _text(draw, (110, y + 16), "市场洞察", f_h, NAVY)
        for i, ins in enumerate(insights):
            _text(draw, (110, y + 74 + i * 74), f"{i + 1}. {ins[:120]}", f_b, (50, 60, 80))
        y += 100 + 74 * len(insights)
    imp = m3_insights.get("improvements") or []
    if imp:
        draw.rounded_rectangle([80, y, W - 80, y + 40 + 60 * len(imp)], radius=18, fill=WHITE)
        _text(draw, (110, y + 16), "渲染改进建议", f_h, GOLD)
        for i, it in enumerate(imp):
            _text(draw, (110, y + 74 + i * 60), f"· {it[:110]}", f_b, (60, 70, 90))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    canvas.save(out_path, "PNG")
    return out_path


def compose_pdf(pages: list[str], out_path: str) -> str:
    """多页 PNG → 单 PDF（Pillow）。"""
    imgs = [Image.open(p).convert("RGB") for p in pages if os.path.isfile(p)]
    if not imgs:
        raise FileNotFoundError("无可用页面")
    imgs[0].save(out_path, "PDF", save_all=True, append_images=imgs[1:])
    return out_path
