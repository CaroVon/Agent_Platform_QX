"""
============================================================
Studio 渲染服务 —— Slide JSON Schema → 结构化 HTML → PDF
============================================================

渲染分工（对齐迁移目标）:
  - AI（Presentation Agent）生成: 内容结构 + layout_type + visual_metadata
  - 本层控制: 字体、间距、版式模板（typography/spacing/component style）

这是"Markdown → PDF"到"Slide JSON → Renderer → PPT/PDF"的升级实现。
"""

from __future__ import annotations

import html
from typing import Any

_LAYOUT_ALIASES = {
    "cover": "cover",
    "section_header": "section_header",
    "two_column": "two_column",
    "bullets": "bullets",
    "timeline": "timeline",
    "matrix": "matrix",
    "image_hero": "bullets",
    "quote": "quote",
    "closing": "closing",
    "default": "bullets",
}


def _escape(text: str) -> str:
    return html.escape(text or "")


def _render_block(block: dict[str, Any]) -> str:
    """单个内容块 → HTML（block_type 决定结构，样式由 CSS 控制）。"""
    block_type = block.get("block_type", "text")
    content = _escape(block.get("content", ""))
    meta = block.get("meta") or {}

    if block_type == "title":
        return f'<h1 class="block-title">{content}</h1>'
    if block_type == "subtitle":
        return f'<p class="block-subtitle">{content}</p>'
    if block_type == "bullets":
        items = [line.strip("•- ") for line in content.splitlines() if line.strip()]
        if not items:
            items = [content]
        lis = "".join(f"<li>{_escape(item)}</li>" for item in items)
        return f'<ul class="block-bullets">{lis}</ul>'
    if block_type == "metric":
        value = _escape(meta.get("value", content))
        label = _escape(meta.get("label", ""))
        return (
            f'<div class="block-metric"><div class="metric-value">{value}</div>'
            f'<div class="metric-label">{label}</div></div>'
        )
    if block_type == "quote":
        return f'<blockquote class="block-quote">{content}</blockquote>'
    if block_type == "table":
        columns: list[str] = meta.get("columns") or []
        rows: list[list[str]] = meta.get("rows") or []
        if not columns and rows:
            columns = [f"列{i + 1}" for i in range(len(rows[0]))]
        head = "".join(f"<th>{_escape(c)}</th>" for c in columns)
        body = "".join(
            "<tr>" + "".join(f"<td>{_escape(c)}</td>" for c in row) + "</tr>"
            for row in rows
        )
        return (
            f'<table class="block-table"><thead><tr>{head}</tr></thead>'
            f"<tbody>{body}</tbody></table>"
        )
    if block_type == "image":
        alt = _escape(meta.get("alt", "概念图"))
        return f'<div class="block-image-placeholder">{alt}</div>'
    return f'<p class="block-text">{content}</p>'


def _estimate_density(blocks: list[dict[str, Any]]) -> str:
    """内容密度估算 → CSS class（WeasyPrint 无法测量溢出，用字符数分级缩字号）。

    P0 完整度策略：
      - 密度分级：估算内容量，compact 级整体缩小字号，降低溢出概率
      - 自动分页兜底：真溢出时不截断（.slide 不设固定高度/overflow），
        内容自然流到下一页 —— 内容永不丢失
    """
    chars = sum(len(b.get("content", "") or "") for b in blocks)
    bullet_lines = sum(
        len([ln for ln in (b.get("content", "") or "").splitlines() if ln.strip()])
        for b in blocks
        if b.get("block_type") in ("bullets", "text")
    )
    score = chars + bullet_lines * 6
    if score >= 380:
        return "density-compact"
    if score >= 240:
        return "density-mid"
    return ""


