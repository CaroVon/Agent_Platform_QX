"""
工作流状态 —— LangGraph TypedDict State
============================================================

每个节点接收完整结构化状态、只写回自己负责的字段，
错误与进度以结构化形式记录在 node_status / errors 中。
"""

from __future__ import annotations

from typing import Any, TypedDict


class ProductStudioState(TypedDict, total=False):
    """产品研究工作流的共享状态。"""

    # ─── 输入 ─────────────────────────────────────────────
    idea: str
    memory_namespace: str

    # ─── 节点产物（dict 形式，最终由 ProductAssetPackage 收敛校验） ──
    requirement: dict[str, Any] | None
    research: dict[str, Any] | None
    competitor_analysis: dict[str, Any] | None
    strategy: dict[str, Any] | None
    design: dict[str, Any] | None
    presentation: dict[str, Any] | None
    asset_package: dict[str, Any] | None

    # ─── 进度与失败记录 ───────────────────────────────────
    node_status: dict[str, str]
    errors: dict[str, str]
