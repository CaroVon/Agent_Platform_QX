"""
============================================================
Agent Platform Runtime
============================================================

面向 AI Product Studio 的现代 Agent Runtime 层：

  - harness/     Agent 执行循环、规划、Prompt 管理、上下文管理、结构化输出
  - workflows/   LangGraph 工作流（状态管理 + 多 Agent 编排）
  - schemas/     Pydantic 结构化契约（Agent 间通信协议）
  - tools/       搜索 / 文档 / 外部 API 工具
  - memory/      项目级持久记忆
  - config/      集中配置
  - llm/         模型层（DeepSeek / Qwen / GPT 兼容）

本平台独立于业务应用（QX_product_agent），不反向依赖任何业务代码。
"""

__version__ = "0.1.0"

from agent_platform.schemas.package import ProductAssetPackage
from agent_platform.workflows.product_research_graph import (
    ProductResearchGraph,
    run_pipeline,
)

__all__ = [
    "__version__",
    "ProductAssetPackage",
    "ProductResearchGraph",
    "run_pipeline",
]
