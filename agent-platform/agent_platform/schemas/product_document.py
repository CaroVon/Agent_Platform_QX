"""
============================================================
Canonical Product Document —— 产品语义层契约
============================================================

P1 核心：表示"产品本身"的数据，**禁止出现任何排版字段**
（不得有 font_size/margin/left 等视觉参数）。

它与叙事层（Presentation DSL）彻底分离：
  - ProductDocument  = 产品是什么（研究/策略/设计的事实）
  - Presentation     = 怎么讲、怎么组织信息（视觉叙事结构）
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from agent_platform.schemas.design import UXDesign
from agent_platform.schemas.product import ProductStrategy
from agent_platform.schemas.research import CompetitorAnalysis, MarketResearch

if TYPE_CHECKING:  # pragma: no cover
    from agent_platform.schemas.package import ProductAssetPackage


class ProjectInfo(BaseModel):
    """项目元信息。"""

    idea: str = Field(description="产品想法（原始/规范化表述）")
    title: str | None = Field(default=None, description="项目标题（可为空，回退 idea）")
    created_at: str = Field(default="", description="ISO 时间戳")
    version: str = Field(default="1.0", description="契约版本")


class ProductDocument(BaseModel):
    """Canonical Product Document —— 语义层的唯一事实来源。"""

    project_info: ProjectInfo
    research: MarketResearch | None = None
    competitor_analysis: CompetitorAnalysis | None = None
    strategy: ProductStrategy | None = None
    design: UXDesign | None = None

    @classmethod
    def from_asset_package(cls, package: "ProductAssetPackage") -> "ProductDocument":
        """从（含 presentation 的）完整资产包提取语义层。"""
        return cls(
            project_info=ProjectInfo(
                idea=package.idea,
                created_at=package.meta.created_at,
            ),
            research=package.research,
            competitor_analysis=package.competitor_analysis,
            strategy=package.strategy,
            design=package.design,
        )
