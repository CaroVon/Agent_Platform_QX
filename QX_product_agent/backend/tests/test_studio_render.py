"""
============================================================
P0 审计测试 —— studio_render PDF 内容完整度
============================================================

验证 P0 修复目标：
  1. 每页标题完整（不再因 grid 塌陷 + overflow 截断丢失）
  2. 源内容逐行可寻回（内容不丢失，允许自动分页）
  3. 密度分级：长内容页字号自动缩小（compact class 生效）
"""

import json
from pathlib import Path

import pytest

from app.services.studio_render import render_slides_html, slides_to_pdf


def _package(slides: list[dict]) -> dict:
    return {
        "idea": "审计测试",
        "presentation": {"topic": "审计测试", "slides": slides, "sections": []},
    }


def _long_text_block(block_id: str, lines: int) -> dict:
    content = "\n".join(f"要点内容行{i}：这是一段用于审计测试的文本内容。" for i in range(lines))
    return {"id": block_id, "block_type": "bullets", "content": content}


def test_two_column_no_grid_and_titles_present(tmp_path):
    """two_column 布局（原 grid 塌陷场景）：标题与双栏内容必须完整。"""
    slides = [
        {
            "id": "s1",
            "title": "用户画像",
            "layout_type": "two_column",
            "blocks": [
                {"id": "b1", "block_type": "text", "content": "画像甲行为特征描述"},
                _long_text_block("b2", 3),
                {"id": "b3", "block_type": "text", "content": "画像乙行为特征描述"},
                _long_text_block("b4", 3),
            ],
        }
    ]
    pdf = tmp_path / "audit_two_column.pdf"
    slides_to_pdf(_package(slides), str(pdf))

    import pymupdf

    doc = pymupdf.open(str(pdf))
    full_text = "\n".join(page.get_text() for page in doc)
    assert "用户画像" in full_text
    assert "画像甲行为特征描述" in full_text
    assert "画像乙行为特征描述" in full_text
    for i in range(3):
        assert f"要点内容行{i}" in full_text
    doc.close()


def test_long_content_not_truncated(tmp_path):
    """长内容页：允许自动分页，但每个内容行必须可寻回（不截断）。"""
    slides = [
        {
            "id": "s1",
            "title": "密集内容页",
            "layout_type": "bullets",
            "blocks": [_long_text_block("b1", 14)],
        }
    ]
    pdf = tmp_path / "audit_long.pdf"
    slides_to_pdf(_package(slides), str(pdf))

    import pymupdf

    doc = pymupdf.open(str(pdf))
    full_text = "\n".join(page.get_text() for page in doc)
    assert "密集内容页" in full_text
    missing = [i for i in range(14) if f"要点内容行{i}" not in full_text]
    assert missing == [], f"丢失内容行: {missing}"
    doc.close()


def test_density_class_applied_for_long_blocks():
    """密度分级：内容量大的页应获得 density-compact class。"""
    import re

    def section_class(slides):
        html = render_slides_html(_package(slides))
        match = re.search(r'<section class="slide([^"]*)"', html)
        return match.group(1) if match else ""

    cls = section_class(
        [
            {
                "id": "s1",
                "title": "长页",
                "layout_type": "bullets",
                "blocks": [_long_text_block("b1", 20)],
            }
        ]
    )
    assert "density-compact" in cls
    cls_short = section_class(
        [
            {
                "id": "s1",
                "title": "短页",
                "layout_type": "bullets",
                "blocks": [{"id": "b1", "block_type": "text", "content": "一句话"}],
            }
        ]
    )
    assert "density-compact" not in cls_short


def test_real_asset_package_audit(tmp_path):
    """真实资产包审计：DB 中最新 completed 包 → 标题无缺、页数 ≥ slides。"""
    import pymupdf
    from sqlalchemy.orm import Session

    from app.core.celery_db import get_sync_engine
    from app.models.studio_product import StudioProduct, StudioProductStatus

    with Session(get_sync_engine()) as s:
        p = (
            s.query(StudioProduct)
            .filter(StudioProduct.status == StudioProductStatus.COMPLETED)
            .order_by(StudioProduct.created_at.desc())
            .first()
        )
    if p is None:
        pytest.skip("无 completed 资产包")

    package = json.loads(p.asset_package)
    slides = (package.get("presentation") or {}).get("slides") or []
    pdf = tmp_path / "audit_real.pdf"
    slides_to_pdf(package, str(pdf))

    doc = pymupdf.open(str(pdf))
    full_text = "\n".join(page.get_text() for page in doc)
    missing_titles = [s["title"] for s in slides if s.get("title") and s["title"] not in full_text]
    assert missing_titles == [], f"标题丢失: {missing_titles}"
    assert len(doc) >= len(slides), f"页数 {len(doc)} < slides {len(slides)}（内容被截断）"
    doc.close()
