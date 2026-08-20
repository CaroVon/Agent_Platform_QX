"""deck 构建 —— 页面 SVG 组装 + ppt-master finalize/svg_to_pptx 转 pptx。

与 PptDesignAgent 相同的集成模式（vendor/ppt-master 作为工具链）：
  {out_dir}/ppt/svg_output/*.svg  →  finalize_svg.py  →  svg_final/
  →  svg_to_pptx.py -s final  →  competitor_matrix.pptx

页面 chrome（主题/页脚/根属性/字号白名单）在 write_pages 统一后处理；
所有图表/数据由 svgcharts 确定性渲染，视觉装饰图由 gen_visual（image-01）
产生，本模块不产生任何编造数据。
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

log = logging.getLogger(__name__)

_SCRIPTS = Path(__file__).resolve().parents[2] / "agents" / "ppt-design-agent" \
    / "vendor" / "ppt-master" / "scripts"


def _scripts_dir() -> Path:
    for cand in (_SCRIPTS,
                 Path(__file__).resolve().parents[2] / "QX_product_agent" / "agents"
                 / "ppt-design-agent" / "vendor" / "ppt-master" / "scripts"):
        if (cand / "svg_to_pptx.py").is_file():
            return cand
    raise FileNotFoundError("未找到 ppt-master scripts 目录")


def _spec_lock_md(page_files: list[str], keyword: str, theme) -> str:
    """ppt-master spec-lock/v1 契约（svg_to_pptx 需要 typography 行等）。"""
    rhythm = "\n".join(
        f"- P{i:02d}: {'anchor' if i == 1 or i == len(page_files) else 'dense'}"
        for i in range(1, len(page_files) + 1))
    return f"""<!-- ppt-master-schema: spec-lock/v1 -->
# Execution Lock

## canvas
- viewBox: 0 0 1280 720
- format: PPT 16:9

## communication
- primary_language: zh-CN
- audience: 产品与运营决策者
- objective: 传达竞品矩阵数据结论并驱动选品/定价行动
- core_message: {keyword}·竞品矩阵 MOD 分析

## mode
- mode: custom

## visual_style
- visual_style: {theme.visual_style}

## colors
- bg: {theme.bg}
- surface: {theme.surface}
- primary: {theme.primary}
- accent: {theme.accent}
- text: {theme.text}
- muted: {theme.muted}

## typography
- font_family: Noto Sans SC, Source Han Sans SC, PingFang SC, Microsoft YaHei, sans-serif
- title: 26
- body: 14
- title_family: Noto Sans SC, Source Han Sans SC, PingFang SC, Microsoft YaHei, sans-serif
- body_family: Noto Sans SC, Source Han Sans SC, PingFang SC, Microsoft YaHei, sans-serif

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


def _finalize_page(root, ctx: dict, fname: str, index: int, total: int) -> None:
    """页面 chrome 后处理：主题已在前置 apply；根属性 + 页脚 + 字号 snap。"""
    from amazon_matrix_mod.deck import chrome
    from amazon_matrix_mod.svgcharts.svg import fmt

    th = ctx["theme"]
    role = "cover" if index == 1 else ("ending" if index == total else "content")
    chrome.set_page_metadata(root, index, total, role)
    identity = chrome.DeckIdentity(
        product_name=str(ctx.get("keyword", "")),
        project_code=time.strftime("%Y.%m"))
    chrome.inject_footer(root, identity, index, total, muted=th.muted)
    chrome.snap_font_sizes(root)


def write_pages(out_dir: str, ctx: dict, revisions: dict | None = None) -> list[str]:
    """生成全部页面 SVG 到 {out_dir}/ppt/svg_output/。返回文件路径列表。"""
    from amazon_matrix_mod.deck.plan import plan_pages
    from amazon_matrix_mod.deck.themes import Theme
    from amazon_matrix_mod.svgcharts.svg import save
    from amazon_matrix_mod.svgcharts.style import apply_theme

    if not ctx.get("theme"):
        ctx["theme"] = Theme("cyber-ivory-navy")
    apply_theme(ctx["theme"])  # 图表轴系/卡片随主题（单线程顺序渲染）

    svg_dir = os.path.join(out_dir, "ppt", "svg_output")
    os.makedirs(svg_dir, exist_ok=True)
    revisions = revisions or {}
    planned = plan_pages(ctx)
    total = len(planned)
    written = []
    for idx, (fname, builder) in enumerate(planned, 1):
        root = builder(ctx, rev=revisions.get(fname))
        _finalize_page(root, ctx, fname, idx, total)
        path = os.path.join(svg_dir, fname)
        save(root, path)
        written.append(path)
    spec = os.path.join(out_dir, "ppt", "spec_lock.md")
    with open(spec, "w", encoding="utf-8") as f:
        f.write(_spec_lock_md([os.path.basename(p) for p in written],
                              str(ctx.get("keyword", "")), ctx["theme"]))
    return written


