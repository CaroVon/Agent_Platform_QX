"""LangGraph 工作流测试 —— 编排、重试与失败降级（Fake Agent，零网络）。"""

import pytest

from agent_platform.harness.agent_loop import BaseAgent
from agent_platform.schemas import AgentResult
from agent_platform.workflows.product_research_graph import ProductResearchGraph

from agent_platform.testing import FakeLLM

IDEA = "AI 健身应用"


def _market_research() -> dict:
    return {
        "market_size": {"summary": "百亿市场"},
        "competitors": [{"name": "Keep", "positioning": "大众健身"}],
        "customer_pain_points": ["不会安排计划"],
        "industry_trends": ["AI 教练化"],
    }


def _competitor_analysis() -> dict:
    return {
        "competitors": [{"name": "Keep", "positioning": "大众健身", "threat_level": "high"}],
        "matrix": {"dimensions": ["定位"], "profiles": [{"name": "Keep", "positioning": "大众健身"}]},
        "competitive_landscape": "头部集中",
        "differentiation_opportunities": ["个性化"],
    }


def _strategy() -> dict:
    return {
        "positioning": "AI 私教",
        "personas": [{"name": "小雅", "role": "新手"}],
        "features": [{"name": "智能计划", "priority": "P0"}],
        "roadmap": [{"phase": "Phase 1", "title": "MVP"}],
        "prd_sections": [{"title": "产品概述", "content": "正文"}],
    }


def _design() -> dict:
    return {
        "user_flow": [{"step": "注册"}],
        "pages": [{"name": "首页"}],
        "components": [{"name": "强度滑块", "kind": "input"}],
    }


def _deck() -> dict:
    return {
        "topic": IDEA,
        "slides": [{"id": "s1", "title": "封面", "layout_type": "cover"}],
        "sections": [{"title": "市场", "slide_ids": ["s1"]}],
    }


class _Agent(BaseAgent):
    """测试 Agent：按 task 返回脚本化响应。"""

    name = "fake"
    description = "fake"

    def __init__(self, script: dict[str, list]):
        # 跳过真实 AgentLoop，测试只关心 execute 协议
        self.script = script
        self.calls: list[str] = []

    def execute(self, task, state, memory=None, memory_namespace="default"):
        self.calls.append(task)
        items = self.script.get(task, [])
        if not items:
            return AgentResult(success=False, error=f"no script for {task}")
        item = items.pop(0)
        if isinstance(item, Exception):
            raise item
        return AgentResult(success=True, data=item)


def _build_graph(research: _Agent, product: _Agent, design: _Agent, pres: _Agent, max_retries=1):
    return ProductResearchGraph(
        research_agent=research,
        product_agent=product,
        design_agent=design,
        presentation_agent=pres,
        llm=FakeLLM(responses=[{"idea": IDEA, "goals": [IDEA]}]),
        max_retries=max_retries,
    )


def test_happy_path_full_pipeline():
    research = _Agent(
        {"market_research": [_market_research()], "competitor_analysis": [_competitor_analysis()]}
    )
    product = _Agent({"strategy": [_strategy()]})
    design = _Agent({"ux_design": [_design()]})
    pres = _Agent({"slide_deck": [_deck()]})

    package = _build_graph(research, product, design, pres).invoke(IDEA)

    assert package.idea == IDEA
    assert package.requirement.goals == [IDEA]
    assert package.research.market_size.summary == "百亿市场"
    assert package.competitor_analysis.competitors[0].name == "Keep"
    assert package.strategy.personas[0].name == "小雅"
    assert package.design.pages[0].name == "首页"
    assert package.presentation.slides[0].layout_type == "cover"
    # 全部节点 completed，无错误
    assert all(status == "completed" for status in package.meta.node_status.values())
    assert package.meta.errors == {}


def test_node_retry_on_transient_failure():
    """research 节点第一次抛异常 → 重试成功，共调用 2 次。"""
    research = _Agent(
        {
            "market_research": [RuntimeError("临时故障"), _market_research()],
            "competitor_analysis": [_competitor_analysis()],
        }
    )
    product = _Agent({"strategy": [_strategy()]})
    design = _Agent({"ux_design": [_design()]})
    pres = _Agent({"slide_deck": [_deck()]})

    package = _build_graph(research, product, design, pres, max_retries=2).invoke(IDEA)

    assert research.calls.count("market_research") == 2
    assert package.meta.node_status["research"] == "completed"
    assert package.meta.errors == {}
    assert package.research.market_size.summary == "百亿市场"


def test_node_failure_degrades_gracefully():
    """presentation 节点持续失败 → 资产包仍产出，错误被结构化记录。"""
    research = _Agent(
        {"market_research": [_market_research()], "competitor_analysis": [_competitor_analysis()]}
    )
    product = _Agent({"strategy": [_strategy()]})
    design = _Agent({"ux_design": [_design()]})
    pres = _Agent({"slide_deck": [RuntimeError("LLM 不可用"), RuntimeError("LLM 不可用")]})

    package = _build_graph(research, product, design, pres, max_retries=1).invoke(IDEA)

    assert package.presentation is None
    assert package.meta.node_status["presentation"] == "failed"
    assert "LLM 不可用" in package.meta.errors["presentation"]
    # 其余节点不受影响
    assert package.strategy is not None
    assert package.meta.node_status["strategy"] == "completed"


def test_schema_violation_marks_node_failed():
    """Agent 返回非法数据 → 节点失败并记录（重试耗尽）。"""
    bad_research = {"market_size": {"summary": "x"}, "competitors": "not-a-list"}  # 类型错误
    research = _Agent(
        {"market_research": [bad_research, bad_research], "competitor_analysis": [_competitor_analysis()]}
    )
    product = _Agent({"strategy": [_strategy()]})
    design = _Agent({"ux_design": [_design()]})
    pres = _Agent({"slide_deck": [_deck()]})

    package = _build_graph(research, product, design, pres, max_retries=1).invoke(IDEA)

    assert package.research is None
    assert package.meta.node_status["research"] == "failed"
    assert "MarketResearch" in package.meta.errors["research"]


def test_requirement_fallback_without_llm():
    """无 LLM 时 Requirement Parser 确定性回退。"""
    research = _Agent(
        {"market_research": [_market_research()], "competitor_analysis": [_competitor_analysis()]}
    )
    product = _Agent({"strategy": [_strategy()]})
    design = _Agent({"ux_design": [_design()]})
    pres = _Agent({"slide_deck": [_deck()]})

    graph = ProductResearchGraph(
        research_agent=research,
        product_agent=product,
        design_agent=design,
        presentation_agent=pres,
        llm=None,  # 无 LLM
        max_retries=1,
    )
    package = graph.invoke(IDEA)
    assert package.requirement.idea == IDEA
    assert package.requirement.goals == [IDEA]
