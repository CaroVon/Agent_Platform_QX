"""
Presentation Agent —— 信息设计（P3 升级）
============================================================

职责（layout.md 第 3 步）:
  - 输入: Canonical Product Document（语义层事实）
  - 输出: Presentation DSL（pages / layout / components / theme）
  - 只做「视觉语义决策」，禁止输出 HTML/CSS/像素

模型角色（layout.md 第 7 步）:
  - 默认使用主 LLM（DeepSeek）
  - 配置 AGENT_PLATFORM_PRESENTATION_LLM_* 后自动切换到专用模型
    （如 Kimi / MiniMax——与 DeepSeek 分工：主流水线用 DeepSeek，
    PPT skill 制作由 MiniMax 承接）
  - 视觉规范由 presentation-design + presentation-cyberppt skill 注入，
    模型可换、规范不漂移
"""

from __future__ import annotations

import json
from typing import Any

from agent_platform.harness.agent_loop import BaseAgent, AgentLoop
from agent_platform.llm.client import get_presentation_llm_client
from agent_platform.memory.memory_store import MemoryStore
from agent_platform.schemas import (
    AgentResult,
    LAYOUT_LIBRARY,
    Presentation,
    ProductDocument,
    ProjectInfo,
)
from agent_platform.skills.loader import SkillLoader

from agents.presentation_agent.prompts import DECK_BUILDER_SYSTEM_V2


def _presentation_evaluator(presentation: Presentation) -> tuple[bool, str]:
    """Presentation 专用评估器：页数、组件密度与布局多样性。"""
    issues: list[str] = []
    pages = presentation.pages
    if not (10 <= len(pages) <= 16):
        issues.append(f"页数 {len(pages)} 不在 8-14 区间")
    layouts = {p.layout for p in pages}
    if len(layouts) < 5:
        issues.append(f"布局多样性不足（{len(layouts)}/5）")
    for page in pages:
        if len(page.components) > 6:
            issues.append(f"页 {page.id} 组件数 {len(page.components)} 超限")
        if page.type not in ("cover", "conclusion") and not page.components:
            issues.append(f"页 {page.id} 无组件")
        if not page.insight and page.type not in ("cover", "conclusion"):
            issues.append(f"页 {page.id} 缺少一句话结论 insight")
    if issues:
        return False, "；".join(issues[:6])
    return True, ""


def _build_system_prompt() -> str:
    """System Prompt = 信息设计角色 + 视觉规范 skill + CyberPPT skill
    + Layout Library + 预置主题。"""
    skill_text = SkillLoader().load("presentation-design")
    cyberppt_text = SkillLoader().load("presentation-cyberppt")
    library = json.dumps(
        {
            layout_id: {"name": spec["name"], "page_types": spec["page_types"]}
            for layout_id, spec in LAYOUT_LIBRARY.items()
        },
        ensure_ascii=False,
        indent=1,
    )
    from agent_platform.schemas.presentation import THEME_PRESETS

    themes = json.dumps(
        {tid: t["name"] for tid, t in THEME_PRESETS.items()},
        ensure_ascii=False,
        indent=1,
    )
    return (
        DECK_BUILDER_SYSTEM_V2
        + "\n\n【Layout Library（只能从中选择布局）】\n"
        + library
        + "\n\n【预置主题（theme.id 只能从其中选择）】\n"
        + themes
        + "\n\n【视觉规范 Skill】\n"
        + skill_text
        + ("\n\n【CyberPPT 咨询风 Skill】\n" + cyberppt_text if cyberppt_text else "")
    )


