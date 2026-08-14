"""A3 确定性兜底（enforce_coverage）测试。"""

from agent_platform.harness.enforce_coverage import enforce_coverage
from agent_platform.schemas import Presentation, ProductDocument

from tests.test_critic_loop import _rich_document
from tests.test_workflow_graph import _full_deck


def _sparse_presentation() -> Presentation:
    """2 页、几乎无内容的演示。"""
    return Presentation.model_validate(
        {
            "title": "x",
            "pages": [
                {"id": "p1", "type": "cover", "layout": "cover", "title": "封面",
                 "components": [{"id": "c1", "type": "text", "data": {"text": "x"}}]},
                {"id": "p2", "type": "market_overview", "layout": "market", "title": "市场",
                 "insight": "概述",
                 "components": [{"id": "c1", "type": "text", "data": {"text": "简短"}}]},
            ],
        }
    )


def test_enforce_injects_missing_metrics_pains_and_trends():
    doc = _rich_document()
    pres = _sparse_presentation()
    result = enforce_coverage(pres, doc)

    market = next(p for p in result.pages if p.type == "market_overview")
    data_text = ""
    for c in market.components:
        data_text += " " + str(c.data)
    # 市场指标注入（TAM/SAM/SOM/CAGR 值）
    assert "100亿" in data_text and "25%" in data_text
    # 痛点要点注入
    assert "用户痛点" in data_text and "痛点条目" in data_text
    # 趋势注入
    assert "行业趋势" in data_text


def test_enforce_deduplicates_component_ids():
    pres = _sparse_presentation()  # p1/p2 组件 id 均为 c1
    result = enforce_coverage(pres, _rich_document())
    ids = [c.id for p in result.pages for c in p.components]
    assert len(ids) == len(set(ids)), f"ID 应全局唯一: {ids}"


def test_enforce_noop_when_fully_covered():
    doc = _rich_document()
    pres = Presentation.model_validate(_full_deck())
    result = enforce_coverage(pres, doc)
    assert result.pages == pres.pages  # 无缺失注入时保持原样
