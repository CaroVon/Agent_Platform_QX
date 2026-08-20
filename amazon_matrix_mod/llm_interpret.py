"""LLM 4 区一句话解读 —— DeepSeek（OpenAI 兼容），JSON 模式 + 重试 2 次 + 失败即报错。

环境变量（复用 QX backend/.env 既有配置，无需重复设置）：
  DEEPSEEK_API_KEY   必填
  DEEPSEEK_BASE_URL  默认 https://api.deepseek.com/v1
  DEEPSEEK_MODEL     默认 deepseek-chat
"""
from __future__ import annotations

import json
import os

import requests

ZONE_LABELS = {
    "price_gap": "价格缺口带",
    "value_opportunity": "性价比机会区",
    "demand_heat": "需求热度区",
    "red_ocean": "红海警示区",
}

_SYSTEM = """你是亚马逊市场策略顾问。基于结构化市场数据，对 4 个市场机会区域给出犀利的中文解读。
要求：
- 每个区域解读 ≤25 字，数据支撑、直击要点，禁止空话套话；
- verdict 为 ≤30 字的我方定位总结；
- 只输出合法 JSON（{"price_gap": "...", "value_opportunity": "...", "demand_heat": "...", "red_ocean": "...", "verdict": "..."}），
  不要输出任何其他内容或 markdown 围栏。"""


def _build_user(zoning_rules: dict, zone_samples: dict, keyword: str,
                marketplace: str, our_asin: str | None, market_context: str) -> str:
    lines = [
        f"- 主关键词：{keyword}",
        f"- 目标站点：{marketplace}",
        f"- 我方产品：{our_asin or '未指定'}",
        f"- 市场上下文：{(market_context or '无')[:300]}",
        "",
    ]
    for zone in ("price_gap", "value_opportunity", "demand_heat", "red_ocean"):
        rule = zoning_rules.get(zone, {})
        samples = zone_samples.get(zone, [])
        lines.append(f"## {ZONE_LABELS[zone]}（规则: {rule}）")
        lines.append(json.dumps(samples, ensure_ascii=False)[:800] if samples else "（无样本）")
        lines.append("")
    return "\n".join(lines)


def _client():
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise RuntimeError("缺少 DEEPSEEK_API_KEY（可在 QX_product_agent/backend/.env 配置后 export）")
    return {
        "base_url": os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1").rstrip("/"),
        "model": os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
        "api_key": api_key,
    }


def interpret_zones(zoning_rules: dict, zone_samples: dict, keyword: str = "",
                    marketplace: str = "amazon.com", our_asin: str | None = None,
                    market_context: str = "", max_retries: int = 2) -> dict:
    """4 区解读。JSON 解析失败重试 max_retries 次，最终失败抛错（不降级，已确认）。"""
    client = _client()
    user = _build_user(zoning_rules, zone_samples, keyword, marketplace,
                       our_asin, market_context)
    last_err: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            r = requests.post(
                f"{client['base_url']}/chat/completions",
                headers={"Authorization": f"Bearer {client['api_key']}",
                         "Content-Type": "application/json"},
                json={
                    "model": client["model"],
                    "messages": [
                        {"role": "system", "content": _SYSTEM},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0.4 if attempt == 0 else 0.2,
                    "max_tokens": 600,
                    "response_format": {"type": "json_object"},
                },
                timeout=90,
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
            data = json.loads(content)
            if not isinstance(data, dict):
                raise ValueError("LLM 输出非对象")
            # 字段兜底：缺哪个补空串（不报错），但核心 4 区缺失视为解析失败
            for k in ("price_gap", "value_opportunity", "demand_heat", "red_ocean", "verdict"):
                data.setdefault(k, "")
            return data
        except Exception as exc:  # noqa: BLE001 —— 重试 2 次后报错
            last_err = exc
    raise RuntimeError(f"LLM 解读失败（重试 {max_retries} 次）: {last_err}")
