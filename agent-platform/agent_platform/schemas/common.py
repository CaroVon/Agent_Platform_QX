"""
通用契约 —— Agent 执行结果、节点错误、规划步骤
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class NodeError(BaseModel):
    """工作流节点的结构化错误信息。"""

    node: str = Field(description="节点名")
    message: str = Field(description="错误信息")
    attempt: int = Field(default=1, description="失败时所在的尝试次数")


class AgentResult(BaseModel):
    """Agent 执行统一返回契约（Agent 与工作流之间的通信协议）。"""

    success: bool
    data: dict[str, Any] | None = Field(default=None, description="schema 校验后的输出")
    error: str | None = Field(default=None, description="失败原因（success=False 时）")
    turns: int = Field(default=1, ge=1, description="Agent 循环迭代轮数")


class PlanStep(BaseModel):
    """规划器产出的单个执行步骤。"""

    action: str = Field(description="该步骤要完成的动作")
    rationale: str = Field(default="", description="为什么需要这一步")


NodeStatus = Literal["pending", "running", "completed", "failed", "skipped"]
