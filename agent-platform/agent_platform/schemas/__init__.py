"""
============================================================
Schemas —— Pydantic 结构化契约
============================================================

所有 Agent 的输入输出必须遵循本层的结构化模型：
  - LLM 只生成 JSON，由 Pydantic 校验后再进入工作流状态
  - 前端渲染器只消费这些结构，LLM 不直接生成 HTML/CSS
"""

from agent_platform.schemas.common import AgentResult, NodeError, PlanStep, SourceRef
from agent_platform.schemas.requirement import RequirementSpec
from agent_platform.schemas.research import (
    Competitor,
    CompetitorAnalysis,
    CompetitorMatrix,
    CompetitorProfile,
    MarketResearch,
    MarketSize,
)
from agent_platform.schemas.product import (
    Feature,
    Persona,
    PRDSection,
    ProductStrategy,
    RoadmapItem,
)
from agent_platform.schemas.design import ComponentSpec, PageSpec, UXDesign, UserFlowStep
from agent_platform.schemas.presentation import (
    Component,
    DeckSection,
    LAYOUT_LIBRARY,
    Page,
    Presentation,
    Slide,
    SlideBlock,
    SlideDeck,
    Theme,
)
from agent_platform.schemas.product_document import ProductDocument, ProjectInfo
from agent_platform.schemas.package import AssetPackageMeta, ProductAssetPackage

__all__ = [
    # common
    "AgentResult",
    "NodeError",
    "PlanStep",
    # requirement
    "RequirementSpec",
    # research
    "Competitor",
    "CompetitorAnalysis",
    "CompetitorMatrix",
    "CompetitorProfile",
    "MarketResearch",
    "MarketSize",
    # product
    "Feature",
    "Persona",
    "PRDSection",
    "ProductStrategy",
    "RoadmapItem",
    # design
    "ComponentSpec",
    "PageSpec",
    "UXDesign",
    "UserFlowStep",
    # presentation (DSL)
    "Component",
    "DeckSection",
    "LAYOUT_LIBRARY",
    "Page",
    "Presentation",
    "Slide",
    "SlideBlock",
    "SlideDeck",
    "Theme",
    # product document (P1)
    "ProductDocument",
    "ProjectInfo",
    # package
    "AssetPackageMeta",
    "ProductAssetPackage",
]
