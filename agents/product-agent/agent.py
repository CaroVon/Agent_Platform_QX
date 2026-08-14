"""
Product Agent —— 产品定位 / 用户画像 / 功能设计 / 路线图 / PRD
============================================================

输入: idea + 市场研究 + 竞品分析
输出: ProductStrategy（personas / features / roadmap / prd_sections + positioning）
"""

from __future__ import annotations

from typing import Any

from agent_platform.harness.agent_loop import BaseAgent
from agent_platform.memory.memory_store import MemoryStore
from agent_platform.schemas import AgentResult, ProductStrategy
from agent_platform.schemas.research import CompetitorAnalysis, MarketResearch

from agents.product_agent.prompts import PRODUCT_STRATEGY_SYSTEM


class ProductAgent(BaseAgent):
    """产品策略专家：从市场洞察推导产品定位、画像、功能与路线图。"""

    name = "product_agent"
    description = "产品定位、用户画像、功能设计、路线图与 PRD"
    output_schema = ProductStrategy
    system_prompt = PRODUCT_STRATEGY_SYSTEM

    def develop_strategy(
        self,
        idea: str,
        research: MarketResearch | None,
        competitors: CompetitorAnalysis | None,
        memory: MemoryStore | None = None,
        memory_namespace: str = "default",
    ) -> AgentResult:
        """产品策略：综合上游洞察 → ProductStrategy。"""
        objective = (
            f"基于产品想法「{idea}」及上游研究结论，制定完整产品策略："
            "一句话定位、2-4 个用户画像、P0/P1/P2 功能清单、3 阶段路线图，"
            "并输出结构化 PRD 章节（产品概述/目标用户/核心功能/路线图/成功指标）。"
        )
        result = self.loop.run(
            agent_name=self.name,
            system_prompt=PRODUCT_STRATEGY_SYSTEM,
            objective=objective,
            schema=ProductStrategy,
            inputs={"idea": idea},
            artifacts={
                "market_research": research,
                "competitor_analysis": competitors,
            },
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
        if task != "strategy":
            return AgentResult(success=False, error=f"未知任务: {task}")

        def _get(model_cls, key):
            value = state.get(key)
            return model_cls.model_validate(value) if value is not None else None

        return self.develop_strategy(
            state.get("idea", ""),
            _get(MarketResearch, "research"),
            _get(CompetitorAnalysis, "competitor_analysis"),
            memory=memory,
            memory_namespace=memory_namespace,
        )
