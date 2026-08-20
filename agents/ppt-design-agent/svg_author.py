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
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

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
- 柱/折线/饼图的原生标记中 data_labels 必须为 true 之外不要加 label 相关配置
- filter 只能直接用于 rect/circle/image/path/text；禁止在 <g> 或 style 中使用 filter"""


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

    # ── 图片 hint（强调产品架构 + 设计） ──
    img_hint = ""
    if images:
        parts = []
        if images.get("hero"):
            parts.append(
                '<image href="images/hero.png" x="0" y="0" width="1280" height="720" '
                'preserveAspectRatio="xMidYMid slice" opacity="0.35"/>'
            )
        # 按 by_kind 列出所有可用图（含 architecture / design / scene）
        by_kind = images.get("by_kind") or {}
        if by_kind:
            kind_names = {
                "hero": "封面主视觉",
                "cover_decorative": "封面装饰",
                "architecture": "产品技术架构图（isometric layered stack）",
                "design": "产品工业设计图（isometric mockup）",
                "scene": "使用场景图",
                "feature": "功能特写",
                "page_concept": "页面概念图",
            }
            for kind, ref in by_kind.items():
                desc = kind_names.get(kind, kind)
                parts.append(
                    f'<image href="{ref}" width="280" height="158" opacity="0.92"/> '
                    f'# {kind}：{desc}'
                )
        for k, v in (images.get("pages") or {}).items():
            parts.append(f'第 {k} 页可用配图 <image href="{v}" …>')
        # 当前页专用图
        cur = images.get("page_image")
        if cur:
            parts.append(f'**当前页推荐配图**：<image href="{cur}" …>')
        if parts:
            img_hint = (
                "## 可用图片资源（已生成并入库 Design Studio，可直接引用）\n"
                + "\n".join(parts) + "\n\n"
                "**重要**：SVG 引用图片时用 `href=\"images/<filename>.png\"` 相对路径，"
                "finalize_svg 会自动 base64 嵌入。如不直接引用也没关系，agent 会自动注入到顶层。\n"
            )

    page_kind_hint = ""
    page_type = (page.get("type") or "").lower()
    if page_type == "product_architecture":
        page_kind_hint = (
            "\n## 视觉强调：本页是**产品架构**页——SVG 内可叠加半透明等距分层栈（4 层），"
            "或与 architecture.png 配合呈现技术蓝图风格\n"
        )
    elif page_type == "user_persona" or page_type == "user_journey":
        page_kind_hint = (
            "\n## 视觉强调：本页是**用户场景**页——配合 scene.png 营造生活感\n"
        )
    elif page_type == "feature_priority":
        page_kind_hint = (
            "\n## 视觉强调：本页是**功能优先级**页——核心功能卡片 + feature.png 特写\n"
        )

    return f"""你是资深咨询风演示 SVG 设计师（ppt-master Executor）。根据页面数据与视觉体系，逐页手写高质量 SVG 页面。

## 设计规范摘要
{design_spec[:1400]}

## 视觉体系（主题「{theme_name}」）
- 画布：1280×720（PPT 16:9），viewBox="0 0 1280 720"
- 背景 bg={colors['bg']} / 卡片 surface={colors['surface']} / 主色 primary={colors['primary']}
- 强调 accent={colors['accent']} / 正文 text={colors['text']} / 次级 muted={colors['muted']}
- 字体栈：{FONT}

{img_hint}{page_kind_hint}## 页面数据（Presentation DSL 页 {page_index + 1}）
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
- **图片使用**：如有产品图（architecture/design/scene），尽量以全宽或大尺寸呈现，作为页面氛围层

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


