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


def test_ensure_consulting_theme_assigns_when_default():
    """默认主题 → 确定性分配 cyber-* 咨询风，palette 完整、可复现。"""
    from agent_platform.harness.enforce_coverage import ensure_consulting_theme
    from agent_platform.schemas.presentation import THEME_PRESETS

    pres = Presentation.model_validate(_full_deck())
    assert pres.theme.id == "default"

    r1 = ensure_consulting_theme(pres, seed="product-A")
    r2 = ensure_consulting_theme(pres, seed="product-A")
    assert r1.theme.id.startswith("cyber-")
    assert r1.theme.id == r2.theme.id  # 同 seed 可复现
    assert set(r1.theme.palette.keys()) == {"bg", "surface", "primary", "accent", "text", "muted"}
    assert r1.theme.palette == THEME_PRESETS[r1.theme.id]["palette"]

    r3 = ensure_consulting_theme(pres, seed="product-B")
    assert r3.theme.id.startswith("cyber-")


def test_ensure_consulting_theme_keeps_explicit_choice():
    """已显式选择 cyber 主题且 palette 完整 → 保持不变。"""
    from agent_platform.harness.enforce_coverage import ensure_consulting_theme
    from agent_platform.schemas.presentation import THEME_PRESETS, Theme

    pres = Presentation.model_validate(_full_deck())
    pres.theme = Theme(id="cyber-ivory-navy", name="象牙白+深蓝",
                       palette=dict(THEME_PRESETS["cyber-ivory-navy"]["palette"]))
    out = ensure_consulting_theme(pres, seed="any")
    assert out.theme.id == "cyber-ivory-navy"
    assert out.theme.palette["primary"] == "#12355B"


def test_ensure_consulting_theme_fills_missing_palette():
    """cyber 主题 palette 缺失 → 从预置补全。"""
    from agent_platform.harness.enforce_coverage import ensure_consulting_theme
    from agent_platform.schemas.presentation import THEME_PRESETS, Theme

    pres = Presentation.model_validate(_full_deck())
    pres.theme = Theme(id="cyber-crimson", name="经典深红咨询", palette={})
    out = ensure_consulting_theme(pres, seed="x")
    assert out.theme.id == "cyber-crimson"
    assert out.theme.palette == THEME_PRESETS["cyber-crimson"]["palette"]


def test_inject_modular_content_adds_prd_and_competitor_weaknesses():
    """PRD 全文与竞品短板未入页时，确定性注入卡片（不依赖 LLM）。"""
    from agent_platform.harness.enforce_coverage import enrich_coverage
    from agent_platform.schemas.product_document import ProductDocument
    from agent_platform.schemas.product import ProductStrategy
    from agent_platform.schemas.research import CompetitorAnalysis, CompetitorProfile

    doc = _rich_document()
    # 上游补充 PRD 全文 + 竞品弱点/定价
    doc.strategy = ProductStrategy(
        positioning=doc.strategy.positioning,
        personas=doc.strategy.personas,
        features=doc.strategy.features,
        roadmap=doc.strategy.roadmap,
        prd_sections=[
            {"title": "产品概述", "content": "这是一段必须进入演示的 PRD 核心结论全文" * 5},
            {"title": "成功指标", "content": "北极星指标：周活跃训练用户数" * 3},
        ],
    )
    doc.competitor_analysis = CompetitorAnalysis(
        competitive_landscape=doc.competitor_analysis.competitive_landscape,
        competitors=[
            CompetitorProfile(name="Keep", positioning="大众健身", pricing="199元/年",
                              strengths=["用户量大"], weaknesses=["个性化弱、缺乏教练实时纠错"]),
        ],
    )

    pres = Presentation.model_validate(_full_deck())
    out = enrich_coverage(pres, doc)
    text = out.model_dump_json()

    assert "PRD 核心结论" in text
    assert "必须进入演示的 PRD 核心结论全文" in text
    assert "竞品短板与定价" in text
    assert "199元/年" in text
    assert "个性化弱" in text

    # 注入卡片 id 唯一
    ids = [c.id for p in out.pages for c in p.components]
    assert len(ids) == len(set(ids))
