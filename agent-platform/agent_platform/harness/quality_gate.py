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

# 单页文本容量估算（字符）：text/bullets 型组件 data 中的文本总量上限
_PAGE_TEXT_BUDGET = 320
# 组件级文本上限
_COMPONENT_TEXT_BUDGET = 200


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


def run_quality_gate(presentation: Presentation) -> QualityGateReport:
    """对 Presentation DSL 执行确定性质量检查。"""
    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, bool] = {}

    pages = presentation.pages

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

    passed = len(errors) == 0
    return QualityGateReport(passed=passed, errors=errors, warnings=warnings, checks=checks)
