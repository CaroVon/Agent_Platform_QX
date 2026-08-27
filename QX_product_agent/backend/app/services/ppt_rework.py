"""PPT 单页外科返工（P0.5 完成态路径）。

对已完成 deck 的指定页：带用户反馈重走「LLM 创作 → 注入链 → QA 门禁 →
finalize → svg_to_pptx → MOD 独立导出」的管线同款路径，产物即时生效
（export-pptx 端点按 mtime 取最新导出）。

与 worker 运行中路径互补：运行中的👎由创作循环批次间消费
（progress.json.rework_requests），本服务只服务完成态。
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_WORKSPACE = Path(__file__).resolve().parents[4]  # 工作区根（含 agents/agent-platform）
for _p in (str(_WORKSPACE), str(_WORKSPACE / "agent-platform")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def surgical_rework_page(product_id: str, package: dict, page_index: int,
                         feedback: str) -> tuple[bool, str]:
    """单页重做。Returns (ok, detail)。"""
    import sqlite3  # noqa: F401 —— 延迟说明：本函数纯文件/LLM 操作，不需 DB

    try:
        from agents.ppt_design_agent import cross_page, image_plan, svg_author, svg_qa

        presentation = package.get("presentation") or {}
        pages = presentation.get("pages") or []
        if not (0 <= page_index < len(pages)):
            return False, f"页码越界：{page_index + 1} / {len(pages)}"
        page = pages[page_index]
        theme = presentation.get("theme") or {}
        total = len(pages)

        from app.core.config import get_settings

        out_dir = Path(get_settings().OUTPUT_DIR).resolve()
        project_dir = out_dir / "studio_assets" / "ppt_projects" / product_id
        if not project_dir.is_dir():
            return False, "PPT 项目目录不存在"
        design_spec_path = project_dir / "设计规范与内容大纲.md"
        design_spec = (design_spec_path.read_text(encoding="utf-8")
                       if design_spec_path.is_file() else "")

        # 页图对位（项目 images/ 内现成资产）
        by_kind: dict[str, str] = {}
        images_dir = project_dir / "images"
        if images_dir.is_dir():
            for f in images_dir.glob("mod_chart_*.png"):
                kind = f.stem.replace("mod_chart_", "")
                by_kind[kind] = f"images/{f.name}"
        page_image = image_plan.select_image_for_page(page, page_index, by_kind)
        img_assets = {"hero": None, "pages": {}, "by_kind": by_kind,
                      "page_image": page_image}

        # ── LLM 重创作（带用户反馈；沿用硬性 insight 单节点规则） ──
        from agent_platform.llm.client import get_presentation_llm_client

        llm = get_presentation_llm_client()
        if llm is None or not llm.api_key:
            return False, "演示模型未配置（AGENT_PLATFORM_PRESENTATION_LLM_*）"
        prompt = svg_author.build_page_prompt(page, theme, design_spec, page_index, img_assets)
        prompt += (
            f"\n\n【用户返工反馈（最高优先级，必须逐条修正）】{feedback}\n"
            f"【硬性要求】insight/标题全文必须完整出现在同一个 <text> 元素内"
            "（禁止拆分 tspan）；已存在的配图引用保持不变。"
        )
        svg = ""
        issue = ""
        for attempt in range(3):
            try:
                raw = llm.complete(
                    [{"role": "system", "content": "你是资深咨询风演示 SVG 设计师。只输出 SVG。"},
                     {"role": "user", "content": prompt}],
                    temperature=0.55, max_tokens=16384) or ""
            except Exception as exc:  # noqa: BLE001
                return False, f"演示模型调用失败: {str(exc)[:120]}"
            cand = svg_author.extract_svg(raw)
            ok, issue = svg_author.validate_svg(cand, page)
            if ok:
                cand = svg_author.sanitize_svg(cand)
                ok, issue = svg_author.validate_native_contract(cand)
            if ok:
                svg = cand
                break
            prompt += f"\n\n上一次失败（{issue[:100]}），必须修正。"
        if not svg:
            return False, f"三次重创作均未通过校验: {str(issue)[:120]}"

        # ── 管线同款 finalize 注入链 + QA ──
        palette = theme.get("palette") or {}
        svg = svg_author.sanitize_svg(svg)
        svg = svg_author.inject_page_image(svg, page_image, page)
        svg = cross_page.inject_root_metadata(svg, page.get("type", "content"), page_index, total)
        if page.get("type") != "cover":
            svg = cross_page.inject_footer(svg, page_index, total, cross_page.DeckIdentity(
                product_name=str(package.get("idea") or product_id)[:32],
                product_code="rework",
                theme_color=str(palette.get("accent") or "#3D6491"),
                muted_color=str(palette.get("muted") or "#6F7275"),
                text_color=str(palette.get("text") or "#111111"),
                bg_color=str(palette.get("bg") or "#F7F6F0")))
        svg, _snap = cross_page.snap_font_sizes(svg)
        qa = svg_qa.qa_page(svg, page, theme, page_image)
        qa = [q for q in qa if "遮挡" not in q] or qa  # 注入层图位置已知合法
        # QA 仅提示（返工以用户反馈为准），记录进 progress 但不阻断

        out_path = project_dir / "svg_output" / f"slide_{page_index + 1:02d}_{page.get('type')}.svg"
        out_path.write_text(svg, encoding="utf-8")

        # ── 重导出主 PPTX + 独立 MOD PPTX（vendor 进程内桥，省子进程启动） ──
        from agents.ppt_design_agent import vendor_bridge

        rc, tail = vendor_bridge.run_finalize(str(project_dir))
        if rc != 0:
            return False, f"finalize_svg.py 失败: {tail}"
        rc, tail = vendor_bridge.run_svg_to_pptx([str(project_dir), "-s", "final"])
        if rc != 0:
            return False, f"svg_to_pptx.py 失败: {tail}"
        try:
            from agents.ppt_design_agent.agent import PptDesignAgent

            PptDesignAgent._export_mod_standalone(
                project_dir=project_dir, state={"product_id": product_id,
                                                "idea": package.get("idea"),
                                                "competitor_matrix": package.get("competitor_matrix"),
                                                "presentation": presentation},
                out_dir=out_dir, theme=theme)
        except Exception as exc:  # noqa: BLE001 —— 独立导出失败不视为主 deck 失败
            logger.warning("[Rework] MOD 独立导出失败（忽略）: %s", exc)

        # progress.json 同步
        pfile = project_dir / "progress.json"
        try:
            prog = json.loads(pfile.read_text(encoding="utf-8"))
            prog.setdefault("per_page", {})[str(page_index + 1)] = "llm"
            prog["rework_log"] = (prog.get("rework_log") or [])[-9:] + [{
                "page_index": page_index, "feedback": feedback[:100],
                "qa": qa, "ts": __import__("time").strftime("%H:%M:%S")}]
            pfile.write_text(json.dumps(prog, ensure_ascii=False), encoding="utf-8")
        except (OSError, ValueError):
            pass

        return True, f"P{page_index + 1:02d} 已重做并重导出（QA: {qa or 'PASS'}）"
    except Exception as exc:  # noqa: BLE001
        logger.exception("[Rework] 单页返工失败")
        return False, f"返工异常: {str(exc)[:160]}"
