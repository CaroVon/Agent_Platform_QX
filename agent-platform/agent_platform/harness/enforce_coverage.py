"""
============================================================
覆盖度确定性兜底（A3 强化）
============================================================

原则：模型做叙事，代码保底线。
Presentation Agent 输出后，由本层把上游 Canonical Product Document 中
未被覆盖的关键信息**确定性注入**演示（原文数据，不依赖 LLM 再生成），
保证信息完整度 100% + 组件 ID 全局唯一。
"""

from __future__ import annotations

from agent_platform.schemas.presentation import Component, Page, Presentation
from agent_platform.schemas.product_document import ProductDocument


def _hit(text: str | None, dsl_text: str) -> bool:
    if not text:
        return False
    if text in dsl_text:
        return True
    return text[:6] in dsl_text


def enrich_coverage(
    presentation: Presentation,
    document: ProductDocument,
) -> Presentation:
    """确定性内容充实（不依赖 LLM 波动）：
    即使字段已覆盖，也把上游细节注入组件 —— 表格描述列、画像细节、
    市场核心结论、路线图阶段信息，保证内容量稳定丰富。
    """
    pages = list(presentation.pages)

    def find_page(page_type: str) -> Page | None:
        return next((p for p in pages if p.type == page_type), None)

    def find_components(page_type: str, comp_type: str) -> list[Component]:
        page = find_page(page_type)
        if page is None:
            return []
        return [c for c in page.components if c.type == comp_type]

    # ── features 表格：补全描述列 ──────────────────────────
    if document.strategy and document.strategy.features:
        by_name = {f.name: f for f in document.strategy.features}
        for table in find_components("feature_priority", "table"):
            rows = table.data.get("rows")
            if not isinstance(rows, list):
                continue
            for row in rows:
                if len(row) >= 3 and (not row[2] or len(str(row[2])) < 6):
                    feature = by_name.get(row[1])
                    if feature and feature.description:
                        row[2] = feature.description[:60]

    # ── persona 卡片：补全目标/痛点细节 ────────────────────
    if document.strategy and document.strategy.personas:
        by_name = {p.name: p for p in document.strategy.personas}
        for card in find_components("user_persona", "card"):
            persona = by_name.get(card.data.get("title", ""))
            desc = card.data.get("description", "") or ""
            if persona and (not desc or len(str(desc)) < 10):
                goals = "、".join(persona.goals[:3]) if persona.goals else ""
                pains = "、".join(persona.pain_points[:3]) if persona.pain_points else ""
                parts = []
                if goals:
                    parts.append(f"目标：{goals}")
                if pains:
                    parts.append(f"痛点：{pains}")
                if persona.behavior:
                    parts.append(str(persona.behavior)[:40])
                if parts:
                    card.data["description"] = "；".join(parts)[:160]

    # ── market 页：补核心结论 + 来源 ───────────────────────
    if document.research and document.research.market_size:
        ms = document.research.market_size
        market = find_page("market_overview")
        if market is not None:
            dsl_text = Presentation(title=presentation.title, pages=pages).model_dump_json()
            has_conclusion = ms.summary and ms.summary[:10] in dsl_text
            has_source = bool(ms.source) and ms.source[:10] in dsl_text
            if ms.summary and not (has_conclusion and has_source):
                text = ms.summary
                if ms.source and not has_source:
                    text += f"（来源：{ms.source}）"
                market.components.append(
                    Component(
                        id="", type="text",
                        data={"title": "核心结论", "text": text[:220]},
                    )
                )

    # ── roadmap 阶段：补周期与里程碑 ───────────────────────
    if document.strategy and document.strategy.roadmap:
        for tl in find_components("roadmap", "timeline"):
            phases = tl.data.get("phases")
            if not isinstance(phases, list):
                continue
            for phase in phases:
                name = phase.get("name", "")
                upstream = next(
                    (p for p in document.strategy.roadmap if p.phase == name),
                    None,
                )
                if upstream is None:
                    continue
                if not phase.get("period") and upstream.timeline:
                    phase["period"] = upstream.timeline
                if not phase.get("milestones") and upstream.milestones:
                    phase["milestones"] = list(upstream.milestones)[:5]

    # ── 模块化内容注入（CyberPPT 原生文本要求：竞品短板/定价、
    #    PRD 章节全文必须按模块嵌入，不依赖 LLM 自觉） ─────
    pages = _inject_modular_content(pages, presentation, document)

    # ── 图表入页（阶段 A：确定性图表注入，真实计数） ──────
    if document.strategy and document.strategy.features:
        from collections import Counter as _Counter

        by_priority = _Counter(
            (f.priority or "P1") for f in document.strategy.features
        )
        feature_page = next((p for p in pages if p.type == "feature_priority"), None)
        has_chart = feature_page is not None and any(
            c.type in ("chart", "matrix") for c in feature_page.components
        )
        if feature_page is not None and not has_chart and sum(by_priority.values()) >= 4:
            order = [k for k in ("P0", "P1", "P2", "P3") if by_priority.get(k)]
            feature_page.components.append(
                Component(
                    id="",
                    type="chart",
                    data={
                        "chart_type": "bar",
                        "title": "功能优先级分布",
                        "items": [
                            {"label": k, "value": by_priority.get(k, 0)} for k in order
                        ],
                    },
                )
            )

    # ── 组件 ID 归一化（充实新增组件同样保证唯一） ─────────
    seen: set[str] = set()
    for page in pages:
        for comp in page.components:
            if not comp.id or comp.id in seen:
                comp.id = _unique_id(page.id, seen, f"{page.id}-auto")
            else:
                seen.add(comp.id)

    return Presentation(title=presentation.title, theme=presentation.theme, pages=pages)


