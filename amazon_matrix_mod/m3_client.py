"""MiniMax-M3 多模态客户端（P3.3）—— 图审 / 评论聚类 / 执行摘要。

能力边界（官方文档确认）：M3 接收文本+图像 → 输出文本；不做图像生成。
配置（复用 QX backend/.env）：
  AGENT_PLATFORM_PRESENTATION_LLM_API_KEY / _BASE_URL（https://api.minimax.chat/v1）
  AGENT_PLATFORM_PRESENTATION_LLM_EXTRA_JSON={"thinking":{"type":"disabled"}}
失败策略：M3 为增强层——失败记 warning 返回空结构，不阻塞主报告（确定性章节仍完整）。
"""
from __future__ import annotations

import base64
import json
import logging
import os

import requests

log = logging.getLogger(__name__)

MODEL = "MiniMax-M3"


def _cfg() -> dict:
    api_key = os.environ.get("AGENT_PLATFORM_PRESENTATION_LLM_API_KEY", "")
    if not api_key:
        raise RuntimeError("缺少 AGENT_PLATFORM_PRESENTATION_LLM_API_KEY（QX backend/.env）")
    base = os.environ.get("AGENT_PLATFORM_PRESENTATION_LLM_BASE_URL",
                          "https://api.minimax.chat/v1").rstrip("/")
    extra = {}
    raw = os.environ.get("AGENT_PLATFORM_PRESENTATION_LLM_EXTRA_JSON", "")
    if raw:
        try:
            extra = json.loads(raw)
        except json.JSONDecodeError:
            extra = {}
    return {"api_key": api_key, "base": base, "extra": extra}


def _strip_think(text: str) -> str:
    """剥离 M3 思考块（<think>...</think>，可能含未转义嵌套）。

    截断产生的未闭合 <think>（无 </think>）同样剥离到块尾——闭包缺失时
    其后内容属于思考过程残留，不可作为正文使用（实测 max_tokens 截断会复现）。
    """
    while "<think>" in text:
        start = text.find("<think>")
        end = text.find("</think>", start)
        if end == -1:
            text = text[:start]
            break
        text = text[:start] + text[end + len("</think>"):]
    return text.strip()


def chat(prompt: str, image_path: str | None = None, max_tokens: int = 1500,
         temperature: float = 0.4) -> str:
    """文本（可选附图）→ M3 回复文本（剥离思考块）。失败抛错。"""
    cfg = _cfg()
    content: list = [{"type": "text", "text": prompt}]
    if image_path and os.path.isfile(image_path):
        b64 = base64.b64encode(open(image_path, "rb").read()).decode()
        mime = "image/png" if image_path.endswith(".png") else "image/jpeg"
        content.append({"type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"}})
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": max_tokens,
        "temperature": temperature,
        **cfg["extra"],
    }
    last_err: Exception | None = None
    for attempt in range(3):  # 网络偶发（SSL/EOF）重试 3 次
        try:
            r = requests.post(f"{cfg['base']}/chat/completions",
                              headers={"Authorization": f"Bearer {cfg['api_key']}",
                                       "Content-Type": "application/json"},
                              json=payload, timeout=120)
            r.raise_for_status()
            msg = r.json()["choices"][0]["message"]["content"]
            return _strip_think(msg)
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            import time
            time.sleep(4 * (attempt + 1))
    raise RuntimeError(f"M3 请求失败: {last_err}")


def _extract_json(text: str) -> dict:
    """M3 输出 → JSON：剥离 markdown 围栏/思考前缀，提取首个 {...} 块。"""
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.startswith("json"):
            t = t[4:]
    start = t.find("{")
    end = t.rfind("}")
    if start >= 0 and end > start:
        t = t[start:end + 1]
    return json.loads(t)


def audit_chart(chart_path: str, data_summary: str) -> dict:
    """图审：读主海报 → {assess, insights[], improvements[]}。失败返回空结构。"""
    prompt = f"""你正在审查一张亚马逊竞品价格×销量气泡矩阵图（数据摘要如下）。
任务：
1. assess：图表信息密度与视觉质量评估（80 字内）
2. insights：3-5 条市场洞察（价格带结构/机会区/异常点，每条必须有数据依据，≤60 字）
3. improvements：≤3 条下一版渲染改进建议
数据摘要：{data_summary[:1200]}
只输出 JSON：{{"assess": "...", "insights": ["..."], "improvements": ["..."]}}，无其他内容。"""
    try:
        text = chat(prompt, image_path=chart_path, max_tokens=1200)
        data = _extract_json(text)
        return {"assess": str(data.get("assess", "")),
                "insights": list(data.get("insights", [])),
                "improvements": list(data.get("improvements", []))}
    except Exception as exc:  # noqa: BLE001 —— 增强层失败降级
        log.warning("M3 图审失败: %s", exc)
        return {"assess": "", "insights": [], "improvements": [], "error": str(exc)[:100]}


def cluster_reviews(reviews: list[dict], limit: int = 30) -> dict:
    """评论聚类：{topics[], pain_points[], strengths[], opportunities[]}。失败返回空。"""
    if not reviews:
        return {}
    sample = []
    for r in reviews[:limit]:
        body = (r.get("body") or "")[:150].replace("\n", " ")
        sample.append(f"- [{r.get('asin')} {r.get('rating')}★] {body}")
    prompt = f"""以下是亚马逊竞品评论样本（{len(sample)} 条）。
请聚类输出：
- topics: 高频讨论主题（≤6 项）
- pain_points: 用户痛点（≤5 项，含证据）
- strengths: 被反复认可的优点（≤4 项）
- opportunities: 产品差异化机会（≤4 项）
样本：
{chr(10).join(sample)}
只输出 JSON：{{"topics": ["..."], "pain_points": ["..."], "strengths": ["..."], "opportunities": ["..."]}}"""
    try:
        text = chat(prompt, max_tokens=1200)
        return json.loads(text)
    except Exception as exc:  # noqa: BLE001
        log.warning("M3 评论聚类失败: %s", exc)
        return {}


def executive_summary(chapters: list[dict], keyword: str) -> str:
    """执行摘要：基于各章结论生成 ≤200 字中文摘要。失败返回空。"""
    lines = []
    for ch in chapters:
        for c in (ch.get("conclusion") or [])[:2]:
            lines.append(f"- {c}")
    prompt = f"""基于以下竞品矩阵分析结论，为「{keyword}」生成执行摘要（≤200 字）：
- 市场结论/机会/风险/行动优先级，简洁犀利，数据支撑
结论：
{chr(10).join(lines)[:2500]}"""
    try:
        # max_tokens 2000：<think> 思考块占额，400 会截断导致摘要丢失
        return chat(prompt, max_tokens=2000).strip()
    except Exception as exc:  # noqa: BLE001
        log.warning("M3 执行摘要失败: %s", exc)
        return ""