class PresentationAgent(BaseAgent):
    """信息设计师：把产品事实转化为 Presentation DSL。"""

    name = "presentation_agent"
    description = "视觉叙事设计（Presentation DSL：页型/布局/组件/主题，不含像素）"
    output_schema = Presentation
    system_prompt = _build_system_prompt()

    def __init__(self, loop: AgentLoop | None = None, memory: MemoryStore | None = None):
        if loop is None:
            # P3: 使用专用模型（Kimi 等，未配置回退主 LLM）+ 专用评估器
            loop = AgentLoop(
                llm=get_presentation_llm_client(),
                memory=memory,
                evaluator=_presentation_evaluator,
            )
        super().__init__(loop=loop)

    def build_deck(
        self,
        idea: str,
        document: ProductDocument | None,
        memory: MemoryStore | None = None,
        memory_namespace: str = "default",
        revise_feedback: str = "",
        evidence_pack: dict | None = None,
        instruction: str = "",
    ) -> AgentResult:
        """构建 Presentation DSL；revise_feedback 用于 Critic 修订循环（P5）。"""
        objective = (
            f"为产品「{idea}」构建 10-16 页演示（Presentation DSL）。"
            "严格按视觉规范 skill：one slide = one message；"
            "每页选择布局枚举 + 2-8 个组件；数据必须来自上游产品文档，禁止编造；"
            "专有名词（功能/竞品/画像/阶段名）必须原文引用，禁止改写。"
        )
        if revise_feedback:
            objective += f"\n\n【上一版评审意见（必须逐条修正）】\n{revise_feedback}"
        if instruction:
            objective += f"\n\n【本次修订要求】{instruction}"

        # ── A3 强化：AgentLoop 内评估器（结构性自检） ──
        # 注：逐字覆盖度由 critic 质量门在确定性注入（enforce/enrich）之后
        # 检查，循环内不再逐字比对 —— 兼容会改写表述的模型（如 MiniMax），
        # 避免"改写 → 误判缺失 → 无限修订"。
        def coverage_evaluator(model: Presentation) -> tuple[bool, str]:
            return _presentation_evaluator(model)

        artifacts: dict[str, Any] = {"canonical_product_document": document}
        if evidence_pack:
            # CyberPPT 材料包：证据表 + 关键数字 + SCR 提示 + 密度预算
            from agent_platform.harness.evidence_pack import render_evidence_pack

            artifacts["cyberppt_evidence_pack"] = render_evidence_pack(evidence_pack)

        result = self.loop.run(
            agent_name=self.name,
            system_prompt=self.system_prompt,
            objective=objective,
            schema=Presentation,
            inputs={"idea": idea},
            artifacts=artifacts,
            memory_namespace=memory_namespace,
            evaluator=coverage_evaluator,
        )
        return result

    def execute(
        self,
        task: str,
        state: dict[str, Any],
        memory: MemoryStore | None = None,
        memory_namespace: str = "default",
    ) -> AgentResult:
        if task != "slide_deck":
            return AgentResult(success=False, error=f"未知任务: {task}")

        # document 优先取 state（assemble 已产出时），否则由四类资产即时构造
        document_data = state.get("document")
        if document_data is not None:
            document = ProductDocument.model_validate(document_data)
        else:
            from agent_platform.schemas.design import UXDesign
            from agent_platform.schemas.product import ProductStrategy
            from agent_platform.schemas.research import CompetitorAnalysis, MarketResearch

            def _v(model_cls, value):
                return model_cls.model_validate(value) if value is not None else None

            document = ProductDocument(
                project_info=ProjectInfo(idea=state.get("idea", "")),
                research=_v(MarketResearch, state.get("research")),
                competitor_analysis=_v(CompetitorAnalysis, state.get("competitor_analysis")),
                strategy=_v(ProductStrategy, state.get("strategy")),
                design=_v(UXDesign, state.get("design")),
            )
        from agent_platform.harness.evidence_pack import build_evidence_pack

        return self.build_deck(
            state.get("idea", ""),
            document,
            memory=memory,
            memory_namespace=memory_namespace,
            revise_feedback=state.get("revision_feedback", ""),
            evidence_pack=build_evidence_pack(document),
            instruction=str(state.get("instruction") or ""),
        )
