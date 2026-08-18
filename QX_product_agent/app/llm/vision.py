"""
============================================================
MiniMax 视觉分析客户端 (VL)
—— 图片理解 → 结构化 JSON（描述/OCR/标签/主体/场景/图表数据）
============================================================

模型: minimax-vl-01（MiniMax VL-01）
接入: OpenAI 兼容多模态消息格式（image_url 内容块）
  - 官方 V2 端点:  {base}/v1/text/chatcompletion_v2
  - OpenAI 兼容:   {base}/v1/chat/completions

图片传递方式:
  - 本地文件 → base64 data URL（单图 ≤20MB，单请求 ≤6 张）
  - 网络 URL  → 直接传 http(s) URL

配置（app.core.config.Settings）:
  MINIMAX_API_KEY            必填（与文本模型共用同一 Key）
  MINIMAX_VISION_MODEL       默认 minimax-vl-01
  MINIMAX_VISION_ENDPOINT    默认 https://api.minimax.chat/v1/text/chatcompletion_v2
"""

from __future__ import annotations

import base64
import json
import logging
import mimetypes
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# 官方/社区公认的图片格式 → MIME 映射
_IMAGE_MIME_MAP = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
}


def _mime_of(path: str) -> str:
    mime, _ = mimetypes.guess_type(path)
    if mime and mime.startswith("image/"):
        return mime
    suffix = Path(path).suffix.lower()
    mime = _IMAGE_MIME_MAP.get(suffix)
    if not mime:
        raise ValueError(f"不支持的图片格式: {suffix or '(无扩展名)'}")
    return mime


def image_to_data_url(path: str, max_bytes: int = 20 * 1024 * 1024) -> str:
    """读取本地图片并编码为 data URL（供 VL 接口直接消费）。"""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"图片不存在: {path}")
    if p.stat().st_size > max_bytes:
        raise ValueError(f"图片超过大小上限 {max_bytes // (1024 * 1024)}MB: {path}")
    encoded = base64.b64encode(p.read_bytes()).decode("ascii")
    return f"data:{_mime_of(path)};base64,{encoded}"


def _resolve_endpoint(base_url: str, endpoint: str) -> str:
    """端点兼容：允许配置 'chat/completions' 与 'chatcompletion_v2' 两种形态。"""
    e = endpoint.strip().rstrip("/")
    if e.endswith("chat/completions") or e.endswith("chatcompletion_v2"):
        return e
    if e.endswith("/v1"):
        return e + "/text/chatcompletion_v2"
    return e


