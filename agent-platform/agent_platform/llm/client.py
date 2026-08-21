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
import threading
import time
from functools import lru_cache
from typing import Any, ClassVar

import httpx

from agent_platform.config.settings import PlatformSettings, get_settings

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """模型调用失败（网络 / 认证 / 服务端错误）。

    扩展字段（供限流分类与自适应并发降级使用）：
      - status_code: HTTP 状态码；MiniMax 等兼容端点在 HTTP 200 内返回
        业务错误时，此处为业务错误码（如图片接口配额耗尽的 2056）
      - error_body: 原始响应体片段，供关键词判定
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        error_body: str = "",
    ):
        super().__init__(message)
        self.status_code = status_code
        self.error_body = error_body


class LLMOutputParseError(ValueError):
    """模型输出不是合法 JSON，或解析失败。"""


# ── 限流分类（供并发控制器决定降级策略） ──────────────────────────
# MiniMax 配额耗尽关键词（中文 + 英文；图片接口实测 2056:
#   "已达到 Token Plan 用量上限：请升级 Token Plan 套餐或购买积分补充用量。"）
_QUOTA_MARKERS = (
    "token plan", "用量上限", "配额", "quota", "余额",
    "insufficient", "plan exhausted", "credit",
)


def classify_llm_error(exc: Exception) -> str:
    """把 LLM 调用异常分为三类，供自适应并发控制器决策。

    Returns:
      - "rate_limit_transient": 瞬时限流（RPM/TPM 429）。暂停 + 降并发后
        重试可能成功 → 页面重排队。
      - "rate_limit_quota": 配额耗尽（MiniMax Token Plan 等）。重试无意义，
        → 页面立即 fallback，不浪费请求。
      - "other": 网络 / 认证 / 解析等其它错误。按页面级重试处理。
    """
    if not isinstance(exc, LLMError):
        return "other"
    code = exc.status_code
    text = f"{exc} {exc.error_body}".lower()
    if any(marker in text for marker in _QUOTA_MARKERS):
        return "rate_limit_quota"
    if code == 429:
        return "rate_limit_transient"
    if any(k in text for k in (
        "rate limit", "rate-limit", "rate_limit", "too many requests",
        "throttl", "429",
    )):
        return "rate_limit_transient"
    return "other"


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
        # ── token 用量累计（成本可观测；并发调用需加锁防丢更新） ──
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_requests = 0
        self._stats_lock = threading.Lock()

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
    # 硬超时余量：sync httpx 的 timeout 不覆盖 DNS 解析（getaddrinfo），
    # fork 子进程/内存高压下会无限挂起（E2E 实测：所有线程 futex 等待）。
    # 三层防御：
    #   1) 域名钉扎：父进程侧有界解析 → 按 IP 直连 + SNI/Host 保真（绕开
    #      fork 子进程的 getaddrinfo 挂死，证书校验不受影响）
    #   2) 硬超时：守护线程 + future 超时兜底（挂起转化为 LLMError）
    #   3) 既有降级：LLMError 由各调用点的回退/重试路径承接
    _HARD_TIMEOUT_MARGIN = 30.0
    _DNS_PIN_TTL = 600.0
    _DNS_PIN: ClassVar[dict[str, tuple[str, float]]] = {}

    @classmethod
    def _resolve_bounded(cls, host: str, timeout: float = 5.0) -> str | None:
        """有界域名解析（守护线程，5s 超时；失败/超时返回 None 走原 URL）。"""
        import socket
        from concurrent.futures import ThreadPoolExecutor
        from concurrent.futures import TimeoutError as _FutTimeout

        cached = cls._DNS_PIN.get(host)
        now = time.monotonic()
        if cached and cached[1] > now:
            return cached[0]
        ex = ThreadPoolExecutor(max_workers=1, thread_name_prefix="llm-dns")
        try:
            infos = ex.submit(
                socket.getaddrinfo, host, 443, socket.AF_INET, socket.SOCK_STREAM
            ).result(timeout=timeout)
            ip = infos[0][4][0] if infos else None
            if ip:
                cls._DNS_PIN[host] = (ip, now + cls._DNS_PIN_TTL)
            return ip
        except (_FutTimeout, Exception):  # noqa: BLE001 —— 解析失败回退原 URL
            return None
        finally:
            ex.shutdown(wait=False)

    @staticmethod
    def _post_with_hard_timeout(fn, timeout_s: float):
        from concurrent.futures import ThreadPoolExecutor
        from concurrent.futures import TimeoutError as _FutTimeout

        ex = ThreadPoolExecutor(max_workers=1, thread_name_prefix="llm-post")
        try:
            return ex.submit(fn).result(timeout=timeout_s)
        except _FutTimeout:
            raise LLMError(
                f"LLM 请求硬超时（>{timeout_s:.0f}s，疑似 DNS/连接挂起），已中止等待")
        finally:
            # wait=False：挂起线程不阻塞调用方（泄漏线程数=挂起次数，可观测）
            ex.shutdown(wait=False)

    def complete(
        self,
        messages: list[dict, str],
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

        # 域名钉扎：有界解析 → IP 直连（SNI/Host 保真，绕开 fork 子进程
        # 的 getaddrinfo 挂死；解析失败回退原 URL，硬超时兜底）
        from urllib.parse import urlparse

        host = urlparse(self.base_url).hostname or ""
        ip = self._resolve_bounded(host) if host else None
        url = f"{self.base_url}/chat/completions"
        if ip and ip != host:
            url = f"{self.base_url.replace(host, ip, 1)}/chat/completions"
            headers["Host"] = host

        def _do_post():
            with httpx.Client(trust_env=False, timeout=self.timeout) as client:
                req = client.build_request("POST", url, json=payload, headers=headers)
                if ip and ip != host:
                    # TLS SNI 与证书校验仍按真实域名进行
                    req.extensions["sni_hostname"] = host
                return client.send(req)

        try:
            resp = self._post_with_hard_timeout(
                _do_post,
                self.timeout + self._HARD_TIMEOUT_MARGIN,
            )
        except httpx.HTTPError as exc:
            raise LLMError(f"LLM 请求失败: {exc}") from exc

        if resp.status_code != 200:
            raise LLMError(
                f"LLM 返回 {resp.status_code}: {resp.text[:300]}",
                status_code=resp.status_code,
                error_body=resp.text[:1000],
            )

        data = resp.json()
        # MiniMax 兼容：HTTP 200 但业务错误（如 Token Plan 用量上限 → base_resp.status_code 2056）。
        # 必须在此识别，否则会落入下方"响应结构异常"而丢失限流分类信息。
        base_resp = data.get("base_resp") or {}
        biz_code = base_resp.get("status_code")
        if biz_code not in (None, 0, "0"):
            raise LLMError(
                f"LLM 业务错误 {biz_code}: {str(base_resp.get('status_msg') or '')[:300]}",
                status_code=int(biz_code) if str(biz_code).isdigit() else None,
                error_body=str(data)[:1000],
            )
        # OpenAI 兼容网关：200 + error 字段
        if data.get("error"):
            err = data["error"]
            code = err.get("code") if isinstance(err, dict) else None
            raise LLMError(
                f"LLM 业务错误: {str(err)[:300]}",
                status_code=int(code) if str(code).isdigit() else None,
                error_body=str(data)[:1000],
            )
        try:
            content = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"LLM 响应结构异常: {str(data)[:300]}") from exc
        # ── usage 累计（多数兼容端点返回 usage 字段） ──
        try:
            usage = data.get("usage") or {}
            with self._stats_lock:  # 并发调用下防止计数器丢更新
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
