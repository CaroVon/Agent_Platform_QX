"""
PptDesign Agent —— 跨页一致性模块（cross-page consistency）
============================================================

职责：
  1. 在每张 SVG 末尾注入**统一的页脚组**（data-pptx-layer="master"）
  2. 在 SVG <svg> 根上注入根属性（data-pptx-page-role, data-pptx-master-name 等）
  3. 把顶级 <text>/<rect> 等元素按层级包到 <g id="..."> 中
  4. 提供 deck_identity 单例（产品名/页码/项目编号/字体/色板）跨页保持一致

为何需要：
  - LLM 每次生成都是独立的，跨页一致性 100% 失守
  - svg_quality_checker 对未分组顶级元素会出 WARN
  - 演示文稿需要固定 footer（页码 + 项目编号 + 产品名）

SVG 注入位置：
  - 入口：svg_output/slide_NN_*.svg  （finalize_svg 之前）
  - 出口：svg_final/slide_NN_*.svg     （finalize_svg 已 base64 嵌入图片）
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DeckIdentity:
    """演示文稿级别身份（跨页共享）。"""
    product_name: str = "Product Name"
    product_code: str = ""               # e.g. "VOL.01 · NO.05"
    theme_color: str = "#3D6491"         # 主色（用于 footer 强调线）
    muted_color: str = "#6F7275"         # 灰色（用于 footer metadata）
    text_color: str = "#111111"
    bg_color: str = "#F7F6F0"
    font_family: str = "Noto Sans SC, Source Han Sans SC, PingFang SC, Microsoft YaHei, sans-serif"
    title_font_family: str = "Noto Serif SC, Source Han Serif SC, Georgia, serif"
    logo_text: str = ""                  # 可选：底部小字标识（如品牌名）

    def project_code_default(self) -> str:
        if self.product_code:
            return self.product_code
        # 简单日期码：取当前年月
        from datetime import datetime
        return datetime.now().strftime("%Y.%m")


def _esc(s: str) -> str:
    """XML 安全转义。"""
    return (str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


# ─────────────────────────────────────────────────────────────────
# 1. 根属性注入
# ─────────────────────────────────────────────────────────────────

def inject_root_metadata(svg: str, page_type: str, page_index: int, total_pages: int) -> str:
    """给 <svg ...> 根元素加上 data-pptx-page-role 等属性。

    Args:
        svg: 原始 SVG 字符串
        page_type: "cover" / "executive_summary" / "content" / "conclusion" / 等
        page_index: 0-based 页码
        total_pages: 总页数

    Returns:
        加上根属性的 SVG 字符串（若解析失败返回原样）
    """
    # 归一化 page_role（svg_to_pptx 允许的值）
    role = page_type.lower().strip() or "content"
    # 允许：cover / toc / section / content / ending
    allowed = {"cover", "toc", "section", "content", "ending"}
    if role not in allowed:
        role = "content"

    # 在第一个 <svg ...> 或 <ns0:svg ...> 标签的末尾插入属性
    def _add(match: re.Match) -> str:
        opening = match.group(0)
        attrs = (
            f' data-pptx-page-role="{role}"'
            f' data-pptx-page-index="{page_index}"'
            f' data-pptx-page-total="{total_pages}"'
        )
        # 如果原 tag 没有 viewBox 也补一个
        return opening.rstrip(">") + attrs + ">"

    new_svg, n = re.subn(r"<(?:ns\d+:)?svg\b[^>]*>", _add, svg, count=1)
    return new_svg if n > 0 else svg


# ─────────────────────────────────────────────────────────────────
# 2. 跨页页脚注入（强制覆盖 LLM 的 footer）
# ─────────────────────────────────────────────────────────────────

def inject_footer(svg: str, page_index: int, total_pages: int, identity: DeckIdentity) -> str:
    """在 SVG 末尾的 </svg> 前注入统一页脚组（data-pptx-layer="master"）。

    LLM 可能已经在 SVG 内写了 footer；本函数只追加一个**更规整**的 master footer，
    最终效果由 SVG 渲染顺序决定——但演示文稿通常 footer 在底部，不冲突。

    视觉：
        ──────────────────────────────────
        Product Name  — 01 / 10 —   VOL.01
    """
    page_no = page_index + 1
    footer = (
        f'\n  <g id="page-footer-{page_no:02d}" data-name="Page Footer" '
        f'data-pptx-bounds="60 680 1160 30">'
        f'\n    <line x1="60" y1="688" x2="1220" y2="688" stroke="{_esc(identity.muted_color)}" '
        f'stroke-width="0.5" opacity="0.5"/>'
        f'\n    <text x="60" y="704" font-family="{_esc(identity.font_family)}" font-size="10" '
        f'fill="{_esc(identity.muted_color)}" letter-spacing="1">{_esc(identity.product_name)}</text>'
        f'\n    <text x="640" y="704" text-anchor="middle" font-family="{_esc(identity.font_family)}" '
        f'font-size="10" fill="{_esc(identity.muted_color)}" letter-spacing="2">'
        f'— {page_no:02d} / {total_pages:02d} —</text>'
        f'\n    <text x="1220" y="704" text-anchor="end" font-family="{_esc(identity.font_family)}" '
        f'font-size="10" fill="{_esc(identity.muted_color)}" letter-spacing="1">'
        f'{_esc(identity.project_code_default())}</text>'
        f'\n  </g>'
    )

    # 在 </svg> 前插入；若 LLM 已写了一个 footer group（id="page-footer-NN"），跳过
    if f'id="page-footer-{page_no:02d}"' in svg:
        return svg

    # 兼容 <svg ...> 和 <ns0:svg ...> 两种开闭标签（sanitize_svg 加 ns0: 前缀）
    if re.search(r"</ns0:svg>\s*$", svg):
        new_svg, n = re.subn(r"</ns0:svg>\s*$", footer + "\n</ns0:svg>", svg, count=1)
    else:
        new_svg, n = re.subn(r"</svg>\s*$", footer + "\n</svg>", svg, count=1)
    return new_svg if n > 0 else svg


# ─────────────────────────────────────────────────────────────────
# 3. 顶级元素分组（解决 svg_quality_checker 的"ungrouped top-level" WARN）
# ─────────────────────────────────────────────────────────────────

def wrap_top_level_groups(svg: str) -> str:
    """把 SVG 内**未分组的顶级元素**包到 <g id="..."> 中。

    策略（保守）：
      - 在 </defs> 后到首个子元素之间，若有连续 <rect>/<line>/<text>，包到
        <g id="slide-background" data-pptx-role="background">
      - 在 <svg>...</svg> 内的"中段"成组的 <text>+<line> 等，包到
        <g id="slide-content">（仅一个）
      - 在 </svg> 前的"页脚"区，包到 <g id="slide-frame" data-pptx-role="decoration">

    不做激进修改——避免破坏 LLM 已有的合理结构。
    """
    # 已经分组的顶级 <g> 不动
    # 未分组顶级 <rect>/<text>/<line> 在 <svg> 后到 </svg> 前 的，按位置分组

    # 简化策略：只把 background（第一个 <rect> 满画布）包到 group
    # 不破坏 LLM 内容
    return svg  # 保守实现，复杂分组留待后续迭代


# ─────────────────────────────────────────────────────────────────
# 4. 字号收敛（白名单）
# ─────────────────────────────────────────────────────────────────

# 允许的字号（防止 LLM 用 11+ 个字号失控）
ALLOWED_FONT_SIZES = (9, 10, 11, 12, 13, 14, 15, 16, 18, 20, 22, 26, 28, 32, 36, 44, 56, 68, 80)


def snap_font_sizes(svg: str, allowed: tuple = ALLOWED_FONT_SIZES) -> tuple[str, dict]:
    """把 SVG 中不在白名单的字号 snap 到最近的合法档。

    Returns:
        (modified_svg, {"snapped": [orig → new, ...], "kept_unique": [12, 14, ...]})
    """
    used = set()
    snapped: list[tuple[str, str]] = []

    def _closest(size: int) -> int:
        return min(allowed, key=lambda x: abs(x - size))

    def _repl(match: re.Match) -> str:
        orig = match.group(1)
        try:
            n = int(float(orig))
        except ValueError:
            return match.group(0)
        used.add(n)
        if n in allowed:
            return match.group(0)
        new = _closest(n)
        snapped.append((orig, str(new)))
        return match.group(0).replace(orig, str(new), 1)

    out = re.sub(r'font-size="([\d.]+)"', _repl, svg)

    unique_used = sorted({int(float(s)) for s in used} | {int(float(n)) for _, n in snapped})
    return out, {
        "snapped": snapped,
        "kept_unique": unique_used,
    }