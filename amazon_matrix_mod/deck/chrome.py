"""deck 页面 chrome —— 对齐主管线（ppt-design-agent cross_page.py）规范。

- 页脚：y=688 细线（muted 50% 透明）+ 左产品名 / 中 — NN / MM — / 右项目码，
  10px muted + letter-spacing，封面不注入
- 根属性：data-pptx-page-role/-page-index/-page-total
- 字号白名单 snap（19 档，与主管线 ALLOWED_FONT_SIZES 一致）
本地实现避免跨包耦合；几何/命名与 cross_page.py 保持一致以获得同样的
svg_to_pptx master 层处理。
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

# 与 ppt-design-agent cross_page.ALLOWED_FONT_SIZES 完全一致
ALLOWED_FONT_SIZES = [9, 10, 11, 12, 13, 14, 15, 16, 18, 20, 22,
                      26, 28, 32, 36, 44, 56, 68, 80]


class DeckIdentity:
    """跨页共享的页脚身份（产品名/项目码/主题色）。"""

    def __init__(self, product_name: str, project_code: str):
        self.product_name = (product_name or "")[:24]
        # 项目码：YYYY.MM（与主管线一致）
        self.project_code = project_code


def set_page_metadata(root: ET.Element, index: int, total: int,
                      role: str = "content") -> None:
    """根 SVG 属性注入（svg_to_pptx master 层契约）。"""
    root.set("data-pptx-page-role", role)
    root.set("data-pptx-page-index", str(index))
    root.set("data-pptx-page-total", str(total))


def inject_footer(root: ET.Element, identity: DeckIdentity, page_num: int,
                  total: int, *, muted: str) -> None:
    """y=688 页脚：细线 + 左产品名 / 中 — NN / MM — / 右项目码。

    注：flat pptx_structure 模式禁用 data-pptx-layer 元数据，页脚用普通
    <g>（与主管线视觉一致，结构标记省略）。
    """
    if page_num <= 1:  # 封面不注入页脚
        return
    g = ET.SubElement(root, "{http://www.w3.org/2000/svg}g")
    line = ET.SubElement(g, "{http://www.w3.org/2000/svg}line")
    line.set("x1", "56"); line.set("y1", "688")
    line.set("x2", "1224"); line.set("y2", "688")
    line.set("stroke", muted); line.set("stroke-width", "0.5")
    line.set("opacity", "0.5")
    for x, anchor, content in (
            (56, "start", identity.product_name),
            (640, "middle", f"— {page_num:02d} / {total:02d} —"),
            (1224, "end", identity.project_code)):
        t = ET.SubElement(g, "{http://www.w3.org/2000/svg}text")
        t.set("x", str(x)); t.set("y", "702")
        t.set("font-size", "10"); t.set("fill", muted)
        t.set("text-anchor", anchor); t.set("letter-spacing", "1.5")
        t.set("font-family",
              "Noto Sans SC, Source Han Sans SC, PingFang SC, "
              "Microsoft YaHei, sans-serif")
        t.text = content


def snap_font_sizes(root: ET.Element) -> None:
    """全部 text font-size 吸附到白名单档位（主管线 19 档）。"""
    for t in root.iter("{http://www.w3.org/2000/svg}text"):
        raw = t.get("font-size")
        if not raw:
            continue
        try:
            v = float(raw)
        except ValueError:
            continue
        snapped = min(ALLOWED_FONT_SIZES, key=lambda s: abs(s - v))
        t.set("font-size", str(snapped))