def analyze_image(
    image_path: str | None = None,
    image_url: str | None = None,
    prompt: str | None = None,
    max_tokens: int = 4096,
    timeout: int = 120,
) -> str:
    """
    调用 MiniMax VL 模型分析一张图片，返回模型文本输出。

    Args:
        image_path: 本地图片路径（与 image_url 二选一，优先 image_path）
        image_url:  http(s) 图片 URL 或 data URL
        prompt:     分析指令（默认：结构化中文描述）
        max_tokens: 输出上限
        timeout:    请求超时（秒）

    Returns:
        模型输出文本。分析失败抛异常由调用方决定重试/降级。
    """
    try:
        from app.core.config import get_settings
        settings = get_settings()
        api_key = settings.MINIMAX_API_KEY
        endpoint = _resolve_endpoint(settings.MINIMAX_BASE_URL or "https://api.minimax.chat/v1",
                                     settings.MINIMAX_VISION_ENDPOINT)
        model = settings.MINIMAX_VISION_MODEL or "minimax-vl-01"
        max_mb = settings.KB_IMAGE_MAX_MB
    except ImportError:
        import os
        api_key = os.environ.get("MINIMAX_API_KEY", "")
        endpoint = os.environ.get(
            "MINIMAX_VISION_ENDPOINT",
            "https://api.minimax.chat/v1/text/chatcompletion_v2",
        )
        model = os.environ.get("MINIMAX_VISION_MODEL", "minimax-vl-01")
        max_mb = int(os.environ.get("KB_IMAGE_MAX_MB", "20"))

    if not api_key:
        raise RuntimeError("MINIMAX_API_KEY 未配置，无法执行图片分析")

    if image_path:
        url = image_to_data_url(image_path, max_bytes=max_mb * 1024 * 1024)
    elif image_url:
        url = image_url
    else:
        raise ValueError("必须提供 image_path 或 image_url 之一")

    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": url}},
                {"type": "text", "text": prompt or (
                    "请用中文详细分析这张图片，输出：1) 图片概述（主体、场景、关键信息，80-150字）；"
                    "2) 图中全部文字（OCR，无则写'无'）；"
                    "3) 3-6 个标签（如行业、品类、设计风格）；"
                    "4) 核心主体/产品名；5) 使用场景；6) 若为图表/数据图，提取数据要点。"
                )},
            ],
        }],
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        resp = httpx.post(endpoint, json=payload, headers=headers, timeout=timeout)
    except httpx.HTTPError as exc:
        raise RuntimeError(f"MiniMax VL 请求失败: {exc}") from exc

    if resp.status_code != 200:
        raise RuntimeError(f"MiniMax VL 返回 {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        # 官方 V2 端点个别响应形态：data.reply 或 data.content
        content = data.get("reply") or data.get("content") or ""
    if not content:
        raise RuntimeError(f"MiniMax VL 返回空内容: {str(data)[:300]}")
    return content


def analyze_image_structured(
    image_path: str | None = None,
    image_url: str | None = None,
    max_tokens: int = 4096,
) -> dict[str, Any]:
    """
    分析图片并强制解析为结构化 JSON。

    返回 schema:
      {
        "summary":    str  概述（80-150字）
        "ocr_text":   str  图中全部文字（无则空串）
        "tags":       list[str] 3-6 个标签
        "subject":    str  核心主体/产品名
        "scene":      str  使用场景
        "chart_data": str  图表数据要点（非图表则空串）
      }

    解析失败时抛出 ValueError（调用方应降级为纯文本入库）。
    """
    prompt = (
        "请分析这张图片，严格输出 JSON 对象（不要 Markdown 代码块、不要解释），字段：\n"
        '{"summary": "80-150字中文概述（主体、场景、关键信息）", '
        '"ocr_text": "图中全部文字，无文字则为空字符串", '
        '"tags": ["3-6个标签，如行业、品类、设计风格"], '
        '"subject": "核心主体/产品名", '
        '"scene": "使用场景", '
        '"chart_data": "图表/数据图的数据要点，非图表则为空字符串"}'
    )
    raw = analyze_image(
        image_path=image_path, image_url=image_url,
        prompt=prompt, max_tokens=max_tokens,
    )
    # 剥离推理前缀/围栏后解析
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        text = text[start:end + 1]
    try:
        result = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"MiniMax VL 结构化输出解析失败: {exc}（原文: {raw[:200]!r}）") from exc

    # 归一化字段
    normalized = {
        "summary": str(result.get("summary") or "").strip(),
        "ocr_text": str(result.get("ocr_text") or result.get("ocr") or "").strip(),
        "tags": [str(t).strip() for t in (result.get("tags") or []) if str(t).strip()][:8],
        "subject": str(result.get("subject") or "").strip(),
        "scene": str(result.get("scene") or "").strip(),
        "chart_data": str(result.get("chart_data") or "").strip(),
    }
    if not normalized["summary"] and not normalized["ocr_text"]:
        raise ValueError("MiniMax VL 输出缺少有效内容")
    return normalized


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python vision.py <图片路径或URL>")
        sys.exit(1)
    src = sys.argv[1]
    if src.startswith(("http://", "https://")):
        result = analyze_image_structured(image_url=src)
    else:
        result = analyze_image_structured(image_path=src)
    print(json.dumps(result, ensure_ascii=False, indent=2))
