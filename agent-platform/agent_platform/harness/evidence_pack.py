"""
CyberPPT 上游数据适配层 —— 证据包（Evidence Pack）
============================================================

把上游 Canonical Product Document 的语义层事实，确定性转换为
CyberPPT 方法论所需的「证据表 + 关键数字 + SCR 叙事提示 + 密度预算」，
注入 Presentation Agent 作为材料包（artifact: cyberppt_evidence_pack）。

设计原则：
- **确定性**：纯函数提取，不依赖 LLM，任何产品输入都有稳定输出
- **紧凑**：材料包受上下文预算约束，条目截断、总数设上限
- **可追溯**：每条证据带 ID（E001…）与来源字段，prompt 要求按 ID 引用
"""

from __future__ import annotations

from typing import Any

from agent_platform.schemas.product_document import ProductDocument

# 咨询风密度预算：页型 → 组件数建议区间（与 density-planning skill 及
# quality_gate 区间对齐：cover/closing 1-2，其余 2-6 取上限）
DENSITY_BUDGET: dict[str, tuple[int, int]] = {
    "cover": (1, 2),
    "summary": (3, 5),
    "market_overview": (4, 6),
    "competitor_matrix": (3, 5),
    "user_persona": (2, 4),
    "user_journey": (2, 4),
    "feature_priority": (2, 5),
    "product_architecture": (2, 4),
    "roadmap": (2, 4),
    "closing": (1, 2),
}

_MAX_ENTRIES = 70
_MAX_TEXT = 80
_MAX_TEXT_BLOCK = 300  # 模块化文本块（PRD 章节/画像/竞品说明等）长度上限


def _clip(text: str | None, limit: int = _MAX_TEXT) -> str:
    """截断并清理单条证据文本（含省略号不超 limit）。"""
    s = (text or "").strip().replace("\n", " ")
    return s if len(s) <= limit else s[: limit - 1] + "…"


def _add(
    evidence: list[dict[str, str]],
    source: str,
    claim: str,
    value: str | None = None,
    caveat: str | None = None,
    text_block: bool = False,
) -> None:
    """证据条目。text_block=True 用于模块化文本（PRD 章节/画像/竞品说明），
    截断上限放宽到 _MAX_TEXT_BLOCK，保结构「标题：正文」供页面直接嵌入。"""
    if not claim:
        return
    limit = _MAX_TEXT_BLOCK if text_block else _MAX_TEXT
    evidence.append(
        {
            "id": f"E{len(evidence) + 1:03d}",
            "source": source,
            "claim": _clip(claim, limit),
            "value": _clip(value, 40) if value else "",
            "caveat": _clip(caveat, 60) if caveat else "",
        }
    )


