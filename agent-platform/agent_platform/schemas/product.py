"""
产品策略 —— Product Agent 的结构化输出

Product Agent 输出契约（对齐产品需求）:
  {
    "personas": [],
    "features": [],
    "roadmap": [],
    "prd_sections": []
  }
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from agent_platform.schemas.common import SourceRef


class Persona(BaseModel):
    """用户画像 —— 供前端 PersonaCard 组件渲染。"""

    name: str = Field(description="画像名称（如：都市健身新手 小雅）")
    role: str = Field(default="", description="角色标签")
    goals: list[str] = Field(default_factory=list, description="目标")
    pain_points: list[str] = Field(default_factory=list, description="痛点")
    behavior: str | None = Field(default=None, description="行为特征描述")


class Feature(BaseModel):
    """功能点 —— 供前端 FeatureMatrix 组件渲染。"""

    name: str
    description: str = Field(default="", description="功能描述")
    category: str | None = Field(default=None, description="功能分类")
    priority: Literal["P0", "P1", "P2"] = Field(default="P1", description="优先级")


class RoadmapItem(BaseModel):
    """路线图阶段 —— 供前端 RoadmapTimeline 组件渲染。"""

    phase: str = Field(description="阶段名（如 Phase 1 · MVP）")
    title: str = Field(description="阶段主题")
    goal: str | None = Field(default=None, description="阶段目标")
    timeline: str | None = Field(default=None, description="时间周期（如 Q1-Q2）")
    milestones: list[str] = Field(default_factory=list, description="里程碑")


class PRDSection(BaseModel):
    """PRD 章节 —— 供前端 PRDViewer 组件渲染。"""

    title: str = Field(description="章节标题（如：产品概述）")
    content: str = Field(description="章节正文（Markdown 文本，不含 HTML/CSS）")


class ProductStrategy(BaseModel):
    """Product Agent 完整输出。"""

    positioning: str = Field(default="", description="产品定位一句话")
    personas: list[Persona] = Field(default_factory=list)
    features: list[Feature] = Field(default_factory=list)
    roadmap: list[RoadmapItem] = Field(default_factory=list)
    prd_sections: list[PRDSection] = Field(default_factory=list)
    sources: list[SourceRef] = Field(default_factory=list, description="本资产使用的资料来源（必须来自审核资料列表）")
