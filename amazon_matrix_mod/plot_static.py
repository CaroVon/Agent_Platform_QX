"""静态报告图 —— 1920×1080 PNG（matplotlib + Pillow）。

布局（对应执行前最终方案 §5.1）：
  Header 60px        标题/副标题（数据源、N、credits）
  主图 720px         气泡矩阵：X=log(price) Y=log(est_monthly_sales)，
                     气泡=主图缩略图，4 区着色 + 价格标签，我方产品 ★
  解读卡片 160px     4 区一句话解读（横排 4 列）
  底部 80px          价格分布直方图 + 数据溯源
"""
from __future__ import annotations

import io
import logging
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.font_manager import FontProperties, fontManager  # noqa: E402
from matplotlib.offsetbox import AnnotationBbox, OffsetImage  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from amazon_matrix_mod.zoning import ZONE_LABELS  # noqa: E402

log = logging.getLogger(__name__)

CANVAS_W, CANVAS_H = 1920, 1080
THUMB_SIZE = 60

# 4 区配色（背景/描边）
ZONE_COLORS = {
    "price_gap": "#2E7D32",
    "value_opportunity": "#1565C0",
    "demand_heat": "#F9A825",
    "red_ocean": "#C62828",
    "neutral": "#9E9E9E",
}
ZONE_BG = {
    "price_gap": "#E8F5E9",
    "value_opportunity": "#E3F2FD",
    "demand_heat": "#FFF8E1",
    "red_ocean": "#FFEBEE",
    "neutral": "#FFFFFF",
}


def _setup_cjk_font() -> str:
    """中文字体：优先 Noto Sans CJK / 文泉驿正黑。返回 family 名。"""
    for fam in ("Noto Sans CJK SC", "WenQuanYi Zen Hei", "WenQuanYi Micro Hei"):
        try:
            fontManager.findfont(fam, fallback_to_default=False)
            return fam
        except Exception:  # noqa: BLE001
            continue
    # 手动注册 ttc/otf（findfont 失败时兜底）
    for path in ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
                 "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                 "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"):
        if os.path.isfile(path):
            try:
                fontManager.addfont(path)
                return os.path.basename(path).split(".")[0]
            except Exception:  # noqa: BLE001
                continue
    return "DejaVu Sans"


_CJK = _setup_cjk_font()


def _load_thumb(url: str, size: int = THUMB_SIZE, cache_dir: str | None = None,
                asin: str | None = None):
    """主图 → 圆角缩略图（PIL RGBA）；优先读 image_cache；失败返回灰色占位块。"""
    img = None
    from amazon_matrix_mod.storage import image_failed
    local = None
    if cache_dir and asin:
        if image_failed(cache_dir, asin):
            img = Image.new("RGBA", (size, size), (200, 200, 200, 255))
            d = ImageDraw.Draw(img)
            d.rectangle([2, 2, size - 3, size - 3], outline=(120, 120, 120, 255), width=2)
            img = img.resize((size, size), Image.LANCZOS)
            mask = Image.new("L", (size, size), 0)
            d = ImageDraw.Draw(mask)
            d.rounded_rectangle([0, 0, size - 1, size - 1], radius=10, fill=255)
            img.putalpha(mask)
            return img
        p = os.path.join(cache_dir, "image_cache", f"{asin}.jpg")
        if os.path.isfile(p) and os.path.getsize(p) > 1000:
            local = p
    if local:
        try:
            img = Image.open(local).convert("RGBA")
        except Exception:  # noqa: BLE001
            img = None
    if img is None and url:
        try:
            import requests
            r = requests.get(url, timeout=(2, 5))
            if r.status_code == 200:
                img = Image.open(io.BytesIO(r.content)).convert("RGBA")
        except Exception as exc:  # noqa: BLE001
            log.warning("缩略图下载失败 %s: %s", url, exc)
    if img is None:
        img = Image.new("RGBA", (size, size), (200, 200, 200, 255))
        d = ImageDraw.Draw(img)
        d.rectangle([2, 2, size - 3, size - 3], outline=(120, 120, 120, 255), width=2)
    img = img.resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=10, fill=255)
    img.putalpha(mask)
    return img


def _price_hist(ax, prices: list[float], p25, p50, p75) -> None:
    ax.hist(prices, bins=min(20, max(6, len(prices))), color="#BBDEFB",
            edgecolor="#64B5F6", alpha=0.9)
    for v, c, label in ((p25, "#F9A825", "P25"), (p50, "#2E7D32", "P50"),
                        (p75, "#C62828", "P75")):
        ax.axvline(v, color=c, linestyle="--", linewidth=1.2)
        ax.text(v, ax.get_ylim()[1] * 0.92, label, color=c, fontsize=9,
                fontproperties=FontProperties(family=_CJK))
    ax.set_title("价格分布（美元）", fontsize=11,
                 fontproperties=FontProperties(family=_CJK))
    ax.tick_params(labelsize=8)


