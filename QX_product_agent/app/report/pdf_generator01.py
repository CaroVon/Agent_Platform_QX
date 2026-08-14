"""
Professional Research Report PDF Generator
Converts Markdown to a beautifully formatted PDF research report.
"""

from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    HRFlowable, Table, TableStyle, ListFlowable, ListItem,
    KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm, cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas as rl_canvas

import markdown2
import re
from datetime import datetime
from html.parser import HTMLParser


# ── 字体注册 ──────────────────────────────────────────────
pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
# ReportLab 环境中默认可用的中文 CID 字体为 STSong-Light。
# 如需标题加粗效果，可改为自定义 TTF 字体注册。


# ── 品牌色板 ──────────────────────────────────────────────
BRAND_DARK   = colors.HexColor('#1a2744')   # 深藏青 —— 封面/页眉背景
BRAND_MID    = colors.HexColor('#2e4a8c')   # 中蓝   —— H1 标题
BRAND_ACCENT = colors.HexColor('#4a90d9')   # 亮蓝   —— H2 标题、分隔线
BRAND_LIGHT  = colors.HexColor('#eaf1fb')   # 浅蓝   —— 表格行底色
TEXT_MAIN    = colors.HexColor('#1a1a2e')   # 正文主色
TEXT_MUTED   = colors.HexColor('#555577')   # 次要文字
RULE_COLOR   = colors.HexColor('#c8d8f0')   # 细分隔线


# ── 页面参数 ──────────────────────────────────────────────
PAGE_W, PAGE_H = A4
MARGIN_OUTER = 2.2 * cm
MARGIN_INNER = 2.2 * cm
MARGIN_TOP   = 2.5 * cm
MARGIN_BOT   = 2.5 * cm


# ══════════════════════════════════════════════════════════
# 页眉 / 页脚
# ══════════════════════════════════════════════════════════
def make_page_decorator(report_title: str):
    """返回一个 onPage 回调，在每页绘制页眉和页脚。"""

    def _draw(canv: rl_canvas.Canvas, doc):
        canv.saveState()
        w, h = A4

        # ── 页眉 ──────────────────────────────────────────
        # 深色背景条
        canv.setFillColor(BRAND_DARK)
        canv.rect(0, h - 1.4 * cm, w, 1.4 * cm, fill=1, stroke=0)

        # 报告标题（左）
        canv.setFont('STSong-Light', 9)
        canv.setFillColor(colors.white)
        short = report_title if len(report_title) <= 30 else report_title[:29] + '…'
        canv.drawString(MARGIN_OUTER, h - 0.9 * cm, short)

        # 机构名（右）
        canv.setFont('STSong-Light', 8)
        canv.setFillColor(colors.HexColor('#b0c4de'))
        canv.drawRightString(w - MARGIN_OUTER, h - 0.9 * cm, '产品分析报告')

        # ── 页脚 ──────────────────────────────────────────
        # 细分隔线
        canv.setStrokeColor(RULE_COLOR)
        canv.setLineWidth(0.5)
        canv.line(MARGIN_OUTER, 1.8 * cm, w - MARGIN_OUTER, 1.8 * cm)

        # 左：日期
        canv.setFont('STSong-Light', 7.5)
        canv.setFillColor(TEXT_MUTED)
        canv.drawString(MARGIN_OUTER, 1.1 * cm, datetime.now().strftime('%Y年%m月'))

        # 右：页码
        page_num = canv.getPageNumber()
        canv.drawRightString(w - MARGIN_OUTER, 1.1 * cm, f'第 {page_num} 页')

        canv.restoreState()

    return _draw


