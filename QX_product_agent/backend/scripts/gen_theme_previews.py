#!/usr/bin/env python3
"""gen_theme_previews.py —— 为 9 套设计主题生成预览图（前端模板选择器）。

每主题用 MOD deck 渲染器（确定性）生成封面 + 执行摘要两张样张，
Chromium 光栅化后横向拼合 → frontend/public/theme-previews/{id}.png。
静态资产随前端构建分发，运行时零成本。

用法（workspace 根）:
    QX_product_agent/venv/bin/python backend/scripts/gen_theme_previews.py
"""
from __future__ import annotations

import os
import sys

WORKSPACE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, WORKSPACE)


def _fixture_ctx(theme):
    """样张数据（演示数值，仅用于展示主题视觉，不入任何报告）。"""
    import pandas as pd
    from amazon_matrix_mod.deck.themes import Theme

    return {
        "df": pd.DataFrame([
            {"asin": f"B0PREVIEW{i}", "title": f"Preview Product {i}",
             "brand": ["Anker", "Logitech", "Amazon Basics", "Razer",
                       "Microsoft", "Acer"][i % 6],
             "current_price": [9.99, 14.49, 19.99, 24.99, 29.99, 39.99][i % 6],
             "rating": [4.3, 4.5, 4.6, 4.4, 4.7, 4.2][i % 6],
             "review_count": [1200, 8500, 42000, 3100, 15600, 900][i % 6],
             "est_monthly_sales": [800, 2500, 6000, 1200, 3000, 500][i % 6],
             "zone": ["price_gap", "value_opportunity", "demand_heat",
                      "red_ocean", "neutral", "neutral"][i % 6],
             } for i in range(6)]),
        "interpretation": {
            "price_gap": "价格缺口区：中价位存在空白带，适合差异化切入",
            "value_opportunity": "性价比机会区：低价高评产品集中在 $10-15",
            "demand_heat": "需求热度区：头部月销 6000+，需求旺盛",
            "red_ocean": "红海警示区：头部评论壁垒高，正面竞争成本大",
            "verdict": "切入 $14-17 中价位带，主打差异化功能与内容营销",
        },
        "rules": {}, "chapters": [], "exec_summary":
            "市场高度集中（HHI 0.32），头部三品牌占 78% 月销；"
            "价格弹性 -0.29，竞争点不在价格；建议内容力破局。",
        "m3_insights": {"insights": ["中价位带竞争密度最低", "评论壁垒集中在头部"]},
        "visuals": {}, "keyword": "wireless mouse preview", "marketplace": "amazon.com",
        "fetched_at": "2026-08-20T00:00:00Z", "credits": 9, "our_asin": None,
        "image_cache_dir": None, "search_raw": {}, "products_raw": {},
        "theme": theme,
    }


def main() -> int:
    from amazon_matrix_mod.deck import pages as deck_pages
    from amazon_matrix_mod.deck.themes import Theme, available_themes
    from amazon_matrix_mod.svgcharts.rasterize import svg_to_png
    from amazon_matrix_mod.svgcharts.svg import save, svg_document
    from PIL import Image

    out_dir = os.path.join(WORKSPACE, "QX_product_agent", "frontend", "public",
                           "theme-previews")
    os.makedirs(out_dir, exist_ok=True)
    tmp = "/tmp/theme_previews"
    os.makedirs(tmp, exist_ok=True)

    for t in available_themes():
        theme = Theme(t["id"])
        ctx = _fixture_ctx(theme)
        pngs = []
        for name, builder in (("cover", deck_pages.page_cover),
                              ("exec", deck_pages.page_exec_summary)):
            svg_path = os.path.join(tmp, f"{t['id']}_{name}.svg")
            save(builder(ctx), svg_path)
            png_path = os.path.join(tmp, f"{t['id']}_{name}.png")
            if svg_to_png(svg_path, png_path, width=640):
                pngs.append(png_path)
        if not pngs:
            print(f"[跳过] {t['id']}（光栅化失败）")
            continue
        imgs = [Image.open(p) for p in pngs]
        h = min(im.height for im in imgs)
        imgs = [im.crop((0, 0, int(im.width * h / im.height), h)) for im in imgs]
        total_w = sum(im.width for im in imgs) + 8 * (len(imgs) - 1)
        board = Image.new("RGB", (total_w, h), "#FFFFFF")
        x = 0
        for im in imgs:
            board.paste(im, (x, 0))
            x += im.width + 8
        out = os.path.join(out_dir, f"{t['id']}.png")
        board.save(out, "PNG", optimize=True)
        print(f"[OK] {t['id']:22s} -> {out} ({os.path.getsize(out):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
