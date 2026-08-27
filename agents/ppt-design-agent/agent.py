"""
PptDesign Agent —— 独立 PPT 设计成员（hugohe3/ppt-master 工作流适配 v2）
==========================================================================

v2 升级重点：
  1. **生图能力完全释放**：每项目生成 5+ 张图（hero/cover/architecture/design/scene + 每页配图）
  2. **生图聚焦产品架构 + 产品设计**（_STYLE_PREFIX + ARCHITECTURE/DESIGN prompt）
  3. **图片入库 design studio**：outputs/assets/{product_id}/，前端 /api/v1/files/assets/ 读取
  4. **spec_lock 自动反推**：扫描 svg_output/ 实际产物，补全 font_size_recurrence/gradient_ids
  5. **跨页一致性**：每页强制注入统一 footer (data-pptx-layer="master")
  6. **字号收敛**：白名单 19 档，未声明字号 snap 到最近合法档
  7. **根属性注入**：data-pptx-page-role + page_index + page_total

模型分工：本 Agent 的 LLM 环节（设计简报）使用 Presentation 专用模型
（AGENT_PLATFORM_PRESENTATION_LLM_*，如 MiniMax）；未配置时回退主 LLM
（DeepSeek）或完全确定性生成（无 LLM 调用）。渲染/转换全程无模型。

设计资产流向（Design Studio）：
  image_prompts.json → image_gen.py → {project_dir}/images/
  + 同步到 → {OUTPUT_DIR}/assets/{product_id}/
  + 设计工作室 API → 前端 DesignStudioPage 通过 /api/v1/files/assets/{product_id}/ 展示
"""

from __future__ import annotations

import json
import hashlib
import logging
import os
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_platform.config.settings import get_settings
from agent_platform.harness.agent_loop import BaseAgent
from agent_platform.llm.client import get_presentation_llm_client, get_llm_client
from agent_platform.llm.client import LLMError, classify_llm_error
from agent_platform.schemas import AgentResult

logger = logging.getLogger(__name__)

_SKILL_DIR = Path(__file__).resolve().parent / "vendor" / "ppt-master"
_SCRIPTS_DIR = _SKILL_DIR / "scripts"

# ── 逐页 SVG 并发参数（自适应 batch，参照 image_gen._run_manifest） ──
_PPT_SVG_MAX_PAGE_ATTEMPTS = 3        # 单页校验失败重试上限（与原顺序版一致）
_PPT_SVG_MAX_RATE_LIMIT_ATTEMPTS = 3  # 单页限流重排队预算（超出 → fallback）
_PPT_SVG_BATCH_GAP_SEC = 0.3          # batch 间温和节流，避免突发

_FONT = "Noto Sans SC, Source Han Sans SC, PingFang SC, Microsoft YaHei, sans-serif"
_TITLE_FONT = "Noto Serif SC, Source Han Serif SC, Georgia, serif"


def _get_reusable_project_dir(base: Path, product_id: str) -> Path:
    """为同一产品复用 PPT 项目目录，避免节点重试制造新目录。"""
    project_key = re.sub(r"[^A-Za-z0-9._-]+", "_", product_id).strip("._")[:80]
    if not project_key:
        # 中文 idea 清洗后可能只剩下下划线，不能再退回共享的 product 目录。
        project_key = f"idea-{hashlib.sha256(product_id.encode('utf-8')).hexdigest()[:16]}"
    base.mkdir(parents=True, exist_ok=True)
    stable = base / project_key
    if stable.is_dir():
        return stable

    # 兼容此前按 product_id_timestamp 命名的目录，优先复用最近一次产物。
    legacy = list(base.glob(f"{project_key}_*"))
    legacy = [path for path in legacy if path.is_dir()]
    if legacy:
        return max(legacy, key=lambda path: path.stat().st_mtime)
    return stable


# ─────────────────────────────────────────────────────────────────
# 设计简报（LLM 可选）
# ─────────────────────────────────────────────────────────────────

def _design_brief_llm(idea: str, theme_name: str, page_count: int) -> str:
    """设计简报（可选 LLM，MiniMax 承接；失败回退确定性文案）。"""
    try:
        llm = get_presentation_llm_client() or get_llm_client()
        if llm is None or not llm.api_key:
            return ""
        prompt = (
            f"为产品「{idea}」写 120 字以内的演示设计简报（咨询风格，主题「{theme_name}」，"
            f"约 {page_count} 页）：受众、叙事基调、视觉语气。直接输出中文正文，不要格式。"
        )
        return (llm.complete(
            [{"role": "system", "content": "你是演示设计总监，输出精炼的中文设计简报。"},
             {"role": "user", "content": prompt}],
            temperature=0.4, max_tokens=300,
        ) or "").strip()[:200]
    except Exception as exc:  # noqa: BLE001
        logger.warning("设计简报生成失败（回退确定性文案）: %s", exc)
        return ""


# ─────────────────────────────────────────────────────────────────
# 兜底设计规范（确定性）
# ─────────────────────────────────────────────────────────────────

def _build_design_spec(presentation: dict, idea: str, brief: str) -> str:
    pages = presentation.get("pages") or []
    theme = presentation.get("theme") or {}
    lines = [
        "# 设计规范与内容大纲",
        "",
        f"## 产品：{idea}",
        f"- 主题：{theme.get('name', '默认主题')}（id={theme.get('id', 'default')}）",
        f"- 页数：{len(pages)} 页 · 画布：1280×720（PPT 16:9）",
        "",
        "## 设计简报",
        brief or "咨询风格：信息密度高、结论先行、黑白灰基底 + 单强调色（palette primary/accent）。",
        "",
        "## 逐页大纲",
    ]
    for i, page in enumerate(pages):
        comps = page.get("components") or []
        desc = "、".join(
            f"{c.get('type')}({', '.join(str(k) for k in (c.get('data') or {}).keys())[:40]})"
            for c in comps[:6]
        )
        lines.append(
            f"- P{i + 1:02d} [{page.get('type', 'content')}] {page.get('title', '')}："
            f"{page.get('insight', '')[:60]} ｜ 组件：{desc}"
        )
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────
# 兜底 spec_lock（被 _backfill_spec_lock 二次覆盖）
# ─────────────────────────────────────────────────────────────────