def render_slides_html(package: dict[str, Any]) -> str:
    """完整资产包 → 16:9 幻灯片 HTML 文档（WeasyPrint 兼容布局）。"""
    topic = _escape(package.get("idea", "Product Studio"))
    slides = (package.get("presentation") or {}).get("slides") or []
    if not slides:
        return _render_empty_document(topic)

    body = []
    for slide in slides:
        layout = _LAYOUT_ALIASES.get(slide.get("layout_type", "default"), "bullets")
        blocks = slide.get("blocks", [])
        density = _estimate_density(blocks)
        title = _escape(slide.get("title", ""))
        subtitle = _escape(slide.get("subtitle", "") or "")
        subtitle_html = f'<p class="slide-subtitle">{subtitle}</p>' if subtitle else ""

        # two_column：块列表对半切分，各入一栏（WeasyPrint 无 grid，用 table-cell）
        if layout == "two_column":
            half = (len(blocks) + 1) // 2
            left = "".join(_render_block(b) for b in blocks[:half])
            right = "".join(_render_block(b) for b in blocks[half:])
            blocks_html = (
                f'<div class="two-col-row"><div class="col">{"".join(left)}</div>'
                f'<div class="col">{"".join(right)}</div></div>'
            )
        else:
            blocks_html = "".join(_render_block(b) for b in blocks)

        body.append(
            f'<section class="slide layout-{layout} {density}">'
            f'<h2 class="slide-title">{title}</h2>{subtitle_html}'
            f'<div class="slide-body">{blocks_html}</div></section>'
        )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>
@page {{ size: 1440px 810px; margin: 0; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif; }}
.slide {{
  width: 1440px; min-height: 760px; padding: 80px 100px 70px;
  page-break-after: always;
  background: linear-gradient(160deg, #f8fafc 0%, #eef2ff 100%);
}}
.slide:last-child {{ page-break-after: auto; }}
.slide-title {{ margin: 0; font-size: 50px; color: #0f172a; letter-spacing: 0.5px; }}
.slide-subtitle {{ margin: 14px 0 0; font-size: 25px; color: #475569; }}
.slide-body {{ margin-top: 42px; }}
.layout-cover {{ min-height: 810px; padding-top: 250px; text-align: center; }}
.layout-cover .slide-title {{ font-size: 72px; }}
.layout-closing {{ min-height: 810px; padding-top: 260px; text-align: center; }}
.layout-section_header {{ padding-top: 260px; }}
.layout-section_header .slide-title {{ font-size: 62px; }}
.two-col-row {{ display: table; width: 100%; border-spacing: 40px 0; margin: -20px 0; }}
.two-col-row .col {{ display: table-cell; width: 50%; vertical-align: top; }}
.block-title {{ margin: 0 0 18px; font-size: 60px; color: #0f172a; }}
.block-subtitle {{ margin: 0; font-size: 28px; color: #64748b; }}
.block-text {{ font-size: 26px; line-height: 1.55; color: #1e293b; }}
.block-bullets {{ margin: 0; padding-left: 36px; }}
.block-bullets li {{ font-size: 28px; line-height: 1.7; color: #1e293b; margin-bottom: 9px; }}
.block-quote {{ margin: 0; padding: 32px 40px; border-left: 8px solid #6366f1;
  background: #ffffffcc; border-radius: 14px; font-size: 30px; color: #334155; }}
.block-metric {{ display: inline-block; margin-right: 52px; text-align: center; }}
.metric-value {{ font-size: 68px; font-weight: 700; color: #4f46e5; }}
.metric-label {{ margin-top: 8px; font-size: 24px; color: #64748b; }}
.block-table {{ width: 100%; border-collapse: collapse; font-size: 24px; }}
.block-table th {{ background: #4f46e5; color: #fff; padding: 12px 16px; text-align: left; }}
.block-table td {{ padding: 12px 16px; border-bottom: 1px solid #e2e8f0; color: #1e293b; }}
.block-image-placeholder {{ display: flex; align-items: center; justify-content: center;
  height: 340px; border: 2px dashed #c7d2fe; border-radius: 18px;
  background: #eef2ff88; color: #6366f1; font-size: 28px; }}
.layout-timeline .block-bullets {{ list-style: none; padding-left: 0; }}
.layout-timeline .block-bullets li {{ border-left: 4px solid #6366f1; padding-left: 22px; }}
/* 密度分级字号（P0 完整度策略） */
.density-mid .slide-body {{ font-size: 0.9em; }}
.density-compact .slide-body {{ font-size: 0.78em; }}
</style>
</head>
<body>{''.join(body)}</body>
</html>"""


def _render_empty_document(topic: str) -> str:
    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"></head>
<body><section class="slide layout-cover"><h2>{topic}</h2></section></body></html>"""


def slides_to_pdf(package: dict[str, Any], output_path: str) -> str:
    """资产包 → PPT 风格 16:9 PDF（WeasyPrint）。"""
    from weasyprint import HTML  # 延迟导入，避免冷启动开销

    document = render_slides_html(package)
    HTML(string=document, base_url=".").write_pdf(output_path)
    return output_path