# ══════════════════════════════════════════════════════════
# 样式表
# ══════════════════════════════════════════════════════════
def build_styles() -> dict:
    base = getSampleStyleSheet()

    def ps(name, **kw) -> ParagraphStyle:
        return ParagraphStyle(name, **kw)

    BODY_FONT   = 'STSong-Light'
    TITLE_FONT  = 'STSong-Light'  # 使用可用的 ReportLab 中文 CID 字体
    BODY_SIZE   = 10.5
    LEAD        = 19

    styles = {
        # ── 正文 ──────────────────────────────────────────
        'body': ps('body',
            fontName=BODY_FONT, fontSize=BODY_SIZE,
            leading=LEAD, textColor=TEXT_MAIN,
            alignment=TA_JUSTIFY,
            spaceAfter=6, firstLineIndent=0,
        ),
        # ── 标题 H1 ───────────────────────────────────────
        'h1': ps('h1',
            fontName=TITLE_FONT, fontSize=18,
            leading=26, textColor=BRAND_MID,
            spaceBefore=18, spaceAfter=4,
            alignment=TA_LEFT,
        ),
        # ── 标题 H2 ───────────────────────────────────────
        'h2': ps('h2',
            fontName=TITLE_FONT, fontSize=14,
            leading=22, textColor=BRAND_ACCENT,
            spaceBefore=14, spaceAfter=3,
        ),
        # ── 标题 H3 ───────────────────────────────────────
        'h3': ps('h3',
            fontName=TITLE_FONT, fontSize=11.5,
            leading=18, textColor=BRAND_DARK,
            spaceBefore=10, spaceAfter=2,
        ),
        # ── 标题 H4 ───────────────────────────────────────
        'h4': ps('h4',
            fontName=TITLE_FONT, fontSize=10.5,
            leading=17, textColor=TEXT_MAIN,
            spaceBefore=8, spaceAfter=2,
        ),
        # ── 引用块 ────────────────────────────────────────
        'blockquote': ps('blockquote',
            fontName=BODY_FONT, fontSize=10,
            leading=17, textColor=TEXT_MUTED,
            leftIndent=18, rightIndent=8,
            spaceAfter=8, spaceBefore=4,
            borderPad=6,
        ),
        # ── 列表项 ────────────────────────────────────────
        'li': ps('li',
            fontName=BODY_FONT, fontSize=BODY_SIZE,
            leading=LEAD, textColor=TEXT_MAIN,
            leftIndent=14, spaceAfter=3,
        ),
        # ── 封面主标题 ────────────────────────────────────
        'cover_title': ps('cover_title',
            fontName=TITLE_FONT, fontSize=28,
            leading=38, textColor=colors.white,
            alignment=TA_CENTER, spaceAfter=10,
        ),
        # ── 封面副标题 ────────────────────────────────────
        'cover_sub': ps('cover_sub',
            fontName=BODY_FONT, fontSize=13,
            leading=20, textColor=colors.HexColor('#b0c4de'),
            alignment=TA_CENTER, spaceAfter=6,
        ),
        # ── 封面元信息 ────────────────────────────────────
        'cover_meta': ps('cover_meta',
            fontName=BODY_FONT, fontSize=10,
            leading=16, textColor=colors.HexColor('#8899bb'),
            alignment=TA_CENTER,
        ),
    }
    return styles


