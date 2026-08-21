"""P5 质量门 + Critic 修订循环测试（FakeLLM，零网络）。"""

from agent_platform.schemas import Presentation
from agent_platform.schemas.evaluation import QualityGateReport
from agent_platform.harness.quality_gate import run_quality_gate

from tests.test_workflow_graph import (
    _Agent,
    _competitor_analysis,
    _competitor_matrix,
    _deck,
    _design,
    _full_deck,
    _market_research,
    _strategy,
    IDEA,
)
from agent_platform.testing import FakeLLM
from agent_platform.workflows.product_research_graph import ProductResearchGraph


def _presentation(**page_overrides) -> Presentation:
    """构造一个 8 页、六维度基本达标的演示。"""
    base_pages = [
        {
            "id": "p1", "type": "cover", "layout": "cover", "title": "封面",
            "components": [{"id": "c1", "type": "text", "data": {"text": IDEA}}],
        },
        {
            "id": "p2", "type": "executive_summary", "layout": "summary", "title": "执行摘要",
            "insight": "核心结论",
            "components": [
                {"id": "c2", "type": "metric", "data": {"value": "100亿", "label": "市场规模"}},
            ],
        },
        {
            "id": "p3", "type": "market_overview", "layout": "market", "title": "市场概览",
            "insight": "增长迅速",
            "components": [{"id": "c3", "type": "chart", "data": {"items": [{"label": "A", "value": 1}]}}],
        },
        {
            "id": "p4", "type": "competitor_matrix", "layout": "matrix", "title": "竞品矩阵",
            "insight": "存在缺口",
            "components": [
                {"id": "c4", "type": "matrix", "data": {"chart_type": "quadrant", "points": [{"name": "A", "x": 0.5, "y": 0.5}]}},
            ],
        },
        {
            "id": "p5", "type": "user_persona", "layout": "persona", "title": "用户画像",
            "insight": "两类用户",
            "components": [{"id": "c5", "type": "card", "data": {"title": "画像", "description": "描述"}}],
        },
        {
            "id": "p6", "type": "feature_priority", "layout": "features", "title": "功能优先级",
            "insight": "P0 聚焦",
            "components": [{"id": "c6", "type": "table", "data": {"columns": ["A"], "rows": [["B"]]}}],
        },
        {
            "id": "p7", "type": "roadmap", "layout": "roadmap", "title": "路线图",
            "insight": "三阶段",
            "components": [{"id": "c7", "type": "timeline", "data": {"phases": [{"name": "P1"}]}}],
        },
        {
            "id": "p8", "type": "user_journey", "layout": "journey", "title": "用户旅程",
            "insight": "完整旅程",
            "components": [{"id": "c8a", "type": "timeline", "data": {"phases": [{"name": "注册"}]}}],
        },
        {
            "id": "p9", "type": "product_architecture", "layout": "architecture", "title": "产品架构",
            "insight": "分层架构",
            "components": [{"id": "c8b", "type": "card", "data": {"title": "数据层", "description": "架构说明"}}],
        },
        {
            "id": "p10", "type": "conclusion", "layout": "closing", "title": "结语",
            "components": [{"id": "c8c", "type": "quote", "data": {"quote": "行动号召"}}],
        },
    ]
    return Presentation.model_validate({"title": IDEA, "pages": base_pages})


def test_quality_gate_passes_for_balanced_presentation():
    gate = run_quality_gate(_presentation())
    assert gate.passed is True
    assert gate.errors == []
    assert gate.checks["page_count_10_16"] is True


def test_quality_gate_flags_missing_metric_value():
    pres = _presentation()
    pres.pages[1].components[0].data.pop("value")
    gate = run_quality_gate(pres)
    assert gate.passed is False
    assert any("metric" in err for err in gate.errors)


def test_quality_gate_flags_duplicate_titles():
    pres = _presentation()
    pres.pages[2].title = pres.pages[1].title  # 与 p2 重复
    gate = run_quality_gate(pres)
    assert any("重复" in w for w in gate.warnings)


def test_quality_gate_flags_page_count():
    pres = _presentation()
    pres.pages = pres.pages[:5]
    gate = run_quality_gate(pres)
    assert gate.passed is False
    assert any("10-16" in e for e in gate.errors)


def _make_critic(script: list) -> _Agent:
    return _Agent({"critique": script})


def _build(research, product, design, pres, critic, **kwargs):
    return ProductResearchGraph(
        research_agent=research,
        product_agent=product,
        design_agent=design,
        presentation_agent=pres,
        critic_agent=critic,
        llm=FakeLLM(responses=[{"idea": IDEA, "goals": [IDEA]}]),
        max_retries=1,
        **kwargs,
    )


def _agents(pres_script: list):
    research = _Agent(
        {"market_research": [_market_research()], "competitor_matrix": [_competitor_matrix()],
         "competitor_analysis": [_competitor_analysis()]}
    )
    product = _Agent({"strategy": [_strategy()]})
    design = _Agent({"ux_design": [_design()]})
    pres = _Agent({"slide_deck": pres_script})
    return research, product, design, pres


def test_critic_revise_loop_until_pass():
    """第一次评分 60 → 修订；第二次评分 92 → 收尾。"""
    research, product, design, pres = _agents([_full_deck(), _full_deck()])
    critic = _make_critic(
        [
            {"score": 60, "issues": [{"type": "visual_variety", "severity": "high",
                                        "description": "增加矩阵布局"}], "summary": "需修订"},
            {"score": 92, "issues": [], "summary": "达标"},
        ]
    )
    package = _build(research, product, design, pres, critic).invoke(IDEA)

    assert pres.calls.count("slide_deck") == 2  # 修订了一次
    assert package.presentation is not None
    assert package.meta.node_status["critic"] == "completed"
    # 最终 revision_count 反映两次 critic
    assert package.meta.errors == {}


