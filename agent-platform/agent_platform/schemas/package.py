"""
最终产品资产包 —— 工作流的最终交付物
============================================================

包含六个专业节点产出的全部结构化资产:
  requirement → research → competitor_analysis → strategy → design → presentation
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from agent_platform.schemas.requirement import RequirementSpec
from agent_platform.schemas.research import CompetitorAnalysis, MarketResearch
from agent_platform.schemas.product import ProductStrategy
from agent_platform.schemas.design import UXDesign
from agent_platform.schemas.presentation import Presentation
from agent_platform.schemas.product_document import ProductDocument


class AssetPackageMeta(BaseModel):
    """资产包元信息（进度与模型分工记录）。"""

    idea: str
    created_at: str = Field(description="ISO 时间戳")
    node_status: dict[str, str] = Field(default_factory=dict, description="节点名 → 状态")
    node_models: dict[str, str] = Field(
        default_factory=dict, description="节点名 → 模型名（前端展示当前工作的模型）"
    )
    errors: dict[str, str] = Field(default_factory=dict, description="节点名 → 错误信息")


class ProductAssetPackage(BaseModel):
    """最终交付：完整的产品资产包（API 响应 / 前端工作区数据源）。"""

    idea: str
    requirement: RequirementSpec | None = None
    research: MarketResearch | None = None
    competitor_analysis: CompetitorAnalysis | None = None
    strategy: ProductStrategy | None = None
    design: UXDesign | None = None
    presentation: Presentation | None = None
    ppt_design: dict | None = Field(
        default=None,
        description="P6: PPT 设计成员产物（ppt-master 项目/pptx 路径/模型）",
    )
    document: ProductDocument | None = Field(
        default=None,
        description="P1: Canonical Product Document（语义层，不含排版）",
    )
    critic_score: int | None = Field(
        default=None,
        description="P5: Critic Agent 最终评分（0-100）",
    )
    gate_report: dict | None = Field(
        default=None,
        description="P5: 确定性视觉质量门报告",
    )
    meta: AssetPackageMeta