# ══════════════════════════════════════════════════════════
# HTML → Flowable 解析器
# ══════════════════════════════════════════════════════════
class HTMLToFlowables(HTMLParser):
    """将 markdown2 生成的 HTML 逐标签转换为 ReportLab Flowable 列表。"""

    # ReportLab Paragraph 支持的内联标签白名单
    INLINE_TAGS = {'b', 'strong', 'i', 'em', 'u', 'br', 'a', 'code', 'span'}

    def __init__(self, styles: dict):
        super().__init__()
        self.styles   = styles
        self.flowables: list = []

        self._buf      = ''          # 当前段落文字缓冲
        self._cur_tag  = 'p'         # 当前块级标签
        self._in_block = False
        self._li_buf   = []          # 列表项缓冲
        self._in_li    = False
        self._in_list  = False
        self._list_type = 'ul'

    # ── 工具 ──────────────────────────────────────────────
    def _flush(self):
        """将缓冲区内容按当前标签类型生成 Flowable 并追加。"""
        text = self._buf.strip()
        self._buf = ''
        if not text:
            return

        tag = self._cur_tag
        s   = self.styles

        if tag in ('h1',):
            # H1：文字 + 下方蓝色粗线
            self.flowables.append(Spacer(1, 4))
            self.flowables.append(Paragraph(text, s['h1']))
            self.flowables.append(
                HRFlowable(width='100%', thickness=2.5,
                           color=BRAND_MID, spaceAfter=6)
            )
        elif tag == 'h2':
            self.flowables.append(Spacer(1, 2))
            self.flowables.append(Paragraph(text, s['h2']))
            self.flowables.append(
                HRFlowable(width='40%', thickness=1.2,
                           color=BRAND_ACCENT, spaceAfter=4,
                           hAlign='LEFT')
            )
        elif tag == 'h3':
            self.flowables.append(Paragraph(text, s['h3']))
        elif tag == 'h4':
            self.flowables.append(Paragraph(text, s['h4']))
        elif tag == 'blockquote':
            # 引用块：左侧蓝色竖条
            tbl = Table(
                [[Paragraph(text, s['blockquote'])]],
                colWidths=['100%'],
            )
            tbl.setStyle(TableStyle([
                ('LEFTPADDING',  (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING',   (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING',(0, 0), (-1, -1), 6),
                ('LINEBEFORE',   (0, 0), (0, -1), 3, BRAND_ACCENT),
                ('BACKGROUND',   (0, 0), (-1, -1), BRAND_LIGHT),
                ('ROUNDEDCORNERS', [3]),
            ]))
            self.flowables.append(tbl)
            self.flowables.append(Spacer(1, 6))
        else:
            # 普通段落
            self.flowables.append(Paragraph(text, s['body']))
            self.flowables.append(Spacer(1, 4))

    # ── HTMLParser 回调 ───────────────────────────────────
    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in ('h1','h2','h3','h4','h5','h6'):
            self._flush()
            self._cur_tag  = tag if tag in ('h1','h2','h3','h4') else 'h4'
            self._in_block = True
        elif tag == 'p':
            self._flush()
            self._cur_tag  = 'p'
            self._in_block = True
        elif tag == 'blockquote':
            self._flush()
            self._cur_tag  = 'blockquote'
            self._in_block = True
        elif tag in ('ul', 'ol'):
            self._flush()
            self._in_list  = True
            self._list_type = tag
            self._li_buf   = []
        elif tag == 'li':
            self._in_li = True
            self._li_buf.append('')
        elif tag in self.INLINE_TAGS:
            # 内联标签直接透传给 ReportLab XML 解析器
            attr_str = ''
            if tag == 'a':
                href = dict(attrs).get('href', '')
                attr_str = f' href="{href}"'
            self._buf += f'<{tag}{attr_str}>'
        elif tag == 'br':
            self._buf += '<br/>'
        elif tag == 'hr':
            self._flush()
            self.flowables.append(
                HRFlowable(width='100%', thickness=0.5,
                           color=RULE_COLOR, spaceAfter=8, spaceBefore=8)
            )

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ('h1','h2','h3','h4','h5','h6','p','blockquote'):
            self._flush()
            self._in_block = False
        elif tag in ('ul','ol'):
            # 提交列表
            self._in_list = False
            items = []
            for item_text in self._li_buf:
                item_text = item_text.strip()
                if item_text:
                    items.append(
                        ListItem(
                            Paragraph(item_text, self.styles['li']),
                            leftIndent=20, bulletIndent=6,
                        )
                    )
            if items:
                bullet = '•' if self._list_type == 'ul' else '1'
                lf = ListFlowable(
                    items,
                    bulletType='bullet' if self._list_type == 'ul' else '1',
                    bulletColor=BRAND_ACCENT,
                    leftIndent=16,
                    spaceBefore=4, spaceAfter=6,
                )
                self.flowables.append(lf)
            self._li_buf = []
        elif tag == 'li':
            self._in_li = False
        elif tag in self.INLINE_TAGS:
            if tag != 'br':
                self._buf += f'</{tag}>'

    def handle_data(self, data):
        if self._in_li and self._li_buf:
            self._li_buf[-1] += data
        elif self._in_block or self._buf:
            self._buf += data

    def get_flowables(self):
        self._flush()
        return self.flowables


# ══════════════════════════════════════════════════════════
# Markdown 清洗
# ══════════════════════════════════════════════════════════
def clean_markdown(md_text: str) -> str:
    # 去除代码块（可选：保留为引用块）
    md_text = re.sub(r'```[\s\S]*?```', '', md_text)
    md_text = re.sub(r'`[^`]+`', '', md_text)
    return md_text


# ══════════════════════════════════════════════════════════
# 封面页
# ══════════════════════════════════════════════════════════
def build_cover(title: str, styles: dict) -> list:
    """生成封面所需的 Flowable 列表（第一页）。"""
    cover = []

    # 大段空白把内容推到页面中央
    cover.append(Spacer(1, 5.5 * cm))

    # 装饰色条（用 1×1 Table 模拟）
    bar = Table(
        [['']],
        colWidths=[PAGE_W - MARGIN_OUTER * 2],
        rowHeights=[0.35 * cm],
    )
    bar.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BRAND_ACCENT),
        ('LINEABOVE',  (0, 0), (-1, 0), 0, colors.transparent),
    ]))
    cover.append(bar)
    cover.append(Spacer(1, 0.6 * cm))

    # 主标题
    cover.append(Paragraph(title, styles['cover_title']))
    cover.append(Spacer(1, 0.4 * cm))

    # 下方装饰条
    cover.append(bar)
    cover.append(Spacer(1, 1.2 * cm))

    # 副标题 / 元信息
    cover.append(Paragraph('行业深度研究报告', styles['cover_sub']))
    cover.append(Spacer(1, 0.6 * cm))
    cover.append(
        Paragraph(
            f'发布日期：{datetime.now().strftime("%Y 年 %m 月")}',
            styles['cover_meta'],
        )
    )

    cover.append(PageBreak())
    return cover


