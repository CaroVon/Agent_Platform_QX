"""
============================================================
Research Agent —— 市场研究 + 竞品分析
============================================================

输入: 产品想法（idea）
输出:
  - market_research:     MarketResearch     （market_size / competitors / pain_points / trends）
  - competitor_analysis: CompetitorAnalysis （竞品画像 / 对比矩阵 / 差异化机会）
"""

from __future__ import annotations

from typing import Any

from agent_platform.harness.agent_loop import BaseAgent
from agent_platform.memory.memory_store import MemoryStore
from agent_platform.schemas import AgentResult, MarketResearch, CompetitorAnalysis

from agents.research_agent.prompts import (
    COMPETITOR_ANALYSIS_SYSTEM,
    MARKET_RESEARCH_SYSTEM,
)


class ResearchAgent(BaseAgent):
    """市场研究专家：搜索市场事实 → 结构化市场研究与竞品分析。"""

    name = "research_agent"
    description = "全网搜索市场信息，产出市场规模、竞品、用户痛点与行业趋势"
    output_schema = MarketResearch
    system_prompt = MARKET_RESEARCH_SYSTEM

    def research_market(self, idea: str, memory: MemoryStore | None = None, memory_namespace: str = "default") -> AgentResult:
        """市场研究：搜索 + 综合 → MarketResearch。"""
        objective = (
            f"对产品想法「{idea}」进行市场研究。"
            "调研市场规模与增长、主要竞品、目标用户痛点与行业趋势，"
            "每个结论尽量给出具体数据与依据。"
        )
        result = self.loop.run(
            agent_name=self.name,
            system_prompt=MARKET_RESEARCH_SYSTEM,
            objective=objective,
            schema=MarketResearch,
            inputs={"idea": idea},
            memory_namespace=memory_namespace,
        )
        return result

    def analyze_competitors(
        self,
        idea: str,
        market_research: MarketResearch,
        memory: MemoryStore | None = None,
        memory_namespace: str = "default",
    ) -> AgentResult:
        """竞品分析：基于市场研究 → CompetitorAnalysis。"""
        objective = (
            f"基于产品想法「{idea}」的市场研究成果，产出深度竞品分析："
            "为每个主要竞品建立画像（定位/目标客群/定价/优劣势/威胁等级），"
            "构建对比矩阵，并指出我方可切入的差异化机会。"
        )
        result = self.loop.run(
            agent_name="competitor_analysis_agent",
            system_prompt=COMPETITOR_ANALYSIS_SYSTEM,
            objective=objective,
            schema=CompetitorAnalysis,
            inputs={"idea": idea},
            artifacts={"market_research": market_research},
            memory_namespace=memory_namespace,
        )
        return result

    def execute(
        self,
        task: str,
        state: dict[str, Any],
        memory: MemoryStore | None = None,
        memory_namespace: str = "default",
    ) -> AgentResult:
        """工作流统一入口：按任务名分派。"""
        idea = state.get("idea", "")
        if task == "market_research":
            return self.research_market(idea, memory=memory, memory_namespace=memory_namespace)

        if task == "competitor_analysis":
            research_data = state.get("research")
            research = (
                MarketResearch.model_validate(research_data)
                if research_data is not None
                else None
            )
            if research is None:
                return AgentResult(success=False, error="缺少上游市场研究成果")
            return self.analyze_competitors(
                idea, research, memory=memory, memory_namespace=memory_namespace
            )

        return AgentResult(success=False, error=f"未知任务: {task}")
