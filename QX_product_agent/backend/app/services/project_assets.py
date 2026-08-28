"""
============================================================
项目资产库服务 —— 每个任务（产品）的全部资产归档与下载
============================================================

设计目标（替代旧的「PPT 资产库」单一种类视角）：
  1. 每个任务（studio_products 一条记录）拥有**对应资产库**，
     集中归档该任务的全部产出资产；
  2. 文本资产（需求 / 市场研究 / 竞品分析 / 策略与PRD / UX设计 /
     演示文案 / 项目完整文档）自动转化为 **Markdown（必产）+ PDF（尽力）**；
  3. PPT 按现有模式产出（ppt-master 原生 PPTX + SVG 预览，见 ppt_asset_recovery）；
  4. 设计图资产库（design_studio）、编辑器上传素材（assets）一并归档；
  5. 支持**单文件下载**与 **ZIP 打包下载**。

存储布局（静态目录 {OUTPUT_DIR} 已挂载于 /api/v1/files）：
  {OUTPUT_DIR}/studio_assets/{product_id}/            任务资产库目录（文本 md/pdf + index.json）
  {OUTPUT_DIR}/studio_assets/{product_id}.pdf|html|pptx   演示导出（既有，按需引用）
  {OUTPUT_DIR}/studio_assets/ppt_projects/...         PPT 工程目录（既有，ppt-master 产出）
  {OUTPUT_DIR}/design_studio/{product_id}/            设计图资产库（既有）
  {OUTPUT_DIR}/assets/{product_id}/                   编辑器上传素材（既有）

文本资产文件名（{key} 为资产包键名）：
  {library_dir}/document.md|.pdf           项目完整文档（含研究/竞品/策略/设计）
  {library_dir}/requirement.md|.pdf        需求文档
  {library_dir}/research.md|.pdf           市场研究报告
  {library_dir}/competitor_analysis.md|.pdf 竞品分析
  {library_dir}/strategy.md|.pdf           产品策略与 PRD
  {library_dir}/design.md|.pdf             UX 设计规格
  {library_dir}/presentation.md|.pdf       演示文案
============================================================
"""

from __future__ import annotations

import io
import json
import logging
import os
import re
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# 资产键 → 中文显示名（生成顺序即展示顺序）
TEXT_ASSETS: list[tuple[str, str]] = [
    ("document", "项目完整文档"),
    ("requirement", "需求文档"),
    ("research", "市场研究报告"),
    ("competitor_matrix", "竞品矩阵"),
    ("competitor_analysis", "竞品分析"),
    ("strategy", "产品策略与 PRD"),
    ("design", "UX 设计规格"),
    ("presentation", "演示文案"),
]

# 文件类别（ZIP 子目录 / 前端分组，顺序即展示顺序）
CATEGORY_DOC = "文档"
CATEGORY_PPT = "演示文稿"
CATEGORY_KEYWORDS = "关键词"
CATEGORY_DESIGN = "设计图片"
CATEGORY_MATERIAL = "素材"
CATEGORY_MOD = "竞品矩阵"

_SAFE_RE = re.compile(r"[^\w\u4e00-\u9fff\-]+")


def _canonical_id(product_id: str) -> str:
    """规范化为带连字符的 UUID 字符串（与 design_studio 目录命名一致）。

    DB 存储可能为无连字符形式，而 SQLAlchemy Uuid / FastAPI uuid.UUID
    均返回带连字符形式 —— 资产库路径统一使用带连字符形式。
    """
    try:
        return str(uuid.UUID(str(product_id)))
    except (ValueError, AttributeError):
        return str(product_id)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def library_dir(product_id: str) -> Path:
    """任务资产库目录（文本 md/pdf 与 index.json 同目录）。"""
    root = Path(get_settings().OUTPUT_DIR).resolve() / "studio_assets"
    return root / _canonical_id(product_id)


def library_path(product_id: str) -> Path:
    return library_dir(product_id) / "index.json"


# ─────────────────────────────────────────────────────────────
# 文本资产 → Markdown 序列化（结构化资产包 → 可交付文本）
# ─────────────────────────────────────────────────────────────

def _md_list(items, indent: int = 0) -> list[str]:
    pad = "  " * indent
    return [f"{pad}- {item}" for item in items]


def _md_sources(sources) -> list[str]:
    if not sources:
        return []
    lines = ["## 资料来源"]
    for src in sources:
        if not isinstance(src, dict):
            continue
        title = src.get("title") or src.get("url") or ""
        url = src.get("url") or ""
        lines.append(f"- [{title}]({url})" if url else f"- {title}")
    return lines


