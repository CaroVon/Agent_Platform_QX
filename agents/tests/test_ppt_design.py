"""
PptDesignAgent 单元测试 —— dsl_to_svg 渲染 + spec_lock 生成
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]  # ~/dev/agents
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "agent-platform"))

from agent_platform.schemas.presentation import Theme
from agents.ppt_design_agent import dsl_to_svg as dsl
from agents.ppt_design_agent.agent import _build_design_spec, _build_spec_lock


def _page() -> dict:
    return {
        "title": "市场存在个性化缺口，TAM达500亿",
        "type": "market_overview",
        "insight": "2023年市场规模500亿元（E001）",
        "components": [
            {"type": "metric", "data": {"value": "500亿", "label": "TAM"}},
            {"type": "card", "data": {"title": "核心差异化", "items": ["新国潮设计", "高密度面料"]}},
            {"type": "table", "data": {"columns": ["趋势", "说明"], "rows": [["AI监测", "渗透率15%"]]}},
        ],
    }


def test_render_page_svg_contains_all_content():
    theme = Theme(id="cyber-ivory-navy", name="象牙白+深蓝", palette={
        "bg": "#F7F6F0", "surface": "#FFFFFF", "primary": "#12355B",
        "accent": "#3D6491", "text": "#101820", "muted": "#6F7275"})
    r = dsl.render_page_svg(_page(), theme.model_dump(), 0)
    svg = r["svg"]
    assert svg.startswith("<svg")
    assert r["overflow"] is False
    assert "500亿" in svg
    assert "新国潮设计" in svg
    assert "AI监测" in svg
    assert "#12355B" in svg


def test_render_quadrant_svg():
    page = {
        "title": "竞品矩阵", "type": "competitor_matrix", "insight": "中端空白",
        "components": [{"type": "matrix", "data": {"chart_type": "quadrant",
            "x_axis": "价格", "y_axis": "功能",
            "points": [{"name": "A", "x": 0.2, "y": 0.7, "kind": "competitor"},
                       {"name": "本产品", "x": 0.8, "y": 0.8, "kind": "product"}]}}],
    }
    svg = dsl.render_page_svg(page, Theme().model_dump(), 1)["svg"]
    assert "circle" in svg and "本产品" in svg


def test_render_project_svgs_writes_files(tmp_path):
    result = dsl.render_project_svgs(
        {"pages": [_page()], "theme": Theme().model_dump()}, str(tmp_path))
    assert result["files"] == ["slide_01_market_overview.svg"]
    assert result["overflow_pages"] == []
    assert (tmp_path / "svg_output" / result["files"][0]).is_file()


def test_spec_lock_and_design_spec():
    presentation = {"title": "Demo", "theme": Theme(id="cyber-crimson", name="经典深红咨询",
        palette={"bg": "#F3F4EF", "surface": "#FFFFFF", "primary": "#8B1E1E",
                 "accent": "#B54B4B", "text": "#111111", "muted": "#555555"}).model_dump(),
        "pages": [_page()]}
    lock = _build_spec_lock(presentation, "Demo 产品")
    assert "ppt-master-schema: spec-lock/v1" in lock
    assert "viewBox: 0 0 1280 720" in lock
    assert "mode: flat" in lock
    assert "P01: dense" in lock
    spec = _build_design_spec(presentation, "Demo 产品", "咨询风格简报")
    assert "## 产品：Demo 产品" in spec
    assert "经典深红咨询" in spec
