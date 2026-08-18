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
        instruction: str = "",
        sources: list[dict] | None = None,
    ) -> AgentResult:
        """UX 设计：基于产品策略 → UXDesign。"""
        objective = (
            f"基于产品想法「{idea}」与产品策略，输出核心用户旅程、"
            "信息架构（页面清单）与关键 UI 组件清单。"
            "只产出结构化设计规格，不写任何视觉实现代码。"
        )
        if instruction:
            objective += f"\n\n【本次修订要求】{instruction}"
        result = self.loop.run(
            agent_name=self.name,
            system_prompt=UX_DESIGN_SYSTEM,
            objective=objective,
            schema=UXDesign,
            inputs={
                "idea": idea,
                "参考资料（编号来源：关键论断必须标注 [编号]，未提供的资料禁止编造）": self._render_sources(sources),
            },
            artifacts={"product_strategy": strategy},
            memory_namespace=memory_namespace,
        )
        # 确定性兜底：模型未输出 sources 时，用审核资料前 5 条填充（禁止编造来源）
        if result.success and sources:
            data = result.data or {}
            if not data.get("sources"):
                data["sources"] = [
                    {"url": s["url"], "title": s.get("title", ""), "weight": s.get("weight", 0.5)}
                    for s in sources[:5]
                ]
                result.data = data
        return result

    @staticmethod
    def _render_sources(sources: list[dict] | None) -> str:
        if not sources:
            return "（无可用来源：所有论断必须标注为估算/假设，禁止编造来源）"
        return "\n".join(
            f"[{i + 1}] {s.get('title', '')} | {s.get('url', '')}"
            for i, s in enumerate(sources)
        )

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
            instruction=str(state.get("instruction") or ""),
            sources=state.get("_approved_sources"),
        )
