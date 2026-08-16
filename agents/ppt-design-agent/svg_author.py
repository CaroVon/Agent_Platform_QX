"""
PptDesign Agent —— MiniMax SVG 逐页创作模块（ppt-master 前置内容重构）
============================================================

完全遵循 hugohe3/ppt-master skill 的「Executor 逐页手写 SVG」范式：
- 每个页面由 MiniMax 根据「页面 DSL + 视觉体系 + skill 约束」自由创作 SVG
- 放弃此前的确定性模板渲染（dsl_to_svg）
- 校验：SVG 可解析、包含页面关键文本、无越界（≤720）、无禁用元素
- 失败重试（带错误反馈）；仍失败 → 极简兜底页（仅保证内容不丢，非模板）
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET

W, H = 1280, 720
FONT = "Noto Sans SC, Source Han Sans SC, PingFang SC, Microsoft YaHei, sans-serif"

_SKILL_RULES = """## 硬性规则（必须遵守）
- 输出必须是一个完整的 <svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">…</svg>，不要输出任何解释文字
- 页面设计闭合：页面上所有可见内容（标题/结论/数字/清单/图表/装饰）都必须出现在 SVG 内
- 禁止使用：<style>、class 属性、外部 CSS、<foreignObject>、<textPath>、@font-face、<animate*>/<set>/<script>、<iframe>、mask
- 文字必须使用给出的字体栈；中文文本必须手动换行（每行 ≤ 约 40 个全角字符）
- <text>/<tspan> 只允许属性：x/y/fill/font-family/font-size/font-weight/font-style/letter-spacing/text-anchor/transform/opacity；**禁止 dx、dy、style、dominant-baseline、text-align、line-height 等任何其他属性**（导出转换会拒绝）
- 所有元素必须位于画布内（y+高度 ≤ 700，x+宽度 ≤ 1280），禁止溢出
- 颜色只能使用给出的 palette 六色（可加 10-15% 透明度的同色变体）
- 图表组件：可以输出 <g data-pptx-replace-with="chart" data-pptx-id="c1" data-pptx-bounds="x,y,w,h" data-pptx-json='{...}'> + 内部 SVG 兜底图形；data-pptx-json 用 chart payload：{"type":"column|line|pie|radar","categories":[...],"series":[{"name":"...","values":[...]}],"data_labels":true}（bounds 单位=EMU，1px=9525）
- 矩阵/象限图：**纯 SVG 散点**（竞争者为浅灰色 #94A3B8 圆点，本产品为主色圆点）+ 虚线中轴 + 轴名；**禁止为象限/散点使用 data-pptx-replace-with 原生标记**（转换器不支持 scatter 数据标签）
- 柱/折线/饼图的原生标记中 data_labels 必须为 true 之外不要加 label 相关配置"""


def _trim_data(data: dict, max_text: int = 180, max_items: int = 8) -> dict:
    """精简组件数据以控制 prompt 长度（保留关键内容）。"""
    out: dict = {}
    for k, v in data.items():
        if isinstance(v, str):
            out[k] = v[:max_text]
        elif isinstance(v, list):
            out[k] = [str(x)[:max_text] for x in v[:max_items]]
        elif isinstance(v, dict):
            out[k] = _trim_data(v, max_text, max_items)
        else:
            out[k] = v
    return out


def _page_json(page: dict) -> str:
    comps = []
    for c in page.get("components", [])[:10]:
        comps.append({"type": c.get("type"), "data": _trim_data(c.get("data") or {})})
    return json.dumps(
        {
            "type": page.get("type"),
            "title": str(page.get("title") or "")[:120],
            "subtitle": str(page.get("subtitle") or "")[:120],
            "insight": str(page.get("insight") or "")[:160],
            "components": comps,
        },
        ensure_ascii=False,
    )


def build_page_prompt(
    page: dict,
    theme: dict | None,
    design_spec: str,
    page_index: int,
    images: dict | None = None,
) -> str:
    """构建单页 SVG 创作 prompt（页面 DSL + 视觉体系 + skill 约束）。"""
    palette = (theme or {}).get("palette") or {}
    default_p = {"bg": "#f8fafc", "surface": "#ffffff", "primary": "#4f46e5",
                 "accent": "#6366f1", "text": "#0f172a", "muted": "#64748b"}
    colors = {**default_p, **{k: v for k, v in palette.items() if v}}
    theme_name = (theme or {}).get("name", "咨询风")

    img_hint = ""
    if images:
        parts = []
        if images.get("hero"):
            parts.append(f'<image href="images/hero.png" x="0" y="0" width="1280" height="720" preserveAspectRatio="xMidYMid slice" opacity="0.3"/>')
        for k, v in (images.get("pages") or {}).items():
            parts.append(f'第 {k} 页可用配图 <image href="{v}" …>（标题区或页面右上，宽 ≤ 240）')
        if parts:
            img_hint = "## 可用图片\n" + "\n".join(parts) + "\n（可选使用，使用后 finalize 会自动内嵌）\n"

    return f"""你是资深咨询风演示 SVG 设计师（ppt-master Executor）。根据页面数据与视觉体系，逐页手写高质量 SVG 页面。

