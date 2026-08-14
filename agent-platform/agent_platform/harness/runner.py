"""
结构化输出 Runner —— LLM JSON → Pydantic 校验 + 自愈重试
============================================================

核心机制（对应 Phase 5 的 retry + self-reflection）:
  1. 要求 LLM 输出 JSON
  2. Pydantic 严格校验
  3. 校验失败 → 把错误信息作为修正要求回传给 LLM → 重试
  4. 超过 max_retries 仍未通过 → 抛 StructuredOutputError

这是"LLM 输出必须遵循 Schema"的强制执行点。
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, ValidationError

from agent_platform.llm.client import LLMClient, LLMError, LLMOutputParseError

logger = logging.getLogger(__name__)


class StructuredOutputError(RuntimeError):
    """结构化输出在重试后仍无法通过 Schema 校验。"""


def schema_guidance(schema: type[BaseModel]) -> str:
    """把 Pydantic Schema 转成注入 Prompt 的 JSON 结构说明。"""
    import json

    return json.dumps(schema.model_json_schema(), ensure_ascii=False)


class StructuredRunner:
    """带自愈重试的结构化 LLM 调用器。"""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def run(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: type[BaseModel],
        max_retries: int = 2,
        temperature: float | None = None,
    ) -> BaseModel:
        """
        执行一次结构化生成，返回 Schema 校验通过的模型实例。

        Raises:
            StructuredOutputError: 重试耗尽后仍未通过校验
        """
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"{user_prompt}\n\n"
                    f"【输出 Schema（JSON Schema，必须严格遵循）】\n{schema_guidance(schema)}"
                ),
            },
        ]

        last_error: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                data = self.llm.complete_json(messages, temperature=temperature)
                return schema.model_validate(data)
            except (LLMOutputParseError, ValidationError, LLMError) as exc:
                last_error = exc
                if attempt >= max_retries:
                    break
                logger.warning(
                    "结构化输出第 %d/%d 次失败（%s），回传错误自愈重试",
                    attempt + 1,
                    max_retries + 1,
                    type(exc).__name__,
                )
                messages.append({"role": "assistant", "content": f"(上次输出无效)"})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "你的上一次输出未通过校验，错误如下：\n"
                            f"{_error_text(exc)}\n\n"
                            "请修正后重新输出符合 Schema 的 JSON 对象，不要输出任何其他内容。"
                        ),
                    }
                )

        raise StructuredOutputError(
            f"结构化输出在 {max_retries + 1} 次尝试后仍未通过校验: {_error_text(last_error)}"
        )


def _error_text(exc: Exception | None) -> str:
    if exc is None:
        return "未知错误"
    if isinstance(exc, ValidationError):
        return str(exc)[:1500]
    return str(exc)[:1500]
