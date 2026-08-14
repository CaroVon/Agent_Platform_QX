"""
上下文管理 —— 组装消息与预算截断
============================================================

把上游 Agent 的结构化产物序列化为带标签的上下文块注入 Prompt，
超过字符预算时按块截断，防止超长上下文失控。
"""

from __future__ import annotations

from typing import Any


def _to_json(data: Any) -> str:
    import json

    if hasattr(data, "model_dump_json"):
        return data.model_dump_json()
    return json.dumps(data, ensure_ascii=False, default=str)


class ContextManager:
    """消息组装 + 字符预算管理。"""

    def __init__(self, char_budget: int = 60000):
        self.char_budget = char_budget

    def build_user_message(
        self,
        objective: str,
        inputs: dict[str, Any] | None = None,
        artifacts: dict[str, Any] | None = None,
        plan_text: str = "",
        reflection: str = "",
    ) -> str:
        """组装 User Message：目标 + 计划 + 输入 + 上游产物 + 反思。"""
        parts: list[str] = [f"【任务目标】\n{objective}"]

        if plan_text:
            parts.append(f"【执行计划】\n{plan_text}")

        if inputs:
            parts.append("【输入】\n" + self._render_blocks(inputs))

        if artifacts:
            parts.append("【上游 Agent 产物（可信参考）】\n" + self._render_blocks(artifacts))

        if reflection:
            parts.append(f"【上一轮反思与修正要求】\n{reflection}")

        message = "\n\n".join(parts)
        return self._apply_budget(message)

    def _render_blocks(self, blocks: dict[str, Any]) -> str:
        lines: list[str] = []
        for label, value in blocks.items():
            if value is None:
                continue
            lines.append(f"### {label}\n{_to_json(value)}")
        return "\n\n".join(lines)

    def _apply_budget(self, message: str) -> str:
        """按字符预算截断，优先保留目标/计划（头部），截断尾部产物块。"""
        if len(message) <= self.char_budget:
            return message
        head = message[: max(self.char_budget // 3, 500)]
        tail = message[-(self.char_budget - len(head)) :]
        return head + "\n\n...（中间内容因上下文预算被截断）...\n\n" + tail
