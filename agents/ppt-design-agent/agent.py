"""
PptDesign Agent —— 独立 PPT 设计成员（hugohe3/ppt-master 工作流适配）
============================================================

职责（框架适配）：
  1. 以 Presentation DSL（canonical）为输入，建立 ppt-master 项目：
     设计规范（设计规范与内容大纲.md）+ spec_lock.md（执行锁）
  2. 逐页 SVG 由 MiniMax 按 skill 自由创作（svg_author.py：校验/重试/兜底）
  3. 调用 finalize_svg + svg_to_pptx 导出**原生可编辑 PPTX**（DrawingML 形状）
  4. 返回 {project_dir, pptx_path, pages, model, design_spec, spec_lock}

模型分工：本 Agent 的 LLM 环节（设计简报）使用 Presentation 专用模型
（AGENT_PLATFORM_PRESENTATION_LLM_*，如 MiniMax）；未配置时回退主 LLM
（DeepSeek）或完全确定性生成（无 LLM 调用）。渲染/转换全程无模型。
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from agent_platform.harness.agent_loop import BaseAgent
from agent_platform.llm.client import get_presentation_llm_client, get_llm_client
from agent_platform.schemas import AgentResult
from agent_platform.config.settings import get_settings

logger = logging.getLogger(__name__)

_SKILL_DIR = Path(__file__).resolve().parent / "vendor" / "ppt-master"
_SCRIPTS_DIR = _SKILL_DIR / "scripts"

_FONT = "Noto Sans SC, Source Han Sans SC, PingFang SC, Microsoft YaHei, sans-serif"
_TITLE_FONT = "Noto Serif SC, Source Han Serif SC, Georgia, serif"


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
    except Exception as exc:  # noqa: BLE001 —— 简报失败不阻断生产
        logger.warning("设计简报生成失败（回退确定性文案）: %s", exc)
        return ""


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
- title: 26
- body: 14
- title_family: {_TITLE_FONT}
- body_family: {_FONT}

## icons
- library: none
- inventory: none

## page_rhythm
{rhythm}

## pptx_structure
- mode: flat

## forbidden
- `mask`, `<style>`, `class`, external CSS, `<foreignObject>`, `textPath`, `@font-face`, `<animate*>`, `<set>`, `<script>` / event attributes, `<iframe>`
"""


