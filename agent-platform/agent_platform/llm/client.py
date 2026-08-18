"""
============================================================
模型层客户端 —— OpenAI 兼容接口（DeepSeek / Qwen / GPT）
============================================================

平台层不依赖 LangChain，直接以 httpx 调用 Chat Completions，
保证与任何 OpenAI 兼容网关（DeepSeek / Qwen / GPT / 硅基流动）互通。

文本补全 + 结构化 JSON 输出两条路径：
  - complete()      自由文本补全
  - complete_json() 强制 JSON 输出（解析失败抛 LLMOutputParseError，
                     由 harness 层负责自愈重试）
"""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from typing import Any

import httpx

from agent_platform.config.settings import PlatformSettings, get_settings

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """模型调用失败（网络 / 认证 / 服务端错误）。"""


class LLMOutputParseError(ValueError):
    """模型输出不是合法 JSON，或解析失败。"""


def _extract_json_block(text: str) -> str:
    """从模型输出中提取 JSON 片段（容忍 ```json 围栏与前后缀文本）。

    兼容带推理前缀的模型（MiniMax-Text-01/M3 等输出 <think>…</think>）：
    先剥离推理块，再按围栏/首尾花括号提取。
    """
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    # 无围栏：截取第一个 { 到最后一个 }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        return text[start : end + 1]
    return text.strip()


class LLMClient:
    """同步 OpenAI 兼容 Chat Completions 客户端。"""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: int = 180,
        max_tokens: int = 8192,
        temperature: float = 0.2,
        extra_body: dict | None = None,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.extra_body = extra_body
        # ── token 用量累计（成本可观测） ──
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_requests = 0

    @property
    def usage_summary(self) -> dict:
        """累计用量摘要。"""
        return {
            "model": self.model,
            "requests": self.total_requests,
            "prompt_tokens": self.total_prompt_tokens,
            "completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_prompt_tokens + self.total_completion_tokens,
        }

    # ─── 文本补全 ────────────────────────────────────────────
    def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """调用 Chat Completions，返回模型文本输出。"""
        if not self.api_key:
            raise LLMError(
                "LLM API Key 未配置。请设置 AGENT_PLATFORM_LLM_API_KEY "
                "或 DEEPSEEK_API_KEY 环境变量。"
            )

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature if temperature is None else temperature,
            "max_tokens": self.max_tokens if max_tokens is None else max_tokens,
            "stream": False,
        }
        if self.extra_body:
            payload.update(self.extra_body)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            resp = httpx.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise LLMError(f"LLM 请求失败: {exc}") from exc

        if resp.status_code != 200:
            raise LLMError(
                f"LLM 返回 {resp.status_code}: {resp.text[:300]}"
            )

        data = resp.json()
        try:
            content = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"LLM 响应结构异常: {str(data)[:300]}") from exc
        # ── usage 累计（多数兼容端点返回 usage 字段） ──
        try:
            usage = data.get("usage") or {}
            self.total_prompt_tokens += int(usage.get("prompt_tokens") or 0)
            self.total_completion_tokens += int(usage.get("completion_tokens") or 0)
            self.total_requests += 1
        except (TypeError, ValueError):
            pass
        return content

    # ─── 结构化 JSON 输出 ────────────────────────────────────
    def complete_json(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """要求模型仅输出 JSON 并解析为字典。"""
        system_note = (
            "你必须只输出一个合法的 JSON 对象，不要输出任何解释、注释或 Markdown 代码块标记。"
        )
        patched = list(messages)
        if patched and patched[0].get("role") == "system":
            patched[0] = {**patched[0], "content": patched[0]["content"] + "\n" + system_note}
        else:
            patched.insert(0, {"role": "system", "content": system_note})

        raw = self.complete(patched, temperature=temperature, max_tokens=max_tokens)
        block = _extract_json_block(raw)
        try:
            return json.loads(block)
        except json.JSONDecodeError as exc:
            # 阶梯兜底：1) 宽松模式（容忍字符串内控制字符，MiniMax 长文常见）
            # 2) 依次尝试其它 `{` 起点（推理文本中可能含花括号干扰）
            for strict in (False, True):
                try:
                    return json.loads(block, strict=strict)
                except json.JSONDecodeError:
                    continue
            idx = block.find("{")
            while idx != -1:
                candidate = block[idx : block.rfind("}") + 1]
                for strict in (False, True):
                    try:
                        return json.loads(candidate, strict=strict)
                    except json.JSONDecodeError:
                        continue
                idx = block.find("{", idx + 1)
            raise LLMOutputParseError(
                f"模型输出无法解析为 JSON: {exc.msg}（原始输出前 200 字符: {raw[:200]!r}）"
            ) from exc


@lru_cache()
def _cached_client() -> LLMClient:
    settings = get_settings()
    return LLMClient(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        model=settings.LLM_MODEL,
        timeout=settings.LLM_TIMEOUT,
        max_tokens=settings.LLM_MAX_TOKENS,
        temperature=settings.LLM_TEMPERATURE,
    )


def get_llm_client() -> LLMClient:
    """惰性单例：按配置创建模型客户端。"""
    return _cached_client()


@lru_cache()
def _cached_presentation_client() -> LLMClient | None:
    """Presentation Agent 专用模型（P3，如 Kimi）；未配置返回 None。"""
    settings = get_settings()
    if not (settings.PRESENTATION_LLM_MODEL and settings.PRESENTATION_LLM_API_KEY):
        return None
    base_url = settings.PRESENTATION_LLM_BASE_URL or settings.LLM_BASE_URL
    extra_body = None
    if settings.PRESENTATION_LLM_EXTRA_JSON.strip():
        try:
            extra_body = json.loads(settings.PRESENTATION_LLM_EXTRA_JSON)
        except json.JSONDecodeError:
            logger.warning("PRESENTATION_LLM_EXTRA_JSON 非合法 JSON，忽略")
    return LLMClient(
        api_key=settings.PRESENTATION_LLM_API_KEY,
        base_url=base_url,
        model=settings.PRESENTATION_LLM_MODEL,
        timeout=settings.LLM_TIMEOUT,
        max_tokens=settings.LLM_MAX_TOKENS,
        temperature=settings.LLM_TEMPERATURE,
        extra_body=extra_body,
    )


def get_presentation_llm_client() -> LLMClient:
    """Presentation 专用模型（Kimi 等）；未配置时回退主 LLM。"""
    return _cached_presentation_client() or get_llm_client()