## 设计规范摘要
{design_spec[:1400]}

## 视觉体系（主题「{theme_name}」）
- 画布：1280×720（PPT 16:9），viewBox="0 0 1280 720"
- 背景 bg={colors['bg']} / 卡片 surface={colors['surface']} / 主色 primary={colors['primary']}
- 强调 accent={colors['accent']} / 正文 text={colors['text']} / 次级 muted={colors['muted']}
- 字体栈：{FONT}

{img_hint}
## 页面数据（Presentation DSL 页 {page_index + 1}）
{_page_json(page)}

{_SKILL_RULES}

## 构图要求（咨询风）
- 封面/结尾：居中标题 + 强调色条 + 留白；可选 Hero 图（低透明度铺底）
- 内容页：左上标题（26px 加粗）+ 强调竖条 + insight（14px 主色）；内容两列网格或全宽布局
- 指标卡：圆角卡片（surface 底 + accent 描边）+ 大号主色数值 + 次级标签
- 清单卡：圆角卡片 + 标题 + "• " 条目（≤8 条，超出用「等 N 项」）
- 表格：主色表头白字 + 斑马纹行
- 时间线：阶段名主色 + 里程碑条目，阶段间用分隔线
- 图表：见硬性规则的原生 chart 标记（数据必须来自页面数据，禁止编造数值）
- 页脚：底部细线 + 页码 {page_index + 1:02d}（y=700 附近，不超出画布）
- 信息密度：宁满勿空，所有数据尽量呈现；页面高度用完但不超过 720