class PptDesignAgent(BaseAgent):
    """PPT 设计成员：DSL → ppt-master 项目 → 原生可编辑 PPTX。"""

    name = "ppt_design_agent"
    description = "PPT 设计制作（ppt-master 工作流：设计规范 → 逐页 SVG → svg_to_pptx）"
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
        except Exception as exc:  # noqa: BLE001 —— 节点级失败由重试/降级处理
            logger.error("PptDesignAgent 执行失败: %s", exc, exc_info=True)
            return AgentResult(success=False, error=str(exc))

    def _run(self, state: dict) -> dict:
        presentation = state.get("presentation")
        if not presentation:
            raise RuntimeError("缺少 presentation（DSL）输入")
        idea = str(state.get("idea", ""))

        # 输出目录：优先环境变量（backend .env 的 OUTPUT_DIR），缺省 ./outputs（worker cwd）
        out_dir = Path(os.environ.get("OUTPUT_DIR", "./outputs")).resolve()
        base = out_dir / "studio_assets" / "ppt_projects"
        project_id = str(state.get("product_id") or idea)[:40]
        project_dir = base / f"{project_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "sources").mkdir(exist_ok=True)
        (project_dir / "svg_output").mkdir(exist_ok=True)
        (project_dir / "notes").mkdir(exist_ok=True)

        # ── 1) 设计规范（MiniMax 自由创作，确定性兜底）+ spec_lock ──
        theme = presentation.get("theme") or {}
        spec = self._compose_design_spec(presentation, idea)
        lock = _build_spec_lock(presentation, idea)
        (project_dir / "设计规范与内容大纲.md").write_text(spec, encoding="utf-8")
        (project_dir / "spec_lock.md").write_text(lock, encoding="utf-8")
        (project_dir / "notes" / "total.md").write_text(
            f"# 页面注释\n\n{spec}\n", encoding="utf-8"
        )

        # ── 2) 生图阶段（阶段 C：MiniMax-Image-01，可降级） ──
        images = self._generate_images(project_dir, presentation, idea, str(state.get("product_id") or idea)[:40])

        # ── 3) 逐页 SVG（MiniMax 按 skill 自由创作，校验+重试+兜底） ──
        files, svg_stats = self._author_pages(project_dir, presentation, theme, spec, images)

        # ── 4) finalize + svg_to_pptx（pptx-master 工具链，venv python） ──
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

        pptx_candidates = sorted((project_dir / "exports").glob("*.pptx")) if (project_dir / "exports").is_dir() else []
        pptx_path = pptx_candidates[0] if pptx_candidates else next(project_dir.glob("*.pptx"), None)
        if pptx_path is None:
            raise RuntimeError("svg_to_pptx 未产出 PPTX 文件")

        # ── 5) 模型记录（分工可见性） ──
        try:
            model = get_presentation_llm_client().model if get_presentation_llm_client() else get_llm_client().model
        except Exception:
            model = "deterministic"

        return {
            "project_dir": str(project_dir),
            "pptx_path": str(pptx_path),
            "pptx_relative": str(pptx_path.relative_to(out_dir)),
            "pages": len(presentation.get("pages") or []),
            "svg_files": files,
            "model": model,
            "design_brief": brief,
            "images": images.get("list", []),
            "svg_stats": svg_stats,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    # ── 设计规范（MiniMax 自由创作；确定性兜底） ──
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
        except Exception as exc:  # noqa: BLE001 —— 规范失败回退确定性大纲
            logger.warning("设计规范创作失败（回退大纲）: %s", exc)
        return _build_design_spec(presentation, idea, "")

    # ── 逐页 SVG（MiniMax 按 skill 创作：校验 → 重试 → 兜底） ──
    def _author_pages(
        self,
        project_dir: Path,
        presentation: dict,
        theme: dict,
        design_spec: str,
        images: dict,
    ) -> tuple[list[str], dict]:
        from agents.ppt_design_agent import svg_author

        svg_dir = project_dir / "svg_output"
        svg_dir.mkdir(exist_ok=True)
        pages = presentation.get("pages") or []
        llm = get_presentation_llm_client() or get_llm_client()
        files: list[str] = []
        stats: dict = {"retries": 0, "fallbacks": 0, "per_page": {}}
        img_assets = {"hero": images.get("hero"), "pages": images.get("pages") or {}}
        for i, page in enumerate(pages):
            name = f"slide_{i + 1:02d}_{page.get('type', 'page')}.svg"
            svg = ""
            status = "llm"
            if llm is not None and llm.api_key:
                for attempt in range(3):
                    prompt = svg_author.build_page_prompt(page, theme, design_spec, i, img_assets)
                    try:
                        raw = llm.complete(
                            [{"role": "system", "content": "你是资深咨询风演示 SVG 设计师。只输出 SVG。"},
                             {"role": "user", "content": prompt}],
                            temperature=0.6, max_tokens=8192,
                        ) or ""
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("P%d SVG 调用失败: %s", i + 1, str(exc)[:120])
                        continue
                    svg = svg_author.extract_svg(raw)
                    ok, issue = svg_author.validate_svg(svg, page)
                    if ok:
                        break
                    stats["retries"] += 1
                    logger.warning("P%d SVG 校验失败（第 %d 次）: %s", i + 1, attempt + 1, issue)
                    svg = ""
            if not svg:
                stats["fallbacks"] += 1
                status = "fallback"
                svg = svg_author.fallback_svg(page, theme)
            svg = svg_author.sanitize_svg(svg)
            (svg_dir / name).write_text(svg, encoding="utf-8")
            files.append(name)
            stats["per_page"][i + 1] = status
        return files, stats


    # ── 生图阶段（阶段 C）：MiniMax-Image-01 via ppt-master image_gen.py ──
    _HERO_PROMPT = (
        "高端咨询风格演示封面主视觉：{theme}，产品「{idea}」主题，"
        "深色渐变背景 + 主色点缀，留白构图，无文字，16:9，商业摄影质感"
    )
    _PAGE_PROMPT = (
        "咨询风格数据页配图（无文字）：{theme} 色系，主题「{topic}」，"
        "抽象信息图形/数据可视化氛围，留白，16:9，高端商务质感"
    )

    def _generate_images(
        self, project_dir: Path, presentation: dict, idea: str, product_id: str
    ) -> dict:
        """生成 image_prompts.json → image_gen.py 批量生成 → 资产库落盘。

        降级：任何失败（无配置/超时/后端错误）→ 返回空，不影响页面生产。
        """
        result: dict = {"hero": None, "pages": {}, "list": [], "asset_dir": ""}
        pages = presentation.get("pages") or []
        theme = presentation.get("theme") or {}
        theme_name = str(theme.get("name", "咨询风"))
        image_dir = project_dir / "images"
        image_dir.mkdir(exist_ok=True)

        try:
            items = [
                {
                    "filename": "hero.png",
                    "prompt": self._HERO_PROMPT.format(theme=theme_name, idea=idea[:40]),
                    "aspect_ratio": "16:9",
                    "image_size": "1K",
                    "status": "Pending",
                    "purpose": "封面主视觉",
                    "page_role": "hero_page",
                }
            ]
            for i, page in enumerate(pages[:6]):
                if page.get("type") in ("cover", "conclusion"):
                    continue
                items.append({
                    "filename": f"page_{i + 1:02d}.png",
                    "prompt": self._PAGE_PROMPT.format(
                        theme=theme_name,
                        topic=str(page.get("title") or page.get("type"))[:40],
                    ),
                    "aspect_ratio": "16:9",
                    "image_size": "1K",
                    "status": "Pending",
                    "purpose": f"P{i + 1:02d} 配图",
                    "page_role": "local",
                })
            manifest_path = image_dir / "image_prompts.json"
            manifest_path.write_text(
                json.dumps({"project": idea, "items": items}, ensure_ascii=False, indent=1),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [sys.executable, str(_SCRIPTS_DIR / "image_gen.py"),
                 "--manifest", str(manifest_path), "-o", str(image_dir)],
                capture_output=True, text=True, timeout=900,
                # cwd 继承工作目录（backend）：image_gen 需读取 backend/.env 的
                # IMAGE_BACKEND/MINIMAX_API_KEY（vendor scripts 目录无 .env）
            )
            if proc.returncode != 0:
                logger.warning("生图失败（降级跳过）: %s", (proc.stderr or proc.stdout)[-300:])
                return result

            out_dir = Path(os.environ.get("OUTPUT_DIR", "./outputs")).resolve()
            asset_root = out_dir / "assets" / str(product_id)
            asset_root.mkdir(parents=True, exist_ok=True)
            hero_rel = None
            page_map: dict[str, str] = {}
            assets_list: list[dict] = []
            for item in items:
                fname = item["filename"]
                src = image_dir / fname
                if not src.is_file():
                    continue
                dst = asset_root / fname
                dst.write_bytes(src.read_bytes())
                assets_list.append({
                    "name": fname,
                    "url": f"/api/v1/files/assets/{product_id}/{fname}",
                    "size": src.stat().st_size,
                })
                svg_ref = f"images/{fname}"
                if item.get("page_role") == "hero_page":
                    hero_rel = svg_ref
                else:
                    m = re.match(r"page_(\d+)\.png", fname)
                    if m:
                        page_map[f"{int(m.group(1)):02d}"] = svg_ref
            result = {
                "hero": hero_rel,
                "pages": page_map,
                "list": assets_list,
                "asset_dir": str(asset_root),
            }
        except Exception as exc:  # noqa: BLE001 —— 生图失败不阻断生产
            logger.warning("生图阶段异常（降级跳过）: %s", exc)
        return result


def get_ppt_design_agent() -> PptDesignAgent:
    return PptDesignAgent()
