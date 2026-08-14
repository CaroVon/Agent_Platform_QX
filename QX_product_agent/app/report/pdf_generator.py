"""
============================================================
横版 PPT 风格 PDF 生成器 —— 行业级双栏瀑布流排版
============================================================

将 Markdown 分析报告转化为 16:9 横版路演级 PDF:
  - 真正 16:9 横版页面 (320mm × 180mm，比例 1.778:1)
  - 杂志级沉浸式封面 (保留全屏概念图 + 暗色遮罩)
  - 🆕 顶级咨询公司范式：引入 CSS Columns 两栏瀑布流
  - 🆕 核心论点置顶：Blockquote 转化为高亮 Summary 卡片
  - 🆕 数据可视化强化：引入专业表格斑马线与品牌色顶条
"""

import logging
import os
import re

import markdown2
from weasyprint import HTML

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════
# 品牌色彩系统 (融合咨询范式与原有设定)
# ══════════════════════════════════════════════════════════
COLOR = {
    "bg_dark":     "#0f1117",   # 深空灰封面背景
    "bg_body":     "#f5f6f8",   # 正文页极淡灰白底
    "overlay":     "rgba(0, 0, 0, 0.55)",  # 封面暗色遮罩
    "accent":      "#2d7cf6",   # 科技亮蓝 (点缀色)
    "accent_dim":  "#1a5dc4",   # 深蓝 (页眉分割线)
    "h2_color":    "#1a1f2e",   # 标题深色
    "body_text":   "#2c3038",   # 正文色
    "muted":       "#8899bb",   # 次要文字
    "divider":     "#dce3ed",   # 细分割线
    "white":       "#ffffff",
    "header_bg":   "#0d1117",   # 页眉深色条 (正文页)
}


# ══════════════════════════════════════════════════════════
# Helper：将 topic 安全化为文件名 / 标题片段
# ══════════════════════════════════════════════════════════
def _safe_topic(topic: str) -> str:
    """移除文件名非法字符，用于图片路径拼接。"""
    return re.sub(r'[\\/:*?"<>|]', '_', topic)


# ══════════════════════════════════════════════════════════
# 主函数
# ══════════════════════════════════════════════════════════
def markdown_to_pdf(md_path: str, pdf_path: str, cover_image: str = ""):
    """
    将 Markdown 分析报告渲染为横版 PPT 风格 PDF。
    """
    logger.info("横版路演级 PDF 渲染启动...")

    # ── 1. 读取 Markdown ──────────────────────────────────
    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    # ── 2. 提取标题 + 清洗 ────────────────────────────────
    title_match = re.search(r"^#\s+(.+)", md_content, re.MULTILINE)
    report_title = title_match.group(1).strip() if title_match else "行业深度研究报告"

    # 移除 H1 (封面已承载)，保留正文用于幻灯片内容
    clean_md = re.sub(r"^#\s+.+", "", md_content, count=1).strip()

    # 移除 emoji 字符（WeasyPrint 字体不支持，会渲染为 .notdef 方框）
    clean_md = re.sub(
        r'[\U0001F300-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF'
        r'\U00002600-\U000027BF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF'
        r'\U0001F900-\U0001F95F\U00002B50\U0001F004\U0001F0CF]',
        '', clean_md
    )

    # ── 3. Markdown → HTML ────────────────────────────────
    html_body = markdown2.markdown(
        clean_md,
        extras=["tables", "fenced-code-blocks", "footnotes", "strike"],
    )

    # ── 4. 封面图逻辑 ─────────────────────────────────────
    has_cover_bg = bool(cover_image) and os.path.isfile(cover_image)
    if has_cover_bg:
        abs_img = os.path.abspath(cover_image).replace("\\", "/")
        logger.info("封面背景图: %s", abs_img)
    else:
        if cover_image:
            logger.info("封面图未找到 (%s)，使用 CSS 渐变兜底", cover_image)
        else:
            logger.info("未提供封面图，使用 CSS 高级渐变兜底封面")

    # ── 5. 构建 PPT 风格 HTML + CSS ───────────────────────
    premium_html = _build_html(report_title, html_body, has_cover_bg, cover_image)

    # ── 6. 写入临时 HTML → WeasyPrint → PDF ───────────────
    temp_html_path = md_path.replace(".md", ".html")
    with open(temp_html_path, "w", encoding="utf-8") as f:
        f.write(premium_html)

    # 确保输出目录存在（WeasyPrint 不会自动创建）
    pdf_dir = os.path.dirname(pdf_path)
    if pdf_dir:
        os.makedirs(pdf_dir, exist_ok=True)

    HTML(filename=temp_html_path).write_pdf(pdf_path)
    logger.info("横版路演 PDF 已生成: %s", pdf_path)


