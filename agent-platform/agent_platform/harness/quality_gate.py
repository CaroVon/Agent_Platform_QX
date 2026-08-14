"""
============================================================
视觉质量门（P5）—— 确定性渲染前检查
============================================================

不依赖 LLM 的结构化校验：在 Renderer 渲染之前拦截可预判的
视觉缺陷（密度超标、重复信息、空页、组件超限等），
渲染后的 overflow/overlap 检查由浏览器端质量门完成（导出脚本）。
"""

from __future__ import annotations

from agent_platform.schemas.evaluation import QualityGateReport
from agent_platform.schemas.presentation import Component, Page, Presentation
from agent_platform.schemas.product_document import ProductDocument

# 单页文本容量估算（字符）：text/bullets 型组件 data 中的文本总量上限
_PAGE_TEXT_BUDGET = 600
# 组件级文本上限
_COMPONENT_TEXT_BUDGET = 150


def _component_text_len(component: Component) -> int:
    """估算组件携带的文本量。"""
    data = component.data or {}
    total = 0
    for key in ("text", "title", "content", "quote", "description", "label"):
        value = data.get(key)
        if isinstance(value, str):
            total += len(value)
    items = data.get("items") or data.get("rows") or data.get("points") or data.get("milestones")
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict):
                total += sum(len(str(v)) for v in item.values() if isinstance(v, str))
            elif isinstance(item, str):
                total += len(item)
    return total


def run_quality_gate(
    presentation: Presentation,
    document: ProductDocument | None = None,
) -> QualityGateReport:
    """对 Presentation DSL 执行确定性质量检查。

    document（Canonical Product Document）提供时，额外执行
    「信息覆盖度」检查（A3）：演示必须覆盖上游关键字段，
    覆盖率不足记为 error（在 Critic 环节压分触发修订）。
    """
    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, bool] = {}

    pages = presentation.pages
    dsl_text = presentation.model_dump_json()

    # 1. 页数区间
    page_count_ok = 8 <= len(pages) <= 14
    checks["page_count_8_14"] = page_count_ok
    if not page_count_ok:
        errors.append(f"页数 {len(pages)} 不在 8-14 区间")

    # 2. 每页组件数（cover/closing 允许 1-2，其余 2-6）
    component_limits_ok = True
    for page in pages:
        count = len(page.components)
        limit = (1, 2) if page.type in ("cover", "conclusion") else (2, 6)
        if not (limit[0] <= count <= limit[1]):
            component_limits_ok = False
            warnings.append(f"页 {page.id} 组件数 {count} 超出建议区间 {limit}")
    checks["component_limits"] = component_limits_ok

    # 3. 组件 id 全局唯一
    ids = [c.id for p in pages for c in p.components]
    unique_ids_ok = len(ids) == len(set(ids))
    checks["unique_component_ids"] = unique_ids_ok
    if not unique_ids_ok:
        errors.append("存在重复的组件 ID")

    # 4. 每页 title 非空 + insight（cover/conclusion 除外）
    hierarchy_ok = True
    for page in pages:
        if not page.title.strip():
            hierarchy_ok = False
            errors.append(f"页 {page.id} 缺少标题")
        if page.type not in ("cover", "conclusion") and not (page.insight or "").strip():
            hierarchy_ok = False
            warnings.append(f"页 {page.id} 缺少一句话结论 insight")
    checks["title_and_insight"] = hierarchy_ok

    # 5. 文本密度（估算）
    density_ok = True
    for page in pages:
        total = sum(_component_text_len(c) for c in page.components)
        if total > _PAGE_TEXT_BUDGET:
            density_ok = False
            warnings.append(f"页 {page.id} 文本量估算 {total} 超出预算 {_PAGE_TEXT_BUDGET}")
        for c in page.components:
            clen = _component_text_len(c)
            if clen > _COMPONENT_TEXT_BUDGET:
                warnings.append(f"页 {page.id} 组件 {c.id} 文本过长（{clen}）")
    checks["text_density"] = density_ok

    # 6. 重复信息检测（title/insight 重复）
    titles = [p.title.strip() for p in pages if p.title.strip()]
    insights = [(p.insight or "").strip() for p in pages if (p.insight or "").strip()]
    dup_ok = len(titles) == len(set(titles)) and len(insights) == len(set(insights))
    checks["no_duplicate_info"] = dup_ok
    if not dup_ok:
        warnings.append("存在重复的页面标题或 insight")

    # 7. metric/chart 数据完整性
    data_ok = True
    for page in pages:
        for c in page.components:
            if c.type == "metric" and not c.data.get("value"):
                data_ok = False
                errors.append(f"页 {page.id} 组件 {c.id} metric 缺少 value")
            if c.type == "chart" and not (c.data.get("items") or c.data.get("points")):
                data_ok = False
                errors.append(f"页 {page.id} 组件 {c.id} chart 缺少数据")
    checks["component_data"] = data_ok

    # 8. 信息覆盖度（A3，需 Canonical Document）
    if document is not None:
        _check_coverage(presentation, document, dsl_text, errors, checks)

    passed = len(errors) == 0
    return QualityGateReport(passed=passed, errors=errors, warnings=warnings, checks=checks)


