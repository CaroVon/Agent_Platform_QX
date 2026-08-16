"""
============================================================
产品研究工作流 —— LangGraph 多 Agent 编排
============================================================

节点链（对齐目标架构）:

  Requirement Parser
        ↓
  Research Agent
        ↓
  Competitor Analysis Agent
        ↓
  Product Strategy Agent
        ↓
  UX Design Agent
        ↓
  Presentation Agent
        ↓
  Final Product Asset Package

每个节点：
  - 接收结构化 state（ProductStudioState）
  - 产出结构化输出（Pydantic Schema 校验通过）
  - 支持失败处理（记录错误后降级继续，不整体崩溃）
  - 支持重试机制（_with_retry 包装器，默认 max_retries+1 次尝试）

Agent 实现通过构造参数注入（依赖倒置）：
平台层不 import 任何具体业务 Agent，测试可注入 Fake Agent。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable

from langgraph.graph import END, START, StateGraph

from agent_platform.harness.agent_loop import BaseAgent
from agent_platform.harness.quality_gate import run_quality_gate
from agent_platform.harness.runner import StructuredRunner
from agent_platform.llm.client import LLMClient
from agent_platform.memory.memory_store import MemoryStore
from agent_platform.schemas.design import UXDesign
from agent_platform.schemas.evaluation import CritiqueResult
from agent_platform.schemas.package import AssetPackageMeta, ProductAssetPackage
from agent_platform.schemas.presentation import Presentation
from agent_platform.schemas.product import ProductStrategy
from agent_platform.schemas.product_document import ProductDocument, ProjectInfo
from agent_platform.schemas.requirement import RequirementSpec
from agent_platform.schemas.research import CompetitorAnalysis, MarketResearch
from agent_platform.workflows.state import ProductStudioState

logger = logging.getLogger(__name__)

# 节点执行顺序（linear pipeline；ppt_design 在 critic 门后执行）
NODE_ORDER = [
    "requirement_parser",
    "research",
    "competitor_analysis",
    "strategy",
    "design",
    "presentation",
]

_REQUIREMENT_SYSTEM = """你是资深产品需求分析师。
解析用户的产品想法，输出结构化的产品需求规格。
只输出符合 Schema 的 JSON。"""


def _with_retry(
    node_fn: Callable[[dict], dict | None],
    node_name: str,
    max_retries: int,
) -> Callable[[dict], dict]:
    """节点重试包装器：失败重试 → 记录错误并降级继续。

    LangGraph 规范：节点通过返回更新 dict 写回状态（而非原地修改）。
    """

    def wrapped(state: dict) -> dict:
        status = dict(state.get("node_status", {}))
        errors = dict(state.get("errors", {}))

        status[node_name] = "running"
        errors.pop(node_name, None)

        last_exc: Exception | None = None
        for attempt in range(1, max_retries + 2):  # 总尝试 = max_retries + 1
            try:
                updates = node_fn(state) or {}
                status[node_name] = "completed"
                return {**updates, "node_status": status, "errors": errors}
            except Exception as exc:  # noqa: BLE001 —— 统一收敛为节点失败
                last_exc = exc
                logger.warning(
                    "[%s] 第 %d/%d 次尝试失败: %s",
                    node_name, attempt, max_retries + 1, exc,
                )

        # 重试耗尽：结构化记录失败，工作流降级继续
        status[node_name] = "failed"
        errors[node_name] = f"重试 {max_retries + 1} 次后仍失败: {last_exc}"
        return {"node_status": status, "errors": errors}

    return wrapped


class ProductResearchGraph:
    """
    产品研究工作流图。

    用法:
        graph = ProductResearchGraph(
            research_agent=..., product_agent=..., design_agent=...,
            presentation_agent=..., llm=..., memory=...,
        )
        asset = graph.invoke("Build an AI fitness application")
    """

    def __init__(
        self,
        research_agent: BaseAgent,
        product_agent: BaseAgent,
        design_agent: BaseAgent,
        presentation_agent: BaseAgent,
        llm: LLMClient | None = None,
        memory: MemoryStore | None = None,
        max_retries: int = 2,
        critic_agent: BaseAgent | None = None,
        ppt_design_agent: BaseAgent | None = None,
        score_threshold: int = 80,
        max_revisions: int = 2,
    ):
        self.research_agent = research_agent
        self.product_agent = product_agent
        self.design_agent = design_agent
        self.presentation_agent = presentation_agent
        self.critic_agent = critic_agent
        self.ppt_design_agent = ppt_design_agent
        self.score_threshold = score_threshold
        self.max_revisions = max_revisions
        self.llm = llm
        self.memory = memory
        self.max_retries = max_retries
        self.node_models = self._resolve_node_models()
        self._checkpointer = self._make_checkpointer()
        self.graph = self._build()

    def _resolve_node_models(self) -> dict[str, str]:
        """模型分工：DeepSeek 主流水线；presentation/critic/ppt_design
        由 Presentation 专用模型（如 MiniMax）承接，未配置回退主 LLM。"""
        def _model_name(client) -> str:
            try:
                return client.model if client is not None else "deterministic"
            except Exception:
                return "deterministic"

        from agent_platform.llm.client import get_presentation_llm_client

        pres_model = _model_name(get_presentation_llm_client()) or _model_name(self.llm)
        main_model = _model_name(self.llm)
        models: dict[str, str] = {}
        for name in NODE_ORDER:
            models[name] = pres_model if name in ("presentation",) else main_model
        models["critic"] = pres_model
        models["ppt_design"] = pres_model
        return models

    # ─── 节点实现 ──────────────────────────────────────────

    def _parse_requirement(self, state: dict) -> dict:
        """Requirement Parser：LLM 解析想法；失败时确定性回退。"""
        idea = state["idea"]
        if self.llm is not None:
            try:
                model = StructuredRunner(self.llm).run(
                    system_prompt=_REQUIREMENT_SYSTEM,
                    user_prompt=f"用户的产品想法：{idea}",
                    schema=RequirementSpec,
                    max_retries=1,
                )
                return {"requirement": model.model_dump()}
            except Exception as exc:  # noqa: BLE001 —— 回退兜底
                logger.warning("需求解析失败，使用确定性回退: %s", exc)
        return {"requirement": RequirementSpec(idea=idea, goals=[idea]).model_dump()}

    def _run_agent_node(self, agent: BaseAgent, task: str, state: dict, field: str) -> dict:
        result = agent.execute(
            task,
            state,
            memory=self.memory,
            memory_namespace=state.get("memory_namespace", "default"),
        )
        if not result.success or result.data is None:
            raise RuntimeError(result.error or f"Agent {agent.name} 执行失败")
        return {field: result.data}

    def _research(self, state: dict) -> dict:
        updates = self._run_agent_node(self.research_agent, "market_research", state, "research")
        MarketResearch.model_validate(updates["research"])
        return updates

    def _competitor_analysis(self, state: dict) -> dict:
        updates = self._run_agent_node(
            self.research_agent, "competitor_analysis", state, "competitor_analysis"
        )
        CompetitorAnalysis.model_validate(updates["competitor_analysis"])
        return updates

    def _strategy(self, state: dict) -> dict:
        updates = self._run_agent_node(self.product_agent, "strategy", state, "strategy")
        ProductStrategy.model_validate(updates["strategy"])
        return updates

    def _design(self, state: dict) -> dict:
        updates = self._run_agent_node(self.design_agent, "ux_design", state, "design")
        UXDesign.model_validate(updates["design"])
        return updates

    def _build_document(self, state: dict) -> ProductDocument:
        """从 state 的四个资产构造 Canonical Product Document（critic 与 assemble 共用）。"""
        def _get(model_cls, key):
            value = state.get(key)
            return model_cls.model_validate(value) if value is not None else None

        return ProductDocument(
            project_info=ProjectInfo(
                idea=state["idea"],
                created_at=datetime.now(timezone.utc).isoformat(),
            ),
            research=_get(MarketResearch, "research"),
            competitor_analysis=_get(CompetitorAnalysis, "competitor_analysis"),
            strategy=_get(ProductStrategy, "strategy"),
            design=_get(UXDesign, "design"),
        )

    def _presentation(self, state: dict) -> dict:
        updates = self._run_agent_node(self.presentation_agent, "slide_deck", state, "presentation")
        presentation = Presentation.model_validate(updates["presentation"])
        # A3 确定性兜底：注入缺失的上游关键信息 + ID 归一化（代码保底线）
        from agent_platform.harness.enforce_coverage import (
            enrich_coverage,
            enforce_coverage,
        )

        document = self._build_document(state)
        presentation = enforce_coverage(presentation, document)
        # 内容充实层：确定性补全描述/细节（不依赖 LLM 波动）
        presentation = enrich_coverage(presentation, document)
        # CyberPPT 风格锁定：未显式选主题时确定性分配 8 套咨询风之一
        from agent_platform.harness.enforce_coverage import ensure_consulting_theme

        presentation = ensure_consulting_theme(
            presentation,
            seed=state.get("product_id") or state.get("idea", ""),
        )
        updates["presentation"] = presentation.model_dump()
        # 修订路径（revision_feedback 非空）→ 修订计数 +1
        if state.get("revision_feedback"):
            updates["revision_count"] = state.get("revision_count", 0) + 1
        return updates

    def _critic(self, state: dict) -> dict:
        """P5: Critic 评审 + 确定性质量门 → 评分与修订反馈。"""
        presentation = Presentation.model_validate(state["presentation"])

        # ── 确定性质量门（含 A3 信息覆盖度检查） ────────────
        document = self._build_document(state)
        gate = run_quality_gate(presentation, document=document)

        # ── Critic Agent（LLM 语义评审） ────────────────────
        if self.critic_agent is not None:
            result = self.critic_agent.execute(
                "critique",
                state,
                memory=self.memory,
                memory_namespace=state.get("memory_namespace", "default"),
            )
            if result.success and result.data:
                critique = CritiqueResult.model_validate(result.data)
            else:
                critique = CritiqueResult(
                    score=100, issues=[], summary=f"Critic 不可用，降级通过: {result.error}"
                )
        else:
            critique = CritiqueResult(score=100, issues=[], summary="未注入 Critic（跳过）")

        # 质量门 error 级问题直接压分（每项 -20）
        final_score = max(0, critique.score - 20 * len(gate.errors))

        # 修订反馈 = Critic issues + 质量门问题
        feedback_lines = [f"[{i.severity}] {i.type}: {i.description}" for i in critique.issues]
        feedback_lines += [f"[error] quality_gate: {err}" for err in gate.errors]
        feedback = "；".join(feedback_lines) if feedback_lines else ""

        return {
            "critic_score": final_score,
            "critic_issues": [i.model_dump() for i in critique.issues],
            "revision_feedback": feedback,
            "gate_report": gate.model_dump(),
        }

    def _after_critic(self, state: dict) -> str:
        """P5: 质量门决策 —— 达标/达修订上限/节点失败 → 进入 PPT 设计；否则修订。"""
        # presentation 节点失败时强制收尾，防止修订循环无法终止
        if state.get("node_status", {}).get("presentation") == "failed":
            return "ppt_design"
        score = state.get("critic_score")
        if score is None:
            score = 100  # 未评审视为通过
        revision = state.get("revision_count", 0)
        if score >= self.score_threshold:
            return "ppt_design"
        if revision >= self.max_revisions:
            return "ppt_design"
        return "revise"

    def _ppt_design(self, state: dict) -> dict:
        """PPT 设计成员：DSL → ppt-master 项目 → 原生可编辑 PPTX。"""
        if self.ppt_design_agent is None:
            return {
                "ppt_design": {
                    "status": "skipped",
                    "reason": "未注入 PptDesignAgent",
                    "model": self.node_models.get("ppt_design", ""),
                }
            }
        result = self.ppt_design_agent.execute(
            "ppt_design",
            state,
            memory=self.memory,
            memory_namespace=state.get("memory_namespace", "default"),
        )
        if not result.success or result.data is None:
            raise RuntimeError(result.error or "PptDesignAgent 执行失败")
        updates: dict = {"ppt_design": result.data}
        updates["ppt_design"]["model"] = self.node_models.get("ppt_design", "")
        return updates

    def _assemble(self, state: dict) -> dict:
        """Final Product Asset Package：收敛全部节点产物 + Canonical Document。"""
        def _get(model_cls, key):
            value = state.get(key)
            return model_cls.model_validate(value) if value is not None else None

        document = self._build_document(state)

        package = ProductAssetPackage(
            idea=state["idea"],
            requirement=_get(RequirementSpec, "requirement"),
            research=document.research,
            competitor_analysis=document.competitor_analysis,
            strategy=document.strategy,
            design=document.design,
            presentation=_get(Presentation, "presentation"),
            ppt_design=state.get("ppt_design"),
            document=document,
            critic_score=state.get("critic_score"),
            gate_report=state.get("gate_report"),
            meta=AssetPackageMeta(
                idea=state["idea"],
                created_at=datetime.now(timezone.utc).isoformat(),
                node_status={
                    **dict(state.get("node_status", {})),
                    "assemble": "completed",
                },
                node_models=dict(state.get("node_models") or {}),
                errors=dict(state.get("errors", {})),
            ),
        )
        status = dict(state.get("node_status", {}))
        status["assemble"] = "completed"
        return {
            "asset_package": package.model_dump(),
            "document": document.model_dump(),
            "node_status": status,
        }

    # ─── 图构建 ────────────────────────────────────────────

    def _build(self):
        builder = StateGraph(ProductStudioState)

        for name in NODE_ORDER:
            builder.add_node(name, _with_retry(self._node_fn(name), name, self.max_retries))
        builder.add_node("critic", _with_retry(self._critic, "critic", self.max_retries))
        builder.add_node("ppt_design", _with_retry(self._ppt_design, "ppt_design", self.max_retries))
        builder.add_node("assemble", self._assemble)

        builder.add_edge(START, NODE_ORDER[0])
        for prev, nxt in zip(NODE_ORDER, NODE_ORDER[1:]):
            builder.add_edge(prev, nxt)
        # P5: presentation → critic →（修订循环 | PPT 设计 → 收尾）
        builder.add_edge("presentation", "critic")
        builder.add_conditional_edges(
            "critic",
            self._after_critic,
            {"revise": "presentation", "ppt_design": "ppt_design"},
        )
        builder.add_edge("ppt_design", "assemble")
        builder.add_edge("assemble", END)

        if self._checkpointer is not None:
            return builder.compile(checkpointer=self._checkpointer)
        return builder.compile()

    def _node_fn(self, name: str) -> Callable[[dict], dict]:
        return {
            "requirement_parser": self._parse_requirement,
            "research": self._research,
            "competitor_analysis": self._competitor_analysis,
            "strategy": self._strategy,
            "design": self._design,
            "presentation": self._presentation,
        }[name]

    @staticmethod
    def _make_checkpointer():
        """内存 checkpoint（支持断点续跑/回放），缺失依赖时禁用。"""
        try:
            from langgraph.checkpoint.memory import MemorySaver

            return MemorySaver()
        except Exception:  # noqa: BLE001 —— 无 checkpoint 依赖时降级
            return None

    # ─── 执行入口 ──────────────────────────────────────────

    def invoke(
        self,
        idea: str,
        memory_namespace: str = "default",
        extra_initial: dict | None = None,
    ) -> ProductAssetPackage:
        """运行全流程，返回最终产品资产包。"""
        initial: ProductStudioState = {
            **dict(extra_initial or {}),
            "idea": idea,
            "memory_namespace": memory_namespace,
            "requirement": None,
            "research": None,
            "competitor_analysis": None,
            "strategy": None,
            "design": None,
            "presentation": None,
            "ppt_design": None,
            "document": None,
            "asset_package": None,
            "node_models": self.node_models,
            "critic_score": None,
            "critic_issues": [],
            "revision_count": 0,
            "revision_feedback": "",
            "gate_report": None,
            "node_status": {name: "pending" for name in NODE_ORDER + ["critic", "assemble"]},
            "errors": {},
        }
        config = None
        if self._checkpointer is not None:
            config = {"configurable": {"thread_id": memory_namespace}}
        final_state = self.graph.invoke(initial, config=config)
        return ProductAssetPackage.model_validate(final_state["asset_package"])


def build_product_research_graph(
    research_agent: BaseAgent,
    product_agent: BaseAgent,
    design_agent: BaseAgent,
    presentation_agent: BaseAgent,
    llm: LLMClient | None = None,
    memory: MemoryStore | None = None,
    max_retries: int = 2,
    critic_agent: BaseAgent | None = None,
    ppt_design_agent: BaseAgent | None = None,
    score_threshold: int = 80,
    max_revisions: int = 2,
) -> ProductResearchGraph:
    """工厂函数：构建产品研究工作流图。"""
    return ProductResearchGraph(
        research_agent=research_agent,
        product_agent=product_agent,
        design_agent=design_agent,
        presentation_agent=presentation_agent,
        llm=llm,
        memory=memory,
        max_retries=max_retries,
        critic_agent=critic_agent,
        score_threshold=score_threshold,
        max_revisions=max_revisions,
    )


def run_pipeline(
    idea: str,
    research_agent: BaseAgent,
    product_agent: BaseAgent,
    design_agent: BaseAgent,
    presentation_agent: BaseAgent,
    llm: LLMClient | None = None,
    memory: MemoryStore | None = None,
    max_retries: int = 2,
    critic_agent: BaseAgent | None = None,
    ppt_design_agent: BaseAgent | None = None,
    score_threshold: int = 80,
    max_revisions: int = 2,
    memory_namespace: str = "default",
) -> ProductAssetPackage:
    """一步式便捷入口：构建图并执行。"""
    graph = build_product_research_graph(
        research_agent=research_agent,
        product_agent=product_agent,
        design_agent=design_agent,
        presentation_agent=presentation_agent,
        llm=llm,
        memory=memory,
        max_retries=max_retries,
        critic_agent=critic_agent,
        ppt_design_agent=ppt_design_agent,
        score_threshold=score_threshold,
        max_revisions=max_revisions,
    )
    return graph.invoke(idea, memory_namespace=memory_namespace)
