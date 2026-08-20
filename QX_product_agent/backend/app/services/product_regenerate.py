"""
============================================================
资产局部重生成服务（Product Studio）
—— 在不重跑整条流水线的前提下，用附加指令重新生成单个资产，
   并将旧版本快照到 asset_versions（最多 5 版/资产）
============================================================
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# 可重生成的资产 → (agent 构造参数名, 任务名, 状态字段名, schema 校验器名)
REGENERABLE = {
    "research": ("research_agent", "market_research", "research"),
    "competitor_matrix": ("research_agent", "competitor_matrix", "competitor_matrix"),
    "competitor_analysis": ("research_agent", "competitor_analysis", "competitor_analysis"),
    "strategy": ("product_agent", "strategy", "strategy"),
    "design": ("design_agent", "ux_design", "design"),
    "presentation": ("presentation_agent", "slide_deck", "presentation"),
}

SCHEMA_VALIDATORS = {
    "research": "MarketResearch",
    "competitor_matrix": "PriceCompetitorMatrix",
    "competitor_analysis": "CompetitorAnalysis",
    "strategy": "ProductStrategy",
    "design": "UXDesign",
    "presentation": "Presentation",
}

MAX_VERSIONS_PER_ASSET = 5


def _build_runtime():
    """构造与 Celery 桥接一致的平台层运行时（惰性 import）。"""
    from agent_platform.harness.agent_loop import AgentLoop
    from agent_platform.memory.memory_store import FileMemoryStore

    from agents.design_agent.agent import DesignAgent
    from agents.presentation_agent.agent import PresentationAgent
    from agents.product_agent.agent import ProductAgent
    from agents.research_agent.agent import ResearchAgent

    from app.core.config import get_settings
    from pathlib import Path

    settings = get_settings()
    memory = FileMemoryStore(
        base_dir=settings.AGENT_PLATFORM_MEMORY_DIR
        if settings.AGENT_PLATFORM_MEMORY_DIR
        else str(Path(settings.OUTPUT_DIR) / "private" / "studio_memory")
    )
    loop = AgentLoop(memory=memory)
    return {
        "research_agent": ResearchAgent(loop=loop),
        "product_agent": ProductAgent(loop=loop),
        "design_agent": DesignAgent(loop=loop),
        "presentation_agent": PresentationAgent(memory=memory),
        "loop": loop,
    }


def snapshot_version(versions: dict, asset: str, old_data: dict) -> dict:
    """把旧资产快照进版本历史（每资产最多保留 MAX_VERSIONS_PER_ASSET 条）。"""
    versions = dict(versions or {})
    history = list(versions.get(asset) or [])
    if old_data:
        history.append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "data": old_data,
        })
    versions[asset] = history[-MAX_VERSIONS_PER_ASSET:]
    return versions


def regenerate_asset(
    product,
    asset: str,
    instruction: str = "",
) -> tuple[bool, dict | str]:
    """重生成单个资产。返回 (ok, data|error)。"""
    if asset not in REGENERABLE:
        return False, f"不支持的资产类型: {asset}（可选: {', '.join(REGENERABLE)}）"

    try:
        package = json.loads(product.asset_package or "{}")
    except json.JSONDecodeError:
        package = {}

    state = {
        "idea": package.get("idea") or product.idea,
        "requirement": package.get("requirement"),
        "research": package.get("research"),
        "competitor_analysis": package.get("competitor_analysis"),
        "strategy": package.get("strategy"),
        "design": package.get("design"),
        "presentation": package.get("presentation"),
        "instruction": instruction,
        "memory_namespace": str(product.id),
    }

    runtime = _build_runtime()
    agent = runtime[REGENERABLE[asset][0]]
    task = REGENERABLE[asset][1]
    result = agent.execute(task, state)
    if not result.success or result.data is None:
        return False, result.error or "生成失败"

    # schema 校验（与流水线一致）
    from agent_platform import schemas as _schemas
    validator_name = SCHEMA_VALIDATORS[asset]
    validator_cls = getattr(_schemas, validator_name)
    try:
        validated = validator_cls.model_validate(result.data)
    except Exception as exc:  # noqa: BLE001
        return False, f"输出未通过 {validator_name} 校验: {exc}"

    return True, validated.model_dump()
