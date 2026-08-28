"""SVG 内核开关层（P1）：Python 实现 ↔ Rust 扩展（qx_svg_tools）。

默认 rust（等价性由 tests/test_svg_qa.py 双实现对照保障）；扩展缺失或
显式 AGENT_PLATFORM_SVG_KERNEL=python 时回退 Python 实现。
"""
from __future__ import annotations

import os
from functools import lru_cache


@lru_cache()
def _rust() -> object | None:
    if os.environ.get("AGENT_PLATFORM_SVG_KERNEL", "rust").lower() == "python":
        return None
    try:
        import qx_svg_tools  # type: ignore

        return qx_svg_tools
    except Exception:  # noqa: BLE001 —— 扩展缺失回退 Python
        return None


def rust_enabled() -> bool:
    return _rust() is not None


def snap(svg: str, allowed: tuple) -> tuple[str, dict]:
    """字号收敛：Rust 快路径（计数）或 Python 原路径（详细 info）。"""
    mod = _rust()
    if mod is not None:
        out, count = mod.snap_font_sizes(svg)
        import re

        kept = sorted({int(s) for s in re.findall(r'font-size="([\d.]+)"', out)})
        return out, {"snapped": [""] * count, "kept_unique": kept,
                     "snap_count_rust": count}
    from agents.ppt_design_agent import cross_page

    return cross_page.snap_font_sizes(svg)


def qa_fast(svg: str, page_type: str, palette: list[str]) -> list[str]:
    """元素预算 + 色板 + 字号三项快检（Rust）；未启用返回空（走 Python 全量）。"""
    mod = _rust()
    if mod is None:
        return []
    return (list(mod.qa_element_budget(svg, page_type))
            + list(mod.qa_palette(svg, palette))
            + list(mod.qa_font_sizes(svg)))
