"""
============================================================
工具层 —— 搜索 / 文档 / 外部 API
============================================================

工具是平台层的可插拔能力，Agent 通过 ToolRegistry 声明式调用。
工具之间无隐式依赖，任何工具缺失（如无 API Key）时优雅降级。
"""

from agent_platform.tools.search_tools import SearchResult, WebSearchTool
from agent_platform.tools.document_tools import DocumentTool
from agent_platform.tools.registry import ToolRegistry

__all__ = ["SearchResult", "WebSearchTool", "DocumentTool", "ToolRegistry"]
