"""MOD 数据包 + enforce_mod_pages 确定性保底测试（P2.3）。"""

from __future__ import annotations

from agent_platform.harness.enforce_coverage import enforce_mod_pages
from agent_platform.harness.evidence_pack import build_mod_data_pack, render_mod_data_pack
from agent_platform.schemas.presentation import Presentation

from tests.test_workflow_graph import _full_deck  # 复用 10 页基础 deck


def _matrix() -> dict:
    return {
        "keyword": "wireless mouse",
        "marketplace": "amazon.com",
        "fetched_at": "2026-08-21T00:00:00Z",
        "products": [
            {"asin": f"B0TEST{i:02d}", "title": f"竞品 {i}", "brand": "Brand",
             "current_price": 9.9 + i, "rating": 4.5, "review_count": 100 * i + 1,
             "est_monthly_sales": 500 * i + 10, "bsr": i + 1,
             "is_fba": i % 2 == 0, "seller_type": "amz", "zone": "red_ocean"}
            for i in range(8)
        ],
        "zoning_rules": {"price_gap": {"p25": 10}},
        "llm_interpretation": {"verdict": "切入价格缺口带", "red_ocean": "头部集中"},
        "mod_charts": {
            "market_donut": {"title": "市场总览", "kind": "mod_overview",
                              "png": "charts/market_donut.png"},
            "matrix_scatter": {"title": "矩阵", "kind": "mod_matrix",
                                "svg": "charts/matrix_scatter.svg"},
        },
        "artifacts_paths": {
            "markdown": "studio_assets/p1/competitor_matrix/competitor_matrix.md",
            "charts": "studio_assets/p1/competitor_matrix/charts",
        },
        "full": {"executive_summary": "头部集中，价格缺口存在",
                 "m3_insights": {"insights": ["评论提及蓝牙断连"]}},
    }


def _state(matrix: dict | None) -> dict:
    state = {"idea": "wireless mouse", "product_id": "p1"}
    if matrix:
        state["competitor_matrix"] = matrix
        state["amazon_collection"] = {
            "keyword": "wireless mouse", "n_products": 8, "credits": 9,
            "price_range": {"min": 9.9, "max": 16.9, "avg": 13.4},
            "rating_avg": 4.5, "fetched_at": "2026-08-21T00:00:00Z",
            "top_asins": [], "zone_counts": {"red_ocean": 8},
        }
    return state


def test_build_mod_data_pack():
    pack = build_mod_data_pack(_state(_matrix()))
    assert pack and pack["available"]
    assert pack["n_products"] == 8
    assert len(pack["top_products"]) == 8
    assert pack["charts"]["market_donut"]["path"].endswith("charts/market_donut.png")
    assert "Rainforest" in pack["citation"]
    # 无矩阵 → None（无 MOD 章节）
    assert build_mod_data_pack(_state(None)) is None


def test_render_mod_data_pack():
    text = render_mod_data_pack(build_mod_data_pack(_state(_matrix())))
    assert "[A1]" in text and "*Rainforest" in text
    assert "market_donut" in text  # 图表资产对位提示
    assert render_mod_data_pack(None) == ""


def _deck() -> Presentation:
    return Presentation(title="t", pages=_full_deck()["pages"])


def test_enforce_mod_pages_appends_blueprint():
    pres = _deck()
    pack = build_mod_data_pack(_state(_matrix()))
    out = enforce_mod_pages(pres, pack)
    mod_types = [p.type for p in out.pages if str(p.type).startswith("mod_")]
    assert mod_types == ["mod_overview", "mod_matrix", "mod_spec_comparison",
                         "mod_sku_analysis", "mod_actions"]
    # MOD 页位于尾部（附录式章节），组件全部带真实数据/图表引用
    overview = next(p for p in out.pages if p.type == "mod_overview")
    comp_types = [c.type for c in overview.components]
    assert "metric" in comp_types and "chart" in comp_types
    # 引用脚注组件存在（数据溯源）
    assert any("Rainforest" in str(c.data.get("text", "")) for c in overview.components)


def test_enforce_mod_pages_passthrough_without_pack():
    pres = _deck()
    assert enforce_mod_pages(pres, None).pages == pres.pages
    # LLM 已产出全部 MOD 页型时不重复追加
    pack = build_mod_data_pack(_state(_matrix()))
    once = enforce_mod_pages(pres, pack)
    twice = enforce_mod_pages(once, pack)
    assert [p.id for p in twice.pages] == [p.id for p in once.pages]