# ══════════════════════════════════════════════════════════
# HTML 骨架 + 完整 CSS 构建
# ══════════════════════════════════════════════════════════
def _build_html(
    title: str, body_html: str, has_bg: bool, img_path: str
) -> str:
    """
    组装完整的 HTML 文档。融合了麦肯锡级双栏排版与原有沉浸式封面。
    """
    cover_html = _build_cover(title, has_bg, img_path)
    # 移除被带入正文的 h1 标题
    body_html = re.sub(r"<h1[^>]*>.*?</h1>", "", body_html, count=1, flags=re.DOTALL)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>
    /* ========================================================
    【页面基础】—— 真正 16:9 横版 = 320mm × 180mm
    ======================================================== */
    @page {{
        size: 320mm 180mm;
        margin: 18mm 20mm 15mm 20mm;
        background-color: #F8F9FA;

        @top-left {{
            content: "CONFIDENTIAL · 产品深度研究路演方案";
            font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
            font-size: 8pt;
            color: #868E96;
            letter-spacing: 1px;
        }}
        @top-center {{
            content: "";
            border-bottom: 2px solid #0052CC;
            width: 100%;
        }}
        @bottom-right {{
            content: counter(page);
            font-family: 'Helvetica Neue', Arial, sans-serif;
            font-size: 14pt;
            font-weight: bold;
            color: #0052CC;
            padding-top: 4mm;
        }}
    }}

    @page cover {{
        size: 320mm 180mm;
        margin: 0;
        background-color: {COLOR["bg_dark"]};
        @top-left   {{ content: none; }}
        @top-right  {{ content: none; }}
        @top-center {{ content: none; border-bottom: none; }}
        @bottom-left  {{ content: none; }}
        @bottom-right {{ content: none; }}
    }}

    /* ========================================================
    【全局重置与字体】
    ======================================================== */
    *, *::before, *::after {{ box-sizing: border-box; }}

    body {{
        font-family: 'PingFang SC', 'Microsoft YaHei', 'Noto Sans CJK SC',
                     'WenQuanYi Zen Hei', 'Helvetica Neue', sans-serif;
        color: #212529;
        line-height: 1.7;
        font-size: 13pt;
        margin: 0;
        padding: 0;
    }}

    /* ========================================================
    【封面排版】—— 沉浸式杂志开屏
    ======================================================== */
    .cover {{
        display: block;
        position: relative;
        width: 100%;
        height: 180mm;
        page: cover;
        page-break-after: always;
        overflow: hidden;
        color: {COLOR["white"]};
    }}

    .cover-bg-img {{
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        z-index: 0;
        object-fit: cover;
    }}

    .cover-overlay {{
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        z-index: 1;
        background-color: {COLOR["overlay"]};
    }}

    .cover-gradient-bg {{
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        z-index: 0;
        background:
            linear-gradient(135deg, #0d1117 0%, #0f1a2e 30%, #0d1525 60%, #0a0e14 100%);
    }}

    .cover-content {{
        position: relative;
        z-index: 2;
        padding: 24mm 28mm 0 28mm;
        height: 100%;
    }}

    .cover-tag {{
        display: inline-block;
        font-size: 9pt;
        font-weight: 500;
        letter-spacing: 3px;
        text-transform: uppercase;
        color: {COLOR["accent"]};
        border: 1.2px solid {COLOR["accent"]};
        padding: 4px 12px;
        margin-bottom: 14mm;
    }}

    .cover-title {{
        font-size: 34pt;
        font-weight: 700;
        line-height: 1.2;
        color: {COLOR["white"]};
        margin-bottom: 6mm;
        letter-spacing: 2px;
    }}

    .cover-divider {{
        width: 45mm;
        height: 4px;
        background-color: {COLOR["accent"]};
        margin-bottom: 10mm;
    }}

    .cover-subtitle {{
        font-size: 14pt;
        color: #bcc8e0;
        letter-spacing: 1px;
        margin-bottom: 2mm;
    }}

    .cover-footer {{
        position: absolute;
        bottom: 14mm;
        left: 28mm;
        font-size: 9pt;
        color: {COLOR["muted"]};
        line-height: 2;
        z-index: 2;
    }}

    /* ========================================================
    【正文幻灯片架构：行业级分栏瀑布流】
    ======================================================== */
    .slide-deck {{
        display: block;
        column-count: 2;
        column-gap: 16mm;
        column-fill: auto;
        max-width: 100%;
    }}

    /* 章节大标题：跨栏展示 */
    h2 {{
        column-span: all;
        font-size: 24pt;
        font-weight: 700;
        color: #0B2447;
        margin-top: 0;
        margin-bottom: 8mm;
        line-height: 1.2;
        padding-bottom: 4mm;
        border-bottom: 2px solid #E9ECEF;
        page-break-before: always;
        page-break-after: avoid;
    }}

    /* 核心观点框：咨询风数据卡片 */
    blockquote {{
        column-span: all;
        background-color: #F4F7FA;
        border-left: 6px solid #2D7CF6;
        padding: 6mm 10mm;
        margin: 0 0 10mm 0;
        border-radius: 0 8px 8px 0;
        font-size: 13pt;
        font-weight: 500;
        color: #2C3038;
        line-height: 1.6;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.03);
        page-break-inside: avoid;
    }}
    blockquote p {{ margin: 0; font-weight: bold; color: #1A1F2E; }}

    /* H3 模块标签化：提升视觉层次 */
    h3 {{
        display: inline-block;
        background-color: #EBF2FE;
        color: #1A5DC4;
        font-size: 13pt;
        font-weight: bold;
        padding: 4px 12px;
        border-radius: 4px;
        margin-top: 10pt;
        margin-bottom: 8pt;
        border: none;
        page-break-after: avoid;
        page-break-inside: avoid;
    }}

    h4 {{
        font-size: 12pt;
        font-weight: 600;
        color: #343A40;
        margin-top: 10pt;
        margin-bottom: 4pt;
        page-break-after: avoid;
    }}

    p {{
        margin-top: 0;
        margin-bottom: 8pt;
        text-align: justify;
        color: #495057;
    }}

    /* 列表UI化重构 */
    ul, ol {{
        margin-top: 6pt;
        margin-bottom: 12pt;
        padding-left: 0;
        list-style-type: none; /* 移除默认圆点 */
    }}

    li {{
        margin-bottom: 8pt;
        font-size: 12pt;
        line-height: 1.5;
        position: relative;
        padding-left: 14pt;
        page-break-inside: avoid; /* 极度重要：防止列表项被切分到两栏 */
        color: #343A40;
    }}

    /* 自定义现代感列表符号 */
    ul li::before {{
        content: "■";
        position: absolute;
        left: 0;
        top: -1pt;
        color: #2D7CF6;
        font-size: 9pt;
    }}

    /* 强调文字配色 */
    strong {{
        color: #0B2447;
        font-weight: 700;
    }}

    /* 行业级数据表格优化 */
    table {{
        column-span: all; /* 跨栏展示防止表格挤压 */
        width: 100%;
        border-collapse: collapse;
        margin: 12pt 0;
        font-size: 10.5pt;
        page-break-inside: avoid;
        background-color: #FFFFFF;
        border-radius: 6px;
        overflow: hidden; /* 圆角表格边缘修剪 */
        border: 1px solid #DEE2E6;
    }}
    th {{
        background-color: #F8F9FA;
        color: #1A1F2E;
        padding: 8pt 10pt;
        font-weight: bold;
        border-bottom: 2px solid #2D7CF6; /* 品牌色顶条 */
        text-align: left;
    }}
    td {{
        padding: 8pt 10pt;
        border-bottom: 1px solid #E9ECEF;
        color: #495057;
    }}
    tr:last-child td {{
        border-bottom: none;
    }}
    tr:nth-child(even) td {{ background-color: #FBFBFC; }} /* 极浅斑马线 */

    /* 图片排版 (跨栏展示) */
    img {{
        column-span: all;
        max-width: 100%;
        max-height: 80mm;
        object-fit: contain;
        margin: 10mm auto;
        border-radius: 4px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        page-break-inside: avoid;
    }}

    /* 代码块与页脚 */
    pre {{
        background-color: #1e2233;
        color: #c8d6e5;
        padding: 10pt 12pt;
        border-radius: 4px;
        font-size: 9.5pt;
        line-height: 1.5;
        overflow-x: auto;
        page-break-inside: avoid;
    }}
    code {{
        font-family: 'SF Mono', 'Cascadia Code', 'Consolas', monospace;
    }}

    .footnotes {{
        column-span: all;
        margin-top: 15mm;
        border-top: 1px solid #DEE2E6;
        padding-top: 4mm;
        font-size: 9pt;
        color: #ADB5BD;
    }}

    hr {{
        border: none;
        height: 1px;
        background-color: #DEE2E6;
        margin: 15pt 0;
    }}
</style>
</head>
<body>

    {cover_html}

    <div class="slide-deck">
        {body_html}
    </div>

</body>
</html>"""


# ══════════════════════════════════════════════════════════
# 封面 HTML 构建
# ══════════════════════════════════════════════════════════
def _build_cover(title: str, has_bg: bool, img_path: str) -> str:
    """
    构建杂志级封面 HTML 片段。
    - 有背景图时：全屏图 + 暗色遮罩 + 白色文字
    - 无背景图时：CSS 高级渐变 + 暗色遮罩 + 白色文字
    """

    if has_bg:
        abs_img = os.path.abspath(img_path).replace("\\", "/")
        bg_html = (
            f'<img class="cover-bg-img" src="file:///{abs_img}" '
            f'alt="封面概念图">'
        )
        overlay_html = '<div class="cover-overlay"></div>'
    else:
        bg_html = '<div class="cover-gradient-bg"></div>'
        overlay_html = '<div class="cover-overlay"></div>'

    return f"""
    <div class="cover">
        {bg_html}
        {overlay_html}
        <div class="cover-content">
            <div class="cover-tag">PRODUCT DEEP RESEARCH</div>
            <div class="cover-title">{title}</div>
            <div class="cover-divider"></div>
            <div class="cover-subtitle">产品深度研究路演方案</div>
        </div>
        <div class="cover-footer">
            <strong>出品机构</strong>&nbsp; 产品前沿战略研究院<br>
            <strong>核心引擎</strong>&nbsp; 硅基流动 AI 多模态视觉管道<br>
            <strong>数据溯源</strong>&nbsp; 混合 RAG 多向并发权威检索链路
        </div>
    </div>"""


# ══════════════════════════════════════════════════════════
# 🆕 手动导出 PDF —— 接收前端编辑后的 HTML 矩阵
# ══════════════════════════════════════════════════════════

def render_custom_html_to_pdf(raw_html: str, topic: str, output_pdf_path: str):
    """
    专门接收前端编辑过的 HTML 矩阵，
    合并最新 CSS 规范，输出 16:9 杂志级 PDF。

    核心流程：
    1. 构造包含 @page / 分页 CSS 的完整 HTML 骨架
    2. 将前端传来的 raw_html 嵌入 <body>
    3. 写入临时 .html 文件
    4. 调用 WeasyPrint 渲染为真实 PDF
    """
    # 确保输出目录存在（WeasyPrint 不会自动创建）
    out_dir = os.path.dirname(output_pdf_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    # 安全化 topic 中的 HTML 特殊字符（防止 f-string 注入破坏 HTML）
    safe_topic = topic.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # 构造顶级排版 HTML 骨架
    premium_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{safe_topic} — 产品深度研究报告</title>
<style>
    @page {{
        size: 320mm 180mm;
        margin: 18mm 20mm 15mm 20mm;
        background-color: #F8F9FA;
    }}

    /* 核心：控制每一页的硬截断，使用户在前端编辑的"每一页"完美映射到 PDF 的每一页 */
    .manual-pdf-page {{
        page-break-after: always;
        box-sizing: border-box;
        height: 180mm;
        max-height: 180mm;
        overflow: hidden;
        position: relative;
    }}

    body {{
        font-family: 'PingFang SC', 'Microsoft YaHei', 'Noto Sans CJK SC',
                     'WenQuanYi Zen Hei', 'Helvetica Neue', sans-serif;
        color: #212529;
        line-height: 1.7;
        font-size: 13pt;
        margin: 0;
        padding: 0;
    }}

    .manual-slide-img {{
        max-width: 100%;
        max-height: 90mm;
        display: block;
        margin: 5mm auto;
    }}
</style>
</head>
<body>
    {raw_html}
</body>
</html>"""

    # 写入临时 HTML 文件供 WeasyPrint 读取
    temp_path = output_pdf_path.replace(".pdf", "_manual_build.html")
    with open(temp_path, "w", encoding="utf-8") as f:
        f.write(premium_html)

    logger.info("手动导出 HTML 已写入临时文件: %s (%d 字符)", temp_path, len(premium_html))

    # 调用 WeasyPrint 执行真实 PDF 渲染
    HTML(filename=temp_path).write_pdf(output_pdf_path)
    logger.info("手动导出 PDF 已生成: %s", output_pdf_path)


# ══════════════════════════════════════════════════════════
# CLI 调试入口
# ══════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 3:
        md_in = sys.argv[1]
        pdf_out = sys.argv[2]
        img = sys.argv[3] if len(sys.argv) > 3 else ""
    else:
        md_in = "outputs/AI眼镜行业_report.md"
        pdf_out = "outputs/AI眼镜行业_report_ppt.pdf"
        img = ""

    markdown_to_pdf(md_in, pdf_out, cover_image=img)