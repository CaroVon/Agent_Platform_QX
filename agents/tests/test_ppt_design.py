"""
PptDesignAgent 单元测试 —— svg_author 创作辅助 + spec_lock/spec 生成
"""

import sys
from types import SimpleNamespace
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]  # ~/dev/agents
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "agent-platform"))

from agents.ppt_design_agent import svg_author as sa
from agents.ppt_design_agent.agent import _build_design_spec, _build_spec_lock, _get_reusable_project_dir
from agents.ppt_design_agent.agent import PptDesignAgent


def _page() -> dict:
    return {
        "id": "p1",
        "type": "market_overview",
        "title": "市场存在个性化缺口，TAM达500亿",
        "insight": "2023年市场规模500亿元（E001）",
        "components": [
            {"type": "metric", "data": {"value": "500亿", "label": "TAM"}},
            {"type": "card", "data": {"title": "核心差异化", "items": ["新国潮设计", "高密度面料"]}},
            {"type": "chart", "id": "c1", "data": {"chart_type": "bar",
                "items": [{"label": "A", "value": 1}, {"label": "B", "value": 3}]}},
        ],
    }


def test_build_page_prompt_contains_data_and_rules():
    theme = {"name": "象牙白+深蓝", "palette": {"bg": "#F7F6F0", "surface": "#FFFFFF",
        "primary": "#12355B", "accent": "#3D6491", "text": "#101820", "muted": "#6F7275"}}
    p = sa.build_page_prompt(_page(), theme, "设计简报：咨询风格", 0)
    assert "1280" in p and "720" in p
    assert "500亿" in p
    assert "#12355B" in p
    assert "data-pptx-replace-with" in p  # 原生图表标记说明
    assert "foreignObject" in p  # 禁用元素说明


def test_extract_and_validate_svg():
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720"><text x="10" y="20">市场存在个性化缺口，TAM达500亿</text><text x="10" y="60">2023年市场规模500亿元（E001）</text><rect x="0" y="0" width="100" height="50"/></svg>'
    assert sa.extract_svg("前缀说明 " + svg + " 后缀") == svg
    ok, issue = sa.validate_svg(svg, _page())
    assert ok, issue


def test_validate_rejects_overflow_and_forbidden():
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720"><text x="10" y="20">市场存在个性化缺口，TAM达500亿</text><text x="10" y="60">2023年市场规模500亿元（E001）</text><rect x="0" y="700" width="100" height="50"/></svg>'
    ok, issue = sa.validate_svg(svg, _page())
    assert not ok and "越界" in issue
    bad = '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720"><style>.x{}</style><text x="10" y="20">市场存在个性化缺口，TAM达500亿</text></svg>'
    ok2, issue2 = sa.validate_svg(bad, _page())
    assert not ok2 and "style" in issue2


def test_validate_native_contract_rejects_group_filter():
    svg = '<svg><defs><filter id="shadow" /></defs><g filter="url(#shadow)"></g></svg>'
    ok, issue = sa.validate_native_contract(svg)
    assert not ok
    assert "<g>" in issue


def test_validate_native_contract_rejects_degenerate_gradient_line():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720">'
        '<defs><linearGradient id="arrowGrad"><stop offset="0" stop-color="#123456" />'
        '<stop offset="1" stop-color="#654321" /></linearGradient></defs>'
        '<line x1="10" y1="20" x2="100" y2="20" stroke="url(#arrowGrad)" />'
        '</svg>'
    )
    ok, issue = sa.validate_native_contract(svg)
    assert not ok
    assert "gradient" in issue.lower()


def test_image_manifest_handles_competitor_matrix_theme():
    from agents.ppt_design_agent import image_plan

    manifest = image_plan.build_image_manifest(
        {"pages": [{"type": "competitor_matrix", "title": "竞品矩阵"}]},
        "测试产品",
        "product-1",
    )
    assert manifest["items"][-1]["filename"] == "page_01_concept.png"


def test_image_generation_cache_skips_second_generation(tmp_path, monkeypatch):
    from agents.ppt_design_agent import agent as agent_module

    class ImagePlan:
        @staticmethod
        def build_image_manifest(**_kwargs):
            return {"project": "demo", "product_id": "p1", "items": [
                {"filename": "hero.png", "prompt": "hero", "asset_kind": "hero"},
            ]}

        @staticmethod
        def sync_to_design_studio(**_kwargs):
            return {"assets": [{"name": "hero.png", "url": "hero.png", "size": 1}],
                    "hero": "hero.png", "by_kind": {}, "asset_dir": ""}

    calls = []

    class _FakeProc:
        """模拟 image_gen.py 子进程：communicate 时落图，returncode=0。"""

        returncode = 0

        def __init__(self, command, **_kwargs):
            self._command = command
            calls.append(command)

        def communicate(self, timeout=None):
            Path(self._command[-1]).joinpath("hero.png").write_bytes(b"image")
            return "", ""

        def kill(self):
            pass

    monkeypatch.setattr(agent_module.subprocess, "Popen", _FakeProc)
    agent = object.__new__(PptDesignAgent)
    kwargs = dict(
        project_dir=tmp_path / "project",
        presentation={"pages": []},
        idea="demo",
        product_id="p1",
        theme_name="咨询风",
        accent_color="#123456",
        out_dir=tmp_path,
        image_plan_module=ImagePlan,
    )
    kwargs["project_dir"].mkdir()
    agent._generate_images_v2(**kwargs)
    agent._generate_images_v2(**kwargs)
    assert len(calls) == 1


def test_chinese_product_id_does_not_use_shared_product_directory(tmp_path):
    project_dir = _get_reusable_project_dir(tmp_path, "面向健身房的智能私教镜")
    assert project_dir.name.startswith("idea-")
    assert project_dir.name != "product"


def test_fallback_svg_keeps_content():
    svg = sa.fallback_svg(_page(), None)
    assert "500亿" in svg and "市场存在个性化缺口" in svg
    assert svg.startswith("<svg")


def test_spec_lock_and_design_spec():
    presentation = {"title": "Demo", "theme": {"id": "cyber-crimson", "name": "经典深红咨询",
        "palette": {"bg": "#F3F4EF", "surface": "#FFFFFF", "primary": "#8B1E1E",
                    "accent": "#B54B4B", "text": "#111111", "muted": "#555555"}},
        "pages": [_page()]}
    lock = _build_spec_lock(presentation, "Demo 产品")
    assert "ppt-master-schema: spec-lock/v1" in lock
    assert "viewBox: 0 0 1280 720" in lock
    assert "mode: flat" in lock
    spec = _build_design_spec(presentation, "Demo 产品", "咨询风格简报")
    assert "## 产品：Demo 产品" in spec
    assert "经典深红咨询" in spec
