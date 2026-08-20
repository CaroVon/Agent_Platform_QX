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
# 主 Agent 类
# ─────────────────────────────────────────────────────────────────

class PptDesignAgent(BaseAgent):
    """PPT 设计成员：DSL → ppt-master 项目 → 原生可编辑 PPTX（v2）。"""

    name = "ppt_design_agent"
    description = "PPT 设计制作（ppt-master 工作流：设计规范 → 多维生图 → 逐页 SVG → svg_to_pptx）"
    output_schema = None  # 输出为 dict（不绑定 Pydantic Schema）

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

        # 输出目录：优先环境变量（backend .env 的 OUTPUT_DIR），缺省 ./outputs（worker cwd）
        out_dir = Path(os.environ.get("OUTPUT_DIR", "./outputs")).resolve()
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

        # ── 1) 设计规范 + spec_lock（占位） ─────────────────────
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

        # ── 3) 生图阶段：完整释放（hero/cover/architecture/design/scene + 每页配图） ──
        images = self._generate_images_v2(
            project_dir=project_dir,
            presentation=presentation,
            idea=idea,
            product_id=product_id,
            theme_name=theme_name,
            accent_color=accent_color,
            out_dir=out_dir,
            image_plan_module=_image_plan,
        )

        # ── 4) 逐页 SVG（MiniMax 按 skill 创作 + 程序化注入图片/页脚/根属性） ──
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

        # ── 5b) MOD 附录合并：主 deck 主题重渲染竞品矩阵页并续接页码 ──
        mod_merge = self._merge_mod_appendix(
            project_dir=project_dir,
            state=state,
            out_dir=out_dir,
            main_files=files,
            theme_id=str(theme.get("id") or ""),
        )

        # ── 6) finalize + svg_to_pptx ───────────────────────────
        python = sys.executable
        for script, args in (
            ("finalize_svg.py", [str(project_dir)]),
            ("svg_to_pptx.py", [str(project_dir), "-s", "final"]),
        ):
            proc = subprocess.run(
                [python, str(_SCRIPTS_DIR / script), *args],
                capture_output=True, text=True, timeout=600,
                cwd=str(_SCRIPTS_DIR),
            )
            if proc.returncode != 0:
                detail = (proc.stderr or proc.stdout)[-500:]
                raise RuntimeError(f"{script} 失败: {detail}")

        pptx_candidates = list((project_dir / "exports").glob("*.pptx")) if (project_dir / "exports").is_dir() else []
        if pptx_candidates:
            # 节点重试复用同一目录时可能保留多个 PPTX，必须返回本轮最新产物。
            pptx_path = max(pptx_candidates, key=lambda path: path.stat().st_mtime)
        else:
            root_candidates = list(project_dir.glob("*.pptx"))
            pptx_path = max(root_candidates, key=lambda path: path.stat().st_mtime) if root_candidates else None
        if pptx_path is None:
            raise RuntimeError("svg_to_pptx 未产出 PPTX 文件")

        # ── 7) 模型记录 ────────────────────────────────────────
        try:
            model = get_presentation_llm_client().model if get_presentation_llm_client() else get_llm_client().model
        except Exception:
            model = "deterministic"

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
            "mod_appendix": mod_merge,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    # ── MOD 附录合并（双管线链接：主 PPT 在前，MOD 分析页续后） ──
    @staticmethod
    def _merge_mod_appendix(project_dir: Path, state: dict, out_dir: Path,
                            main_files: list, theme_id: str) -> dict:
        """把竞品矩阵（MOD）页面用主 deck 主题重渲染并追加进 svg_output。

        - 输入：studio_assets/{product_id}/competitor_matrix/ppt/deck_ctx.json
          （MOD 节点持久化的确定性渲染输入）
        - 页码：主页面 NN/MM 的 MM 总数同步改为合并后总数（页脚/根属性一致）
        - 降级：任何失败仅产出主 PPT，不阻塞主管线
        """
        product_id = str(state.get("product_id") or "")
        empty = {"merged": False, "pages": 0}
        if not product_id or not state.get("competitor_matrix"):
            return empty
        try:
            import pandas as _pd
            from amazon_matrix_mod.deck import build as _mod_build
            from amazon_matrix_mod.deck.plan import plan_pages as _mod_plan
            from amazon_matrix_mod.deck.themes import Theme as _ModTheme

            mod_out = out_dir / "studio_assets" / product_id / "competitor_matrix"
            ctx = _mod_build.load_deck_ctx(str(mod_out))
            if not ctx:
                return {**empty, "reason": "deck_ctx.json 缺失（MOD 未跑 full）"}
            # 相对路径还原为绝对路径（deck_ctx 持久化时转为相对 out_dir）
            abs_of = lambda p: (str(mod_out / p) if p and not os.path.isabs(p) else p)
            ctx["df"] = _pd.DataFrame(ctx.get("df") or [])
            ctx["image_cache_dir"] = abs_of(ctx.get("image_cache_dir"))
            vis = ctx.get("visuals") or {}
            ctx["visuals"] = {
                "background": abs_of(vis.get("background")),
                "cover": abs_of(vis.get("cover")),
                "zones": {k: abs_of(v) for k, v in (vis.get("zones") or {}).items()},
            }
            ctx["theme"] = _ModTheme(theme_id) if theme_id else _ModTheme(
                ctx.get("theme_id") or "cyber-ivory-navy")

            n_main = len(main_files)
            n_mod = len(_mod_plan(ctx))
            total = n_main + n_mod
            svg_dir = project_dir / "svg_output"
            written = _mod_build.render_mod_pages(
                str(svg_dir), ctx, start_index=n_main + 1, total_after_merge=total)

            # 主页面页脚 — NN / MM — 与根属性 page-total 同步为合并总数
            for f in main_files:
                p = Path(f) if not isinstance(f, Path) else f
                if not p.is_absolute():
                    p = svg_dir / p.name
                try:
                    text_content = p.read_text(encoding="utf-8")
                    patched = re.sub(r"— (\d{2}) / \d{2} —",
                                     rf"— \1 / {total:02d} —", text_content)
                    patched = patched.replace(
                        f'data-pptx-page-total="{n_main}"',
                        f'data-pptx-page-total="{total}"')
                    if patched != text_content:
                        p.write_text(patched, encoding="utf-8")
                except OSError:
                    continue

            # spec_lock page_rhythm 追加 MOD 附录条目
            lock_path = project_dir / "spec_lock.md"
            try:
                lock = lock_path.read_text(encoding="utf-8")
                extra = "\n".join(f"- P{i:02d}: dense"
                                  for i in range(n_main + 1, total + 1))
                if "## page_rhythm" in lock:
                    head, _, rest = lock.partition("## page_rhythm")
                    section, sep, tail = rest.partition("\n## ")
                    lock = (head + "## page_rhythm" + section.rstrip()
                            + "\n" + extra + ("\n## " + tail if sep else ""))
                    lock_path.write_text(lock, encoding="utf-8")
            except OSError:
                pass

            logger.info("[ppt_design] MOD 附录合并 %d 页（主题 %s，总页数 %d）",
                        len(written), ctx["theme"].id, total)
            return {"merged": True, "pages": len(written),
                    "theme": ctx["theme"].id, "total_pages": total}
        except Exception as exc:  # noqa: BLE001 —— 合并失败降级为主 PPT
            logger.warning("[ppt_design] MOD 附录合并失败（降级）: %s", str(exc)[:200])
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

        svg_dir = project_dir / "svg_output"
        svg_dir.mkdir(exist_ok=True)
        pages = presentation.get("pages") or []
        llm = get_presentation_llm_client() or get_llm_client()
        files: list[str] = []
        stats: dict = {"retries": 0, "fallbacks": 0, "per_page": {},
                        "images_injected": 0, "footers_injected": 0,
                        "root_metadata_injected": 0, "font_sizes_snapped": 0}
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

        def _finalize(idx: int, svg: str | None, status: str, img_assets: dict) -> None:
            """主线程：程序化后处理 + 写盘 + stats 聚合（确定性、无锁）。"""
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

            # ── d) 字号白名单收敛 ──
            svg, snap_info = cross_page_module.snap_font_sizes(svg)
            stats["font_sizes_snapped"] += len(snap_info["snapped"])

            (svg_dir / name).write_text(svg, encoding="utf-8")
            files.append(name)
            stats["per_page"][page_no] = {
                "status": status,
                "page_image": page_image,
                "font_sizes": snap_info["kept_unique"],
                "snap_count": len(snap_info["snapped"]),
            }

        # ── batch 自适应并发主循环（参照 image_gen._run_manifest） ──
        _tn = threading.current_thread().name
        queue: list[int] = list(range(total))
        while queue:
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
                        _finalize(idx, svg, "llm", img_assets)

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
        - 按 page.type 分配 asset_kind（product_architecture → architecture；user_persona → scene；feature_priority → feature；等等）
        - 同步到 outputs/assets/{product_id}/（Design Studio 路径）

        降级：任何失败（无配置/超时/后端错误）→ 返回空 dict，不影响页面生产。
        """
        empty = {"hero": None, "pages": {}, "by_kind": {}, "list": [], "asset_dir": "",
                  "manifest": None}
        image_dir = project_dir / "images"
        image_dir.mkdir(exist_ok=True)

        # ── a) 构建 manifest（强调 architecture + design） ──
        try:
            manifest = image_plan_module.build_image_manifest(
                presentation=presentation,
                idea=idea,
                product_id=product_id,
                theme_name=theme_name,
                accent_color=accent_color,
                max_pages=10,
            )
            items = manifest.get("items") or []
        except Exception as exc:  # noqa: BLE001
            logger.warning("生图 manifest 构建失败: %s", exc)
            return empty

        # ── b) 写 manifest ──
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
            json.dumps(manifest, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        # 同时生成可读的 sidecar（image_gen.py 支持）
        try:
            sidecar = []
            for it in items:
                sidecar.append(f"- **{it['filename']}** ({it.get('asset_kind', '?')}): {it['prompt']}")
            (image_dir / "image_prompts.md").write_text(
                f"# {idea} 图片 Prompt 清单\n\n" + "\n".join(sidecar) + "\n",
                encoding="utf-8",
            )
        except Exception:  # noqa: BLE001
            pass

        # ── c) 调 image_gen.py 批量生成 ──
        if cache_hit:
            logger.info("生图缓存命中，跳过 image_gen.py | product=%s", product_id)
        else:
            try:
                proc = subprocess.run(
                    [sys.executable, str(_SCRIPTS_DIR / "image_gen.py"),
                     "--manifest", str(manifest_path), "-o", str(image_dir)],
                    capture_output=True, text=True, timeout=900,
                    # cwd 继承工作目录（backend）：image_gen 需读取 backend/.env 的
                    # IMAGE_BACKEND/MINIMAX_API_KEY（vendor scripts 目录无 .env）
                )
                if proc.returncode != 0:
                    logger.warning("生图失败（降级跳过，部分 SVG 无图）: %s",
                                    (proc.stderr or proc.stdout)[-300:])
                elif all((image_dir / str(item.get("filename"))).is_file() for item in items):
                    cache_path.write_text(
                        json.dumps({"fingerprint": fingerprint, "files": [item.get("filename") for item in items]},
                                   ensure_ascii=False),
                        encoding="utf-8",
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning("生图调用异常: %s", exc)

        # ── d) 同步到 Design Studio（outputs/assets/{product_id}/） ──
        try:
            synced = image_plan_module.sync_to_design_studio(
                image_dir=image_dir,
                output_dir=out_dir,
                product_id=product_id,
                items=items,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("同步到 design studio 失败: %s", exc)
            synced = {"assets": [], "asset_dir": "", "hero": None, "by_kind": {}}

        # ── e) 构建 page_map（page_NN.png → svg_ref） ──
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
            "manifest": manifest,
        }


def get_ppt_design_agent() -> PptDesignAgent:
    return PptDesignAgent()