def _build_spec_lock(presentation: dict, idea: str) -> str:
    pages = presentation.get("pages") or []
    theme = presentation.get("theme") or {}
    palette = theme.get("palette") or {}
    default_p = {"bg": "#f8fafc", "surface": "#ffffff", "primary": "#4f46e5",
                 "accent": "#6366f1", "text": "#0f172a", "muted": "#64748b"}
    colors = {**default_p, **{k: v for k, v in palette.items() if v}}

    rhythm = "\n".join(
        f"- P{i + 1:02d}: {('anchor' if p.get('type') in ('cover', 'conclusion') else 'dense')}"
        for i, p in enumerate(pages)
    )
    # 预声明字号角色（Phase 1.3 字号白名单 — 与 cross_page.ALLOWED_FONT_SIZES 对齐）
    # 让 svg_quality_checker 在 spec_lock 阶段就认可所有合法字号
    type_roles = "\n".join(
        f"- role_{sz}: {sz}" for sz in (9, 10, 11, 12, 13, 14, 15, 16, 18, 20, 22, 26, 28, 32, 36, 44, 56, 68, 80)
    )
    return f"""<!-- ppt-master-schema: spec-lock/v1 -->
# Execution Lock

## canvas
- viewBox: 0 0 1280 720
- format: PPT 16:9

## communication
- primary_language: zh-CN
- audience: 决策者与产品团队
- objective: 完整传达产品论证（SCR）并驱动行动
- core_message: {str(presentation.get('title') or idea)[:80]}

## mode
- mode: custom

## visual_style
- visual_style: consulting-{theme.get('id', 'default')}

## colors
- bg: {colors['bg']}
- surface: {colors['surface']}
- primary: {colors['primary']}
- accent: {colors['accent']}
- text: {colors['text']}
- muted: {colors['muted']}

## typography
- font_family: {_FONT}
- title_family: {_TITLE_FONT}
- body_family: {_FONT}
- title: 26
- subtitle: 22
- body: 14
- caption: 11
- eyebrow: 13
- metric_value: 36
- display: 56
- font_size_recurrence_max: 30
# 预声明字号角色（任何 svg_output 出现的字号必须在以下角色中）:
{type_roles}

## icons
- library: none
- inventory: none

## image_rendering
- hero: full-bleed-overlay
- decoration: subtle
- page_thumbnail: corner

## page_rhythm
{rhythm}

## pptx_structure
- mode: flat

## forbidden
- `mask`, `<style>`, `class`, external CSS, `<foreignObject>`, `textPath`, `@font-face`, `<animate*>`, `<set>`, `<script>` / event attributes, `<iframe>`
"""


# ─────────────────────────────────────────────────────────────────
# spec_lock 自动反推（Phase 1.1 核心）
# ─────────────────────────────────────────────────────────────────

def _backfill_spec_lock(spec_lock_path: Path, svg_dir: Path, images_meta: dict | None = None) -> dict:
    """扫描 svg_output/ 实际产物，补全 spec_lock 的字号/渐变/装饰字段。

    这能消除 svg_quality_checker 报的"undeclared font-size 11 (157 occurrences)" ERROR
    —— LLM 实际用了 7+ 档字号，但 spec_lock 只声明了 2 档。

    Returns:
        backfill info dict（便于 diagnostics）
    """
    if not svg_dir.is_dir():
        return {"scanned": 0}

    info: dict[str, Any] = {"scanned": 0, "font_sizes": set(),
                             "gradient_ids": [], "pattern_ids": [],
                             "image_refs": [], "decorative_count": 0}

    for svg_file in sorted(svg_dir.glob("slide_*.svg")):
        try:
            content = svg_file.read_text(encoding="utf-8")
        except Exception:
            continue
        info["scanned"] += 1

        # 收集 font-size 使用
        for m in re.finditer(r'font-size="([\d.]+)"', content):
            try:
                info["font_sizes"].add(int(float(m.group(1))))
            except ValueError:
                pass

        # 收集 gradient / pattern id
        for m in re.finditer(r'<(?:linearGradient|radialGradient)\s+id="([^"]+)"', content):
            gid = m.group(1)
            if gid not in info["gradient_ids"]:
                info["gradient_ids"].append(gid)
        for m in re.finditer(r'<pattern\s+id="([^"]+)"', content):
            pid = m.group(1)
            if pid not in info["pattern_ids"]:
                info["pattern_ids"].append(pid)

        # 收集 image href（用于 image_rendering 字段）
        for m in re.finditer(r'<image[^>]*href="([^"]+)"', content):
            href = m.group(1)
            if not href.startswith("data:"):
                info["image_refs"].append(href)

        # 装饰元素计数（rect/line/circle/path/tspan 等）
        info["decorative_count"] += len(re.findall(
            r'<(?:rect|circle|ellipse|path|line|tspan|polygon|polyline)\b', content
        ))

    if not spec_lock_path.is_file():
        info["font_sizes"] = sorted(info["font_sizes"])
        return info

    # 读取现有 spec_lock，在尾部追加 backfill 段
    text = spec_lock_path.read_text(encoding="utf-8")
    sorted_sizes = sorted(info["font_sizes"])
    extra_lines = [
        "",
        "## auto-backfill (from svg_output scan)",
        f"- scanned_files: {info['scanned']}",
        f"- font_sizes_in_use: {sorted_sizes}",
        f"- gradient_ids: {info['gradient_ids'][:20]}",
        f"- pattern_ids: {info['pattern_ids'][:20]}",
        f"- image_refs: {info['image_refs'][:10]}",
        f"- decorative_element_count: {info['decorative_count']}",
        f"- font_size_recurrence_limit: {max(len(sorted_sizes) * 4, 30)}",  # generous
    ]
    if images_meta:
        extra_lines.append(f"- image_assets: {json.dumps(images_meta, ensure_ascii=False)[:600]}")

    new_text = text.rstrip() + "\n" + "\n".join(extra_lines) + "\n"
    spec_lock_path.write_text(new_text, encoding="utf-8")
    info["written"] = True
    return info


# ─────────────────────────────────────────────────────────────────
# MOD 独立 deck 封面（确定性，主 deck 主题色板）
# ─────────────────────────────────────────────────────────────────
def _mod_standalone_cover_svg(keyword: str, marketplace: str, fetched_at: str,
                              n_products: int, colors: dict) -> str:
    """MOD 独立 PPTX 封面：与主 deck 同主题的确定性咨询风封面。"""
    import html as _html

    def esc(s: str) -> str:
        return _html.escape(str(s or ""), quote=True)

    bg = colors.get("bg", "#F7F6F0")
    primary = colors.get("primary", "#12355B")
    accent = colors.get("accent", "#3D6491")
    text_c = colors.get("text", "#101820")
    muted = colors.get("muted", "#6F7275")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <rect width="1280" height="720" fill="{bg}"/>
  <rect x="0" y="0" width="1280" height="6" fill="{primary}"/>
  <rect x="90" y="150" width="64" height="6" fill="{accent}"/>
  <text x="90" y="130" font-size="13" letter-spacing="4" fill="{muted}" font-family="{_FONT}">AMAZON COMPETITOR MATRIX · MOD</text>
  <text x="90" y="240" font-size="52" font-weight="bold" fill="{text_c}" font-family="{_FONT}">竞品矩阵（MOD）</text>
  <text x="90" y="300" font-size="30" fill="{primary}" font-family="{_FONT}">{esc(keyword[:40])}</text>
  <rect x="90" y="360" width="1100" height="1" fill="{accent}" opacity="0.4"/>
  <text x="90" y="420" font-size="16" fill="{text_c}" font-family="{_FONT}">站点 {esc(marketplace)} ｜ 样本 {n_products} ASIN ｜ 抓取 {esc(fetched_at[:10])}</text>
  <text x="90" y="450" font-size="13" fill="{muted}" font-family="{_FONT}">价格带 × 月销 四区分析 · 参数对比 · SKU 渠道 · 评论洞察</text>
  <g data-pptx-bounds="90 600 1100 40">
    <rect x="90" y="600" width="1100" height="1" fill="{muted}" opacity="0.35"/>
    <text x="90" y="640" font-size="11" letter-spacing="2" fill="{muted}" font-family="{_FONT}">*Rainforest data · {esc(marketplace)}</text>
    <text x="1190" y="640" font-size="11" letter-spacing="2" fill="{muted}" text-anchor="end" font-family="{_FONT}">QX Product Studio</text>
  </g>
