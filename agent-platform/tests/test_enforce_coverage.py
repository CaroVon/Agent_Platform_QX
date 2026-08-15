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


def test_enrich_fills_table_description_column():
    """enrich：features 表格描述列为空 → 从上游补全。"""
    from agent_platform.harness.enforce_coverage import enrich_coverage
    from tests.test_workflow_graph import _full_deck

    doc = _rich_document()
    deck = _full_deck()
    # 制造空描述列的表格
    for pg in deck["pages"]:
        if pg.get("type") == "feature_priority":
            for c in pg.get("components", []):
                if c.get("type") == "table":
                    c["data"]["rows"] = [["P0", "功能0", ""]]
    pres = Presentation.model_validate(deck)
    result = enrich_coverage(pres, doc)
    features_page = next(p for p in result.pages if p.type == "feature_priority")
    table = next(c for c in features_page.components if c.type == "table")
    assert len(table.data["rows"][0]) == 3
    # 上游功能名是"功能0"（_rich_document），描述来自上游
    assert table.data["rows"][0][1] == "功能0"


def test_enrich_adds_market_conclusion():
    """enrich：market 页补核心结论与来源。"""
    from agent_platform.harness.enforce_coverage import enrich_coverage

    doc = _rich_document()
    deck = _full_deck()
    # 移除 market 页的 summary 结论（p3 组件只有 metric）
    for pg in deck["pages"]:
        if pg.get("type") == "market_overview":
            pg["components"] = [
                c for c in pg["components"] if c.get("type") != "text"
            ]
    pres = Presentation.model_validate(deck)
    result = enrich_coverage(pres, doc)
    market = next(p for p in result.pages if p.type == "market_overview")
    texts = [c for c in market.components if c.type == "text"]
    assert len(texts) == 1
    assert "核心结论" in str(texts[0].data.get("title", ""))