def validate_native_contract(svg: str) -> tuple[bool, str]:
    """检查已知的 DrawingML 转换契约，避免整套 PPT 生成后才失败。"""
    if "currentColor" in svg:
        return False, "不支持 currentColor，请使用主题色板中的具体颜色"
    try:
        root = ET.fromstring(svg)
    except ET.ParseError as exc:
        return False, f"XML 解析失败: {exc}"

    # 复用 ppt-master 转换器的确定性规则，避免生成整套页面后才发现
    # gradient/filter/geometry 无法转换。导入失败时保留下面的轻量兜底检查。
    scripts_dir = Path(__file__).resolve().parent / "vendor" / "ppt-master" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    try:
        from svg_to_pptx.drawingml.paths import (
            project_freeform_geometry_errors,
            project_gradient_geometry_errors,
        )
        from svg_to_pptx.drawingml.utils import (
            project_definition_errors,
            project_filter_errors,
            project_geometry_length_errors,
            project_gradient_errors,
            project_paint_reference_errors,
            project_paint_errors,
            project_transform_errors,
        )
        from svg_to_pptx.drawingml.text_properties import project_text_property_errors

        errors: list[str] = []
        for validator in (
            project_geometry_length_errors,
            project_freeform_geometry_errors,
            project_paint_errors,
            project_paint_reference_errors,
            project_definition_errors,
            project_gradient_errors,
            project_gradient_geometry_errors,
            project_filter_errors,
            project_transform_errors,
            project_text_property_errors,
        ):
            errors.extend(validator(root))
        if errors:
            return False, errors[0]
    except (ImportError, ModuleNotFoundError):
        pass

    for element in root.iter():
        tag = str(element.tag).rsplit("}", 1)[-1].lower()
        if element.get("style") and re.search(r"(?:^|;)\s*filter\s*:", element.get("style", "")):
            return False, "不支持在 style 中声明 filter"
        if element.get("filter") and tag == "g":
            return False, "不支持在 <g> 上使用 filter"
        if element.get("filter") and not re.fullmatch(r"url\(#[^)]+\)", element.get("filter", "").strip()):
            return False, "filter 必须是本地 url(#id) 引用"
    return True, ""


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
    import html as _html
    palette = (theme or {}).get("palette") or {}
    default_p = {"bg": "#f8fafc", "surface": "#ffffff", "primary": "#4f46e5",
                 "accent": "#6366f1", "text": "#0f172a", "muted": "#64748b"}
    colors = {**default_p, **{k: v for k, v in palette.items() if v}}

    def _esc(s: str) -> str:
        """XML 安全转义（避免 < > & 引号导致 SVG 解析失败）。"""
        return _html.escape(str(s or ""), quote=True)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        f'<rect width="{W}" height="{H}" fill="{colors["bg"]}"/>',
    ]
    page_type = page.get("type", "content")
    title = str(page.get("title") or "")
    if page_type in ("cover", "conclusion"):
        parts.append(f'<text x="640" y="360" font-size="40" font-weight="bold" fill="{colors["text"]}" text-anchor="middle" font-family="{FONT}">{_esc(title[:40])}</text>')
    else:
        parts.append(f'<text x="56" y="80" font-size="26" font-weight="bold" fill="{colors["text"]}" font-family="{FONT}">{_esc(title[:40])}</text>')
        insight = str(page.get("insight") or "")
        if insight:
            parts.append(f'<text x="56" y="120" font-size="14" fill="{colors["primary"]}" font-family="{FONT}">{_esc(insight[:80])}</text>')
        ty = 190
        for c in page.get("components", [])[:8]:
            data = c.get("data") or {}
            label = str(data.get("value") or data.get("title") or data.get("text") or c.get("type"))[:60]
            parts.append(f'<text x="56" y="{ty}" font-size="15" fill="{colors["text"]}" font-family="{FONT}">{_esc(label)}</text>')
            ty += 34
    parts.append(f'<text x="56" y="700" font-size="11" fill="{colors["muted"]}" font-family="{FONT}">{_esc(page_type)}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


# ─────────────────────────────────────────────────────────────────
# 程序化图片注入（Phase 1.2 / 2.5 核心 —— 不依赖 LLM）
# ─────────────────────────────────────────────────────────────────

# 各页类型的图片位置 + 尺寸规则（x, y, w, h, opacity）
_IMAGE_LAYOUTS: dict[str, list[dict]] = {
    # 封面：全幅铺底 + 半透明遮罩
    "cover": [
        {"x": 0, "y": 0, "w": 1280, "h": 720, "opacity": 0.35,
         "preserveAspectRatio": "xMidYMid slice",
         "name": "cover-bg", "role": "background"},
    ],
    # 通用内容页：右上角小图 280×158（4:2.25）
    "content": [
        {"x": 960, "y": 80, "w": 280, "h": 158, "opacity": 0.92,
         "preserveAspectRatio": "xMidYMid slice",
         "name": "page-thumb", "role": "decoration"},
    ],
    # 用户画像：右上角场景图
    "user_persona": [
        {"x": 940, "y": 70, "w": 300, "h": 200, "opacity": 0.90,
         "preserveAspectRatio": "xMidYMid slice",
         "name": "persona-scene", "role": "decoration"},
    ],
    # 用户旅程：右侧场景图
    "user_journey": [
        {"x": 940, "y": 70, "w": 300, "h": 200, "opacity": 0.90,
         "preserveAspectRatio": "xMidYMid slice",
         "name": "journey-scene", "role": "decoration"},
    ],
    # 产品架构：上半部分全宽架构图
    "product_architecture": [
        {"x": 60, "y": 145, "w": 1160, "h": 320, "opacity": 0.95,
         "preserveAspectRatio": "xMidYMid meet",
         "name": "arch-diagram", "role": "background"},
    ],
    # 工业设计：右侧产品图 320×220
    "design": [
        {"x": 900, "y": 220, "w": 320, "h": 220, "opacity": 0.92,
         "preserveAspectRatio": "xMidYMid slice",
         "name": "design-mockup", "role": "decoration"},
    ],
    # 功能优先级：右上角小图
    "feature_priority": [
        {"x": 940, "y": 80, "w": 300, "h": 170, "opacity": 0.92,
         "preserveAspectRatio": "xMidYMid slice",
         "name": "feature-visual", "role": "decoration"},
    ],
    # 竞品矩阵：右上角小图
    "competitor_matrix": [
        {"x": 940, "y": 80, "w": 300, "h": 170, "opacity": 0.85,
         "preserveAspectRatio": "xMidYMid slice",
         "name": "competitor-visual", "role": "decoration"},
    ],
    # 结论页：下半部分图
    "conclusion": [
        {"x": 940, "y": 320, "w": 300, "h": 200, "opacity": 0.85,
         "preserveAspectRatio": "xMidYMid slice",
         "name": "closing-visual", "role": "decoration"},
    ],
}


def _image_layer_for_page(page: dict) -> list[dict]:
    """根据 page.type 返回图片层定义。"""
    ptype = (page.get("type") or "content").lower()
    return _IMAGE_LAYOUTS.get(ptype, _IMAGE_LAYOUTS["content"])


def inject_page_image(svg: str, page_image_ref: str | None, page: dict) -> str:
    """在 SVG 顶层注入 <image> 元素（不依赖 LLM）。

    Args:
        svg: 原始 SVG 字符串
        page_image_ref: SVG 内可解析的图片引用，如 "images/architecture.png" 或 None
        page: page DSL dict（决定图片位置/尺寸/不透明度）

    Returns:
        注入了 <image> 的 SVG 字符串。
        若 page_image_ref 为空，函数无效。
    """
    if not page_image_ref:
        return svg

    # 防御：避免重复注入
    if page_image_ref in svg:
        return svg

    layers = _image_layer_for_page(page)
    if not layers:
        return svg

    image_tags: list[str] = []
    for layer in layers:
        role = layer.get("role", "decoration")
        name = layer.get("name", role)
        x, y, w, h = layer["x"], layer["y"], layer["w"], layer["h"]
        # 关键：data-pptx-role 必须是 lowercase kebab-case 合法枚举
        # （background/decoration/footer/header/logo/watermark/chrome），
        # 并把 <image> 包在 <g data-pptx-bounds="..."> 内（bounds 仅对 <g> 合法）
        image_tags.append(
            f'  <g id="page-image-{name}-wrap" data-pptx-bounds="{x} {y} {w} {h}">'
            f'\n    <image id="page-image-{name}" data-name="{name}" '
            f'data-pptx-role="{role}" '
            f'href="{page_image_ref}" '
            f'x="{x}" y="{y}" width="{w}" height="{h}" '
            f'opacity="{layer.get("opacity", 0.92)}" '
            f'preserveAspectRatio="{layer.get("preserveAspectRatio", "xMidYMid slice")}"/>'
            f'\n  </g>'
        )

    image_block = "\n".join(image_tags) + "\n"

    # 在 <svg> 后第一个非 defs 子元素之前注入（让图片在底层）
    # 策略：找到 </defs>（兼容 ns0: 前缀），如果有就插到其后；否则插到 <svg ...> 后
    has_defs = bool(re.search(r"</(?:ns\d+:)?defs>", svg))
    if has_defs:
        # 保留原命名空间前缀：分两种情况 sub
        if "</ns0:defs>" in svg:
            new_svg, n = re.subn(r"</ns0:defs>", "</ns0:defs>\n" + image_block, svg, count=1)
        else:
            new_svg, n = re.subn(r"</defs>", "</defs>\n" + image_block, svg, count=1)
    else:
        new_svg, n = re.subn(
            r"(<(?:ns\d+:)?svg\b[^>]*>)",
            r"\1\n" + image_block,
            svg, count=1,
        )
    return new_svg if n > 0 else svg
