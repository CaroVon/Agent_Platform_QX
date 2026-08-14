"""
Presentation Agent —— 报告结构 / 幻灯片结构 / 视觉层级元数据
============================================================

输入: idea + 全部上游资产
输出: SlideDeck（Slide JSON Schema：slides + sections）

分工原则（对齐"AI 生成内容结构，前端控制视觉"）:
  - AI 生成: 内容结构、layout_type（版式）、visual_metadata（视觉层级提示）
  - 前端控制: 字体、间距、组件样式（SlideRenderer 统一实现）
  - LLM 禁止生成 HTML/CSS
"""

from __future__ import annotations

from typing import Any

from agent_platform.harness.agent_loop import BaseAgent
from agent_platform.memory.memory_store import MemoryStore
from agent_platform.schemas import AgentResult, SlideDeck

from agents.presentation_agent.prompts import DECK_BUILDER_SYSTEM


class PresentationAgent(BaseAgent):
    """演示生成专家：把全部资产收敛为 Slide JSON 演示包。"""

    name = "presentation_agent"
    description = "报告结构、幻灯片结构与视觉层级元数据（Slide JSON Schema）"
    output_schema = SlideDeck
    system_prompt = DECK_BUILDER_SYSTEM

    def build_deck(
        self,
        idea: str,
        assets: dict[str, Any],
        memory: MemoryStore | None = None,
        memory_namespace: str = "default",
    ) -> AgentResult:
        """生成演示包：综合全部资产 → SlideDeck。"""
        objective = (
            f"为产品「{idea}」构建 8-14 页演示（Slide JSON）。"
            "覆盖：封面 → 市场分析 → 竞品矩阵 → 用户画像 → 产品策略 → "
            "功能与路线图 → UX 设计 → 结尾。"
            "为每页选择合适的 layout_type 并标注视觉层级（visual_metadata）。"
        )
        result = self.loop.run(
            agent_name=self.name,
            system_prompt=DECK_BUILDER_SYSTEM,
            objective=objective,
            schema=SlideDeck,
            inputs={"idea": idea},
            artifacts=assets,
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
        if task != "slide_deck":
            return AgentResult(success=False, error=f"未知任务: {task}")

        assets = {
            key: state.get(key)
            for key in (
                "requirement",
                "research",
                "competitor_analysis",
                "strategy",
                "design",
            )
            if state.get(key) is not None
        }
        return self.build_deck(
            state.get("idea", ""),
            assets,
            memory=memory,
            memory_namespace=memory_namespace,
        )
