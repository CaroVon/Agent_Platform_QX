"""交互报告图 —— 单文件 ECharts HTML（独立可打开）。

- 内嵌本地 echarts.min.js（QX frontend node_modules）
- 气泡矩阵：X=log(price) Y=log(est_monthly_sales)，气泡=主图缩略图(base64 80×80 JPEG)
- 4 区 markArea + 解读卡片（可折叠）
- hover tooltip：标题/ASIN/价格/评分/评论/月销/BSR/链接
"""
from __future__ import annotations

import base64
import io
import json
import logging
import os

import requests
from PIL import Image

from amazon_matrix_mod.zoning import ZONE_LABELS

log = logging.getLogger(__name__)

ZONE_COLORS = {
    "price_gap": "#2E7D32", "value_opportunity": "#1565C0",
    "demand_heat": "#F9A825", "red_ocean": "#C62828", "neutral": "#9E9E9E",
}


def _echarts_js() -> str:
    candidates = (
        os.environ.get("ECHARTS_MIN_JS", ""),
        "/home/administrator/dev/agents/QX_product_agent/frontend/node_modules/echarts/dist/echarts.min.js",
    )
    for c in candidates:
        if c and os.path.isfile(c):
            return open(c, encoding="utf-8").read()
    # 最后回退 CDN（独立运行时需要网络）
    return '<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>'


def _thumb_b64(url: str, size: int = 80, quality: int = 70,
               cache_dir: str | None = None, asin: str | None = None) -> str:
    """主图 → base64 JPEG（优先本地缓存；失败返回 1px 占位）。"""
    try:
        img = None
        from amazon_matrix_mod.storage import image_failed
        if cache_dir and asin:
            if image_failed(cache_dir, asin):
                return ""
            p = os.path.join(cache_dir, "image_cache", f"{asin}.jpg")
            if os.path.isfile(p) and os.path.getsize(p) > 1000:
                img = Image.open(p).convert("RGB")
        if img is None and url:
            r = requests.get(url, timeout=(2, 5))
            img = Image.open(io.BytesIO(r.content)).convert("RGB")
        if img is None:
            return ""
        img = img.resize((size, size), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=quality)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception as exc:  # noqa: BLE001
        log.warning("缩略图失败 %s: %s", url, exc)
        return ""


def _scatter_data(df, our_asin: str | None, cache_dir: str | None = None) -> tuple[list[dict], list[dict]]:
    """ECharts 散点序列 + markArea 区域。"""
    series = []
    areas = []
    max_sales = df["est_monthly_sales"].fillna(0).max() or 1
    for _, r in df.iterrows():
        price = r.get("current_price")
        sales = r.get("est_monthly_sales")
        if price is None or price != price or price <= 0:  # NaN 自不等
            continue
        if sales is None or sales != sales or sales <= 0:
            sales = max_sales * 0.05
        zone = r.get("zone") or "neutral"
        is_ours = bool(our_asin and r.get("asin") == our_asin)
        b64 = _thumb_b64(r.get("main_image_url"), cache_dir=cache_dir, asin=r.get("asin"))
        series.append({
            "name": ZONE_LABELS.get(zone, zone),
            "value": [round(float(price), 2), int(sales), r.get("asin")],
            "symbol": "image://data:image/jpeg;base64," + b64 if b64 else "circle",
            "symbolSize": 26 if is_ours else 22,
            "itemStyle": {"borderColor": "#FFD700" if is_ours else ZONE_COLORS.get(zone, "#999"),
                          "borderWidth": 3 if is_ours else 1.5,
                          "color": ZONE_COLORS.get(zone, "#999")},
            "asin": r.get("asin"), "title": (r.get("title") or "")[:80],
            "price": r.get("current_price"), "rating": r.get("rating"),
            "review_count": r.get("review_count"),
            "est_monthly_sales": r.get("est_monthly_sales"),
            "bsr": r.get("bsr"), "zone": zone,
            "is_ours": is_ours, "url": r.get("url") or "",
        })
    for zone in ("price_gap", "value_opportunity", "demand_heat", "red_ocean"):
        sub = df[df["zone"] == zone]
        if sub.empty:
            continue
        areas.append({
            "name": ZONE_LABELS[zone],
            "itemStyle": {"color": ZONE_COLORS[zone], "opacity": 0.08},
            "label": {"show": True, "position": "insideTop", "color": ZONE_COLORS[zone],
                      "fontSize": 13, "formatter": ZONE_LABELS[zone]},
            "data": [[{"xAxis": "min", "yAxis": "min"},
                      {"xAxis": "max", "yAxis": "max"}]],
        })
    return series, areas


