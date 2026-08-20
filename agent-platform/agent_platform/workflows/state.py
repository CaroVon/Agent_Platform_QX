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
    # 产品 UUID 必须进入 LangGraph 状态，供 PPT/资产节点做目录与产物隔离。
    product_id: str
    memory_namespace: str

    # ─── 节点产物（dict 形式，最终由 ProductAssetPackage 收敛校验） ──
    requirement: dict[str, Any] | None
    research: dict[str, Any] | None
    competitor_analysis: dict[str, Any] | None
    competitor_matrix: dict[str, Any] | None
    strategy: dict[str, Any] | None
    design: dict[str, Any] | None
    presentation: dict[str, Any] | None
    ppt_design: dict[str, Any] | None
    document: dict[str, Any] | None
    asset_package: dict[str, Any] | None

    # ─── 模型分工（节点名 → 模型名，前端展示"当前哪个模型在工作"） ──
    node_models: dict[str, str]

    # ─── P5: Critic 质量闭环 ──────────────────────────────
    critic_score: int | None
    critic_issues: list[dict[str, Any]]
    revision_count: int
    revision_feedback: str
    gate_report: dict[str, Any] | None

    # ─── 进度与失败记录 ───────────────────────────────────
    node_status: dict[str, str]
    errors: dict[str, str]

    # ─── 节点级 Plan/Act 门（GATE_NODES） ─────────────────
    # 必须显式声明，否则会被 MemorySaver checkpoint 剥离
    _gate_nodes: list[str]
    _gate_passed: list[str]
    _completed_nodes: list[str]
    _paused_node: str | None

    # ─── 资料搜集与审核（source_gathering 节点） ──────────
    _sources_review: list[dict]
    _approved_sources: list[dict]
    source_gathering_meta: dict

    # ─── Critic 修订信号（避免低分无文案时修订循环无法终止） ──
    _revise_requested: bool