def _unique_id(page_id: str, existing: set[str], prefix: str) -> str:
    candidate = prefix
    n = 2
    while candidate in existing:
        candidate = f"{prefix}-{n}"
        n += 1
    existing.add(candidate)
    return candidate


def enforce_coverage(
    presentation: Presentation,
    document: ProductDocument,
) -> Presentation:
    """把缺失的上游关键信息确定性注入演示，并归一化组件 ID。"""
    pages = list(presentation.pages)
    dsl_text = presentation.model_dump_json()

    def page_by_type(page_type: str) -> Page | None:
        return next((p for p in pages if p.type == page_type), None)

    def append_component(page: Page, component: Component) -> None:
        page.components.append(component)

    # ── 市场指标（TAM/SAM/SOM/CAGR） ───────────────────────
    if document.research and document.research.market_size:
        ms = document.research.market_size
        market = page_by_type("market_overview")
        if market is not None:
            for label, value in [("TAM", ms.tam), ("SAM", ms.sam),
                                 ("SOM", ms.som), ("CAGR", ms.cagr)]:
                if value and not _hit(value, dsl_text):
                    append_component(
                        market,
                        Component(
                            id="", type="metric",
                            data={"value": value, "label": label},
                        ),
                    )
                    dsl_text = Presentation(title=presentation.title, pages=pages).model_dump_json()

    # ── 痛点（要点化注入） ─────────────────────────────────
    if document.research and document.research.customer_pain_points:
        market = page_by_type("market_overview") or page_by_type("executive_summary")
        missing = [p for p in document.research.customer_pain_points if not _hit(p[:6], dsl_text)]
        if market is not None and missing:
            bullet = "；".join(f"· {p[:24]}" for p in missing[:6])
            append_component(
                market,
                Component(
                    id="", type="text",
                    data={"title": "用户痛点", "text": bullet},
                ),
            )
            dsl_text = Presentation(title=presentation.title, pages=pages).model_dump_json()

    # ── 行业趋势 ───────────────────────────────────────────
    if document.research and document.research.industry_trends:
        market = page_by_type("market_overview") or page_by_type("executive_summary")
        missing = [t for t in document.research.industry_trends if not _hit(t[:6], dsl_text)]
        if market is not None and missing:
            bullet = "；".join(f"· {t[:24]}" for t in missing[:6])
            append_component(
                market,
                Component(
                    id="", type="text",
                    data={"title": "行业趋势", "text": bullet},
                ),
            )
            dsl_text = Presentation(title=presentation.title, pages=pages).model_dump_json()

    # ── 竞品（matrix 象限点补齐） ──────────────────────────
    if document.competitor_analysis and document.competitor_analysis.competitors:
        matrix_page = page_by_type("competitor_matrix")
        missing = [
            c.name for c in document.competitor_analysis.competitors
            if not _hit(c.name, dsl_text)
        ]
        if matrix_page is not None and missing:
            target = next(
                (c for c in matrix_page.components if c.type == "matrix"),
                None,
            )
            if target is None:
                target = Component(id="", type="matrix", data={
                    "chart_type": "quadrant", "x_axis": "价格", "y_axis": "个性化",
                    "points": [],
                })
                append_component(matrix_page, target)
            points = list(target.data.get("points") or [])
            for i, name in enumerate(missing[:8]):
                points.append({
                    "name": name, "x": round(0.5 + 0.2 * (i % 3 - 1), 1),
                    "y": round(0.5 + 0.2 * (i // 3 - 1), 1),
                    "kind": "competitor",
                })
            target.data["points"] = points
            dsl_text = Presentation(title=presentation.title, pages=pages).model_dump_json()

    # ── 画像（persona 卡补齐） ─────────────────────────────
    if document.strategy and document.strategy.personas:
        persona_page = page_by_type("user_persona")
        missing = [
            p.name for p in document.strategy.personas
            if not _hit(p.name, dsl_text)
        ]
        if persona_page is not None and missing:
            for name in missing[:4]:
                append_component(
                    persona_page,
                    Component(
                        id="", type="card",
                        data={"title": name, "description": "用户画像"},
                    ),
                )
            dsl_text = Presentation(title=presentation.title, pages=pages).model_dump_json()

    # ── 功能（table 行补齐） ───────────────────────────────
    if document.strategy and document.strategy.features:
        feat_page = page_by_type("feature_priority")
        missing = [
            f for f in document.strategy.features
            if not _hit(f.name, dsl_text)
        ]
        if feat_page is not None and missing:
            target = next(
                (c for c in feat_page.components if c.type == "table"),
                None,
            )
            if target is None:
                target = Component(id="", type="table", data={
                    "columns": ["优先级", "功能", "描述"], "rows": [],
                })
                append_component(feat_page, target)
            rows = list(target.data.get("rows") or [])
            for f in missing[:12]:
                rows.append([f.priority, f.name, f.description or ""])
            target.data["rows"] = rows
            dsl_text = Presentation(title=presentation.title, pages=pages).model_dump_json()

    # ── 路线图（阶段补齐） ─────────────────────────────────
    if document.strategy and document.strategy.roadmap:
        road_page = page_by_type("roadmap")
        missing = [
            p for p in document.strategy.roadmap
            if not (_hit(p.phase, dsl_text) or _hit(p.title, dsl_text))
        ]
        if road_page is not None and missing:
            target = next(
                (c for c in road_page.components if c.type == "timeline"),
                None,
            )
            if target is None:
                target = Component(id="", type="timeline", data={"phases": []})
                append_component(road_page, target)
            phases = list(target.data.get("phases") or [])
            for p in missing[:4]:
                phases.append({
                    "name": p.phase, "period": p.timeline or "",
                    "milestones": list(p.milestones or []),
                })
            target.data["phases"] = phases
            dsl_text = Presentation(title=presentation.title, pages=pages).model_dump_json()

    # ── 组件 ID 归一化（全局唯一） ─────────────────────────
    seen: set[str] = set()
    for page in pages:
        for comp in page.components:
            if not comp.id or comp.id in seen:
                comp.id = _unique_id(page.id, seen, f"{page.id}-auto")
            else:
                seen.add(comp.id)

    return Presentation(title=presentation.title, theme=presentation.theme, pages=pages)


def ensure_consulting_theme(presentation: Presentation, seed: str = "") -> Presentation:
    """CyberPPT 风格锁定（确定性）：

    - 主题已是 cyber-* 且 palette 完整 → 保持不变
    - 主题是 cyber-* 但 palette 缺失 → 从预置补全
    - 主题为 default/未知（模型未决策）→ 按 seed 哈希轮换分配 8 套咨询风之一
    """
    from agent_platform.schemas.presentation import THEME_PRESETS, Theme

    presets = THEME_PRESETS
    theme = presentation.theme
    if theme.id in presets and theme.id != "default" and theme.palette:
        return presentation
    if theme.id in presets and theme.id != "default":
        return presentation.model_copy(
            update={
                "theme": theme.model_copy(
                    update={"palette": dict(presets[theme.id]["palette"])}
                )
            }
        )
    cyber_ids = [tid for tid in presets if tid.startswith("cyber-")]
    idx = sum(ord(ch) for ch in seed) % len(cyber_ids) if seed else 0
    tid = cyber_ids[idx]
    preset = presets[tid]
    return presentation.model_copy(
        update={
            "theme": Theme(
                id=tid,
                name=preset["name"],
                palette=dict(preset["palette"]),
                font_scale=theme.font_scale,
            )
        }
    )


def _inject_modular_content(
    pages: list[Page],
    presentation: Presentation,
    document: ProductDocument,
) -> list[Page]:
    """CyberPPT 模块化内容确定性注入：

    1. 竞品 定价/短板（research/competitor_analysis）未入页 → 在
       competitor_matrix 页补「竞品短板与定价」卡片
    2. PRD 章节（strategy.prd_sections 全文）未入页 → 在
       product_architecture / feature_priority 页补「PRD 核心结论」卡片
    """
    dsl_text = Presentation(title=presentation.title, pages=pages).model_dump_json()

    def _norm(text: str | None) -> str:
        return " ".join((text or "").split())

    # ── 1) 竞品短板与定价 ─────────────────────────────────────
    comp = document.competitor_analysis
    if comp and comp.competitors:
        missing: list[str] = []
        for c in comp.competitors[:6]:
            parts = [c.name]
            if c.pricing and _norm(c.pricing)[:8] not in dsl_text:
                parts.append(f"定价：{c.pricing}")
            for w in (c.weaknesses or [])[:3]:
                if _norm(w)[:10] not in dsl_text:
                    parts.append(f"劣势：{_norm(w)[:60]}")
            if len(parts) > 1:
                missing.append("；".join(parts)[:180])
        if missing:
            matrix = next((p for p in pages if p.type == "competitor_matrix"), None)
            if matrix is not None:
                matrix.components.append(
                    Component(
                        id="",
                        type="card",
                        data={"title": "竞品短板与定价", "items": missing[:8]},
                    )
                )
                dsl_text = Presentation(title=presentation.title, pages=pages).model_dump_json()

    # ── 2) PRD 章节核心结论 ───────────────────────────────────
    strat = document.strategy
    if strat and strat.prd_sections:
        missing_prd = [
            s for s in strat.prd_sections[:4]
            if _norm(s.content)[:10] not in dsl_text
        ]
        if missing_prd:
            target = next(
                (p for p in pages if p.type in ("product_architecture", "feature_priority")),
                None,
            )
            if target is not None:
                items = [
                    f"{s.title}：{_norm(s.content)[:110]}"
                    for s in missing_prd[:3]
                ]
                target.components.append(
                    Component(
                        id="",
                        type="card",
                        data={"title": "PRD 核心结论", "items": items},
                    )
                )

    return pages