def _md_requirement(data: dict) -> str:
    out = ["# 需求文档", ""]
    idea = data.get("idea")
    if idea:
        out += [f"> {idea}", ""]
    for key, label in (
        ("goals", "目标"),
        ("target_users", "目标用户"),
        ("constraints", "约束条件"),
        ("success_metrics", "成功指标"),
    ):
        items = data.get(key)
        if items:
            out += [f"## {label}", ""] + _md_list(items) + [""]
    return "\n".join(out).strip() + "\n"


def _md_research(data: dict) -> str:
    out = ["# 市场研究报告", ""]
    ms = data.get("market_size") or {}
    if ms:
        out += ["## 市场规模", ""]
        if ms.get("summary"):
            out += [f"- **概述**：{ms['summary']}"]
        for label, key in (("TAM", "tam"), ("SAM", "sam"), ("SOM", "som")):
            if ms.get(key):
                out.append(f"- **{label}**：{ms[key]}")
        if ms.get("cagr"):
            out.append(f"- **复合年增长率**：{ms['cagr']}")
        if ms.get("source"):
            out.append(f"- **数据来源**：{ms['source']}")
        out.append("")
    competitors = data.get("competitors") or []
    if competitors:
        out += ["## 主要竞品", ""]
        for c in competitors:
            if not isinstance(c, dict):
                continue
            name = c.get("name") or ""
            positioning = c.get("positioning") or ""
            url = c.get("url") or ""
            line = f"- **{name}**" + (f"（{positioning}）" if positioning else "")
            out.append(f"{line}[{url}]({url})" if url else line)
        out.append("")
    for key, label in (
        ("customer_pain_points", "用户痛点"),
        ("industry_trends", "行业趋势"),
    ):
        items = data.get(key)
        if items:
            out += [f"## {label}", ""] + _md_list(items) + [""]
    out += _md_sources(data.get("sources")) + [""]
    return "\n".join(out).strip() + "\n"


def _md_competitor_matrix(data: dict) -> str:
    """竞品矩阵（数据驱动 MOD 报告）→ Markdown 序列化。"""
    out = ["# 竞品矩阵（数据驱动 MOD 报告）", ""]
    out += [f"> 主关键词：{data.get('keyword')} ｜ 站点：{data.get('marketplace')} ｜ "
            f"抓取时间：{data.get('fetched_at')}", ""]

    interp = data.get("llm_interpretation") or {}
    out += ["## 4 区一句话解读", ""]
    zone_labels = {
        "price_gap": "🟢 价格缺口区",
        "value_opportunity": "🔵 性价比机会区",
        "demand_heat": "🟡 需求热度区",
        "red_ocean": "🔴 红海警示区",
    }
    for k, label in zone_labels.items():
        out += [f"- **{label}**：{interp.get(k, '—')}"]
    out += [f"- **我方定位**：{interp.get('verdict', '—')}", ""]

    paths = data.get("artifacts_paths") or {}
    out += ["## 产物文件", ""]
    out += [f"- 分析 PPT：`{paths.get('pptx', '—')}`"]
    out += [f"- 核心矩阵图：`{paths.get('matrix_chart_png') or paths.get('matrix_chart', '—')}`"]
    out += [f"- 数据 CSV：`{paths.get('csv', '—')}`"]
    out += [f"- 完整报告 MD：`{paths.get('markdown', '—')}`（14 章数据驱动分析）", ""]

    rules = data.get("zoning_rules") or {}
    out += ["## 分区阈值", ""]
    for zone, rule in rules.items():
        out += [f"- **{zone_labels.get(zone, zone)}**：{rule}"]
    out += [""]

    products = data.get("products") or []
    if products:
        out += ["## 竞品明细", ""]
        out += ["| ASIN | 标题 | 价格$ | 评分 | 评论数 | 月销估算 | BSR | 分区 |",
                "|---|---|---|---|---|---|---|---|"]
        for p in products:
            zone = p.get("zone") or "neutral"
            out.append(f"| {p.get('asin')} | {str(p.get('title') or '')[:40]} | "
                       f"{p.get('current_price')} | {p.get('rating')} | {p.get('review_count')} | "
                       f"{p.get('est_monthly_sales')} | {p.get('bsr')} | {zone_labels.get(zone, zone)} |")
        out += [""]

    cost = data.get("cost_estimate") or {}
    out += ["## 数据溯源", ""]
    out += [f"- 数据源：Rainforest API（search 关键词发现 + product 详情）"]
    out += ["- 月销估算：Amazon 官方 recent_sales 口径（\"bought in past month\"）解析，缺失回退 BSR 系数"]
    if cost.get("rainforest_credits"):
        out += [f"- credits：~{cost['rainforest_credits']}"]
    return "\n".join(out).strip() + "\n"


