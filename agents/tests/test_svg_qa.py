"""SVG 质量门禁测试（P2.5：对照 svg_final 参考基线的量化阈值）。"""

from __future__ import annotations

import sys
from pathlib import Path

_SYS_ROOT = Path(__file__).resolve().parents[2]
for p in (str(_SYS_ROOT), str(_SYS_ROOT / "agent-platform")):
    if p not in sys.path:
        sys.path.insert(0, p)

from agents.ppt_design_agent.svg_qa import qa_page  # noqa: E402

_THEME = {"palette": {"bg": "#F6F6F4", "surface": "#FFFFFF", "primary": "#2B2A26",
                      "accent": "#A87932", "text": "#0f172a", "muted": "#64748b"}}

_THIN = """<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
<rect width="1280" height="720" fill="#F6F6F4"/>
<text x="60" y="80" font-size="26" fill="#2B2A26">标题</text>
<text x="60" y="120" font-size="14" fill="#2E7D32">解读缺失</text>
<text x="60" y="160" font-size="13" fill="#101820">一行</text>
<text x="60" y="700" font-size="11" fill="#64748b">— 01 / 19 —</text>
</svg>"""

_RICH_BODY = "\n".join(
    f'<text x="60" y="{y}" font-size="14" fill="#2B2A26">[A{i}] 数据行 {i} · B0TEST</text>'
    for i, y in enumerate(range(200, 640, 40))
)
_RICH_CARDS = "\n".join(
    f'<rect x="{x}" y="580" width="120" height="60" fill="#FFFFFF" stroke="#A87932"/>'
    for x in range(60, 900, 150)
)
_RICH = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720" data-pptx-page-role="content" data-pptx-page-index="2" data-pptx-page-total="19">
<defs><linearGradient id="g"><stop offset="0" stop-color="#2B2A26"/><stop offset="1" stop-color="#F6F6F4"/></linearGradient></defs>
<rect width="1280" height="720" fill="#F6F6F4"/>
{_RICH_BODY}
{_RICH_CARDS}
<text x="60" y="700" font-size="10" fill="#64748b">— 02 / 19 —</text>
</svg>"""


def test_thin_page_fails_multiple_checks():
    issues = qa_page(_THIN, {"type": "mod_overview"}, _THEME, None)
    joined = "；".join(issues)
    assert "信息密度不足" in joined
    assert "色板纪律" in joined          # Material 绿 #2E7D32 越板
    assert "禁用空占位" in joined         # 解读缺失
    assert "MOD 页缺数据溯源" in joined
    assert "根属性缺失" in joined


def test_rich_page_passes():
    assert qa_page(_RICH, {"type": "content"}, _THEME, None) == []


def test_mod_page_requires_citation():
    import re as _re
    rich_no_cite = _re.sub(r"\[A\d+\]", "x", _RICH).replace("B0TEST", "TEST")
    issues = qa_page(rich_no_cite, {"type": "mod_matrix"}, _THEME, None)
    assert any("数据溯源" in i for i in issues)
    # 带 [A 编号] 后通过
    assert not any("数据溯源" in i for i in qa_page(_RICH, {"type": "mod_matrix"}, _THEME, None))


def test_cover_exempt_from_density():
    """封面豁免信息密度/页脚检查（色板/字号/根属性仍检查；生产中字号已 snap）。"""
    cover = """<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720" data-pptx-page-role="cover" data-pptx-page-index="1" data-pptx-page-total="19">
<rect width="1280" height="720" fill="#F6F6F4"/>
<text x="640" y="360" font-size="44" fill="#2B2A26">标题</text>
</svg>"""
    assert qa_page(cover, {"type": "cover"}, _THEME, None) == []


def test_ns0_prefix_compat():
    """sanitize_svg 的 ET 往返会产生 ns0: 前缀——QA 正则必须兼容。"""
    ns0 = _RICH.replace("<text", "<ns0:text").replace("<rect", "<ns0:rect") \
               .replace("<defs", "<ns0:defs").replace("</text>", "</ns0:text>") \
               .replace("</rect>", "</ns0:rect>").replace("</defs>", "</ns0:defs>") \
               .replace("<linearGradient", "<ns0:linearGradient").replace("</linearGradient>", "</ns0:linearGradient>") \
               .replace("<stop", "<ns0:stop").replace("</stop>", "</ns0:stop>") \
               .replace("</svg>", "</ns0:svg>").replace("<svg ", "<ns0:svg ", 1)
    assert qa_page(ns0, {"type": "content"}, _THEME, None) == []


# ══════════════════════════════════════════════════════════
# P1 Rust 内核等价性（qx_svg_tools 可选，缺失时 skip）
# ══════════════════════════════════════════════════════════

def _rust():
    try:
        import qx_svg_tools
        return qx_svg_tools
    except ImportError:
        return None


def test_rust_equivalence_snap():
    rust = _rust()
    if rust is None:
        import pytest
        pytest.skip("qx_svg_tools 未安装")
    from agents.ppt_design_agent import cross_page
    cases = [_RICH, _THIN.replace("#2E7D32", "#12355B"),
             _RICH.replace('font-size="14"', 'font-size="15.5"'),
             _RICH.replace('font-size="44"', 'font-size="47"')]
    for svg in cases:
        py_svg, py_info = cross_page.snap_font_sizes(svg)
        rs_svg, rs_count = rust.snap_font_sizes(svg)
        assert py_svg == rs_svg, "snap 产物不一致"
        assert len(py_info["snapped"]) == rs_count, "snap 计数不一致"


def test_rust_equivalence_qa_budget_and_palette():
    rust = _rust()
    if rust is None:
        import pytest
        pytest.skip("qx_svg_tools 未安装")
    from agents.ppt_design_agent import svg_qa
    palette = list(_THEME["palette"].values())
    for svg, page in ((_RICH, "content"), (_THIN, "mod_overview"), (_RICH, "cover")):
        py = svg_qa.qa_page(svg, {"type": page}, _THEME, None)
        py_budget = [i for i in py if any(k in i for k in ("密度", "结构", "层次"))]
        py_palette = [i for i in py if "色板" in i]
        py_fonts = [i for i in py if "字号" in i]
        rs_budget = list(rust.qa_element_budget(svg, page))
        rs_palette = list(rust.qa_palette(svg, palette))
        rs_fonts = list(rust.qa_font_sizes(svg))
        # 判定等价：有问题/无问题的二值结论必须一致（文案措辞允许差异）
        assert bool(py_budget) == bool(rs_budget), (page, py_budget, rs_budget)
        assert bool(py_palette) == bool(rs_palette), (page, py_palette, rs_palette)
        assert bool(py_fonts) == bool(rs_fonts), (page, py_fonts, rs_fonts)


def test_rust_process_page_roundtrip():
    rust = _rust()
    if rust is None:
        import pytest
        pytest.skip("qx_svg_tools 未安装")
    r = rust.process_page(_THIN, "mod_overview", list(_THEME["palette"].values()))
    assert r["svg"] and isinstance(r["issues"], list) and len(r["issues"]) >= 3
    assert r["svg"].startswith("<svg")


def test_kernels_snap_fractional_regression():
    """回归：Rust 内核保留 10.5 原文时，包装层 kept 统计不得 int('10.5') 崩。"""
    from agents.ppt_design_agent import svg_kernels

    svg, info = svg_kernels.snap('<text font-size="10.5"/><text font-size="14"/>', tuple())
    assert 'font-size="10.5"' in svg  # 截断 10 合法 → 保留原文
    assert info["kept_unique"] == [10, 14]
