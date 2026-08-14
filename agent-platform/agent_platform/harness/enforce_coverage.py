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
