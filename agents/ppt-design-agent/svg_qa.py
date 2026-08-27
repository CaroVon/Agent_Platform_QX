"""SVG 页面确定性质量门禁（P2.5）—— 对照 svg_final 参考基线的量化阈值。

质量基线（源自三个参考 deck 的实测）：
  - 主页面平均：text 54-57 / rect 18-20 / 渐变 2-3 / 图片 1-2 / 色板 6-9 全在 spec palette
  - 页脚双格式（细线 + — NN / MM —）、根属性 data-pptx-page-*、字号白名单
  - MOD 页数据可溯源（[A编号]/ASIN/*Rainforest 脚注）

门禁策略（用户确认：硬门禁+返工）：
  - 不达标 → 带结构化反馈重渲染一次（authoring 循环内）
  - 仍不达标 → 放量并标记（stats.qa_warnings / deck_audit.json）
阈值保守设置（防止返工风暴）：下限约为参考均值的 1/3-1/2。
"""
from __future__ import annotations

import re

_BANNED_PLACEHOLDERS = ("解读缺失", "TODO：", "XXX", "？？？")
_MOD_CITATION_MARKS = ("*Rainforest", "[A", "ASIN", "B0")

# 裸占位词：<text> 整节点内容恰为图表类型词（LLM 未画图只留词，
# 曾致"timeline"占位的空图表页通过 QA 混入成品）
_BARE_PLACEHOLDER_RE = re.compile(
    r">\s*(timeline|flowchart|chart|diagram|graph|TBD|待补|占位)\s*<", re.IGNORECASE)

# 硬性失败：重做预算耗尽也不得放行（放行 = 成品出现空壳/占位页），
# 其余（色板/字号等）保持"带警告放行"的原有策略
_HARD_ISSUE_PREFIXES = ("信息密度不足", "视觉结构不足", "缺少视觉层次", "禁用空占位")


def is_hard_issue(issue: str) -> bool:
    return issue.startswith(_HARD_ISSUE_PREFIXES)


def _hex_to_rgb(value: str) -> tuple[int, int, int] | None:
    v = value.lstrip("#")
    if len(v) == 8:
        v = v[:6]
    if len(v) != 3 and len(v) != 6:
        return None
    if len(v) == 3:
        v = "".join(ch * 2 for ch in v)
    try:
        return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)
    except ValueError:
        return None


def _near_any(color: tuple[int, int, int], allowed: list[tuple[int, int, int]],
              tol: int = 52) -> bool:
    return any(abs(color[0] - a[0]) <= tol and abs(color[1] - a[1]) <= tol
               and abs(color[2] - a[2]) <= tol for a in allowed)