def _md_competitor_analysis(data: dict) -> str:
    out = ["# 竞品分析", ""]
    landscape = data.get("competitive_landscape")
    if landscape:
        out += ["## 竞争格局", "", landscape, ""]
    matrix = data.get("matrix") or {}
    profiles = matrix.get("profiles") or data.get("competitors") or []
    if profiles:
        dims = matrix.get("dimensions") or []
        out += ["## 竞品对比矩阵", ""]
        header = "| 竞品 | " + " | ".join(str(d) for d in dims) + " |"
        sep = "| --- |" + " --- |" * len(dims)
        out += [header, sep]
        for p in profiles:
            if not isinstance(p, dict):
                continue
            cells = [str(p.get("name") or "")]
            for d in dims:
                key = {
                    "定位": "positioning", "目标客群": "target_segment", "定价": "pricing",
                    "核心优势": "strengths", "主要劣势": "weaknesses",
                }.get(str(d), "")
                val = p.get(key)
                if isinstance(val, list):
                    val = "；".join(str(v) for v in val)
                cells.append(str(val or ""))
            out.append("| " + " | ".join(cells) + " |")
        out.append("")
    for key, label in (
        ("differentiation_opportunities", "差异化机会"),
        ("competitive_landscape", ""),
    ):
        if label and data.get(key):
            out += [f"## {label}", ""] + _md_list(data[key]) + [""]
    out += _md_sources(data.get("sources")) + [""]
    return "\n".join(out).strip() + "\n"


def _md_strategy(data: dict) -> str:
    out = ["# 产品策略与 PRD", ""]
    positioning = data.get("positioning")
    if positioning:
        out += ["## 产品定位", "", f"> {positioning}", ""]
    personas = data.get("personas") or []
    if personas:
        out += ["## 用户画像", ""]
        for p in personas:
            if not isinstance(p, dict):
                continue
            out += [f"### {p.get('name') or ''}" + (f"（{p.get('role')}）" if p.get("role") else ""), ""]
            for label, key in (("目标", "goals"), ("痛点", "pain_points")):
                items = p.get(key)
                if items:
                    out += [f"**{label}**", ""] + _md_list(items) + [""]
            if p.get("behavior"):
                out += [f"**行为特征**：{p['behavior']}", ""]
    features = data.get("features") or []
    if features:
        out += ["## 功能列表", ""]
        for f in features:
            if not isinstance(f, dict):
                continue
            name = f.get("name") or ""
            desc = f.get("description") or ""
            category = f.get("category") or ""
            priority = f.get("priority") or ""
            tag = " / ".join(x for x in (category, f"优先级 {priority}" if priority else "") if x)
            out.append(f"- **{name}**" + (f"（{tag}）" if tag else "") + (f"：{desc}" if desc else ""))
        out.append("")
    roadmap = data.get("roadmap") or []
    if roadmap:
        out += ["## 路线图", ""]
        for r in roadmap:
            if not isinstance(r, dict):
                continue
            head = f"### {r.get('phase') or ''} · {r.get('title') or ''}"
            if r.get("timeline"):
                head += f"（{r['timeline']}）"
            out += [head, ""]
            if r.get("goal"):
                out += [f"**目标**：{r['goal']}", ""]
            if r.get("milestones"):
                out += _md_list(r["milestones"]) + [""]
    prd = data.get("prd_sections") or []
    if prd:
        out += ["## PRD 章节", ""]
        for s in prd:
            if not isinstance(s, dict):
                continue
            out += [f"### {s.get('title') or ''}", "", str(s.get("content") or ""), ""]
    out += _md_sources(data.get("sources")) + [""]
    return "\n".join(out).strip() + "\n"


def _md_design(data: dict) -> str:
    out = ["# UX 设计规格", ""]
    user_flow = data.get("user_flow") or []
    if user_flow:
        out += ["## 用户旅程", ""]
        for i, step in enumerate(user_flow, 1):
            if not isinstance(step, dict):
                continue
            mark = "（入口）" if step.get("is_entry") else "（出口）" if step.get("is_exit") else ""
            line = f"{i}. **{step.get('step') or ''}**{mark}"
            if step.get("description"):
                line += f"：{step['description']}"
            out.append(line)
        out.append("")
    pages = data.get("pages") or []
    if pages:
        out += ["## 页面规格", ""]
        for p in pages:
            if not isinstance(p, dict):
                continue
            head = f"### {p.get('name') or ''}"
            if p.get("purpose"):
                head += f"（{p['purpose']}）"
            out += [head, ""]
            if p.get("key_elements"):
                out += _md_list(p["key_elements"]) + [""]
    components = data.get("components") or []
    if components:
        out += ["## 组件规格", ""]
        for c in components:
            if not isinstance(c, dict):
                continue
            head = f"### {c.get('name') or ''}"
            if c.get("kind"):
                head += f"（{c['kind']}）"
            out += [head, ""]
            if c.get("description"):
                out += [c["description"], ""]
    out += _md_sources(data.get("sources")) + [""]
    return "\n".join(out).strip() + "\n"