def render_static_png(df: pd.DataFrame, interpretation: dict,
                      out_path: str, keyword: str, marketplace: str,
                      fetched_at: str, our_asin: str | None = None,
                      credits: int | None = None,
                      image_cache_dir: str | None = None) -> str:
    """渲染 1920×1080 报告图。df 需含 zone 列（zoning.classify_zones 输出）。"""
    plt.rcParams["font.sans-serif"] = [_CJK]
    plt.rcParams["axes.unicode_minus"] = False

    fig = plt.figure(figsize=(CANVAS_W / 100, CANVAS_H / 100), dpi=100)
    gs = fig.add_gridspec(5, 12, height_ratios=[0.5, 4.2, 1.0, 0.6, 0.6],
                          hspace=0.35, wspace=0.4,
                          left=0.06, right=0.97, top=0.93, bottom=0.07)

    # ── Header ──────────────────────────────────────────────
    axh = fig.add_subplot(gs[0, :])
    axh.axis("off")
    title = f"MOD 报告 — {keyword} — {fetched_at[:10]}"
    axh.text(0, 0.5, title, fontsize=17, fontweight="bold",
             fontproperties=FontProperties(family=_CJK), va="center")
    sub = f"数据源 {marketplace}（Rainforest API）｜ N={len(df)}"
    if credits is not None:
        sub += f" ｜ credits≈{credits}"
    axh.text(1, 0.5, sub, fontsize=11, color="#555555",
             fontproperties=FontProperties(family=_CJK), va="center", ha="right")

    # ── 气泡矩阵主图 ────────────────────────────────────────
    ax = fig.add_subplot(gs[1, :])
    prices = df["current_price"].dropna()
    p25, p50, p75 = prices.quantile([0.25, 0.5, 0.75])
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("当前价格 $（对数）", fontsize=12, fontproperties=FontProperties(family=_CJK))
    ax.set_ylabel("月销估算（对数）", fontsize=12, fontproperties=FontProperties(family=_CJK))
    ax.grid(True, which="both", linestyle=":", alpha=0.4)
    ax.tick_params(labelsize=9)

    # 4 区背景色带（按 zone 描点区着色太复杂，v1 用散点边框色 + 图例 + 区域标签）
    zone_counts = df["zone"].value_counts().to_dict()
    legend_handles = []
    import matplotlib.patches as mpatches

    for zone in ("price_gap", "value_opportunity", "demand_heat", "red_ocean"):
        legend_handles.append(mpatches.Patch(color=ZONE_COLORS[zone], alpha=0.6,
                                             label=f"{ZONE_LABELS[zone]} ({zone_counts.get(zone, 0)})"))

    max_sales = df["est_monthly_sales"].fillna(0).max() or 1
    for _, row in df.iterrows():
        price, sales = row.get("current_price"), row.get("est_monthly_sales")
        if price is None or price != price or price <= 0:  # NaN 自不等
            continue
        if sales is None or sales != sales or sales <= 0:
            sales = max_sales * 0.05  # 无销量数据的小气泡
        zone = row.get("zone") or "neutral"
        color = ZONE_COLORS.get(zone, "#9E9E9E")
        is_ours = our_asin and row.get("asin") == our_asin
        # 缩略图气泡（优先本地缓存）
        img = _load_thumb(row.get("main_image_url"), cache_dir=image_cache_dir,
                          asin=row.get("asin"))
        im = OffsetImage(img, zoom=1.0)
        ab = AnnotationBbox(im, (price, sales), frameon=True,
                            bboxprops=dict(boxstyle="round,pad=0.15",
                                           facecolor="white",
                                           edgecolor="#FFD700" if is_ours else color,
                                           linewidth=2.5 if is_ours else 1.5))
        ax.add_artist(ab)
        # 价格标签
        ax.annotate(f"${row['current_price']:.2f}",
                    (price, sales), textcoords="offset points", xytext=(0, -18),
                    ha="center", fontsize=8.5, color="#222222")
        if is_ours:
            ax.annotate("★ 我方", (price, sales), textcoords="offset points",
                        xytext=(0, 26), ha="center", fontsize=11, color="#B8860B",
                        fontweight="bold", fontproperties=FontProperties(family=_CJK))

    ax.legend(handles=legend_handles, loc="lower right", fontsize=10,
              prop=FontProperties(family=_CJK), framealpha=0.9)

    # ── 4 区解读卡片 ────────────────────────────────────────
    zones_order = ("price_gap", "value_opportunity", "demand_heat", "red_ocean")
    for i, zone in enumerate(zones_order):
        axc = fig.add_subplot(gs[2, i * 3:(i + 1) * 3])
        axc.axis("off")
        txt = interpretation.get(zone, "—")
        axc.text(0.5, 0.62, ZONE_LABELS[zone], ha="center", fontsize=12,
                 fontweight="bold", color=ZONE_COLORS[zone],
                 fontproperties=FontProperties(family=_CJK))
        axc.text(0.5, 0.35, txt, ha="center", va="center", fontsize=10.5,
                 wrap=True, color="#333333",
                 fontproperties=FontProperties(family=_CJK))

    # ── 底部：价格直方图 + 溯源 ─────────────────────────────
    axh2 = fig.add_subplot(gs[3, :8])
    _price_hist(axh2, list(prices), p25, p50, p75)

    axsrc = fig.add_subplot(gs[3, 8:])
    axsrc.axis("off")
    verdict = interpretation.get("verdict", "")
    axsrc.text(0.02, 0.6, f"我方定位：{verdict}", fontsize=12, color="#0D47A1",
               fontproperties=FontProperties(family=_CJK), wrap=True)
    axsrc.text(0.02, 0.15, f"数据源：Rainforest API @ {fetched_at} ｜ 月销估算为官方 recent_sales 口径解析",
               fontsize=9, color="#777777", fontproperties=FontProperties(family=_CJK))

    fig.savefig(out_path, dpi=100)
    plt.close(fig)
    return out_path


