"""
============================================================
评估契约 —— Critic Agent 输出 + 视觉质量门报告
============================================================
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Issue(BaseModel):
    """单条评审意见。"""

    page_id: str | None = Field(default=None, description="关联页面 ID（可为空）")
    type: Literal[
        "content_density",
        "information_hierarchy",
        "layout_consistency",
        "visual_variety",
        "text_overflow",
        "duplicate_information",
    ] = Field(description="问题维度")
    severity: Literal["high", "medium", "low"] = Field(default="medium")
    description: str = Field(description="问题描述与修正建议")


class CritiqueResult(BaseModel):
    """Critic Agent 输出：评分 + 结构化问题清单。"""

    score: int = Field(ge=0, le=100, description="0-100 综合评分")
    issues: list[Issue] = Field(default_factory=list)
    summary: str = Field(default="", description="一句话总结")


class QualityGateReport(BaseModel):
    """确定性视觉质量门报告（不依赖 LLM）。"""

    passed: bool = Field(description="是否通过（无 error 级问题）")
    errors: list[str] = Field(default_factory=list, description="error 级问题")
    warnings: list[str] = Field(default_factory=list, description="warning 级问题")
    checks: dict[str, bool] = Field(default_factory=dict, description="检查项 → 通过")