def render_interactive_html(df, interpretation: dict, out_path: str,
                            keyword: str, marketplace: str, fetched_at: str,
                            our_asin: str | None = None,
                            image_cache_dir: str | None = None) -> str:
    series, areas = _scatter_data(df, our_asin, cache_dir=image_cache_dir)
    js = _echarts_js()
    interp = json.dumps(interpretation, ensure_ascii=False)
    zone_labels = json.dumps(ZONE_LABELS, ensure_ascii=False)
    series_json = json.dumps(series, ensure_ascii=False)
    areas_json = json.dumps(areas, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>MOD 报告 — {keyword}</title>
{js}
<style>
 body {{ margin:0; font-family:"Noto Sans CJK SC","WenQuanYi Zen Hei",sans-serif; background:#f5f6f8; }}
 .wrap {{ max-width:1280px; margin:0 auto; padding:16px; }}
 h1 {{ font-size:20px; color:#12355B; margin:8px 0 2px; }}
 .sub {{ color:#666; font-size:12px; margin-bottom:10px; }}
 #chart {{ width:100%; height:640px; background:#fff; border-radius:10px; box-shadow:0 2px 10px rgba(0,0,0,.06); }}
 .cards {{ display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-top:12px; }}
 .card {{ background:#fff; border-radius:10px; padding:12px 14px; box-shadow:0 2px 8px rgba(0,0,0,.05); border-top:3px solid #ccc; }}
 .card b {{ font-size:14px; }}
 .card p {{ margin:6px 0 0; font-size:13px; color:#333; line-height:1.6; }}
 .v {{ background:#fff; border-radius:10px; padding:10px 14px; margin-top:10px; font-size:14px; color:#0D47A1; box-shadow:0 2px 8px rgba(0,0,0,.05); }}
 .src {{ color:#888; font-size:11px; margin-top:10px; }}
</style></head><body><div class="wrap">
<h1>MOD 报告 — {keyword}</h1>
<div class="sub">数据源 {marketplace}（Rainforest API）｜ N={len(df)} ｜ 抓取时间 {fetched_at}｜ 气泡大小=月销估算（对数轴）</div>
<div id="chart"></div>
<div class="cards" id="cards"></div>
<div class="v" id="verdict"></div>
<div class="src">数据源：Rainforest API @ {fetched_at} ｜ 月销估算为 Amazon 官方 "bought in past month" 口径解析（recent_sales）</div>
</div>
<script>
const SERIES = {series_json};
const AREAS = {areas_json};
const INTERP = {interp};
const ZONES = {zone_labels};
const zoneColor = {{price_gap:'#2E7D32',value_opportunity:'#1565C0',demand_heat:'#F9A825',red_ocean:'#C62828'}};
const chart = echarts.init(document.getElementById('chart'));
chart.setOption({{
  tooltip: {{
    formatter: function(p) {{
      const d = p.data;
      if (!d || !d.asin) return '';
      return '<b>' + d.title + '</b><br/>ASIN: ' + d.asin +
        '<br/>价格: $' + (d.price ?? '-') + ' ｜ 评分: ' + (d.rating ?? '-') +
        '<br/>评论数: ' + (d.review_count ?? '-') + ' ｜ 月销估算: ' + (d.est_monthly_sales ?? '-') +
        '<br/>BSR: ' + (d.bsr ?? '-') + ' ｜ 分区: ' + (ZONES[d.zone] ?? d.zone) +
        (d.is_ours ? '<br/><b>★ 我方产品</b>' : '') +
        (d.url ? '<br/><a href="' + d.url + '" target="_blank">查看商品页 →</a>' : '');
    }}
  }},
  legend: {{ data: Object.values(ZONES).filter(z => SERIES.some(s => s.name === z)), top: 6 }},
  grid: {{ left: 70, right: 40, top: 48, bottom: 56 }},
  xAxis: {{ type: 'log', name: '价格 $（对数）', min: (v) => Math.max(1, v.min * 0.6) }},
  yAxis: {{ type: 'log', name: '月销估算（对数）', min: (v) => Math.max(1, v.min * 0.6) }},
  series: [{{
    type: 'scatter', data: SERIES, symbolSize: 24,
    markArea: {{ silent: true, data: AREAS }},
    emphasis: {{ focus: 'series', itemStyle: {{ shadowBlur: 12, shadowColor: 'rgba(0,0,0,.4)' }} }},
  }}]
}});
window.addEventListener('resize', () => chart.resize());
const cards = document.getElementById('cards');
for (const z of ['price_gap','value_opportunity','demand_heat','red_ocean']) {{
  const c = document.createElement('div'); c.className = 'card';
  c.style.borderTopColor = zoneColor[z];
  c.innerHTML = '<b style="color:' + zoneColor[z] + '">' + ZONES[z] + '</b><p>' + (INTERP[z] || '—') + '</p>';
  cards.appendChild(c);
}}
document.getElementById('verdict').textContent = '我方定位：' + (INTERP.verdict || '—');
</script></body></html>"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path
