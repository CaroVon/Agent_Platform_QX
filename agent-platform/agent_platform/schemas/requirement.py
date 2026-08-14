"""
需求解析 —— Requirement Parser 节点的结构化输出
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RequirementSpec(BaseModel):
    """从用户想法解析出的产品需求规格。"""

    idea: str = Field(description="原始产品想法（规范后的表述）")
    goals: list[str] = Field(default_factory=list, description="核心目标")
    target_users: list[str] = Field(default_factory=list, description="目标用户群体")
    constraints: list[str] = Field(default_factory=list, description="约束条件（预算/技术/时间等）")
    success_metrics: list[str] = Field(default_factory=list, description="成功衡量指标")
