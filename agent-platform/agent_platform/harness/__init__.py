"""
============================================================
Harness 层 —— Agent 运行时（Agent Harness Layer）
============================================================

  - prompt_manager   集中管理 Prompt 模板
  - planner          规划策略（目标 → 步骤分解）
  - context          上下文管理（字符预算截断）
  - runner           结构化输出（LLM JSON → Pydantic 校验 + 自愈重试）
  - agent_loop       Agent 执行循环（规划 → 执行 → 评估 → 反思）
"""

from agent_platform.harness.prompt_manager import PromptManager
from agent_platform.harness.planner import Planner
from agent_platform.harness.context import ContextManager
from agent_platform.harness.runner import StructuredRunner, StructuredOutputError
from agent_platform.harness.agent_loop import AgentLoop, BaseAgent

__all__ = [
    "AgentLoop",
    "BaseAgent",
    "ContextManager",
    "Planner",
    "PromptManager",
    "StructuredOutputError",
    "StructuredRunner",
]
