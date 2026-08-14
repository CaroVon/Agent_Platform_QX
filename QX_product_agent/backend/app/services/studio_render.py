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


def render_slides_html(package: dict[str, Any]) -> str:
    """完整资产包 → 16:9 幻灯片 HTML 文档。"""
    topic = _escape(package.get("idea", "Product Studio"))
    slides = (package.get("presentation") or {}).get("slides") or []
    if not slides:
        return _render_empty_document(topic)

    body = []
    for slide in slides:
        layout = _LAYOUT_ALIASES.get(slide.get("layout_type", "default"), "bullets")
        blocks = "".join(_render_block(b) for b in slide.get("blocks", []))
        title = _escape(slide.get("title", ""))
        subtitle = _escape(slide.get("subtitle", "") or "")
        subtitle_html = f'<p class="slide-subtitle">{subtitle}</p>' if subtitle else ""
        body.append(
            f'<section class="slide layout-{layout}">'
            f'<h2 class="slide-title">{title}</h2>{subtitle_html}'
            f'<div class="slide-body">{blocks}</div></section>'
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
  width: 1440px; height: 810px; padding: 90px 110px;
  page-break-after: always; overflow: hidden;
  background: linear-gradient(160deg, #f8fafc 0%, #eef2ff 100%);
}}
.slide:last-child {{ page-break-after: auto; }}
.slide-title {{ margin: 0; font-size: 54px; color: #0f172a; letter-spacing: 0.5px; }}
.slide-subtitle {{ margin: 14px 0 0; font-size: 26px; color: #475569; }}
.slide-body {{ margin-top: 48px; }}
.layout-cover {{ display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; }}
.layout-cover .slide-title {{ font-size: 76px; }}
.layout-closing {{ display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; }}
.layout-section_header {{ display: flex; flex-direction: column; justify-content: center; }}
.layout-section_header .slide-title {{ font-size: 64px; }}
.layout-two_column .slide-body {{ display: grid; grid-template-columns: 1fr 1fr; gap: 48px; }}
.block-title {{ margin: 0 0 20px; font-size: 64px; color: #0f172a; }}
.block-subtitle {{ margin: 0; font-size: 30px; color: #64748b; }}
.block-text {{ font-size: 28px; line-height: 1.6; color: #1e293b; }}
.block-bullets {{ margin: 0; padding-left: 40px; }}
.block-bullets li {{ font-size: 30px; line-height: 1.75; color: #1e293b; margin-bottom: 10px; }}
.block-quote {{ margin: 0; padding: 36px 44px; border-left: 8px solid #6366f1;
  background: #ffffffcc; border-radius: 16px; font-size: 32px; color: #334155; }}
.block-metric {{ display: inline-block; margin-right: 60px; text-align: center; }}
.metric-value {{ font-size: 72px; font-weight: 700; color: #4f46e5; }}
.metric-label {{ margin-top: 10px; font-size: 26px; color: #64748b; }}
.block-table {{ width: 100%; border-collapse: collapse; font-size: 26px; }}
.block-table th {{ background: #4f46e5; color: #fff; padding: 14px 18px; text-align: left; }}
.block-table td {{ padding: 14px 18px; border-bottom: 1px solid #e2e8f0; color: #1e293b; }}
.block-image-placeholder {{ display: flex; align-items: center; justify-content: center;
  height: 380px; border: 2px dashed #c7d2fe; border-radius: 20px;
  background: #eef2ff88; color: #6366f1; font-size: 30px; }}
.layout-timeline .block-bullets {{ list-style: none; padding-left: 0; }}
.layout-timeline .block-bullets li {{ border-left: 4px solid #6366f1; padding-left: 24px; }}
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