只输出 <svg>…</svg>。"""


_BANNED_TEXT_ATTRS = frozenset({
    "dx", "dy", "alignment-baseline", "direction", "dominant-baseline",
    "font-kerning", "font-feature-settings", "font-size-adjust", "font-stretch",
    "font-synthesis", "font-variant", "font-variation-settings", "font",
    "hyphens", "kerning", "line-height", "overflow-wrap", "text-align",
    "text-align-last", "text-indent", "text-rendering", "text-shadow",
    "text-transform", "unicode-bidi", "vertical-align", "white-space",
    "word-spacing", "word-break", "writing-mode", "baseline-shift",
    "lengthAdjust", "textLength", "startOffset", "style",
})


def sanitize_svg(svg: str) -> str:
    """剔除 svg_to_pptx 不支持的属性/标记，保证原生转换。

    - 文本属性黑名单（dx/dy/style 等）
    - scatter/xy/bubble 原生图表标记 → 剥除标记属性，保留内部 SVG 兜底图形
      （转换器不支持 scatter 数据标签）
    """
    try:
        root = ET.fromstring(svg)
    except ET.ParseError:
        return svg
    for el in root.iter():
        for attr in list(el.attrib):
            if attr in _BANNED_TEXT_ATTRS:
                del el.attrib[attr]
        if el.get("data-pptx-replace-with"):
            # LLM 生成的原生标记几何不可靠（缺 bounds/兜底 → 转换失败），
            # 全部剥离：保留内部 SVG 图形作为 DrawingML 形状导出
            for attr in ("data-pptx-replace-with", "data-pptx-id",
                         "data-pptx-bounds", "data-pptx-json", "data-pptx-data"):
                el.attrib.pop(attr, None)
    return ET.tostring(root, encoding="unicode")


def extract_svg(text: str) -> str:
    """从模型输出提取 <svg>…</svg> 块。"""
    m = re.search(r"<svg[^>]*>.*?</svg>", text, re.DOTALL)
    return m.group(0) if m else ""


_FORBIDDEN = ("<style", "foreignObject", "textPath", "@font-face",
              "<animate", "<script", "<iframe", "mask")


def _norm(text: str) -> str:
    """归一化文本用于校验（去空白/分隔符/标点，容忍模型拆行改写）。"""
    return re.sub(r"[\s·・,，。;；:：|/\\[\]（）()「」『』、-]", "", text)


def validate_svg(svg: str, page: dict) -> tuple[bool, str]:
    """校验：可解析 + 关键文本（归一化匹配）+ 无越界 + 无禁用元素。"""
    if not svg:
        return False, "空 SVG"
    for bad in _FORBIDDEN:
        if bad in svg:
            return False, f"包含禁用元素 {bad}"
    try:
        ET.fromstring(svg)
    except ET.ParseError as exc:
        return False, f"XML 解析失败: {exc}"
    # 关键文本（归一化后子串匹配，容忍拆行/空格/分隔符）
    svg_norm = _norm(svg)
    title = _norm(str(page.get("title") or ""))
    insight = _norm(str(page.get("insight") or ""))
    if title and title[:4] not in svg_norm:
        return False, "缺少页面标题"
    if insight and insight[:4] not in svg_norm:
        return False, "缺少 insight 结论"
    # 越界检查（排除全画布背景矩形；内容 y+height ≤ 715）
    ys = [float(m) for m in re.findall(r'y="([\d.]+)"', svg)]
    heights = re.findall(r'y="([\d.]+)"[^>]*height="([\d.]+)"', svg)
    max_y = max(ys or [0])
    for ry, rh in heights:
        ry_f, rh_f = float(ry), float(rh)
        if ry_f == 0 and rh_f >= 720:
            continue  # 全画布背景/铺底
        max_y = max(max_y, ry_f + rh_f)
    if max_y > 718:
        return False, f"内容越界（最大 y={max_y:.0f} > 718）"
    return True, ""


def fallback_svg(page: dict, theme: dict | None) -> str:
    """极简兜底页（仅保证内容不丢；非创作模板）。"""
    palette = (theme or {}).get("palette") or {}
    default_p = {"bg": "#f8fafc", "surface": "#ffffff", "primary": "#4f46e5",
                 "accent": "#6366f1", "text": "#0f172a", "muted": "#64748b"}
    colors = {**default_p, **{k: v for k, v in palette.items() if v}}
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        f'<rect width="{W}" height="{H}" fill="{colors["bg"]}"/>',
    ]
    page_type = page.get("type", "content")
    title = str(page.get("title") or "")
    if page_type in ("cover", "conclusion"):
        parts.append(f'<text x="640" y="360" font-size="40" font-weight="bold" fill="{colors["text"]}" text-anchor="middle" font-family="{FONT}">{title[:40]}</text>')
    else:
        parts.append(f'<text x="56" y="80" font-size="26" font-weight="bold" fill="{colors["text"]}" font-family="{FONT}">{title[:40]}</text>')
        insight = str(page.get("insight") or "")
        if insight:
            parts.append(f'<text x="56" y="120" font-size="14" fill="{colors["primary"]}" font-family="{FONT}">{insight[:80]}</text>')
        ty = 190
        for c in page.get("components", [])[:8]:
            data = c.get("data") or {}
            label = str(data.get("value") or data.get("title") or data.get("text") or c.get("type"))[:60]
            parts.append(f'<text x="56" y="{ty}" font-size="15" fill="{colors["text"]}" font-family="{FONT}">{label}</text>')
            ty += 34
    parts.append(f'<text x="56" y="700" font-size="11" fill="{colors["muted"]}" font-family="{FONT}">{page_type}</text>')
    parts.append("</svg>")
    return "\n".join(parts)