def _md_presentation(data: dict) -> str:
    out = ["# 演示文案", ""]
    title = data.get("title")
    theme = (data.get("theme") or {}).get("name") or ""
    if title:
        out += [f"> {title}", ""]
    if theme:
        out += [f"主题：{theme}", ""]
    pages = data.get("pages") or []
    for i, page in enumerate(pages, 1):
        if not isinstance(page, dict):
            continue
        out += [f"## 第 {i} 页 · {page.get('title') or ''}", ""]
        if page.get("subtitle"):
            out += [page["subtitle"], ""]
        if page.get("insight"):
            out += [f"> **洞察**：{page['insight']}", ""]
        for comp in page.get("components") or []:
            if not isinstance(comp, dict):
                continue
            out += _md_component(comp)
        out.append("")
    return "\n".join(out).strip() + "\n"


def _md_component(comp: dict) -> list[str]:
    """演示组件 → markdown 行（常见组件结构化呈现，其余通用兜底）。"""
    ctype = comp.get("type") or ""
    data = comp.get("data") or {}
    if ctype == "metric":
        line = f"- **{data.get('label') or ''}**：{data.get('value') or ''}"
        if data.get("note"):
            line += f"（{data['note']}）"
        return [line]
    if ctype in ("text", "quote"):
        text = data.get("text") or data.get("content") or ""
        return [f"> {text}"] if text else []
    if ctype == "image":
        alt = data.get("alt") or data.get("caption") or "图片"
        return [f"- 图片：{alt}"]
    return _dict_to_md(data)


def _dict_to_md(data: dict, indent: int = 0) -> list[str]:
    """通用 dict → markdown 兜底（保持可读，不输出空值）。"""
    pad = "  " * indent
    lines: list[str] = []
    for key, value in data.items():
        if value is None or value == "":
            continue
        if isinstance(value, (list, tuple)):
            if not value:
                continue
            if all(not isinstance(v, (dict, list)) for v in value):
                lines.append(f"{pad}- **{key}**：{'；'.join(str(v) for v in value)}")
            else:
                lines.append(f"{pad}- **{key}**")
                for v in value:
                    if isinstance(v, dict):
                        lines += _dict_to_md(v, indent + 1)
                    else:
                        lines.append(f"{pad}  - {v}")
        elif isinstance(value, dict):
            lines.append(f"{pad}- **{key}**")
            lines += _dict_to_md(value, indent + 1)
        else:
            lines.append(f"{pad}- **{key}**：{value}")
    return lines


def _serialize_md(asset_key: str, data) -> str:
    """资产包节点 → Markdown 文本（未识别结构时 JSON 兜底）。"""
    if not isinstance(data, dict):
        return f"# {asset_key}\n\n{data}\n"
    serializer = {
        "requirement": _md_requirement,
        "research": _md_research,
        "competitor_matrix": _md_competitor_matrix,
        "competitor_analysis": _md_competitor_analysis,
        "strategy": _md_strategy,
        "design": _md_design,
        "presentation": _md_presentation,
    }.get(asset_key)
    if serializer:
        return serializer(data)
    if asset_key == "document":
        return _md_document(data)
    return f"# {asset_key}\n\n```json\n{json.dumps(data, ensure_ascii=False, indent=2)}\n```\n"


def _md_document(data: dict) -> str:
    """项目完整文档：project_info + 各文本资产汇总。"""
    out = ["# 项目完整文档", ""]
    info = data.get("project_info") or {}
    title = info.get("title") or info.get("idea") or ""
    if title:
        out += [f"> {title}", ""]
    if info.get("created_at"):
        out += [f"创建时间：{info['created_at']}", ""]
    for key, _label in TEXT_ASSETS:
        if key == "document":
            continue
        section = data.get(key)
        if not section:
            continue
        body = _serialize_md(key, section)
        # 去掉子文档一级标题，作为章节嵌入
        body = re.sub(r"^# .+\n+", "", body, count=1)
        out += [body, ""]
    return "\n".join(out).strip() + "\n"


# ─────────────────────────────────────────────────────────────
# Markdown → PDF（weasyprint，尽力而为）
# ─────────────────────────────────────────────────────────────

