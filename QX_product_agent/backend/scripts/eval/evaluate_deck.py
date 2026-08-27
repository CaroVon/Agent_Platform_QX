#!/usr/bin/env python3
"""黄金集评测 harness（P2）—— 对最新 deck 产出自动评分报告。

评分维度（无 LLM、确定性）：
  1. 结构：页数区间 10-24、MOD 章节 ≥4 页、页型分布
  2. 质量门禁逐页复检（svg_qa：密度/色板/字号/溯源/遮挡）
  3. 产物完整性：主 PPTX / 独立 competitor_matrix.pptx / reveal deck.html / MOD 数据资产
  4. 渐进交付：节点 md/pdf 是否齐备
输出：JSON 报告（stdout）+ 非 0 退出码表示存在 error 级问题（供 CI gate）。

用法：
  python scripts/eval/evaluate_deck.py <product_id> [--out report.json]
  nightly.sh —— 取最新 completed 产品自动评测
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
for p in (str(ROOT), str(ROOT / "agent-platform")):
    if p not in sys.path:
        sys.path.insert(0, p)


def evaluate(product_id: str, out_root: Path) -> dict:
    from agents.ppt_design_agent import svg_qa

    report: dict = {"product_id": product_id, "errors": [], "warnings": [], "stats": {}}
    proj = out_root / "studio_assets" / "ppt_projects" / product_id
    mod_dir = out_root / "studio_assets" / product_id / "competitor_matrix"
    if not proj.is_dir():
        report["errors"].append(f"项目目录不存在: {proj}")
        return report

    # 1) 结构
    finals = sorted((proj / "svg_final").glob("slide_*.svg")) if (proj / "svg_final").is_dir() else []
    n = len(finals)
    report["stats"]["pages"] = n
    if not (10 <= n <= 24):
        report["errors"].append(f"页数 {n} 超出 10-24 区间")
    mod_pages = [f for f in finals if "_mod_" in f.name]
    report["stats"]["mod_pages"] = len(mod_pages)
    if len(mod_pages) < 4:
        report["warnings"].append(f"MOD 章节仅 {len(mod_pages)} 页（参考 ≥4）")

    # 2) 逐页 QA 复检
    qa_fail = 0
    for f in finals:
        svg = f.read_text(encoding="utf-8")
        page_type = ("mod_" + f.stem.split("_mod_")[-1]) if "_mod_" in f.stem else "content"
        issues = svg_qa.qa_page(svg, {"type": page_type}, {"palette": {}}, None)
        hard = [i for i in issues if ("遮挡" in i or "空占位" in i)]
        if hard:
            qa_fail += 1
            report["errors"].append(f"{f.name}: {hard[0][:60]}")
        elif issues:
            report["warnings"].append(f"{f.name}: {issues[0][:50]}")
    report["stats"]["qa_hard_fail_pages"] = qa_fail

    # 3) 产物完整性
    checks = {
        "main_pptx": bool(list((proj / "exports").glob("*.pptx"))) if (proj / "exports").is_dir() else False,
        "mod_pptx": (mod_dir / "competitor_matrix.pptx").is_file(),
        "reveal_html": (proj / "exports" / "deck.html").is_file(),
        "mod_data": (mod_dir / "data").is_dir(),
        "mod_charts": (mod_dir / "charts").is_dir(),
    }
    report["stats"]["artifacts"] = checks
    for k in ("main_pptx", "mod_pptx", "mod_charts"):
        if not checks.get(k):
            report["errors"].append(f"缺关键产物: {k}")

    # 4) 渐进交付资产
    lib = out_root / "studio_assets" / product_id
    expected = ["research.md", "competitor_matrix.md", "competitor_analysis.md",
                "strategy.md", "design.md", "presentation.json"]
    missing = [e for e in expected if not (lib / e).is_file()]
    report["stats"]["incremental_assets_missing"] = missing
    if missing:
        report["warnings"].append(f"渐进资产缺失: {missing}")

    report["verdict"] = "PASS" if not report["errors"] else "FAIL"
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("product_id")
    ap.add_argument("--out", help="报告 JSON 落盘路径")
    ap.add_argument("--output-root", default="/mnt/d/DEV/agents_outputs")
    args = ap.parse_args()
    rep = evaluate(args.product_id, Path(args.output_root))
    text = json.dumps(rep, ensure_ascii=False, indent=1)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    sys.exit(0 if rep["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
