"""
============================================================
LangGraph 工作流层
============================================================

  - state.py                   工作流结构化状态（TypedDict）
  - product_research_graph.py  产品研究工作流图（7 节点线性流水线）
"""

from agent_platform.workflows.product_research_graph import (
    ProductResearchGraph,
    build_product_research_graph,
    run_pipeline,
)
from agent_platform.workflows.state import ProductStudioState

__all__ = [
    "ProductResearchGraph",
    "ProductStudioState",
    "build_product_research_graph",
    "run_pipeline",
]
