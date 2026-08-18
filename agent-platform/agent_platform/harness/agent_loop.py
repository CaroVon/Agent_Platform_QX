"""
Agent 执行循环 —— 规划 → 执行 → 评估 → 反思（Phase 5 核心）
============================================================

AgentLoop 是每个专业 Agent 的运行引擎：
  - Planning      Planner 将目标分解为步骤
  - Execution     StructuredRunner 生成 Schema 校验通过的结构化输出
  - Evaluation    默认评估器检查关键字段非空
  - Reflection    评估未通过时，把差距写成修正要求进入下一轮
  - Memory        每轮关键产物写入 MemoryStore

BaseAgent 是所有专业 Agent 的抽象基类：
  子类声明 name / output_schema / system_prompt，
  并实现 execute(task, state, memory) 完成「任务分派 → 上下文组装 → 循环执行」。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Callable

from pydantic import BaseModel

from agent_platform.config.settings import get_settings
from agent_platform.harness.context import ContextManager
from agent_platform.harness.planner import Planner
from agent_platform.harness.runner import StructuredRunner
from agent_platform.llm.client import LLMClient, get_llm_client
from agent_platform.memory.memory_store import MemoryStore
from agent_platform.schemas.common import AgentResult

logger = logging.getLogger(__name__)

# 评估器签名：(模型实例) -> (是否通过, 反馈文本)
Evaluator = Callable[[BaseModel], tuple[bool, str]]


def default_evaluator(model: BaseModel) -> tuple[bool, str]:
    """默认评估：必填字符串非空；**必填列表字段不允许为空列表**。"""
    issues: list[str] = []
    for name, field_info in model.model_fields.items():
        value = getattr(model, name, None)
        if isinstance(value, str) and not value.strip():
            issues.append(f"字段 {name} 为空")
        if value is None:
            issues.append(f"字段 {name} 为 null")
        # 仅对"无默认值"的必填 list 字段做非空校验（带默认值/可选的列表如 sources 允许为空）
        if isinstance(value, list) and field_info.is_required() and len(value) == 0:
            issues.append(f"字段 {name} 为空列表（必填内容缺失）")
    if issues:
        return False, "；".join(issues)
    return True, ""


class AgentLoop:
    """专业 Agent 的统一执行循环。"""

    def __init__(
        self,
        llm: LLMClient | None = None,
        memory: MemoryStore | None = None,
        evaluator: Evaluator | None = None,
    ):
        settings = get_settings()
        self.llm = llm or get_llm_client()
        self.planner = Planner(self.llm)
        self.runner = StructuredRunner(self.llm)
        self.context = ContextManager(char_budget=settings.CONTEXT_CHAR_BUDGET)
        self.memory = memory
        self.evaluator = evaluator or default_evaluator
        self.max_turns = settings.AGENT_MAX_TURNS
        self.max_retries = settings.AGENT_MAX_RETRIES

    def run(
        self,
        agent_name: str,
        system_prompt: str,
        objective: str,
        schema: type[BaseModel],
        inputs: dict[str, Any] | None = None,
        artifacts: dict[str, Any] | None = None,
        memory_namespace: str = "default",
        evaluator: Evaluator | None = None,
    ) -> AgentResult:
        """
        执行一轮完整 Agent 循环。

        Args:
            evaluator: 本轮专用评估器（如覆盖率评估闭包），
                       缺省使用 AgentLoop 构造时注入的评估器。

        Returns:
            AgentResult —— success=False 时 data 为 None，error 记录最终失败原因
        """
        active_evaluator = evaluator or self.evaluator

        # ── 1. Planning ─────────────────────────────────────
        context_text = (objective or "") + ("\n" + str(inputs)[:2000] if inputs else "")
        plan = self.planner.plan(objective, context=context_text)
        plan_text = "\n".join(
            f"{i + 1}. {step.action}（{step.rationale}）"
            for i, step in enumerate(plan)
        )

        reflection = ""
        last_result: BaseModel | None = None
        last_error = ""

        # 记忆读回：把本项目最近产出注入上下文（记忆闭环，避免重复解释）
        memory_context = ""
        if self.memory is not None:
            try:
                recent_entries = self.memory.recent(memory_namespace, limit=3)
                if recent_entries:
                    memory_context = "\n\n".join(
                        f"- [{e.kind}] {e.content[:400]}" for e in recent_entries
                    )
            except Exception as exc:  # noqa: BLE001 —— 记忆读回失败不阻塞
                logger.warning("记忆读回失败: %s", exc)

        # ── 2~4. Execute / Evaluate / Reflect 循环 ──────────
        for turn in range(1, self.max_turns + 1):
            user_prompt = self.context.build_user_message(
                objective=objective,
                inputs=inputs,
                artifacts=artifacts,
                plan_text=plan_text,
                reflection=reflection,
            )
            if memory_context:
                user_prompt += f"\n\n【本项目历史产出（仅作参考，勿重复生成相同内容）】\n{memory_context}" 
            try:
                model = self.runner.run(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    schema=schema,
                    max_retries=self.max_retries,
                )
            except Exception as exc:  # noqa: BLE001 —— 统一收敛为 AgentResult
                last_error = f"执行失败: {exc}"
                logger.error("[%s] 第 %d 轮执行失败: %s", agent_name, turn, exc)
                break

            ok, feedback = active_evaluator(model)
            if ok:
                self._remember(
                    memory_namespace,
                    kind=f"{agent_name}_output",
                    content=model.model_dump_json(),
                )
                return AgentResult(success=True, data=model.model_dump(), turns=turn)

            # 评估未通过 → 反思修正，进入下一轮
            last_result = model
            reflection = f"评估未通过：{feedback}。请补全或修正这些缺陷后重新输出完整 JSON。"
            logger.info("[%s] 第 %d 轮评估未通过: %s", agent_name, turn, feedback)

        if last_result is not None:
            # 循环耗尽但已有产物：降级返回（仍比失败好）
            self._remember(
                memory_namespace,
                kind=f"{agent_name}_output_degraded",
                content=last_result.model_dump_json(),
            )
            return AgentResult(
                success=True,
                data=last_result.model_dump(),
                turns=self.max_turns,
                error="评估未完全通过，返回降级产物",
            )
        return AgentResult(success=False, error=last_error or "未产生输出", turns=self.max_turns)

    def _remember(self, namespace: str, kind: str, content: str) -> None:
        if self.memory is not None:
            try:
                self.memory.add(namespace, kind, content)
            except Exception as exc:  # noqa: BLE001 —— 记忆失败不阻塞主流程
                logger.warning("记忆写入失败: %s", exc)


class BaseAgent(ABC):
    """专业 Agent 抽象基类 —— agents/ 下的四个专家均继承它。"""

    name: str = "base_agent"
    description: str = ""
    output_schema: type[BaseModel]
    system_prompt: str = ""

    def __init__(self, loop: AgentLoop | None = None):
        self.loop = loop or AgentLoop()

    @abstractmethod
    def execute(
        self,
        task: str,
        state: dict[str, Any],
        memory: MemoryStore | None = None,
        memory_namespace: str = "default",
    ) -> AgentResult:
        """执行指定任务。

        Args:
            task: 任务名（如 market_research / competitor_analysis）
            state: 工作流结构化状态（含 idea 与上游产物）
            memory: 项目记忆（可为 None）
            memory_namespace: 记忆隔离命名空间（通常为 product_id）
        """
