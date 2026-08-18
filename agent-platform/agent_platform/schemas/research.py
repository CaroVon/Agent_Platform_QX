"""
市场研究 —— Research Agent 与 Competitor Analysis 节点的结构化输出

Research Agent 输出契约（对齐产品需求）:
  {
    "market_size": { ... },
    "competitors": [],
    "customer_pain_points": [],
    "industry_trends": []
  }
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from agent_platform.schemas.common import SourceRef


class MarketSize(BaseModel):
    """市场规模（结构化对象，替代原先的纯文本描述）。"""

    summary: str = Field(description="市场规模一句话总结")
    tam: str | None = Field(default=None, description="TAM 总体可寻址市场")
    sam: str | None = Field(default=None, description="SAM 可服务市场")
    som: str | None = Field(default=None, description="SOM 可获得市场")
    cagr: str | None = Field(default=None, description="复合年增长率")
    source: str | None = Field(default=None, description="数据来源")


class Competitor(BaseModel):
    """市场研究阶段的竞品摘要（轻量级）。"""

    name: str
    url: str | None = Field(default=None, description="官网/产品链接")
    positioning: str | None = Field(default=None, description="一句话定位")


class MarketResearch(BaseModel):
    """Research Agent 的市场研究输出。"""

    market_size: MarketSize
    competitors: list[Competitor] = Field(default_factory=list)
    customer_pain_points: list[str] = Field(default_factory=list, description="用户痛点")
    industry_trends: list[str] = Field(default_factory=list, description="行业趋势")
    sources: list[SourceRef] = Field(default_factory=list, description="本资产使用的资料来源（必须来自审核资料列表）")


class CompetitorProfile(BaseModel):
    """Competitor Analysis 节点的单竞品深度画像。"""

    name: str
    positioning: str = Field(default="", description="市场定位")
    target_segment: str | None = Field(default=None, description="目标客群")
    pricing: str | None = Field(default=None, description="定价策略")
    strengths: list[str] = Field(default_factory=list, description="优势")
    weaknesses: list[str] = Field(default_factory=list, description="劣势")
    threat_level: Literal["high", "medium", "low"] = Field(default="medium", description="威胁等级")


class CompetitorMatrix(BaseModel):
    """竞品对比矩阵 —— 供前端 CompetitorMatrix 组件渲染。"""

    dimensions: list[str] = Field(
        default_factory=lambda: ["定位", "目标客群", "定价", "核心优势", "主要劣势"],
        description="矩阵对比维度",
    )
    profiles: list[CompetitorProfile] = Field(default_factory=list)


class CompetitorAnalysis(BaseModel):
    """Competitor Analysis 节点输出。"""

    competitors: list[CompetitorProfile] = Field(default_factory=list)
    matrix: CompetitorMatrix = Field(default_factory=CompetitorMatrix)
    competitive_landscape: str = Field(default="", description="竞争格局综述")
    differentiation_opportunities: list[str] = Field(
        default_factory=list, description="差异化机会点"
    )
    sources: list[SourceRef] = Field(default_factory=list, description="本资产使用的资料来源（必须来自审核资料列表）")
