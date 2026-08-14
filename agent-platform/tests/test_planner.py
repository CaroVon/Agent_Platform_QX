"""Planner 测试 —— 正常分解与降级回退。"""

from agent_platform.harness.planner import Planner
from agent_platform.testing import FakeLLM


def test_plan_decomposes_objective():
    llm = FakeLLM(
        responses=[
            {
                "steps": [
                    {"action": "搜索市场信息", "rationale": "获取事实"},
                    {"action": "撰写分析", "rationale": "综合结论"},
                ]
            }
        ]
    )
    plan = Planner(llm).plan("研究 AI 健身市场")
    assert [s.action for s in plan] == ["搜索市场信息", "撰写分析"]


def test_plan_falls_back_on_llm_failure():
    llm = FakeLLM(responses=[ValueError("boom")])
    plan = Planner(llm).plan("目标")
    assert len(plan) == 1
    assert plan[0].action == "目标"


def test_plan_without_llm():
    plan = Planner(None).plan("单步目标")
    assert plan[0].action == "单步目标"
