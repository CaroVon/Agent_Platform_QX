"""
规划策略 —— 目标 → 步骤分解
============================================================

Planner 用 LLM 将执行目标分解为有序步骤（JSON 输出）；
LLM 失败时回退为单步计划，保证 Agent 循环不因规划而中断。
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from agent_platform.llm.client import LLMClient
from agent_platform.schemas.common import PlanStep

logger = logging.getLogger(__name__)

_PLAN_SYSTEM = """你是一个资深 AI Agent 规划器。
把给定的执行目标分解为 2-6 个具体、有序、可验证的执行步骤。
只输出 JSON: {"steps": [{"action": "...", "rationale": "..."}]}"""


class _PlanOutput(BaseModel):
    steps: list[PlanStep]


class Planner:
    """Agent 循环的规划策略组件。"""

    def __init__(self, llm: LLMClient | None = None):
        self.llm = llm

    def plan(self, objective: str, context: str = "", max_steps: int = 6) -> list[PlanStep]:
        """分解目标；LLM 不可用时回退单步计划。"""
        if self.llm is None:
            return [PlanStep(action=objective)]

        user = f"执行目标：{objective}\n\n背景信息：\n{context or '（无）'}"
        try:
            data = self.llm.complete_json(
                [
                    {"role": "system", "content": _PLAN_SYSTEM},
                    {"role": "user", "content": user},
                ],
                temperature=0.1,
                max_tokens=1000,
            )
            plan = _PlanOutput.model_validate(data).steps[:max_steps]
            return plan or [PlanStep(action=objective)]
        except Exception as exc:  # noqa: BLE001 —— 规划失败不阻塞执行
            logger.warning("规划失败，回退单步计划: %s", exc)
            return [PlanStep(action=objective)]