</svg>"""


# ─────────────────────────────────────────────────────────────────
# 主 Agent 类
# ─────────────────────────────────────────────────────────────────

class PptDesignAgent(BaseAgent):
    """PPT 设计成员：DSL → ppt-master 项目 → 原生可编辑 PPTX（v2）。"""

    name = "ppt_design_agent"
    description = "PPT 设计制作（ppt-master 工作流：设计规范 → 多维生图 → 逐页 SVG → svg_to_pptx）"
    output_schema = None  # 输出为 dict（不绑定 Pydantic Schema）

    def __init__(self, progress_callback=None):
        """progress_callback（P5）：接收 {node, status, detail} 进度事件；
        项目目录同步维护 progress.json 供前端 PPT 制作可视化面板轮询。"""
        super().__init__()
        self._progress_cb = progress_callback

    def _emit(self, status: str, detail: str = "", **extra) -> None:
        if self._progress_cb is None:
            return
        try:
            self._progress_cb({"node": "ppt_design", "status": status,
                               "detail": detail, **extra})
        except Exception:  # noqa: BLE001 —— 进度事件失败不影响制作
            pass

    @staticmethod
    def _write_progress(project_dir: Path, **fields) -> None:
        """合并更新项目目录 progress.json（PPT 制作可视化数据源）。"""
        import json as _json

        path = project_dir / "progress.json"
        data: dict = {}
        try:
            data = _json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        data.update(fields)
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        try:
            path.write_text(_json.dumps(data, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def execute(
        self,
        task: str,
        state: dict,
        memory=None,
        memory_namespace: str = "default",
    ) -> AgentResult:
        if task != "ppt_design":
            return AgentResult(success=False, error=f"未知任务: {task}")
        try:
            result = self._run(state)
            return AgentResult(success=True, data=result)
        except Exception as exc:  # noqa: BLE001
            logger.error("PptDesignAgent 执行失败: %s", exc, exc_info=True)
            return AgentResult(success=False, error=str(exc), data={"errors": [str(exc)]})

    # ── 主管线 ─────────────────────────────────────────────────
    def _run(self, state: dict) -> dict:
        from agents.ppt_design_agent import image_plan as _image_plan
        from agents.ppt_design_agent import cross_page as _cross_page

        presentation = state.get("presentation")
        if not presentation:
            raise RuntimeError("缺少 presentation（DSL）输入")
        idea = str(state.get("idea", ""))
        product_id = str(state.get("product_id") or idea)[:40]

        # 输出目录：OUTPUT_DIR > QX_OUTPUT_DIR（任务层桥接）> ./outputs（worker cwd）
        out_dir = Path(os.environ.get("OUTPUT_DIR")
                       or os.environ.get("QX_OUTPUT_DIR")
                       or "./outputs").resolve()
        base = out_dir / "studio_assets" / "ppt_projects"
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        project_dir = _get_reusable_project_dir(base, product_id)
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "sources").mkdir(exist_ok=True)
        (project_dir / "svg_output").mkdir(exist_ok=True)
        (project_dir / "notes").mkdir(exist_ok=True)

        theme = presentation.get("theme") or {}
        theme_name = str(theme.get("name", "咨询风"))
        accent_color = str((theme.get("palette") or {}).get("accent") or "#3D6491")

        # ── 0) 制作进度初始化（P5：progress.json + 事件流） ──
        total_pages = len(presentation.get("pages") or [])
        self._write_progress(
            project_dir, stage="spec", total=total_pages, done_pages=0,
            per_page={}, critic_score=state.get("critic_score"),
            revision_round=int(state.get("revision_count") or 0) + 1,
            pptx_url=None)
        self._emit("running", f"PPT 制作启动：{total_pages} 页规划")

        # ── 0b) 生图提前发射（耗时优化：manifest 仅依赖 DSL，
        #     与规范/简报创作并行；authoring 前 join，产物与串行一致） ──
        img_job = self._prepare_images_job(
            project_dir, presentation, idea, product_id,
            theme_name, accent_color, _image_plan)
        img_proc, img_job = self._launch_images_gen(img_job)
        if img_proc is not None:
            self._emit("running", "配图生成已启动（与设计规范创作并行）")

        # ── 1) 设计规范 + spec_lock（占位） ─────────────────────
        self._emit("running", "设计规范与 spec_lock 生成")
        spec = self._compose_design_spec(presentation, idea)
        lock = _build_spec_lock(presentation, idea)
        (project_dir / "设计规范与内容大纲.md").write_text(spec, encoding="utf-8")
        (project_dir / "spec_lock.md").write_text(lock, encoding="utf-8")
        (project_dir / "notes" / "total.md").write_text(
            f"# 页面注释\n\n{spec}\n", encoding="utf-8"
        )

        # ── 2) 设计简报（LLM 可选） ─────────────────────────────
        brief = _design_brief_llm(
            idea, theme_name, len(presentation.get("pages") or [])
        )

        # ── 3) 生图收集（子进程已在后台生成，此处等待+同步 Design Studio） ──
        self._write_progress(project_dir, stage="images")
        self._emit("running", "配图收集（已与规范创作并行）")
        images = self._collect_images(
            img_job, img_proc, out_dir, product_id, _image_plan)

        # ── 3b) MOD 章节图表资产同步（B/C 共享数据层 → 项目 images/） ──
        # 确定性图表（品牌环形/矩阵散点/参数矩阵/SKU 结构/hero 主图）以图片
        # 组件参与页面排版（_pick_page_image 按 mod_* 页型对位注入）
        mod_assets = self._sync_mod_chart_assets(
            project_dir=project_dir, state=state, out_dir=out_dir, images=images,
        )

        # ── 4) 逐页 SVG（MiniMax 按 skill 创作 + 程序化注入图片/页脚/根属性） ──
        self._write_progress(project_dir, stage="authoring")
        self._emit("running", f"逐页 SVG 创作（{total_pages} 页，含质量门禁返工）")
        identity = _cross_page.DeckIdentity(
            product_name=idea[:32] or product_id[:32],
            product_code=ts[:6].replace("_", "."),  # YYYYMM
            theme_color=accent_color,
            muted_color=str((theme.get("palette") or {}).get("muted") or "#6F7275"),
            text_color=str((theme.get("palette") or {}).get("text") or "#111111"),
            bg_color=str((theme.get("palette") or {}).get("bg") or "#F7F6F0"),
        )
        files, svg_stats = self._author_pages_v2(
            project_dir=project_dir,
            presentation=presentation,
            theme=theme,
            design_spec=spec,
            images=images,
            identity=identity,
            cross_page_module=_cross_page,
        )

        # ── 5) spec_lock 自动反推（消除 svg_quality_checker ERROR） ──
        try:
            backfill = _backfill_spec_lock(
                project_dir / "spec_lock.md",
                project_dir / "svg_output",
                images_meta={"asset_dir": images.get("asset_dir"),
                              "assets_count": len(images.get("list") or []),
                              "by_kind": images.get("by_kind")},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("spec_lock 反推失败: %s", exc)
            backfill = {"error": str(exc)}

        # ── 6) finalize + svg_to_pptx ───────────────────────────
        # 导出一致性门：svg_output 页数必须与 DSL 页数一致（跨运行遗留/
        # 清理异常会混装；曾出现 16+17 两代共 30 页的成品 deck）
        _n_svg = len(list((project_dir / "svg_output").glob("slide_*.svg")))
        if _n_svg != total_pages:
            raise RuntimeError(
                f"导出一致性门失败：svg_output {_n_svg} 页 != DSL {total_pages} 页"
                "（疑似跨运行遗留文件混入）")
        self._write_progress(project_dir, stage="finalizing")
        self._emit("running", "finalize + 转换 PPTX")
        # P1 耗时优化：vendor 转换器进程内调用（省 3-4 次解释器启动 ≈ 10-15s/deck）
        from agents.ppt_design_agent import vendor_bridge

        rc, tail = vendor_bridge.run_finalize(str(project_dir))
        if rc != 0:
            raise RuntimeError(f"finalize_svg.py 失败: {tail}")
        rc, tail = vendor_bridge.run_svg_to_pptx([str(project_dir), "-s", "final"])
        if rc != 0:
            raise RuntimeError(f"svg_to_pptx.py 失败: {tail}")

        pptx_candidates = list((project_dir / "exports").glob("*.pptx")) if (project_dir / "exports").is_dir() else []
        if pptx_candidates:
            # 节点重试复用同一目录时可能保留多个 PPTX，必须返回本轮最新产物。
            pptx_path = max(pptx_candidates, key=lambda path: path.stat().st_mtime)
        else:
            root_candidates = list(project_dir.glob("*.pptx"))
            pptx_path = max(root_candidates, key=lambda path: path.stat().st_mtime) if root_candidates else None
        if pptx_path is None:
            raise RuntimeError("svg_to_pptx 未产出 PPTX 文件")

        # ── 6b) MOD 独立 PPTX 双产出：MOD 章节页 + 专用封面 → 独立导出 ──
        # 单一制作双产出（与主 deck 同源数据/同主题/同 authoring 质量）
        self._write_progress(project_dir, stage="mod_export")
        self._emit("running", "MOD 独立 PPTX 导出")
        mod_standalone = self._export_mod_standalone(
            project_dir=project_dir, state=state, out_dir=out_dir, theme=theme,
        )

        # ── 7) 模型记录 ────────────────────────────────────────
        try:
            model = get_presentation_llm_client().model if get_presentation_llm_client() else get_llm_client().model
        except Exception:
            model = "deterministic"

        reveal_html = self._export_reveal_html(project_dir, str(pkg_idea := presentation.get("title") or idea))
        self._write_progress(project_dir, stage="done", pptx_url=str(pptx_path))
        self._emit("completed", f"PPT 制作完成：{len(files)} 页 → {pptx_path.name}")

        return {
            "project_dir": str(project_dir),
            "pptx_path": str(pptx_path),
            "pptx_relative": str(pptx_path.relative_to(out_dir)) if pptx_path else None,
            "pages": len(presentation.get("pages") or []),
            "svg_files": files,
            "model": model,
            "design_brief": brief,
            # ── 图片资产（Design Studio 入口） ──
            "images": images.get("list", []),         # [{name, url, size, asset_kind, ...}, ...]
            "image_by_kind": images.get("by_kind") or {},
            "asset_dir": images.get("asset_dir"),      # outputs/assets/{product_id}/
            "hero_image": images.get("hero"),          # svg_ref: images/hero.png
            # ── 元信息 ──
            "svg_stats": svg_stats,
            "spec_lock_backfill": backfill,
            "mod_chart_assets": mod_assets,
            "mod_standalone": mod_standalone,
            "reveal_html": reveal_html,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }



    # ── reveal.js 网页 deck 导出（P1 多格式出口） ──
    @staticmethod
    def _export_reveal_html(project_dir: Path, title: str) -> str | None:
        """svg_final/*.svg → exports/deck.html（reveal.js，CDN 引用，离线降级为纵向滚动）。"""
        import html as _html
        svg_dir = project_dir / "svg_final"
        svgs = sorted(svg_dir.glob("slide_*.svg")) if svg_dir.is_dir() else []
        if not svgs:
            return None
        try:
            sections = "\n".join(
                f'<section><div class="svg-wrap">{svg.read_text(encoding="utf-8")}</div></section>'
                for svg in svgs)
            html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>{_html.escape(title)}</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@5/dist/reveal.css">
<style>body{{margin:0;background:#F7F6F0}}
.svg-wrap svg{{width:100%;height:auto;display:block}}
.reveal .slides{{text-align:left}}</style>
</head><body>
<div class="reveal"><div class="slides">{sections}</div></div>
<script src="https://cdn.jsdelivr.net/npm/reveal.js@5/dist/reveal.js"></script>
<script>try{{Reveal.initialize({{hash:true, embedded:false}})}}catch(e){{/* 离线时保持纵向滚动 */}}</script>
</body></html>"""
            out = project_dir / "exports" / "deck.html"
            out.parent.mkdir(exist_ok=True)
            out.write_text(html_doc, encoding="utf-8")
            return str(out)
        except Exception:  # noqa: BLE001 —— 增强出口失败不影响主产物
            return None

    # ── MOD 章节图表资产同步（共享数据层 → 项目 images/） ──
    @staticmethod
    def _sync_mod_chart_assets(project_dir: Path, state: dict, out_dir: Path,
                               images: dict) -> dict:
        """把 MOD 确定性图表（charts/）与 hero 主图复制进项目 images/，
        并注册到 images.by_kind 供 _pick_page_image 按 mod_* 页型对位注入。

        - 来源：studio_assets/{product_id}/competitor_matrix/{charts/,matrix_chart.*,data/image_cache}
        - kind 对位：mod_overview←market_donut · mod_matrix←matrix_scatter ·
          mod_spec_comparison←spec_matrix · mod_sku_analysis←sku_channels ·
          mod_hero←Top1 ASIN 主图缓存
        任何失败仅跳过（增强层，不阻塞页面生产）。
        """
        import shutil

        synced: dict[str, str] = {}
        try:
            matrix = state.get("competitor_matrix") or {}
            if not matrix:
                return synced
            arts = matrix.get("artifacts_paths") or {}
            mod_rel = arts.get("charts") or ""
            if not mod_rel:
                return synced
            charts_root = Path(mod_rel)
            if not charts_root.is_absolute():
                charts_root = out_dir / mod_rel
            if not charts_root.is_dir():
                return synced
            image_dir = project_dir / "images"
            image_dir.mkdir(exist_ok=True)
            # mod_matrix 首选真·产品矩阵图（MOD 根目录 matrix_chart.png：竞品主图
            # 缩略图 + 防重叠引擎 + P25-P75 带，参考 deck 的核心视觉）；
            # charts/matrix_scatter（无主图简化版）仅作其缺失时的次选
            priority = {
                "mod_matrix": ("__root_matrix_chart__", "matrix_scatter"),
                "mod_overview": ("market_donut", "zone_grid", "price_bands", "demand_bars"),
                "mod_spec_comparison": ("spec_matrix",),
                "mod_sku_analysis": ("sku_channels",),
            }
            index = matrix.get("mod_charts") or {}
            for kind, names in priority.items():
                for name in names:
                    if name == "__root_matrix_chart__":
                        root_png = charts_root.parent / "matrix_chart.png"
                        if not root_png.is_file():
                            continue
                        dst = image_dir / "mod_chart_matrix.png"
                        shutil.copyfile(root_png, dst)
                        synced[kind] = f"images/{dst.name}"
                        break
                    entry = index.get(name) or {}
                    rel = entry.get("png") or entry.get("svg")
                    if not rel:
                        continue
                    src = charts_root / Path(rel).name
                    if not src.is_file():
                        continue
                    ext = src.suffix.lower()
                    dst = image_dir / f"mod_chart_{name}{ext}"
                    shutil.copyfile(src, dst)
                    synced[kind] = f"images/{dst.name}"
                    break
            # mod_matrix 兜底：核心矩阵图（旧逻辑保留，双保险）
            if "mod_matrix" not in synced:
                mm = charts_root.parent / "matrix_chart.png"
                if mm.is_file():
                    dst = image_dir / "mod_chart_matrix.png"
                    shutil.copyfile(mm, dst)
                    synced["mod_matrix"] = f"images/{dst.name}"
            # mod_hero：Top1 销量 ASIN 主图缓存
            products = matrix.get("products") or []
            hero = sorted(products, key=lambda p: -(p.get("est_monthly_sales") or 0))
            data_dir = charts_root.parent / "data" / "image_cache"
            for p in hero[:3]:
                cand = data_dir / f"{p.get('asin')}.jpg"
                if cand.is_file():
                    dst = image_dir / "mod_hero.jpg"
                    shutil.copyfile(cand, dst)
                    synced["mod_hero"] = f"images/{dst.name}"
                    break
            if synced:
                images.setdefault("by_kind", {}).update(synced)
                logger.info("[ppt_design] MOD 图表资产同步 %s", list(synced))
        except Exception as exc:  # noqa: BLE001 —— 同步失败不阻塞
            logger.warning("[ppt_design] MOD 图表资产同步失败（跳过）: %s", str(exc)[:200])
        return synced

    # ── MOD 独立 PPTX 双产出（MOD 章节页 + 专用封面 → 独立导出） ──
    @staticmethod
    def _export_mod_standalone(project_dir: Path, state: dict, out_dir: Path,
                               theme: dict) -> dict:
        """主 deck 的 MOD 章节页复制 + 专用封面 → 独立 competitor_matrix.pptx。

        - 与主 deck 同源数据/同主题/同 authoring 质量（单一制作双产出）
        - 页脚重编号（NN/独立总数），根属性同步
        - 失败降级：返回原因，不影响主 PPTX
        """
        import shutil

        empty = {"exported": False, "pages": 0}
        product_id = str(state.get("product_id") or "")
        if not product_id or not state.get("competitor_matrix"):
            return empty
        svg_dir = project_dir / "svg_output"
        mod_files = sorted(
            [f for f in svg_dir.glob("slide_*.svg")
             if re.search(r"slide_\d+_mod_", f.name)],
            key=lambda f: int(re.search(r"slide_(\d+)", f.name).group(1)),
        )
        if not mod_files:
            return {**empty, "reason": "主 deck 无 MOD 章节页"}
        try:
            mod_out = out_dir / "studio_assets" / product_id / "competitor_matrix"
            standalone = mod_out / "ppt_standalone"
            st_svg = standalone / "svg_output"
            st_svg.mkdir(parents=True, exist_ok=True)
            lock_src = project_dir / "spec_lock.md"
            if lock_src.is_file():
                shutil.copyfile(lock_src, standalone / "spec_lock.md")

            matrix = state.get("competitor_matrix") or {}
            palette = (theme or {}).get("palette") or {}
            colors = {"bg": "#F7F6F0", "surface": "#FFFFFF", "primary": "#12355B",
                      "accent": "#3D6491", "text": "#101820", "muted": "#6F7275"}
            colors.update({k: v for k, v in palette.items() if v})
            cover = _mod_standalone_cover_svg(
                keyword=str(matrix.get("keyword") or state.get("idea") or ""),
                marketplace=str(matrix.get("marketplace") or "amazon.com"),
                fetched_at=str(matrix.get("fetched_at") or ""),
                n_products=len(matrix.get("products") or []),
                colors=colors,
            )
            (st_svg / "slide_00_cover.svg").write_text(cover, encoding="utf-8")

            # 主项目 images/ 一并复制（页面 SVG 以相对路径引用
            # images/mod_chart_* 等，finalize 需在同目录结构下解析）
            src_images = project_dir / "images"
            if src_images.is_dir():
                shutil.copytree(src_images, standalone / "images",
                                dirs_exist_ok=True)

            total = len(mod_files) + 1  # 封面 + MOD 页
            for i, src in enumerate(mod_files, start=1):
                text_content = src.read_text(encoding="utf-8")
                # 页脚/根属性重编号：主 deck 的 NN/MM → 独立 deck 的 i/total
                text_content = re.sub(r"— \d{2} / \d{2} —", f"— {i:02d} / {total:02d} —",
                                      text_content)
                text_content = re.sub(
                    r'data-pptx-page-index="\d+"', f'data-pptx-page-index="{i}"',
                    text_content)
                text_content = re.sub(
                    r'data-pptx-page-total="\d+"', f'data-pptx-page-total="{total}"',
                    text_content)
                dst = st_svg / f"slide_{i:02d}_{src.name.split('_', 2)[2]}"
                dst.write_text(text_content, encoding="utf-8")

            from agents.ppt_design_agent import vendor_bridge

            rc, tail = vendor_bridge.run_finalize(str(standalone))
            if rc != 0:
                raise RuntimeError(f"finalize_svg.py 失败: {tail}")
            rc, tail = vendor_bridge.run_svg_to_pptx(
                [str(standalone), "-s", "final",
                 "-o", str(mod_out / "compet_matrix_tmp.pptx")])
            if rc != 0:
                raise RuntimeError(f"svg_to_pptx.py 失败: {tail}")
            final_pptx = mod_out / "competitor_matrix.pptx"
            if (mod_out / "compet_matrix_tmp.pptx").is_file():
                shutil.move(str(mod_out / "compet_matrix_tmp.pptx"), str(final_pptx))
            elif (standalone / "exports").is_dir():
                cands = list((standalone / "exports").glob("*.pptx"))
                if cands:
                    shutil.move(str(max(cands, key=lambda p: p.stat().st_mtime)),
                                str(final_pptx))
            if not final_pptx.is_file():
                raise RuntimeError("独立导出未产出 PPTX")

            logger.info("[ppt_design] MOD 独立 PPTX 导出 %d+%d 封面 → %s",
                        len(mod_files), 1, final_pptx)
            return {"exported": True, "pages": len(mod_files) + 1,
                    "pptx": str(final_pptx)}
        except Exception as exc:  # noqa: BLE001 —— 独立导出失败不影响主 PPT
            logger.warning("[ppt_design] MOD 独立 PPTX 导出失败（降级）: %s", str(exc)[:200])
            return {**empty, "reason": str(exc)[:200]}

    # ── 设计规范（MiniMax 自由创作；确定性兜底） ──────────────
    _SPEC_SYSTEM = (
        "你是咨询风演示设计总监（ppt-master Strategist）。根据产品信息与页面清单，"
        "输出《设计规范与内容大纲》：1) 设计简报（受众/叙事基调/视觉语气，120 字内）；"
        "2) 视觉方向（构图节奏/卡片语言/图表风格/留白策略，150 字内）；"
        "3) 逐页大纲（每页：页面目标 + 设计要点，每页一行）。直接输出正文，不要格式标记。"
    )

    def _compose_design_spec(self, presentation: dict, idea: str) -> str:
        try:
            llm = get_presentation_llm_client() or get_llm_client()
            if llm is None or not llm.api_key:
                raise RuntimeError("无 LLM")
            pages = presentation.get("pages") or []
            outline = "\n".join(
                f"- P{i + 1:02d} [{p.get('type', 'content')}] {str(p.get('title') or '')[:40]}"
                for i, p in enumerate(pages)
            )
            user = (
                f"产品：{idea}\n页数：{len(pages)}\n逐页清单：\n{outline}\n"
                f"主题：{(presentation.get('theme') or {}).get('name', '咨询风')}"
            )
            spec = (llm.complete(
                [{"role": "system", "content": self._SPEC_SYSTEM},
                 {"role": "user", "content": user}],
                temperature=0.5, max_tokens=900,
            ) or "").strip()
            if len(spec) > 60:
                return spec[:1800]
        except Exception as exc:  # noqa: BLE001
            logger.warning("设计规范创作失败（回退大纲）: %s", exc)
        return _build_design_spec(presentation, idea, "")

    # ── 逐页 SVG（v2：程序化注入图片 + 页脚 + 根属性 + 字号收敛） ──
    # 并发策略（v2.1）：batch 自适应（参照 image_gen._run_manifest）——
    #   · LLM 创作 + 校验在 worker 线程并发（唯一耗时部分）；
    #     程序化后处理 / 写盘 / stats 聚合全部在主线程（确定性、无需加锁）
    #   · 瞬时限流（HTTP 429）→ 页面重排队 + 减半并发 + 暂停；
    #     预算耗尽或并发 1 仍限流 → 该页 fallback
    #   · 配额型限流（MiniMax Token Plan 2056 等）→ 立即 fallback，不浪费请求
    #   · 结果按 slide_NN 排序返回；与顺序版输出逐字节一致（质量回归由测试保证）
    def _author_pages_v2(
        self,
        project_dir: Path,
        presentation: dict,
        theme: dict,
        design_spec: str,
        images: dict,
        identity: Any,
        cross_page_module: Any,
    ) -> tuple[list[str], dict]:
        from agents.ppt_design_agent import svg_author
        from agents.ppt_design_agent import svg_qa

        svg_dir = project_dir / "svg_output"
        svg_dir.mkdir(exist_ok=True)
        # 跨运行/节点重试遗留清理：project_dir 按产品复用，每轮全量重画；
        # 旧 slide 文件不清理会被导出器全量打包（曾致新旧两代 30 页混装）。
        # finalize_svg 以 svg_output 为源原子重建 svg_final，清这里即足够。
        for _old in svg_dir.glob("slide_*.svg"):
            _old.unlink()
        pages = presentation.get("pages") or []
        llm = get_presentation_llm_client() or get_llm_client()
        files: list[str] = []
        stats: dict = {"retries": 0, "fallbacks": 0, "per_page": {},
                        "images_injected": 0, "footers_injected": 0,
                        "root_metadata_injected": 0, "font_sizes_snapped": 0,
                        "qa_reworks": 0, "qa_warnings": {}}
        total = len(pages)
        if total == 0:
            return files, stats

        # ── 并发参数（env 可配：AGENT_PLATFORM_PPT_DESIGN_*；1 = 纯顺序） ──
        _settings = get_settings()
        initial = max(
            1, min(_settings.PPT_DESIGN_CONCURRENCY,
                   _settings.PPT_DESIGN_CONCURRENCY_MAX, total)
        )
        pause_sec = _settings.PPT_DESIGN_RATE_PAUSE
        current = initial
        rate_limit_attempts: dict[int, int] = {}
        page_retries: dict[int, int] = {}
        qa_attempts: dict[int, int] = {}
        qa_feedback: dict[int, str] = {}

        def _page_img_assets(page: dict, page_index: int) -> dict:
            return {
                "hero": images.get("hero"),
                "pages": images.get("pages") or {},
                "by_kind": images.get("by_kind") or {},
                "page_image": self._pick_page_image(page, page_index, images),
            }

        def _author_one(idx: int) -> tuple[str | None, str, int, dict]:
            """worker 线程：LLM 创作 + 校验循环（唯一耗时部分）。

            Returns: (svg | None, status, retries, img_assets)
              status: "llm" | "fallback_needed" | "rate_limited" | "quota_limited"
            """
            page = pages[idx]
            img_assets = _page_img_assets(page, idx)
            svg = ""
            retries = 0
            _tn = threading.current_thread().name
            if llm is not None and llm.api_key:
                contract_feedback = ""
                for attempt in range(_PPT_SVG_MAX_PAGE_ATTEMPTS):
                    prompt = svg_author.build_page_prompt(page, theme, design_spec, idx, img_assets)
                    if contract_feedback:
                        prompt += f"\n\n上一次 SVG 转换契约失败，请修正：{contract_feedback}"
                    if idx in qa_feedback:
                        prompt += (f"\n\n上一版未通过确定性质量门禁（对照高质量参考基线），"
                                   f"必须逐条修正后再输出：{qa_feedback[idx]}")
                    try:
                        raw = llm.complete(
                            [{"role": "system", "content": "你是资深咨询风演示 SVG 设计师。只输出 SVG。"},
                             {"role": "user", "content": prompt}],
                            temperature=0.6, max_tokens=16384,  # 提升到 16K 让 LLM 画更复杂
                        ) or ""
                    except LLMError as exc:
                        kind = classify_llm_error(exc)
                        if kind == "rate_limit_transient":
                            # 瞬时限流：不消耗页面尝试次数，交给主线程重排队
                            return None, "rate_limited", retries, img_assets
                        if kind == "rate_limit_quota":
                            # 配额耗尽（Token Plan）：重试无意义，立即 fallback
                            logger.warning("[%s] P%d 配额耗尽（%s），直接 fallback",
                                           _tn, idx + 1, str(exc)[:120])
                            return None, "quota_limited", retries, img_assets
                        logger.warning("[%s] P%d SVG 调用失败: %s",
                                       _tn, idx + 1, str(exc)[:120])
                        continue
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("[%s] P%d SVG 调用失败: %s",
                                       _tn, idx + 1, str(exc)[:120])
                        continue
                    svg = svg_author.extract_svg(raw)
                    ok, issue = svg_author.validate_svg(svg, page)
                    if ok:
                        svg = svg_author.sanitize_svg(svg)
                        native_ok, native_issue = svg_author.validate_native_contract(svg)
                        if not native_ok:
                            ok = False
                            issue = native_issue
                        else:
                            break
                    retries += 1
                    contract_feedback = issue
                    logger.warning("[%s] P%d SVG 校验失败（第 %d 次）: %s",
                                   _tn, idx + 1, attempt + 1, issue)
                    svg = ""
            if not svg:
                return None, "fallback_needed", retries, img_assets
            return svg, "llm", retries, img_assets

        def _finalize(idx: int, svg: str | None, status: str, img_assets: dict) -> tuple[bool, list[str]]:
            """主线程：程序化后处理 + 质量门禁 + 写盘 + stats 聚合（确定性、无锁）。

            Returns: (written, qa_issues)
              written=False 表示 QA 不达标且重做预算可用——不落盘，
              由主循环重排队带反馈重渲染（硬门禁+返工一次）。
            """
            page = pages[idx]
            page_no = idx + 1
            name = f"slide_{page_no:02d}_{page.get('type', 'page')}.svg"
            stats["retries"] += page_retries.get(idx, 0)
            if status != "llm":
                stats["fallbacks"] += 1
                svg = svg_author.fallback_svg(page, theme)

            # ── b) 后处理（程序化注入，不依赖 LLM） ──
            svg = svg_author.sanitize_svg(svg)
            page_image = img_assets["page_image"]
            svg = svg_author.inject_page_image(svg, page_image, page)
            stats["images_injected"] += 1 if page_image and "<image" in svg else 0

            # ── c) 跨页一致性（footer + 根属性） ──
            svg = cross_page_module.inject_root_metadata(svg, page.get("type", "content"), idx, total)
            stats["root_metadata_injected"] += 1
            if page.get("type") != "cover":  # 封面不放 footer
                svg = cross_page_module.inject_footer(svg, idx, total, identity)
                stats["footers_injected"] += 1

            # ── d) 字号白名单收敛（P1：Rust 内核可选开关） ──
            from agents.ppt_design_agent import svg_kernels

            svg, snap_info = svg_kernels.snap(svg, tuple())
            stats["font_sizes_snapped"] += len(snap_info.get("snapped", [])) or int(
                snap_info.get("snap_count_rust", 0))

            # ── e) 确定性质量门禁（对照 svg_final 参考基线） ──
            qa_issues: list[str] = []
            if status == "llm":
                qa_issues = svg_qa.qa_page(svg, page, theme, page_image)
                if qa_issues and qa_attempts.get(idx, 0) < 1:
                    qa_attempts[idx] = qa_attempts.get(idx, 0) + 1
                    stats["qa_reworks"] += 1
                    return False, qa_issues  # 重排队（带反馈）
                # 硬性失败（信息密度/视觉结构/占位）：重做预算耗尽也不放行
                # ——曾出现仅含"timeline"占位词的空图表页带警告混入成品。
                # 降级为确定性兜底版式并重走注入链，保证页面非空可读。
                if qa_issues and any(svg_qa.is_hard_issue(i) for i in qa_issues):
                    logger.warning(
                        "[finalize] P%d 重做耗尽仍硬性不达标（%s），降级兜底版式",
                        page_no, "; ".join(qa_issues[:3]))
                    status = "fallback"
                    stats["fallbacks"] += 1
                    svg = svg_author.fallback_svg(page, theme)
                    svg = svg_author.sanitize_svg(svg)
                    svg = svg_author.inject_page_image(svg, page_image, page)
                    svg = cross_page_module.inject_root_metadata(
                        svg, page.get("type", "content"), idx, total)
                    if page.get("type") != "cover":
                        svg = cross_page_module.inject_footer(svg, idx, total, identity)
                    svg, _ = cross_page_module.snap_font_sizes(svg)
                    qa_issues = []

            (svg_dir / name).write_text(svg, encoding="utf-8")
            if name in files:
                files.remove(name)  # 用户返工重写同名页：去重计数
            files.append(name)
            qa_feedback.pop(idx, None)  # 重做成功，清除反馈
            if qa_issues:
                stats["qa_warnings"][page_no] = qa_issues
            stats["per_page"][page_no] = {
                "status": status,
                "page_image": page_image,
                "font_sizes": snap_info.get("kept_unique", []),
                "snap_count": len(snap_info["snapped"]),
                "qa_issues": qa_issues,
            }
            # P5：逐页进度（progress.json + 事件流，前端缩略图流式填充）
            try:
                progress_state = {}
                import json as _json
                _pp = project_dir / "progress.json"
                try:
                    progress_state = _json.loads(_pp.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    progress_state = {}
                per_page = dict(progress_state.get("per_page") or {})
                per_page[str(page_no)] = status
                self._write_progress(project_dir, done_pages=len(files),
                                     per_page=per_page)
                self._emit("running", f"P{page_no:02d}/{total} 完成（{status}）")
            except Exception:  # noqa: BLE001 —— 进度更新失败不影响制作
                pass
            return True, qa_issues

        # ── batch 自适应并发主循环（参照 image_gen._run_manifest） ──
        _tn = threading.current_thread().name
        queue: list[int] = list(range(total))

        def _consume_user_rework() -> None:
            """P0.5：批次间消费用户👎返工请求（progress.json.rework_requests），
            对该页重新入队并携带反馈（走既有 qa_feedback 返工通道）。"""
            try:
                import json as _json
                _pp = project_dir / "progress.json"
                _prog = _json.loads(_pp.read_text(encoding="utf-8"))
                _reqs = _prog.get("rework_requests") or []
                if not _reqs:
                    return
                _prog["rework_requests"] = []
                _pp.write_text(_json.dumps(_prog, ensure_ascii=False), encoding="utf-8")
                for _req in _reqs:
                    _idx = int(_req.get("page_index", -1))
                    if 0 <= _idx < total:
                        qa_feedback[_idx] = str(_req.get("feedback") or "用户要求改进")
                        if _idx not in queue:
                            queue.append(_idx)
                            stats["qa_reworks"] += 1
                        self._emit("running", f"P{_idx + 1:02d} 收到用户返工请求，已重新排队")
                        logger.info("[ppt_design] P%d 用户返工请求入队: %s",
                                    _idx + 1, str(_req.get("feedback"))[:80])
            except Exception:  # noqa: BLE001 —— 消费失败不影响主循环
                pass

        while queue:
            _consume_user_rework()
            batch_size = min(current, len(queue))
            batch = queue[:batch_size]
            queue = queue[batch_size:]
            rate_limited = False
            with ThreadPoolExecutor(max_workers=batch_size) as ex:
                futures = {ex.submit(_author_one, idx): idx for idx in batch}
                for fut in as_completed(futures):
                    idx = futures[fut]
                    page_no = idx + 1
                    svg, status, retries, img_assets = fut.result()
                    page_retries[idx] = page_retries.get(idx, 0) + retries
                    if status == "rate_limited":
                        rate_limited = True
                        attempts = rate_limit_attempts.get(idx, 0) + 1
                        rate_limit_attempts[idx] = attempts
                        if current > 1 and attempts < _PPT_SVG_MAX_RATE_LIMIT_ATTEMPTS:
                            queue.append(idx)
                            logger.warning("[%s] P%d 瞬时限流，重排队（第 %d 次）",
                                           _tn, page_no, attempts)
                        else:
                            logger.warning("[%s] P%d 限流持久（并发 %d / 重试 %d 次），fallback",
                                           _tn, page_no, current, attempts)
                            _finalize(idx, None, "fallback", img_assets)
                    elif status == "quota_limited":
                        _finalize(idx, None, "fallback", img_assets)
                    elif status == "fallback_needed":
                        _finalize(idx, None, "fallback", img_assets)
                    else:
                        written, issues = _finalize(idx, svg, "llm", img_assets)
                        if not written:
                            # 质量门禁未达标：带反馈重排队（硬门禁+返工一次）
                            qa_feedback[idx] = svg_qa.qa_feedback_text(issues)
                            queue.append(idx)
                            logger.warning("[%s] P%d 质量门禁未达标，重排队：%s",
                                           _tn, page_no, qa_feedback[idx][:120])

            if rate_limited and current > 1 and queue:
                new_current = max(1, current // 2)
                logger.warning("[%s] 限流：并发 %d → %d，暂停 %ds",
                               _tn, current, new_current, pause_sec)
                current = new_current
                time.sleep(pause_sec)
            elif queue and current > 1:
                # batch 间温和节流（并发 1 = 顺序模式，不加间隔，与原顺序版行为一致）
                time.sleep(_PPT_SVG_BATCH_GAP_SEC)

        # 结果按页码排序（PPTX 组装本身按文件名排序，此处保证返回列表有序）
        files.sort(key=lambda f: int(re.search(r"slide_(\d+)", f).group(1)))
        return files, stats

    # ── 辅助：按页选图 ─────────────────────────────────────
    def _pick_page_image(self, page: dict, page_index: int, images: dict) -> str | None:
        """根据 page.type 和 by_kind 字典，选最合适的图片 SVG 引用。"""
        by_kind = images.get("by_kind") or {}
        if not by_kind:
            return None
        # 优先：按 page_type 映射
        from agents.ppt_design_agent import image_plan as _image_plan
        return _image_plan.select_image_for_page(page, page_index, by_kind)

    # ── 生图阶段（v2：聚焦产品架构 + 设计 + Design Studio 入库） ──
    # 优化：拆为 准备(manifest) / 发射(subprocess) / 收集(等待+同步) 三段，
    # 供 _run 与 spec/brief 创作并行（manifest 仅依赖 DSL，不依赖规范文本）。
    _IMAGES_EMPTY = {"hero": None, "pages": {}, "by_kind": {}, "list": [],
                     "asset_dir": "", "manifest": None}

    def _prepare_images_job(
        self, project_dir: Path, presentation: dict, idea: str, product_id: str,
        theme_name: str, accent_color: str, image_plan_module: Any,
    ) -> dict | None:
        """生图准备：manifest 构建 + 落盘 + 缓存判定（无网络/无子进程）。失败返回 None。"""
        image_dir = project_dir / "images"
        image_dir.mkdir(exist_ok=True)
        try:
            manifest = image_plan_module.build_image_manifest(
                presentation=presentation, idea=idea, product_id=product_id,
                theme_name=theme_name, accent_color=accent_color, max_pages=10,
            )
            items = manifest.get("items") or []
        except Exception as exc:  # noqa: BLE001
            logger.warning("生图 manifest 构建失败: %s", exc)
            return None

        manifest_path = image_dir / "image_prompts.json"
        fingerprint = hashlib.sha256(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        cache_path = image_dir / ".image_cache.json"
        cache_hit = False
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
            expected = [str(item.get("filename")) for item in items if item.get("filename")]
            cache_hit = (
                cache.get("fingerprint") == fingerprint
                and cache.get("files") == expected
                and all((image_dir / name).is_file() for name in expected)
            )
        except (OSError, json.JSONDecodeError):
            pass

        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
        try:
            sidecar = [f"- **{it['filename']}** ({it.get('asset_kind', '?')}): {it['prompt']}"
                       for it in items]
            (image_dir / "image_prompts.md").write_text(
                f"# {idea} 图片 Prompt 清单\n\n" + "\n".join(sidecar) + "\n",
                encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
        return {"image_dir": image_dir, "manifest": manifest, "items": items,
                "fingerprint": fingerprint, "cache_hit": cache_hit,
                "manifest_path": manifest_path, "cache_path": cache_path,
                "launched_at": None}

    @staticmethod
    def _launch_images_gen(job: dict | None) -> tuple:
        """发射 image_gen.py 子进程（缓存命中/无 job → proc=None）。返回 (proc, job)。"""
        import time as _time

        if not job:
            return None, None
        if job.get("cache_hit"):
            logger.info("生图缓存命中，跳过 image_gen.py | fingerprint=%s",
                        str(job.get("fingerprint"))[:12])
            return None, job
        try:
            # cwd 继承工作目录（backend）：image_gen 需读取 backend/.env 的
            # IMAGE_BACKEND/MINIMAX_API_KEY（vendor scripts 目录无 .env）
            proc = subprocess.Popen(
                [sys.executable, str(_SCRIPTS_DIR / "image_gen.py"),
                 "--manifest", str(job["manifest_path"]), "-o", str(job["image_dir"])],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            job["launched_at"] = _time.monotonic()
            return proc, job
        except Exception as exc:  # noqa: BLE001
            logger.warning("生图发射异常: %s", exc)
            return None, job

    def _collect_images(self, job: dict | None, proc, out_dir: Path,
                        product_id: str, image_plan_module: Any) -> dict:
        """收集生图结果：等待子进程（预算自发射起 900s）→ 写缓存 → 同步 Design Studio。"""
        empty = dict(self._IMAGES_EMPTY)
        if not job:
            return empty
        items = job.get("items") or []
        image_dir = job["image_dir"]
        if proc is not None:
            import time as _time
            elapsed = _time.monotonic() - (job.get("launched_at") or _time.monotonic())
            budget = max(60.0, 900.0 - elapsed)
            try:
                _out, err = proc.communicate(timeout=budget)
                if proc.returncode != 0:
                    logger.warning("生图失败（降级跳过，部分 SVG 无图）: %s",
                                   ((err or _out) or "")[-300:])
                elif all((image_dir / str(item.get("filename"))).is_file() for item in items):
                    job["cache_path"].write_text(
                        json.dumps({"fingerprint": job["fingerprint"],
                                    "files": [item.get("filename") for item in items]},
                                   ensure_ascii=False), encoding="utf-8")
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
                logger.warning("生图超时（%.0fs，降级跳过）", budget)
            except Exception as exc:  # noqa: BLE001
                logger.warning("生图收集异常: %s", exc)

        try:
            synced = image_plan_module.sync_to_design_studio(
                image_dir=image_dir, output_dir=out_dir,
                product_id=product_id, items=items,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("同步到 design studio 失败: %s", exc)
            synced = {"assets": [], "asset_dir": "", "hero": None, "by_kind": {}}

        page_map: dict[str, str] = {}
        for asset in synced.get("assets", []):
            m = re.match(r"page_(\d+)(?:_\w+)?\.png", asset.get("name", ""))
            if m:
                page_map[m.group(1).zfill(2)] = f"images/{asset['name']}"

        return {
            "hero": synced.get("hero"),
            "pages": page_map,
            "by_kind": synced.get("by_kind") or {},
            "list": synced.get("assets") or [],
            "asset_dir": synced.get("asset_dir") or "",
            "manifest": job.get("manifest"),
        }

    def _generate_images_v2(
        self,
        project_dir: Path,
        presentation: dict,
        idea: str,
        product_id: str,
        theme_name: str,
        accent_color: str,
        out_dir: Path,
        image_plan_module: Any,
    ) -> dict:
        """v2 生图：构建 manifest → image_gen.py 批量生成 → 同步 Design Studio。

        与 v1 的核心差异：
        - 必出图从 1 张（hero）扩展到 5 张（hero/cover/architecture/design/scene）
        - 按 page.type 分配 asset_kind（product_architecture → architecture 等）
        - 同步到 outputs/assets/{product_id}/（Design Studio 路径）

        降级：任何失败（无配置/超时/后端错误）→ 返回空 dict，不影响页面生产。
        （兼容包装：_run 已改为 发射→并行创作→收集 的高效编排，此方法保留给
        独立调用与测试。）
        """
        job = self._prepare_images_job(
            project_dir, presentation, idea, product_id,
            theme_name, accent_color, image_plan_module)
        proc, job = self._launch_images_gen(job)
        return self._collect_images(job, proc, out_dir, product_id, image_plan_module)


def get_ppt_design_agent() -> PptDesignAgent:
    return PptDesignAgent()
