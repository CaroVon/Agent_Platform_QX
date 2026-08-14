"""
测试替身 —— FakeLLM（零网络依赖）
============================================================

供平台层与业务 Agent 的单元/集成测试共用：
responses 按调用顺序弹出脚本化响应（dict / 原始文本 / Exception）。
"""

from __future__ import annotations

from agent_platform.llm.client import LLMOutputParseError


class FakeLLM:
    """脚本化模型客户端。"""

    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.calls: list[dict] = []

    def complete(self, messages, temperature=None, max_tokens=None) -> str:
        self.calls.append({"kind": "complete", "messages": messages})
        if not self.responses:
            return "{}"
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def complete_json(self, messages, temperature=None, max_tokens=None) -> dict:
        self.calls.append({"kind": "json", "messages": messages})
        if not self.responses:
            return {}
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        if isinstance(item, dict):
            return item
        # 字符串：当作原始 LLM 文本，走真实解析路径（含围栏剥离）
        import json

        from agent_platform.llm.client import _extract_json_block

        try:
            return json.loads(_extract_json_block(item))
        except json.JSONDecodeError as exc:
            raise LLMOutputParseError(str(exc)) from exc