def render_mod_pages(target_svg_dir: str, ctx: dict, start_index: int,
                     total_after_merge: int, revisions: dict | None = None,
                     name_prefix: str = "mod") -> list[str]:
    """把 MOD 页面直接渲染进主 PPT 工程（双管线合并入口）。

    - 主题：使用 ctx["theme"]（调用方传入主 deck 的主题）
    - 页码：start_index 起连续编号，页脚 NN/MM 与主 deck 合并后一致
    - 文件名：slide_{NN:02d}_{name_prefix}_{原slug}.svg
    """
    from amazon_matrix_mod.deck.plan import plan_pages
    from amazon_matrix_mod.svgcharts.svg import save
    from amazon_matrix_mod.svgcharts.style import apply_theme

    if not ctx.get("theme"):
        from amazon_matrix_mod.deck.themes import Theme
        ctx["theme"] = Theme("cyber-ivory-navy")
    apply_theme(ctx["theme"])
    os.makedirs(target_svg_dir, exist_ok=True)
    revisions = revisions or {}
    planned = plan_pages(ctx)
    written = []
    for k, (fname, builder) in enumerate(planned):
        idx = start_index + k
        root = builder(ctx, rev=revisions.get(fname))
        _finalize_page(root, ctx, fname, idx, total_after_merge)
        slug = fname.split("_", 2)[-1] if fname.count("_") >= 2 else fname
        out_name = f"slide_{idx:02d}_{name_prefix}_{slug}"
        path = os.path.join(target_svg_dir, out_name)
        save(root, path)
        written.append(path)
    return written


def build_pptx(out_dir: str, pptx_name: str = "competitor_matrix.pptx",
               timeout: int = 600) -> str:
    """finalize + svg_to_pptx → {out_dir}/{pptx_name}。失败抛错（调用方降级）。"""
    scripts = _scripts_dir()
    ppt_dir = os.path.join(out_dir, "ppt")
    for script, args in (
            ("finalize_svg.py", [str(ppt_dir)]),
            ("svg_to_pptx.py", [str(ppt_dir), "-s", "final",
                                "-o", os.path.join(out_dir, pptx_name)]),
    ):
        proc = subprocess.run(
            [sys.executable, str(scripts / script), *args],
            capture_output=True, text=True, timeout=timeout,
            cwd=str(scripts))
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout)[-600:]
            raise RuntimeError(f"{script} 失败: {detail}")
    out = os.path.join(out_dir, pptx_name)
    if not os.path.isfile(out):
        raise RuntimeError(f"pptx 未生成: {out}")
    return out


def validate_pptx(pptx_path: str) -> dict:
    """pptx_qa 校验（尽力而为，不阻塞）。"""
    qa = Path(__file__).resolve().parents[2] / "QX_product_agent" / "backend" \
        / "scripts" / "pptx_qa" / "validate_pptx.py"
    if not qa.is_file():
        return {"available": False}
    try:
        proc = subprocess.run(
            [sys.executable, str(qa), pptx_path],
            capture_output=True, text=True, timeout=180)
        return {"available": True, "returncode": proc.returncode,
                "tail": (proc.stdout or proc.stderr)[-500:]}
    except Exception as exc:  # noqa: BLE001
        return {"available": True, "error": str(exc)[:120]}


def build_deck(out_dir: str, ctx: dict, *, audit_hook=None) -> dict:
    """完整构建：页面 → pptx →（可选审图回环）→ 元信息。

    audit_hook(out_dir, ctx, written) → (revisions, audit_result)；
    返回 revisions 非空时重写受影响页面并重建 pptx（一次回环）。
    """
    if not ctx.get("theme"):
        from amazon_matrix_mod.deck.themes import Theme
        ctx["theme"] = Theme("cyber-ivory-navy")
    written = write_pages(out_dir, ctx)
    log.info("[deck] %d 页 SVG（主题 %s）", len(written), ctx["theme"].id)
    revisions: dict = {}
    audit_result: dict = {}
    if audit_hook:
        try:
            revisions, audit_result = audit_hook(out_dir, ctx, written)
        except Exception as exc:  # noqa: BLE001 —— 审图为增强层
            log.warning("[deck] 审图回环失败（降级）: %s", str(exc)[:120])
            audit_result = {"error": str(exc)[:120]}
        if revisions:
            rewritten = write_pages(out_dir, ctx, revisions=revisions)
            log.info("[deck] 审图修订 %d 页", len(rewritten))
    pptx_path = build_pptx(out_dir)
    result = {
        "pptx": pptx_path,
        "pages": [os.path.basename(p) for p in written],
        "theme": ctx["theme"].id,
        "audit": audit_result,
        "revised_pages": sorted(revisions),
    }
    with open(os.path.join(out_dir, "ppt", "deck_meta.json"), "w",
              encoding="utf-8") as f:
        json.dump({**result, "audit": audit_result}, f, ensure_ascii=False, indent=1)
    return result


def load_deck_ctx(mod_out_dir: str) -> dict | None:
    """读取 MOD 节点持久化的 deck_ctx.json（合并渲染输入）。"""
    path = os.path.join(mod_out_dir, "ppt", "deck_ctx.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