def render_matrix_only(df: pd.DataFrame, out_path: str,
                       our_asin: str | None = None,
                       image_cache_dir: str | None = None,
                       width_px: int = 3840, height_px: int = 1800) -> str:
    """仅渲染气泡矩阵（透明背景，供海报合成叠加）。3840×1800（2x）。"""
    plt.rcParams["font.sans-serif"] = [_CJK]
    plt.rcParams["axes.unicode_minus"] = False
    fig = plt.figure(figsize=(width_px / 100, height_px / 100), dpi=100)
    ax = fig.add_axes([0.04, 0.06, 0.92, 0.86])

    prices = df["current_price"].dropna()
    if not prices.empty:
        p25, p50, p75 = prices.quantile([0.25, 0.5, 0.75])
        ax.axvspan(p50, p75, color="#2E7D32", alpha=0.05)
        ax.axvspan(p50 * 0.9, p50 * 1.1, color="#C62828", alpha=0.05)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("当前价格 $（对数）", fontsize=22, fontproperties=FontProperties(family=_CJK))
    ax.set_ylabel("月销估算（对数）", fontsize=22, fontproperties=FontProperties(family=_CJK))
    ax.grid(True, which="both", linestyle=":", alpha=0.35)
    ax.tick_params(labelsize=16)

    zone_counts = df["zone"].value_counts().to_dict()
    import matplotlib.patches as mpatches
    legend_handles = []
    for zone in ("price_gap", "value_opportunity", "demand_heat", "red_ocean"):
        legend_handles.append(mpatches.Patch(color=ZONE_COLORS[zone], alpha=0.6,
                                             label=f"{ZONE_LABELS[zone]} ({zone_counts.get(zone, 0)})"))

    max_sales = df["est_monthly_sales"].fillna(0).max() or 1
    thumb_size = 110
    for _, row in df.iterrows():
        price, sales = row.get("current_price"), row.get("est_monthly_sales")
        if price is None or price != price or price <= 0:
            continue
        if sales is None or sales != sales or sales <= 0:
            sales = max_sales * 0.05
        zone = row.get("zone") or "neutral"
        color = ZONE_COLORS.get(zone, "#9E9E9E")
        is_ours = our_asin and row.get("asin") == our_asin
        img = _load_thumb(row.get("main_image_url"), size=thumb_size,
                          cache_dir=image_cache_dir, asin=row.get("asin"))
        im = OffsetImage(img, zoom=1.0)
        ab = AnnotationBbox(im, (price, sales), frameon=True,
                            bboxprops=dict(boxstyle="round,pad=0.18",
                                           facecolor="white",
                                           edgecolor="#FFD700" if is_ours else color,
                                           linewidth=4 if is_ours else 2.2))
        ax.add_artist(ab)
        ax.annotate(f"${row['current_price']:.2f}", (price, sales),
                    textcoords="offset points", xytext=(0, -30), ha="center",
                    fontsize=15, color="#222222")
        if is_ours:
            ax.annotate("★ 我方", (price, sales), textcoords="offset points",
                        xytext=(0, 46), ha="center", fontsize=20, color="#B8860B",
                        fontweight="bold", fontproperties=FontProperties(family=_CJK))

    ax.legend(handles=legend_handles, loc="lower right", fontsize=18,
              prop=FontProperties(family=_CJK), framealpha=0.92)
    fig.savefig(out_path, dpi=100, transparent=True)
    plt.close(fig)
    return out_path
