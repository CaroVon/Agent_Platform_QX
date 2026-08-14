"""
============================================================
演示质量审计脚本（内容完整度 + PDF 美观度）
============================================================

对比三个层面:
  1. 上游资产 vs Presentation DSL —— 信息压缩率与覆盖度
  2. DSL vs PDF 文本 —— 渲染完整性（组件文本 0 缺失）
  3. PDF 坐标 —— 标题安全边距（不再贴边）

用法:
  ../venv/bin/python ../scripts/audit_presentation.py [product_id]
  （缺省审计最新一条 completed 产品）
"""

import json
import os
import sys
import uuid
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(_BACKEND))
# DB 相对路径（./local_dev.db）以 backend/ 为基准
os.chdir(_BACKEND)

import pymupdf  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.celery_db import get_sync_engine  # noqa: E402
from app.models.studio_product import StudioProduct, StudioProductStatus  # noqa: E402


def chars(x) -> int:
    if isinstance(x, str):
        return len(x)
    if isinstance(x, dict):
        return sum(chars(v) for v in x.values())
    if isinstance(x, list):
        return sum(chars(v) for v in x)
    return 0


def text_of(data, out=None):
    out = out if out is not None else []
    if isinstance(data, str):
        out.append(data)
    elif isinstance(data, dict):
        for v in data.values():
            text_of(v, out)
    elif isinstance(data, list):
        for v in data:
            text_of(v, out)
    return out


def main():
    with Session(get_sync_engine()) as s:
        query = s.query(StudioProduct).filter(
            StudioProduct.status == StudioProductStatus.COMPLETED
        )
        if len(sys.argv) > 1:
            product = s.get(StudioProduct, uuid.UUID(sys.argv[1]))
        else:
            product = query.order_by(StudioProduct.created_at.desc()).first()
        if product is None:
            print("无 completed 产品"); return
        pkg = json.loads(product.asset_package)

    pres = pkg.get("presentation") or {}
    pages = pres.get("pages", [])
    research = pkg.get("research") or {}
    strategy = pkg.get("strategy") or {}
    comp = pkg.get("competitor_analysis") or {}

    # ── 1. 压缩率 ─────────────────────────────────────────
    up_chars = chars(pkg.get("document") or {})
    dsl_chars = chars(pages)
    print(f"产品: {product.idea} | 页数 {len(pages)}")
    print(f"[1] 压缩率: 上游 {up_chars} 字 → DSL {dsl_chars} 字 = {dsl_chars/max(up_chars,1)*100:.0f}%")

    # ── 2. 覆盖度 ─────────────────────────────────────────
    dsl_text = json.dumps(pres, ensure_ascii=False)
    def hit(t): return bool(t) and t in dsl_text
    feats = strategy.get("features", [])
    fcov = sum(1 for f in feats if hit(f.get("name", "")))
    pains = research.get("customer_pain_points", [])
    pcov = sum(1 for p in pains if hit(p[:8]))
    comps = comp.get("competitors", [])
    ccov = sum(1 for c in comps if hit(c.get("name", "")))
    ms = research.get("market_size", {})
    mvals = [ms.get("tam"), ms.get("sam"), ms.get("som"), ms.get("cagr")]
    mcov = sum(1 for v in mvals if hit(v))
    phases = strategy.get("roadmap", [])
    rcov = sum(1 for p in phases if hit(p.get("phase", "")) or hit(p.get("title", "")))
    print(f"[2] 覆盖度: 功能 {fcov}/{len(feats)} | 痛点 {pcov}/{len(pains)} | "
          f"竞品 {ccov}/{len(comps)} | 市场指标 {mcov}/4 | 路线图 {rcov}/{len(phases)}")

    # ── 3. DSL vs PDF ─────────────────────────────────────
    pdf_path = Path("backend/outputs/studio_assets") / f"{product.id}.pdf"
    if not pdf_path.is_file():
        print("[3] PDF 未导出（先调 POST /api/v1/product/{id}/export-pdf）"); return
    doc = pymupdf.open(str(pdf_path))
    missing_total = 0
    title_boxes = []
    for i, page_def in enumerate(pages):
        pdf_text = doc[i].get_text() if i < len(doc) else ""
        comp_texts = []
        for c in page_def.get("components", []):
            comp_texts.extend(text_of(c.get("data", {})))
        missing = [t for t in comp_texts if len(t) > 4 and t not in pdf_text]
        missing_total += len(missing)
        # 标题坐标：找最大字号 span
        best = None
        for b in doc[i].get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                for sp in l["spans"]:
                    if best is None or sp["size"] > best["size"]:
                        best = {"x0": sp["bbox"][0], "y0": sp["bbox"][1], "size": sp["size"]}
        if best:
            title_boxes.append((i + 1, round(best["x0"], 1), round(best["y0"], 1)))
    print(f"[3] 渲染完整性: 组件文本缺失 {missing_total} 条（应 0）")
    print(f"[3] 标题左上坐标: {title_boxes}")
    edge = [t for t in title_boxes if t[1] < 30]
    print(f"[3] 贴边判定: {'✗ 仍有贴边页 ' + str(edge) if edge else '✓ 全部在安全边距内 (x≥30pt)'}")
    doc.close()


if __name__ == "__main__":
    main()