def test_critic_revision_capped_by_max_revisions():
    """Critic 持续低分 → 达到 max_revisions 后强制收尾（不无限循环）。"""
    research, product, design, pres = _agents([_full_deck(), _full_deck(), _full_deck()])
    critic = _make_critic(
        [
            {"score": 50, "issues": [{"type": "content_density", "severity": "high",
                                       "description": "密度过高"}], "summary": "差"},
            {"score": 55, "issues": [{"type": "content_density", "severity": "high",
                                       "description": "密度过高"}], "summary": "差"},
            {"score": 58, "issues": [{"type": "content_density", "severity": "high",
                                       "description": "密度过高"}], "summary": "差"},
        ]
    )
    package = _build(research, product, design, pres, critic, max_revisions=2).invoke(IDEA)

    # 初始 1 次 + 修订 2 次（max_revisions=2）
    assert pres.calls.count("slide_deck") == 3
    assert package.presentation is not None


def test_quality_gate_penalty_forces_revision():
    """质量门 error（两个 metric 缺 value）压分 → 触发修订。"""
    bad_deck = _full_deck()
    # 制造两个 gate error：p2 与 p3 的 metric 缺 value
    bad_deck["pages"][1]["components"][0]["data"].pop("value")
    bad_deck["pages"][2]["components"][0]["data"].pop("value")
    research, product, design, pres = _agents([bad_deck, _full_deck()])
    critic = _make_critic(
        [
            {"score": 100, "issues": [], "summary": "语义满分"},
            {"score": 100, "issues": [], "summary": "语义满分"},
        ]
    )
    package = _build(research, product, design, pres, critic).invoke(IDEA)

    # 第一次被质量门压到 60 → 修订；第二次通过
    assert pres.calls.count("slide_deck") == 2
    assert package.presentation.pages[1].components[0].data.get("value")


def test_without_critic_agent_no_loop():
    """未注入 Critic 时：单次 presentation 直接收尾（质量门仅记录）。"""
    research, product, design, pres = _agents([_deck()])
    package = _build(research, product, design, pres, critic=None).invoke(IDEA)
    assert pres.calls.count("slide_deck") == 1
    assert package.presentation is not None


# ─── A3: 信息覆盖度质量门 ──────────────────────────────────

def _rich_document():
    """构造信息丰富的 Canonical Product Document。"""
    from agent_platform.schemas import (
        CompetitorAnalysis,
        CompetitorProfile,
        Feature,
        MarketResearch,
        MarketSize,
        Persona,
        PRDSection,
        ProductDocument,
        ProductStrategy,
        ProjectInfo,
        RoadmapItem,
    )

    return ProductDocument(
        project_info=ProjectInfo(idea=IDEA),
        research=MarketResearch(
            market_size=MarketSize(
                summary="百亿市场", tam="100亿", sam="80亿", som="20亿", cagr="25%",
            ),
            competitors=[],
            customer_pain_points=[f"痛点条目{i}：用户困扰描述" for i in range(5)],
            industry_trends=[f"趋势条目{i}：技术方向" for i in range(4)],
        ),
        competitor_analysis=CompetitorAnalysis(
            competitors=[
                CompetitorProfile(name=f"竞品{i}", positioning=f"定位{i}")
                for i in range(5)
            ],
            matrix={},
            competitive_landscape="竞争格局",
            differentiation_opportunities=["差异化机会"],
        ),
        strategy=ProductStrategy(
            positioning="AI 私教",
            personas=[Persona(name=f"画像{i}") for i in range(3)],
            features=[Feature(name=f"功能{i}", priority="P1") for i in range(8)],
            roadmap=[
                RoadmapItem(phase=f"阶段{i}", title=f"主题{i}", milestones=[f"里程碑{i}"])
                for i in range(3)
            ],
            prd_sections=[PRDSection(title="产品概述", content="正文")],
        ),
        design=None,
    )


def test_coverage_gate_flags_sparse_presentation():
    """演示未覆盖上游关键字段 → 质量门产出 coverage errors。"""
    doc = _rich_document()
    gate = run_quality_gate(_presentation(), document=doc)
    coverage_errors = [e for e in gate.errors if "覆盖" in e or "覆盖率" in e]
    assert coverage_errors, "应有覆盖度不足错误"
    assert gate.passed is False


def test_coverage_gate_passes_rich_presentation():
    """演示覆盖全部关键字段 → 无 coverage errors。"""
    doc = _rich_document()
    # 构造覆盖充分的演示：把上游字段值全部嵌入组件 data
    tokens = {
        "text": (
            "100亿 80亿 20亿 25% "
            + " ".join(f"痛点条目{i}：用户困扰描述" for i in range(5)) + " "
            + " ".join(f"趋势条目{i}：技术方向" for i in range(4)) + " "
            + " ".join(f"竞品{i}" for i in range(5)) + " "
            + " ".join(f"画像{i}" for i in range(3)) + " "
            + " ".join(f"功能{i}" for i in range(8)) + " "
            + " ".join(f"阶段{i} 主题{i}" for i in range(3))
        ),
    }
    pages = _presentation().pages
    pages[1].components[0].data = tokens  # 塞进摘要页组件
    rich = Presentation.model_validate({"title": IDEA, "pages": pages})
    gate = run_quality_gate(rich, document=doc)
    coverage_errors = [e for e in gate.errors if "覆盖" in e]
    assert coverage_errors == [], f"不应有覆盖度错误: {coverage_errors}"