def qa_page(svg: str, page: dict, theme: dict | None,
            page_image: str | None = None) -> list[str]:
    """单页确定性 QA。返回问题列表（空 = 通过）。

    检查项：画布契约 / 色板纪律 / 字号白名单 / 页脚与根属性 /
    元素预算（信息密度下限）/ 禁用空占位 / MOD 页数据溯源。
    """
    issues: list[str] = []
    if not svg:
        return ["空 SVG"]
    page_type = (page.get("type") or "content").lower()
    is_cover = page_type in ("cover", "conclusion")
    is_mod = page_type.startswith("mod_")

    # 1. 画布契约
    if 'viewBox="0 0 1280 720"' not in svg:
        issues.append("画布契约缺失（viewBox 0 0 1280 720）")

    # 2. 元素预算（信息密度下限；封面/结语豁免）。
    #    注意 sanitize_svg 的 ET 往返可能引入 ns0: 前缀，正则须兼容。
    if not is_cover:
        n_text = len(re.findall(r"<(?:ns\d+:)?text\b", svg))
        n_rect = len(re.findall(r"<(?:ns\d+:)?rect\b", svg))
        n_shape = len(re.findall(r"<(?:ns\d+:)?(?:circle|ellipse|path|polygon)\b", svg))
        has_defs = bool(re.search(r"<(?:ns\d+:)?defs\b", svg)) or "linearGradient" in svg
        if n_text < 8:
            issues.append(f"信息密度不足：<text> 仅 {n_text} 个（参考基线≥35，下限 8）")
        if n_rect < 4 and n_shape < 6:
            issues.append(f"视觉结构不足：rect {n_rect} / 图形 {n_shape}（参考基线 rect≥14）")
        if not has_defs and n_rect + n_shape < 12:
            # 参考页均有渐变/图案或足量卡片结构；纯文本墙不放行
            issues.append("缺少视觉层次（无 defs/渐变且图形元素过少）")

    # 3. 色板纪律：所有 hex 颜色须在主题色板邻域（或中性灰/白色）
    palette = (theme or {}).get("palette") or {}
    allowed_hex = ["#f8fafc", "#ffffff", "#0f172a", "#64748b", "#4f46e5", "#6366f1"]
    allowed_hex += [str(v) for v in palette.values() if v]
    allowed_rgb = [rgb for rgb in (_hex_to_rgb(h) for h in allowed_hex) if rgb]
    hexes = set(re.findall(r'(?:fill|stroke)="(#[0-9A-Fa-f]{3,8})"', svg))
    off_palette: list[str] = []
    for hx in hexes:
        rgb = _hex_to_rgb(hx)
        if rgb is None:
            continue
        neutral = max(rgb) - min(rgb) <= 24  # 中性灰（含黑白）
        if not (neutral or _near_any(rgb, allowed_rgb)):
            off_palette.append(hx)
    if off_palette:
        issues.append(f"色板纪律：{len(off_palette)} 个色值偏离主题（如 {sorted(off_palette)[:3]}）")

    # 4. 字号白名单（cross_page snap 后应为合法档；此处兜底核查）
    from agents.ppt_design_agent.cross_page import ALLOWED_FONT_SIZES
    sizes = {int(float(s)) for s in re.findall(r'font-size="([\d.]+)"', svg)}
    bad_sizes = sorted(s for s in sizes if s not in ALLOWED_FONT_SIZES)
    if bad_sizes:
        issues.append(f"字号越档：{bad_sizes[:5]}")

    # 5. 页脚与根属性（注入层产物；authoring 后应有）
    if not is_cover:
        if not re.search(r"— \d{2} / \d{2} —", svg):
            issues.append("页脚格式缺失（— NN / MM —）")
    if "data-pptx-page-role" not in svg:
        issues.append("根属性缺失（data-pptx-page-role）")

    # 6. 禁用空占位
    for banned in _BANNED_PLACEHOLDERS:
        if banned in svg:
            issues.append(f"禁用空占位：{banned}")
            break
    else:
        m = _BARE_PLACEHOLDER_RE.search(svg)
        if m:
            issues.append(f"禁用空占位：裸占位词充当图表（{m.group(1)}）")

    # 7. MOD 页数据溯源
    if is_mod and not any(mark in svg for mark in _MOD_CITATION_MARKS):
        issues.append("MOD 页缺数据溯源标记（[A编号]/ASIN/*Rainforest）")

    # 8. 图片预期（配置了页图而未引用；兼容 sanitize 后的 ns0: 前缀）
    if page_image and not re.search(r"<(?:ns\d+:)?image\b", svg):
        issues.append("未引用页图（图片会由注入层补，但页面应为其留白布局）")

    # 8b. 图片退化不可见：LLM 写出的 assets 引用若 opacity≈0 或被压成细条
    #     （曾致 P12 矩阵图表页"有图不可见"，且绕过注入层的去重短路）
    for m in re.finditer(r"<(?:ns\d+:)?image\b[^>]*>", svg):
        tag = m.group(0)
        if "images/" not in tag and "page-image-" not in tag:
            continue

        def _attr(name, default):
            am = re.search(rf'\b{name}="([^"]*)"', tag)
            return am.group(1) if am else default

        try:
            w = float(_attr("width", "0") or 0)
            h = float(_attr("height", "0") or 0)
            op = float(_attr("opacity", "1") or 1)
        except ValueError:
            continue
        if op < 0.15:
            issues.append(f"图片退化不可见：opacity={op}（{w:.0f}×{h:.0f}）")
            break
        if w >= 80 and h < 40:
            issues.append(f"图片退化不可见：{w:.0f}×{h:.0f} 细条")
            break

    # 9. 配图遮挡（本质防护：注入层图片位于 </defs> 后的底层，
    #    其后任何不透明矩形若完全覆盖图片 bbox → 视觉不可见）
    if page_image:
        issues.extend(_occluded_image_issues(svg))

    return issues[:8]


def _occluded_image_issues(svg: str) -> list[str]:
    """检测被后续不透明矩形完全遮挡的 <image>（SVG 按文档顺序绘制，后画覆盖先画）。"""
    import xml.etree.ElementTree as ET

    try:
        root = ET.fromstring(svg)
    except ET.ParseError:
        return []
    images: list[tuple[float, float, float, float]] = []
    rects: list[tuple[float, float, float, float, float, str]] = []
    for el in root.iter():
        tag = str(el.tag).rsplit("}", 1)[-1].lower()
        if tag not in ("image", "rect"):
            continue
        try:
            x = float(el.get("x", 0)); y = float(el.get("y", 0))
            w = float(el.get("width", 0)); h = float(el.get("height", 0))
        except ValueError:
            continue
        seq = len(rects) + len(images)
        if tag == "image":
            images.append((x, y, w, h, seq, "img"))
        else:
            opacity = 1.0
            for attr in ("opacity", "fill-opacity"):
                try:
                    if el.get(attr) is not None:
                        opacity = min(opacity, float(el.get(attr)))
                except ValueError:
                    pass
            fill = (el.get("fill") or "").lower()
            if fill in ("none", "transparent") or opacity < 0.85 or w * h < 10000:
                continue  # 透明/装饰细线不构成遮挡
            rects.append((x, y, w, h, seq, fill))
    out: list[str] = []
    for ix, iy, iw, ih, iseq, _ in images:
        if iw < 40 or ih < 40:
            continue
        for rx, ry, rw, rh, rseq, fill in rects:
            if rseq <= iseq:
                continue
            if rx <= ix and ry <= iy and rx + rw >= ix + iw and ry + rh >= iy + ih:
                out.append(
                    f"配图 ({ix:.0f},{iy:.0f},{iw:.0f}×{ih:.0f}) 被其后不透明矩形"
                    f" ({fill}) 完全遮挡——图片会存在于文件但视觉不可见")
                break
    return out

def qa_feedback_text(issues: list[str]) -> str:
    """问题列表 → authoring 反馈文本。"""
    return "；".join(issues)
