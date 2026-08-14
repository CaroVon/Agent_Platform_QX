"""
Design Agent —— 用户旅程 / 信息架构 / UI 结构
============================================================

输入: idea + ProductStrategy
输出: UXDesign（user_flow / pages / components）

注意：Design Agent 只产出结构化设计规格，视觉实现（字体/间距/样式）
由前端渲染层负责 —— LLM 禁止生成 HTML/CSS。
"""

from __future__ import annotations

from typing import Any

from agent_platform.harness.agent_loop import BaseAgent
from agent_platform.memory.memory_store import MemoryStore
from agent_platform.schemas import AgentResult, UXDesign
from agent_platform.schemas.product import ProductStrategy

from agents.design_agent.prompts import UX_DESIGN_SYSTEM


class DesignAgent(BaseAgent):
    """UX 设计专家：用户旅程、信息架构与 UI 结构规格。"""

    name = "design_agent"
    description = "用户旅程、信息架构与 UI 结构设计（结构化规格，非视觉实现）"
    output_schema = UXDesign
    system_prompt = UX_DESIGN_SYSTEM

    def design_ux(
        self,
        idea: str,
        strategy: ProductStrategy | None,
        memory: MemoryStore | None = None,
        memory_namespace: str = "default",
    ) -> AgentResult:
        """UX 设计：基于产品策略 → UXDesign。"""
        objective = (
            f"基于产品想法「{idea}」与产品策略，输出核心用户旅程、"
            "信息架构（页面清单）与关键 UI 组件清单。"
            "只产出结构化设计规格，不写任何视觉实现代码。"
        )
        result = self.loop.run(
            agent_name=self.name,
            system_prompt=UX_DESIGN_SYSTEM,
            objective=objective,
            schema=UXDesign,
            inputs={"idea": idea},
            artifacts={"product_strategy": strategy},
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
        if task != "ux_design":
            return AgentResult(success=False, error=f"未知任务: {task}")

        strategy_data = state.get("strategy")
        strategy = (
            ProductStrategy.model_validate(strategy_data)
            if strategy_data is not None
            else None
        )
        return self.design_ux(
            state.get("idea", ""),
            strategy,
            memory=memory,
            memory_namespace=memory_namespace,
        )
