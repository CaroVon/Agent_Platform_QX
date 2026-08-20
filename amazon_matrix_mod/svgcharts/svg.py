"""SVG 基础构建 —— ElementTree 封装（默认命名空间 + 数字格式化）。"""
from __future__ import annotations

import xml.etree.ElementTree as ET

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)


def q(tag: str) -> str:
    return f"{{{SVG_NS}}}{tag}"


def el(parent, tag: str, **attrs) -> ET.Element:
    """创建 SVG 子元素；值为 None 的属性跳过，数值自动格式化。"""
    e = ET.SubElement(parent, q(tag))
    for k, v in attrs.items():
        if v is None:
            continue
        if isinstance(v, float):
            e.set(k.replace("_", "-"), fmt(v))
        else:
            e.set(k.replace("_", "-"), str(v))
    return e


def fmt(v: float) -> str:
    """数值输出：最多 2 位小数，去尾零（避免 SVG 里的浮点噪音）。"""
    s = f"{v:.2f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


def text(parent, x: float, y: float, content: str, *, size=12, fill="#101820",
         weight=None, family=None, anchor=None, opacity=None, letter_spacing=None):
    t = el(parent, "text", x=x, y=y, font_size=size, fill=fill,
           font_family=family, font_weight=weight,
           text_anchor=anchor, opacity=opacity, letter_spacing=letter_spacing)
    t.text = content
    return t


def svg_document(w: float, h: float, bg: str | None = "#F7F6F0") -> ET.Element:
    """根 SVG（viewBox "0 0 W H"，满足 svg_to_pptx canvas contract）。"""
    root = ET.Element(q("svg"), {
        "width": fmt(w), "height": fmt(h),
        "viewBox": f"0 0 {fmt(w)} {fmt(h)}",
    })
    if bg:
        el(root, "rect", x=0, y=0, width=w, height=h, fill=bg)
    return root


def save(root: ET.Element, path: str) -> str:
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(path, encoding="unicode", xml_declaration=False)
    return path
