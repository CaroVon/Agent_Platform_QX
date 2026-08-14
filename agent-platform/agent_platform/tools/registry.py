"""
工具注册表 —— Agent 声明式获取工具能力
============================================================

每个工具暴露统一的 (name, description, run) 契约；
describe() 生成注入 System Prompt 的工具清单。
"""

from __future__ import annotations

from typing import Any, Protocol

from agent_platform.tools.document_tools import DocumentTool
from agent_platform.tools.search_tools import WebSearchTool


class Tool(Protocol):
    name: str
    description: str

    def run(self, *args: Any, **kwargs: Any) -> Any: ...


class ToolRegistry:
    """按名称注册/获取工具。"""

    def __init__(self, tools: list[Tool] | None = None):
        self._tools: dict[str, Tool] = {t.name: t for t in (tools or [])}

    def register(self, tool: Tool) -> "ToolRegistry":
        self._tools[tool.name] = tool
        return self

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def describe(self) -> str:
        """生成工具清单文本，供 Agent Prompt 引用。"""
        if not self._tools:
            return "（无可用工具）"
        lines = [f"- {name}: {tool.description}" for name, tool in self._tools.items()]
        return "\n".join(lines)

    @classmethod
    def default(cls) -> "ToolRegistry":
        """默认工具集：全网搜索 + 本地文档。"""
        return cls(tools=[WebSearchTool(), DocumentTool()])