def coverage_issues(
    presentation: Presentation,
    document: ProductDocument,
) -> list[str]:
    """信息覆盖度检查：返回问题清单（供质量门与 AgentLoop 评估器共用）。

    匹配策略（容忍 Agent 合理重述，但要求名称原文或核心前缀出现）:
      - 名称原文出现在 DSL 中
      - 或名称前 6 个字符（核心词）出现在 DSL 中
    """
    dsl_text = presentation.model_dump_json()
    issues: list[str] = []

    def hit(text: str | None) -> bool:
        if not text:
            return False
        if text in dsl_text:
            return True
        return text[:6] in dsl_text

    def missing_names(items: list, key) -> list[str]:
        return [key(item) for item in items if not hit(key(item))]

    # ── 功能覆盖（≥70% 且至少 6 个） ────────────────────────
    if document.strategy and document.strategy.features:
        features = document.strategy.features
        covered = [f for f in features if hit(f.name)]
        min_required = min(6, len(features))
        coverage_ok = len(covered) >= max(min_required, int(len(features) * 0.7))
        if not coverage_ok:
            missing = missing_names(features, lambda f: f.name)[:12]
            issues.append(
                f"功能覆盖率不足：{len(covered)}/{len(features)} 个功能进入演示，"
                f"缺失（必须原文引用）：{', '.join(missing)}"
            )

    # ── 痛点覆盖（≥60%，至少 min(4, 上游条数) 条） ──────────
    if document.research and document.research.customer_pain_points:
        pains = document.research.customer_pain_points
        covered = [p for p in pains if hit(p[:8])]
        required = max(min(4, len(pains)), int(len(pains) * 0.6))
        if len(covered) < required:
            missing = [p for p in pains if not hit(p[:8])][:8]
            issues.append(
                f"痛点覆盖率不足：{len(covered)}/{len(pains)} 条（要求 ≥{required}），"
                f"缺失原文：{'；'.join(missing)}"
            )

    # ── 竞品覆盖（≥70%，至少 min(4, 上游个数) 个） ──────────
    if document.competitor_analysis and document.competitor_analysis.competitors:
        comps = document.competitor_analysis.competitors
        covered = [c for c in comps if hit(c.name)]
        required = max(min(4, len(comps)), int(len(comps) * 0.7))
        if len(covered) < required:
            missing = missing_names(comps, lambda c: c.name)[:10]
            issues.append(
                f"竞品覆盖率不足：{len(covered)}/{len(comps)}（要求 ≥{required}），"
                f"缺失（必须原文引用）：{', '.join(missing)}"
            )

    # ── 市场指标覆盖（上游提供的指标 ≥ min(3, 提供数) 项） ────
    if document.research and document.research.market_size:
        ms = document.research.market_size
        metrics = [
            (label, value) for label, value in
            [("TAM", ms.tam), ("SAM", ms.sam), ("SOM", ms.som), ("CAGR", ms.cagr)]
            if value
        ]
        covered = [label for label, value in metrics if hit(value)]
        required = min(3, len(metrics)) if metrics else 0
        if metrics and len(covered) < required:
            missing = [label for label, value in metrics if not hit(value)]
            issues.append(
                f"市场指标覆盖率不足：{len(covered)}/{len(metrics)}（要求 ≥{required}），"
                f"缺失：{', '.join(missing)}"
            )

    # ── 路线图阶段覆盖（全部阶段） ──────────────────────────
    if document.strategy and document.strategy.roadmap:
        phases = document.strategy.roadmap
        covered = [p for p in phases if hit(p.phase) or hit(p.title)]
        if len(covered) != len(phases):
            missing = [p.phase for p in phases if not (hit(p.phase) or hit(p.title))]
            issues.append(
                f"路线图覆盖不足：{len(covered)}/{len(phases)} 个阶段，"
                f"缺失（必须原文引用）：{', '.join(missing[:8])}"
            )

    # ── 趋势覆盖（≥60%，至少 min(3, 上游条数) 条） ──────────
    if document.research and document.research.industry_trends:
        trends = document.research.industry_trends
        covered = [t for t in trends if hit(t[:8])]
        required = max(min(3, len(trends)), int(len(trends) * 0.6))
        if len(covered) < required:
            missing = [t for t in trends if not hit(t[:8])][:8]
            issues.append(
                f"行业趋势覆盖率不足：{len(covered)}/{len(trends)}（要求 ≥{required}），"
                f"缺失原文：{'；'.join(missing)}"
            )

    # ── 画像覆盖（全部） ───────────────────────────────────
    if document.strategy and document.strategy.personas:
        personas = document.strategy.personas
        covered = [p for p in personas if hit(p.name)]
        if len(covered) != len(personas):
            missing = missing_names(personas, lambda p: p.name)[:8]
            issues.append(
                f"画像覆盖率不足：{len(covered)}/{len(personas)} 个，"
                f"缺失（必须原文引用）：{', '.join(missing)}"
            )

    return issues


def _check_coverage(
    presentation: Presentation,
    document: ProductDocument,
    dsl_text: str,
    errors: list[str],
    checks: dict[str, bool],
) -> None:
    """信息覆盖度：把 coverage_issues 的结论写入质量门报告。"""
    issues = coverage_issues(presentation, document)
    # 检查项按 issue 主题标记
    for key in (
        "coverage_features", "coverage_pain_points", "coverage_competitors",
        "coverage_market_metrics", "coverage_roadmap", "coverage_trends",
        "coverage_personas",
    ):
        checks[key] = not any(issue.startswith({
            "coverage_features": "功能覆盖",
            "coverage_pain_points": "痛点覆盖",
            "coverage_competitors": "竞品覆盖",
            "coverage_market_metrics": "市场指标覆盖",
            "coverage_roadmap": "路线图覆盖",
            "coverage_trends": "行业趋势覆盖",
            "coverage_personas": "画像覆盖",
        }[key]) for issue in issues)
    errors.extend(issues)