# ══════════════════════════════════════════════════════════
# 主函数
# ══════════════════════════════════════════════════════════
def markdown_to_pdf(md_path: str, pdf_path: str):

    # 1. 读取 & 清洗 Markdown
    with open(md_path, 'r', encoding='utf-8') as f:
        md_content = f.read()
    md_content = clean_markdown(md_content)

    # 2. 提取第一个 H1 作为报告标题
    title_match = re.search(r'^#\s+(.+)', md_content, re.MULTILINE)
    report_title = title_match.group(1).strip() if title_match else '研究报告'

    # 3. Markdown → HTML
    html = markdown2.markdown(
        md_content,
        extras=['tables', 'fenced-code-blocks', 'strike', 'cuddled-lists'],
    )

    # 4. 构建样式
    styles = build_styles()

    # 5. HTML → Flowables
    parser = HTMLToFlowables(styles)
    parser.feed(html)
    body_flowables = parser.get_flowables()

    # 6. 构建文档（带封面、页眉页脚的 BaseDocTemplate）
    on_page = make_page_decorator(report_title)

    doc = BaseDocTemplate(
        pdf_path,
        pagesize=A4,
        leftMargin=MARGIN_OUTER,
        rightMargin=MARGIN_OUTER,
        topMargin=MARGIN_TOP + 1.4 * cm,   # 为页眉留空
        bottomMargin=MARGIN_BOT,
        title=report_title,
        author='产品分析',
    )

    # 封面页（无页眉页脚）
    cover_frame = Frame(
        0, 0, PAGE_W, PAGE_H,
        leftPadding=MARGIN_OUTER, rightPadding=MARGIN_OUTER,
        topPadding=0, bottomPadding=0,
        id='cover',
    )
    # 内容页（有页眉页脚）
    content_frame = Frame(
        MARGIN_OUTER,
        MARGIN_BOT,
        PAGE_W - MARGIN_OUTER * 2,
        PAGE_H - MARGIN_TOP - 1.4 * cm - MARGIN_BOT,
        id='content',
    )

    def cover_page(canv, doc):
        """封面：深色满版背景，不画页眉页脚。"""
        canv.saveState()
        canv.setFillColor(BRAND_DARK)
        canv.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
        canv.restoreState()

    doc.addPageTemplates([
        PageTemplate(id='Cover',   frames=[cover_frame],   onPage=cover_page),
        PageTemplate(id='Content', frames=[content_frame], onPage=on_page),
    ])

    # 7. 拼装 story
    story = build_cover(report_title, styles)
    # 封面之后切换到 Content 模板
    from reportlab.platypus import NextPageTemplate
    story.insert(len(story) - 1, NextPageTemplate('Content'))
    story.extend(body_flowables)

    # 8. 生成 PDF
    doc.build(story)
    print(f'[OK] PDF generated: {pdf_path}')


# ══════════════════════════════════════════════════════════
if __name__ == '__main__':
    markdown_to_pdf(
        'outputs/AI眼镜行业_report.md',
        'outputs/AI眼镜行业_report.pdf',
    )