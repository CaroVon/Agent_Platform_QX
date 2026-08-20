"""M3 审图回环 —— 关键页 SVG→PNG（Chromium）→ MiniMax-M3 多模态审查 → 一次修订。

审图为增强层：M3 不可用/失败时返回空结果，不阻塞 pptx 构建。
可渲染修复项（标签重叠/字号过小/图例遮挡）映射为页面修订参数重渲染。
"""
from __future__ import annotations

import json
import logging
import os
import re

log = logging.getLogger(__name__)

# 审查重点页（文件名子串 → 用途）
KEY_PAGES = ("matrix", "cover", "zones", "price_bands")


def _page_prompt(fname: str, ctx: dict) -> str:
    df = ctx.get("df")
    n = len(df) if df is not None else 0
    base = (f"这是「{ctx.get('keyword', '')}」亚马逊竞品分析 PPT 的一页（{fname}），"
            f"N={n} 个竞品，价格×月销矩阵体系。")
    if "matrix" in fname:
        base += ("本页为核心主图：x=价格(对数)、y=预估月销(对数)，缩略图=竞品真实主图，"
                 "边框色=四区分区，金色=我方产品。请重点检查：缩略图是否重叠、"
                 "价格标签可读性、图例完整性、坐标轴刻度合理性。")
    elif "cover" in fname:
        base += "本页为封面。请检查：标题排版、视觉档次、信息完整度。"
    else:
        base += "请检查：文字可读性、数据展示清晰度、布局均衡。"
    return base


def audit_deck(out_dir: str, ctx: dict, written: list[str]) -> tuple[dict, dict]:
    """审图主入口。返回 (revisions, audit_result)。

    revisions: {文件名: 修订参数}（仅含可渲染修复项）
    audit_result: 写入 deck_audit.json 的完整结果。
    """
    from amazon_matrix_mod import m3_client
    from amazon_matrix_mod.svgcharts.rasterize import svg_to_png

    audit_dir = os.path.join(out_dir, "ppt", "audit")
    os.makedirs(audit_dir, exist_ok=True)
    results: dict = {}
    revisions: dict = {}
    data_summary = ""
    df = ctx.get("df")
    if df is not None and len(df):
        data_summary = (f"keyword={ctx.get('keyword')}, N={len(df)}, "
                        f"价格 ${df['current_price'].min():.2f}-"
                        f"${df['current_price'].max():.2f}")

    for path in written:
        fname = os.path.basename(path)
        if not any(k in fname for k in KEY_PAGES):
            continue
        png = os.path.join(audit_dir, fname.replace(".svg", ".png"))
        if not svg_to_png(path, png):
            results[fname] = {"error": "光栅化失败（跳过）"}
            continue
        prompt = _page_prompt(fname, ctx)
        try:
            verdict = m3_client.chat(
                f"{prompt}\n请输出 JSON：{{\"assess\": \"页面质量评估(60字内)\", "
                f"\"issues\": [\"可渲染修复的问题，如 标签重叠/字号过小，无则空\"], "
                f"\"must_fix\": true|false}}\n数据摘要：{data_summary}",
                image_path=png, max_tokens=800)
            parsed = _parse_verdict(verdict)
            results[fname] = parsed
            rev = _revisions_from(parsed.get("issues") or [], fname)
            if rev and parsed.get("must_fix", True):
                revisions[fname] = rev
        except Exception as exc:  # noqa: BLE001 —— 单页失败不影响其他页
            results[fname] = {"error": str(exc)[:100]}

    audit_result = {"pages": results,
                    "revisions": {k: v for k, v in revisions.items()},
                    "note": "M3 审图增强层；可渲染修复项已触发一次重渲染"}
    with open(os.path.join(out_dir, "deck_audit.json"), "w", encoding="utf-8") as f:
        json.dump(audit_result, f, ensure_ascii=False, indent=1)
    return revisions, audit_result


def _parse_verdict(text: str) -> dict:
    """M3 返回 → {assess, issues[], must_fix}（容错解析：剥围栏/取首尾大括号）。"""
    import re as _re
    t = text.strip()
    t = _re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", t).strip()  # 剥 markdown 围栏
    start, end = t.find("{"), t.rfind("}")
    if start >= 0 and end > start:
        candidate = t[start:end + 1]
        try:
            data = json.loads(candidate)
            return {"assess": str(data.get("assess", "")),
                    "issues": [str(i) for i in (data.get("issues") or [])][:4],
                    "must_fix": bool(data.get("must_fix", False))}
        except json.JSONDecodeError:
            # 围栏内仍是非法 JSON（嵌套引号等）→ 正则抽 issues 数组兜底
            issues = _re.findall(r'"issues"\s*:\s*\[(.*?)\]', candidate, _re.S)
            extracted = _re.findall(r'"([^"]{6,120})"', issues[0]) if issues else []
            if extracted:
                return {"assess": candidate[:100], "issues": extracted[:4],
                        "must_fix": True, "partial_parse": True}
    return {"assess": t[:120], "issues": [], "must_fix": False,
            "parse_error": True}


def _revisions_from(issues: list[str], fname: str = "") -> dict:
    """issues 文本 → 页面修订参数（仅可渲染修复项，按页面类型匹配）。"""
    rev: dict = {}
    joined = "；".join(issues)
    if "matrix" in fname and re.search(r"重叠|遮挡|overlap|crowd", joined, re.I):
        rev["thumb_scale"] = 0.8  # 仅核心矩阵页支持缩略图缩放
    if re.search(r"字号|过小|太小|font|无法读取|难以辨认", joined, re.I):
        rev["font_scale"] = 1.15
    return rev