def build_evidence_pack(document: ProductDocument | None) -> dict[str, Any]:
    """上游文档 → CyberPPT 材料包（证据表 / 关键数字 / SCR 提示 / 密度预算）。"""
    evidence: list[dict[str, str]] = []
    key_numbers: list[dict[str, str]] = []

    if document is None:
        return {
            "evidence_table": [],
            "key_numbers": [],
            "narrative_hints": {"situation": "", "complication": "", "resolution": ""},
            "density_budget": DENSITY_BUDGET,
        }

    idea = document.project_info.idea if document.project_info else ""

    # ── S 现状：市场规模 / 竞品 / 趋势 ─────────────────────────
    research = document.research
    if research:
        ms = research.market_size
        if ms:
            _add(evidence, "research.market_size.summary", ms.summary,
                 caveat=ms.source and f"来源:{ms.source}")
            for key, label in (("tam", "TAM"), ("sam", "SAM"), ("som", "SOM"), ("cagr", "CAGR")):
                val = getattr(ms, key, None)
                if val:
                    key_numbers.append({"metric": label, "value": _clip(val, 40)})
                    _add(evidence, f"research.market_size.{key}", f"{label}={val}", value=val)
        for i, c in enumerate(research.competitors[:6]):
            _add(evidence, "research.competitors", c.name, value=c.positioning)
        for i, p in enumerate(research.customer_pain_points[:8]):
            _add(evidence, "research.customer_pain_points", p)
        for i, t in enumerate(research.industry_trends[:8]):
            _add(evidence, "research.industry_trends", t)

    # ── C 矛盾：竞品矩阵 / 差异化机会 ─────────────────────────
    comp = document.competitor_analysis
    if comp:
        _add(evidence, "competitor_analysis.competitive_landscape", comp.competitive_landscape)
        for p in comp.competitors[:6]:
            # 模块化文本块：竞品 定位/定价/优势/劣势 完整入包
            bits = [p.name]
            if p.positioning:
                bits.append(f"定位:{p.positioning}")
            if p.pricing:
                bits.append(f"定价:{p.pricing}")
            if p.strengths:
                bits.append("优势:" + "、".join(p.strengths[:4]))
            if p.weaknesses:
                bits.append("劣势:" + "、".join(p.weaknesses[:4]))
            _add(evidence, "competitor_analysis.competitors", "；".join(bits),
                 text_block=True)
        for i, d in enumerate(comp.differentiation_opportunities[:8]):
            _add(evidence, "competitor_analysis.differentiation_opportunities", d)

    # ── R 解法：定位 / 画像 / 功能 / 路线图 / PRD ──────────────
    strat = document.strategy
    if strat:
        _add(evidence, "strategy.positioning", strat.positioning)
        for p in strat.personas[:4]:
            # 模块化文本块：画像三段（目标/痛点/行为）完整入包
            _add(
                evidence,
                "strategy.personas",
                f"{p.name}（{p.role}）：目标={p.goals[:3] and '、'.join(p.goals[:3]) or '—'}；"
                f"痛点={'、'.join(p.pain_points[:3]) or '—'}；"
                f"行为={p.behavior or '—'}",
                text_block=True,
            )
        for f in strat.features[:16]:
            _add(evidence, "strategy.features", f.name, value=f.description,
                 caveat=f.category)
        for r in strat.roadmap[:6]:
            _add(
                evidence,
                "strategy.roadmap",
                f"{r.phase}·{r.title}",
                value=r.timeline,
                caveat=("里程碑:" + "、".join(r.milestones[:6])) if r.milestones else None,
            )
        for s in strat.prd_sections[:6]:
            # 模块化文本块：PRD 章节全文（标题：正文）供页面直接嵌入
            _add(
                evidence,
                "strategy.prd_sections",
                f"{s.title}：{s.content}",
                text_block=True,
            )

    # ── 旅程（步骤 + 描述，模块化文本） ────────────────────────
    design = document.design
    if design and design.user_flow:
        steps = [
            f"{s.step}（{s.description}）"
            for s in design.user_flow[:8]
            if s.step
        ]
        if steps:
            _add(evidence, "design.user_flow", "→".join(steps), text_block=True)

    # 关键数字封顶
    key_numbers = key_numbers[:10]

    # ── SCR 叙事提示（确定性规则 → 文本提示） ──────────────────
    situation, complication, resolution = "", "", ""
    if research and research.market_size:
        situation = (f"市场现状：{_clip(research.market_size.summary, 120)}；"
                     f"关键指标 TAM={getattr(research.market_size, 'tam', None) or '—'}"
                     f" SAM={getattr(research.market_size, 'sam', None) or '—'}"
                     f" CAGR={getattr(research.market_size, 'cagr', None) or '—'}")
    if comp and comp.differentiation_opportunities:
        complication = (f"矛盾/缺口：竞品格局「{_clip(comp.competitive_landscape, 60)}」，"
                        f"差异化机会 {len(comp.differentiation_opportunities)} 条："
                        f"「{_clip(comp.differentiation_opportunities[0], 50)}」等。")
    elif research and research.customer_pain_points:
        complication = (f"矛盾/缺口：用户痛点 {len(research.customer_pain_points)} 项，"
                        f"首项「{_clip(research.customer_pain_points[0], 50)}」。")
    if strat:
        resolution = (f"解法：定位「{_clip(strat.positioning, 60)}」；"
                      f"功能 {len(strat.features)} 项、路线图 {len(strat.roadmap)} 阶段。")
    if not resolution and idea:
        resolution = f"解法：围绕「{idea}」的产品方案。"

    return {
        "evidence_table": evidence[: _MAX_ENTRIES],
        "key_numbers": key_numbers,
        "narrative_hints": {
            "situation": situation,
            "complication": complication,
            "resolution": resolution,
        },
        "density_budget": DENSITY_BUDGET,
    }


def render_evidence_pack(pack: dict[str, Any]) -> str:
    """材料包 → 紧凑文本（注入 prompt 使用）。"""
    lines: list[str] = []
    hints = pack.get("narrative_hints", {})
    lines.append("【SCR 叙事提示】")
    for k in ("situation", "complication", "resolution"):
        v = hints.get(k, "")
        lines.append(f"- {k.upper()}: {v or '（材料不足，可标注待补充）'}")
    key_nums = pack.get("key_numbers", [])
    if key_nums:
        lines.append("【关键数字（必须入页）】")
        lines.append("；".join(f"{n['metric']}={n['value']}" for n in key_nums))
    table = pack.get("evidence_table", [])
    if table:
        lines.append("【证据表（insight/组件数据按 ID 引用，禁止脱离证据编数字）】")
        for e in table:
            line = f"{e['id']} [{e['source']}] {e['claim']}"
            if e.get("value"):
                line += f" | {e['value']}"
            if e.get("caveat"):
                line += f" ({e['caveat']})"
            lines.append(line)
    budget = pack.get("density_budget", {})
    lines.append("【每页组件预算（咨询风取上限）】")
    lines.append(
        "；".join(f"{k}:{lo}-{hi}" for k, (lo, hi) in budget.items())
    )
    return "\n".join(lines)
