"""
真实 Agent 类 + LangGraph 工作流的全链路集成测试（FakeLLM，零网络）
====================================================================

验证 agents/ 下的四个专业 Agent 与平台层工作流的真实接线：
  ResearchAgent → ProductAgent → DesignAgent → PresentationAgent
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]  # ~/dev/agents
for _d in (str(_ROOT / "agent-platform"), str(_ROOT)):
    if _d not in sys.path:
        sys.path.insert(0, _d)

from agent_platform.harness.agent_loop import AgentLoop
from agent_platform.testing import FakeLLM
from agent_platform.workflows.product_research_graph import ProductResearchGraph

from agents.design_agent.agent import DesignAgent
from agents.presentation_agent.agent import PresentationAgent
from agents.product_agent.agent import ProductAgent
from agents.research_agent.agent import ResearchAgent

IDEA = "AI 健身应用"

_PLAN = {"steps": [{"action": "执行", "rationale": "测试"}]}

_MARKET = {
    "market_size": {"summary": "百亿市场", "cagr": "15%"},
    "competitors": [{"name": "Keep", "positioning": "大众健身"}],
    "customer_pain_points": ["不会安排训练计划"],
    "industry_trends": ["AI 教练化"],
}
_COMPETE = {
    "competitors": [
        {"name": "Keep", "positioning": "大众健身", "threat_level": "high"}
    ],
    "matrix": {
        "dimensions": ["定位"],
        "profiles": [{"name": "Keep", "positioning": "大众健身"}],
    },
    "competitive_landscape": "头部集中，个性化不足",
    "differentiation_opportunities": ["AI 个性化"],
}
_STRATEGY = {
    "positioning": "AI 私教",
    "personas": [{"name": "小雅", "role": "健身新手"}],
    "features": [{"name": "智能计划", "priority": "P0"}],
    "roadmap": [{"phase": "Phase 1", "title": "MVP"}],
    "prd_sections": [{"title": "产品概述", "content": "## 概述\n正文"}],
}
_DESIGN = {
    "user_flow": [{"step": "注册", "is_entry": True}],
    "pages": [{"name": "首页"}],
    "components": [{"name": "强度滑块", "kind": "input"}],
}
_DECK = {
    "topic": IDEA,
    "slides": [
        {"id": "s1", "title": "封面", "layout_type": "cover"},
        {"id": "s2", "title": "市场", "layout_type": "bullets"},
    ],
    "sections": [{"title": "市场洞察", "slide_ids": ["s1", "s2"]}],
}


def _loop(responses: list) -> AgentLoop:
    """每个 AgentLoop.run 依次消耗 1 个规划响应 + 1 个输出响应。"""
    return AgentLoop(llm=FakeLLM(responses=responses))


def _build_graph(responses: list) -> ProductResearchGraph:
    loop = _loop(responses)
    return ProductResearchGraph(
        research_agent=ResearchAgent(loop=loop),
        product_agent=ProductAgent(loop=loop),
        design_agent=DesignAgent(loop=loop),
        presentation_agent=PresentationAgent(loop=loop),
        llm=FakeLLM(responses=[{"idea": IDEA, "goals": [IDEA]}]),  # requirement parser
        max_retries=1,
    )


def test_full_pipeline_with_real_agents():
    # 5 次 Agent 执行 ×（规划 + 输出）
    responses = [
        _PLAN, _MARKET,
        _PLAN, _COMPETE,
        _PLAN, _STRATEGY,
        _PLAN, _DESIGN,
        _PLAN, _DECK,
    ]
    package = _build_graph(responses).invoke(IDEA)

    assert package.idea == IDEA
    assert package.requirement.goals == [IDEA]
    assert package.research.market_size.cagr == "15%"
    assert package.research.customer_pain_points == ["不会安排训练计划"]
    assert package.competitor_analysis.competitors[0].name == "Keep"
    assert package.strategy.positioning == "AI 私教"
    assert package.strategy.prd_sections[0].title == "产品概述"
    assert package.design.user_flow[0].is_entry is True
    assert len(package.presentation.slides) == 2
    assert all(status == "completed" for status in package.meta.node_status.values())
    assert package.meta.errors == {}


def test_pipeline_degrades_when_presentation_llm_fails():
    """演示 Agent 的 LLM 失败 → 资产包降级产出并记录错误。"""
    responses = [
        _PLAN, _MARKET,
        _PLAN, _COMPETE,
        _PLAN, _STRATEGY,
        _PLAN, _DESIGN,
        # presentation: 规划失败（不会中断）+ 输出失败 → loop 返回失败
        _PLAN, LLMError("LLM 宕机"),
    ]
    package = _build_graph(responses).invoke(IDEA)

    assert package.presentation is None
    assert package.meta.node_status["presentation"] == "failed"
    assert package.strategy is not None
    assert package.meta.node_status["strategy"] == "completed"


from agent_platform.llm.client import LLMError  # noqa: E402 —— 测试尾部导入，保持阅读顺序
