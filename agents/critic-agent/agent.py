"""
============================================================
Critic Agent —— 演示评审（P5: 生成 → 批判 → 修订闭环）
============================================================

Critic 不重新生成内容，只评估 Presentation DSL 的六个维度:
  content_density / information_hierarchy / layout_consistency /
  visual_variety / text_overflow / duplicate_information

输出 CritiqueResult（score 0-100 + 结构化 issues）。
工作流据此决定: score >= 80 通过；否则把 issues 回传给
Presentation Agent 修订（最多 revision 上限次）。
"""

from __future__ import annotations

from typing import Any

from agent_platform.harness.agent_loop import BaseAgent
from agent_platform.harness.runner import StructuredRunner
from agent_platform.llm.client import LLMClient, get_llm_client
from agent_platform.memory.memory_store import MemoryStore
from agent_platform.schemas import AgentResult
from agent_platform.schemas.evaluation import CritiqueResult
from agent_platform.schemas.presentation import Presentation
from agent_platform.schemas.product_document import ProductDocument

from agents.critic_agent.prompts import CRITIC_SYSTEM


class CriticAgent(BaseAgent):
    """演示质量评审员。"""

    name = "critic_agent"
    description = "评估 Presentation DSL 的语义与视觉规划质量（0-100 评分 + 问题清单）"
    output_schema = CritiqueResult
    system_prompt = CRITIC_SYSTEM

    def __init__(self, llm: LLMClient | None = None):
        self.llm = llm or get_llm_client()
        self.runner = StructuredRunner(self.llm)

    def critique(
        self,
        presentation: Presentation,
        document: ProductDocument | None = None,
    ) -> AgentResult:
        """评审演示：返回 {score, issues}。"""
        user_prompt = (
            "【演示 DSL（请评审）】\n"
            + presentation.model_dump_json()
            + "\n\n【上游产品文档（事实依据）】\n"
            + (document.model_dump_json() if document else "（未提供）")
        )
        try:
            result = self.runner.run(
                system_prompt=CRITIC_SYSTEM,
                user_prompt=user_prompt,
                schema=CritiqueResult,
                max_retries=2,
                temperature=0.1,
            )
        except Exception as exc:  # noqa: BLE001 —— 评审失败记为"未通过"（不假装满分）
            return AgentResult(
                success=True,
                data={
                    "score": 0,
                    "issues": [{"severity": "error", "type": "critic_unavailable", "description": "评审服务不可用"}],
                    "summary": f"评审不可用（按未通过处理）: {exc}",
                },
                turns=1,
                error=str(exc),
            )
        return AgentResult(success=True, data=result.model_dump(), turns=1)

    def execute(
        self,
        task: str,
        state: dict[str, Any],
        memory: MemoryStore | None = None,
        memory_namespace: str = "default",
    ) -> AgentResult:
        if task != "critique":
            return AgentResult(success=False, error=f"未知任务: {task}")

        presentation_data = state.get("presentation")
        if presentation_data is None:
            return AgentResult(success=False, error="缺少 Presentation DSL")
        presentation = Presentation.model_validate(presentation_data)

        document_data = state.get("document")
        document = (
            ProductDocument.model_validate(document_data)
            if document_data is not None
            else None
        )
        return self.critique(presentation, document=document)