_PDF_CSS = """
@page { size: A4; margin: 2cm 1.8cm; }
body { font-family: "Noto Sans CJK SC", "PingFang SC", "Microsoft YaHei", sans-serif;
       font-size: 12px; line-height: 1.7; color: #1f2937; }
h1 { font-size: 22px; color: #12355B; border-bottom: 2px solid #12355B; padding-bottom: 6px; }
h2 { font-size: 16px; color: #12355B; margin-top: 22px; }
h3 { font-size: 14px; color: #24415E; margin-top: 16px; }
table { border-collapse: collapse; width: 100%; margin: 8px 0; }
th, td { border: 1px solid #d1d5db; padding: 5px 8px; font-size: 11px; text-align: left; }
th { background: #f3f4f6; }
blockquote { border-left: 3px solid #C87E4F; margin: 6px 0; padding: 2px 12px; color: #4b5563; }
code { background: #f3f4f6; padding: 1px 4px; border-radius: 3px; font-size: 11px; }
"""


def _md_to_pdf(md_text: str, out_path: Path) -> bool:
    """Markdown → PDF（weasyprint）；失败返回 False（不阻断，md 为必产）。"""
    try:
        import markdown2
        from weasyprint import HTML

        html_body = markdown2.markdown(md_text, extras=["tables", "fenced-code-blocks"])
        html = (
            f'<meta charset="utf-8"><style>{_PDF_CSS}</style>'
            f"<body>{html_body}</body>"
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        HTML(string=html, base_url=".").write_pdf(str(out_path))
        return out_path.is_file() and out_path.stat().st_size > 0
    except Exception as exc:  # noqa: BLE001 —— PDF 尽力而为
        logger.warning("[Project Assets] PDF 渲染失败 | %s | %s", out_path, exc)
        return False


# ─────────────────────────────────────────────────────────────
# 文本资产产出（任务完成时调用；读取资产库时惰性兜底）
# ─────────────────────────────────────────────────────────────

_PDF_FAIL_CACHE: set[str] = set()


def ensure_text_assets(product_id: str, package: dict | None,
                       render_pdf: bool = False) -> dict:
    """为任务的文本资产生成 Markdown（必产）写入任务资产库目录。

    - 幂等：md 已存在且内容一致则跳过重写
    - render_pdf=True 时补产缺失 PDF（weasyprint 同步耗时——仅完成态
      后处理与 POST /render-pdf 显式调用；读路径禁止开启）
    - PDF 渲染失败负缓存：同产品同键本进程内不再重试
    - Presentation DSL 另存为任务专属 presentation.json，供项目资产库和 Web 演示入口使用
    - 返回本次实际写入的 {资产键: path}
    """
    product_id = _canonical_id(product_id)
    package = package or {}
    written: dict[str, str] = {}
    keywords = package.get("keywords")
    if isinstance(keywords, dict) and keywords:
        dir_path = library_dir(product_id)
        dir_path.mkdir(parents=True, exist_ok=True)
        keywords_path = dir_path / "keywords.json"
        try:
            keywords_text = json.dumps(keywords, ensure_ascii=False, indent=2) + "\n"
            if (
                not keywords_path.is_file()
                or keywords_path.read_text(encoding="utf-8") != keywords_text
            ):
                keywords_path.write_text(keywords_text, encoding="utf-8")
            written["keywords"] = str(
                keywords_path.relative_to(Path(get_settings().OUTPUT_DIR).resolve())
            )
        except OSError as exc:
            logger.warning(
                "[Project Assets] Keywords 资产写入失败 | product=%s | %s",
                product_id,
                exc,
            )
    presentation = package.get("presentation")
    if presentation:
        dir_path = library_dir(product_id)
        dir_path.mkdir(parents=True, exist_ok=True)
        presentation_path = dir_path / "presentation.json"
        try:
            presentation_text = json.dumps(
                presentation, ensure_ascii=False, indent=2, default=str,
            ) + "\n"
            if (
                not presentation_path.is_file()
                or presentation_path.read_text(encoding="utf-8") != presentation_text
            ):
                presentation_path.write_text(presentation_text, encoding="utf-8")
            written["presentation"] = str(
                presentation_path.relative_to(Path(get_settings().OUTPUT_DIR).resolve())
            )
        except OSError as exc:
            logger.warning(
                "[Project Assets] Presentation 资产写入失败 | product=%s | %s",
                product_id, exc,
            )
    for key, label in TEXT_ASSETS:
        data = package.get(key)
        if not data:
            continue
        md_text = _serialize_md(key, data)
        if not md_text.strip():
            continue
        dir_path = library_dir(product_id)
        dir_path.mkdir(parents=True, exist_ok=True)

        md_path = dir_path / f"{key}.md"
        try:
            if not md_path.is_file() or md_path.read_text(encoding="utf-8") != md_text:
                md_path.write_text(md_text, encoding="utf-8")
            written[key] = str(md_path.relative_to(Path(get_settings().OUTPUT_DIR).resolve()))
            pdf_path = md_path.with_suffix(".pdf")
            if (render_pdf and not pdf_path.is_file()
                    and f"{product_id}:{key}" not in _PDF_FAIL_CACHE):
                try:
                    _md_to_pdf(md_text, pdf_path)
                except Exception as exc:  # noqa: BLE001 —— 负缓存，避免每次请求重试
                    _PDF_FAIL_CACHE.add(f"{product_id}:{key}")
                    logger.warning("[Project Assets] PDF 渲染失败（负缓存）| %s:%s | %s",
                                   product_id, key, str(exc)[:80])
        except OSError as exc:
            logger.warning("[Project Assets] 文本资产写入失败 | product=%s | %s | %s",
                           product_id, key, exc)
    if written:
        logger.info("[Project Assets] 文本资产产出 | product=%s | %s",
                    product_id, ",".join(written))
    return written


# ─────────────────────────────────────────────────────────────
# 资产库聚合（单文件列表 + ZIP 打包）
# ─────────────────────────────────────────────────────────────

def _files_url(relative: str) -> str:
    """相对 OUTPUT_DIR 路径 → /api/v1/files 静态 URL（逐段百分号编码）。"""
    parts = [quote(p, safe="") for p in relative.split("/") if p]
    return "/api/v1/files/" + "/".join(parts)


def _entry(relative: str, kind: str, category: str, **extra) -> dict:
    """构造单个资产条目。"""
    output_dir = Path(get_settings().OUTPUT_DIR).resolve()
    path = output_dir / relative
    entry = {
        "name": Path(relative).name,
        "path": relative.replace(os.sep, "/"),
        "url": _files_url(relative),
        "size": path.stat().st_size if path.is_file() else 0,
        "kind": kind,
        "category": category,
        "generated": False,
    }
    entry.update(extra)
    return entry


def _design_studio_images(product_id: str) -> list[dict]:
    """design_studio 资产库中的图片条目（kind=image，category=设计图片）。"""
    from app.services.design_studio import library_dir as ds_dir
    from app.services.design_studio import load_library

    product_id = _canonical_id(product_id)
    try:
        library = load_library(product_id)
    except Exception:  # noqa: BLE001
        return []
    items = [it for it in library.get("items", []) if isinstance(it, dict) and it.get("image")]
    entries = []
    for it in items:
        img = it["image"] or {}
        fname = img.get("name")
        if not fname:
            continue
        path = ds_dir(product_id) / fname
        if not path.is_file():
            continue
        rel = f"design_studio/{product_id}/{fname}"
        entries.append({
            "name": f"{it.get('kind', 'image')}_{it.get('name', '')[:24]}_{fname}",
            "path": rel,
            "url": img.get("url") or _files_url(rel),
            "size": path.stat().st_size,
            "kind": "image",
            "category": CATEGORY_DESIGN,
            "generated": False,
            "preview_url": img.get("url") or _files_url(rel),
        })
    return entries


def _uploaded_images(product_id: str) -> list[dict]:
    """编辑器上传素材（assets/{product_id}/ 图片）。"""
    product_id = _canonical_id(product_id)
    asset_dir = Path(get_settings().OUTPUT_DIR).resolve() / "assets" / product_id
    entries = []
    if asset_dir.is_dir():
        for f in sorted(asset_dir.iterdir()):
            if f.is_file() and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
                rel = f"assets/{product_id}/{f.name}"
                entries.append({
                    "name": f.name,
                    "path": rel,
                    "url": _files_url(rel),
                    "size": f.stat().st_size,
                    "kind": "image",
                    "category": CATEGORY_MATERIAL,
                    "generated": False,
                    "preview_url": _files_url(rel),
                })
    return entries


def _ppt_entry(product_id: str, package: dict) -> dict | None:
    """ppt-master 原生 PPTX（现有模式产物），失败时按磁盘对账恢复。"""
    from app.services.ppt_asset_recovery import (
        build_svg_preview_urls,
        latest_pptx,
        match_asset_for_product,
    )

    product_id = _canonical_id(product_id)
    output_dir = Path(get_settings().OUTPUT_DIR).resolve()
    ppt = package.get("ppt_design") or {}
    rel = ppt.get("pptx_relative")
    path = output_dir / rel if rel else None
    if path and path.is_file():
        # 重试会在同一工程目录留下多个 PPTX；资产包必须引用最新导出。
        current = latest_pptx(path.parent.parent)
        if current:
            path = current
            rel = str(current.relative_to(output_dir))
    if not (rel and path and path.is_file()):
        recovered = match_asset_for_product(
            product_id,
            idea=package.get("idea") or "",
            presentation_title=(package.get("presentation") or {}).get("title") or "",
            created_at_utc=package.get("meta", {}).get("created_at"),
        )
        if recovered:
            ppt = recovered
            rel = recovered.get("pptx_relative")
            path = output_dir / rel if rel else None
    if not (rel and path and path.is_file()):
        # 旧任务：studio_assets 扁平目录中的 PPTX 导出
        flat = output_dir / "studio_assets" / f"{product_id}.pptx"
        if flat.is_file():
            return _entry(f"studio_assets/{product_id}.pptx", "ppt", CATEGORY_PPT,
                          pages=0, preview_urls=[])
        return None
    # svg 预览：资产包未携带时按磁盘 svg_final/svg_output 生成
    previews = ppt.get("svg_previews") or []
    if not previews:
        try:
            project_dir = path.parent.parent  # .../ppt_projects/{folder}
            previews = build_svg_preview_urls(project_dir)
        except Exception:  # noqa: BLE001 —— 预览缺失不影响下载
            previews = []
    return _entry(rel, "ppt", CATEGORY_PPT,
                  pages=ppt.get("pages") or 0,
                  preview_urls=previews)


def _presentation_entry(product_id: str, package: dict,
                         ensure: bool = True) -> dict | None:
    """Presentation DSL 资产：没有原生 PPTX 时仍保留可打开的 Web 演示入口。"""
    presentation = package.get("presentation") or {}
    if not presentation:
        return None
    # 惰性补写仅在 ensure=True（详情端点/完成态）时执行；列表路径纯只读
    if ensure:
        ensure_text_assets(product_id, package, render_pdf=False)
    relative = f"studio_assets/{_canonical_id(product_id)}/presentation.json"
    path = Path(get_settings().OUTPUT_DIR).resolve() / relative
    if not path.is_file():
        return None
    pages = presentation.get("pages") or presentation.get("slides") or []
    return _entry(
        relative,
        "presentation",
        CATEGORY_PPT,
        generated=True,
        pages=len(pages) if isinstance(pages, list) else 0,
        viewer_url=f"/presentation?product_id={_canonical_id(product_id)}",
    )


def _keywords_entry(product_id: str, package: dict,
                     ensure: bool = True) -> dict | None:
    """任务 Keywords 资产：独立 JSON 文件 + 一级 Keywords 页面入口。"""
    keywords = package.get("keywords")
    if not isinstance(keywords, dict) or not keywords:
        return None
    if ensure:
        ensure_text_assets(product_id, package, render_pdf=False)
    relative = f"studio_assets/{_canonical_id(product_id)}/keywords.json"
    path = Path(get_settings().OUTPUT_DIR).resolve() / relative
    if not path.is_file():
        return None
    return _entry(
        relative,
        "keywords",
        CATEGORY_KEYWORDS,
        generated=True,
        viewer_url=f"/keywords?product_id={_canonical_id(product_id)}",
    )


def _text_deliverables(product_id: str) -> list[dict]:
    """任务资产库目录中的文本 md/pdf 产出。"""
    product_id = _canonical_id(product_id)
    dir_path = library_dir(product_id)
    entries = []
    if not dir_path.is_dir():
        return entries
    for f in sorted(dir_path.iterdir()):
        if not f.is_file() or f.suffix.lower() not in (".md", ".pdf"):
            continue
        relative = f"studio_assets/{product_id}/{f.name}"
        entries.append(_entry(
            relative,
            "doc",
            CATEGORY_DOC,
            generated=True,
            preview_url=_files_url(relative) if f.suffix.lower() == ".pdf" else None,
        ))
    return entries


def _mod_matrix_entries(product_id: str) -> list[dict]:
    """竞品矩阵（MOD）产物资产组：pptx/矩阵图/数据文件/章节图。

    目录契约：studio_assets/{product_id}/competitor_matrix/（run_mod 落盘）。
    全部走统一 collect_files → 单文件下载（/api/v1/files）+ ZIP 分组打包。
    """
    product_id = _canonical_id(product_id)
    mod_dir = Path(get_settings().OUTPUT_DIR).resolve() / "studio_assets" \
        / product_id / "competitor_matrix"
    if not mod_dir.is_dir():
        return []
    entries: list[dict] = []

    # 核心交付物（顺序即展示顺序）；pptx 附 svg_final 逐页预览
    svg_final = mod_dir / "ppt" / "svg_final"
    pptx_previews: list[str] = []
    if svg_final.is_dir():
        pptx_previews = [_files_url(
            f"studio_assets/{product_id}/competitor_matrix/ppt/svg_final/{f.name}"
        ) for f in sorted(svg_final.glob("slide_*.svg"))[:20]]

    def _add(fname: str, kind: str, *, preview: bool = False,
             name: str | None = None, preview_urls: list | None = None):
        rel = f"studio_assets/{product_id}/competitor_matrix/{fname}"
        path = mod_dir / fname
        if not path.is_file():
            return
        extra: dict = {}
        if preview:
            extra["preview_url"] = _files_url(rel)
        if name:
            extra["name"] = name
        if preview_urls:
            extra["preview_urls"] = preview_urls
        entries.append(_entry(rel, kind, CATEGORY_MOD, **extra))

    _add("competitor_matrix.pptx", "ppt", preview_urls=pptx_previews)
    _add("competitor_matrix.md", "doc")
    _add("matrix_chart.png", "image", preview=True)
    _add("matrix_chart.svg", "image", preview=True)
    _add("data.csv", "data")
    _add("zoning.json", "data")
    _add("deck_audit.json", "data")
    _add("data/manifest.json", "data", name="manifest.json（数据溯源）")
    _add("data/products.csv", "data", name="products.csv（宽表）")
    # 章节图表（chapters/*.svg）
    chapters_dir = mod_dir / "chapters"
    if chapters_dir.is_dir():
        for f in sorted(chapters_dir.glob("*.svg")):
            rel = f"studio_assets/{product_id}/competitor_matrix/chapters/{f.name}"
            entries.append(_entry(rel, "image", CATEGORY_MOD, preview_url=_files_url(rel)))
    return entries


def collect_files(product_id: str, package: dict | None,
                  ensure: bool = True) -> list[dict]:
    """聚合任务全部资产（文本产出 + PPT + 演示导出 + 设计图 + 上传素材）。

    ensure=False：纯只读扫描（列表端点用）——不触发任何 md/json 补写，
    避免读路径隐藏写放大（实测曾致列表请求 93s）。"""
    product_id = _canonical_id(product_id)
    package = package or {}
    output_dir = Path(get_settings().OUTPUT_DIR).resolve()
    entries: list[dict] = _text_deliverables(product_id)
    seen = {e["path"] for e in entries}

    # 演示导出（既有端点产出：PDF / HTML）
    for ext, kind in ((".pdf", "presentation"), (".html", "presentation")):
        rel = f"studio_assets/{product_id}{ext}"
        if (output_dir / rel).is_file() and rel not in seen:
            entries.append(_entry(rel, kind, CATEGORY_PPT))
            seen.add(rel)

    # PPT（现有模式：ppt-master 原生 PPTX）
    ppt = _ppt_entry(product_id, package)
    if ppt and ppt["path"] not in seen:
        entries.append(ppt)
        seen.add(ppt["path"])

    # Presentation DSL（即使原生 PPTX 节点失败，也必须进入项目资产库）
    presentation = _presentation_entry(product_id, package, ensure=ensure)
    if presentation and presentation["path"] not in seen:
        entries.append(presentation)
        seen.add(presentation["path"])

    keywords = _keywords_entry(product_id, package, ensure=ensure)
    if keywords and keywords["path"] not in seen:
        entries.append(keywords)
        seen.add(keywords["path"])

    # 竞品矩阵（MOD）产物资产组：PPT/矩阵图/数据/章节图
    for entry in _mod_matrix_entries(product_id):
        if entry["path"] not in seen:
            entries.append(entry)
            seen.add(entry["path"])

    # 设计图资产库 + 上传素材
    for entry in (*_design_studio_images(product_id), *_uploaded_images(product_id)):
        if entry["path"] not in seen:
            entries.append(entry)
            seen.add(entry["path"])

    return entries


def save_library_index(product_id: str, package: dict | None,
                       files: list[dict] | None = None) -> dict:
    """把聚合结果落盘到任务资产库 index.json（审计 + 目录自包含）。

    files 传入时复用（详情端点已 collect 过），避免二次全量扫描。"""
    files = files if files is not None else collect_files(product_id, package)
    index = {
        "schema_version": 1,
        "product_id": str(product_id),
        "generated_at": _now(),
        "total_size": sum(f["size"] for f in files),
        "files": files,
    }
    path = library_path(product_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
    except OSError as exc:
        logger.warning("[Project Assets] index.json 写入失败 | product=%s | %s", product_id, exc)
    return index


def build_task_zip_bytes(product_id: str, package: dict | None, idea: str = "") -> bytes | None:
    """打包任务全部资产为 ZIP（按类别分子目录）；无资产返回 None。"""
    files = collect_files(product_id, package)
    if not files:
        return None
    output_dir = Path(get_settings().OUTPUT_DIR).resolve()
    prefix = _SAFE_RE.sub("_", (idea or "").strip())[:40] or str(product_id)[:8]

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for entry in files:
            path = output_dir / entry["path"]
            if not path.is_file():
                continue
            arcname = f"{prefix}/{entry['category']}/{entry['name']}"
            try:
                zf.write(path, arcname)
            except OSError as exc:
                logger.warning("[Project Assets] ZIP 写入跳过 | %s | %s", entry["path"], exc)
    return buf.getvalue()
