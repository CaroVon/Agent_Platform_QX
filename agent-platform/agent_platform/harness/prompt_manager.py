"""
Prompt 管理 —— 模板注册与渲染
============================================================

集中管理各 Agent 的 System Prompt 模板；
render() 使用 str.format_map 渲染变量，缺失变量渲染为空字符串。
"""

from __future__ import annotations


class PromptManager:
    """Prompt 模板注册表。"""

    def __init__(self):
        self._templates: dict[str, str] = {}

    def register(self, name: str, template: str) -> None:
        self._templates[name] = template

    def get(self, name: str) -> str | None:
        return self._templates.get(name)

    def render(self, name: str, **variables: object) -> str:
        """渲染模板；未提供的变量置为空字符串。"""
        template = self._templates.get(name)
        if template is None:
            raise KeyError(f"Prompt 模板未注册: {name}")

        class _Missing(dict):
            def __missing__(self, key: str) -> str:
                return ""

        return template.format_map(_Missing(**variables))
