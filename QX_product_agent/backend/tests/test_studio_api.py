"""
============================================================
AI Product Studio API 集成测试
—— POST /api/v1/product/create + 资产包查询 + PDF 导出
============================================================
"""

import json
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.models.studio_product import StudioProduct, StudioProductStatus


class MockCeleryTask:
    _id = "mock-product-task-001"

    @property
    def id(self):
        return self._id

    def delay(self, *args, **kwargs):
        return self

    def get(self, timeout=None):
        return {"status": "completed"}


mock_pipeline = patch(
    "app.api.v1.endpoints.product.run_product_studio_pipeline",
    MockCeleryTask(),
)


def _package_payload() -> dict:
    """最小完整资产包（六节点齐备）。"""
    return {
        "idea": "AI 健身应用",
        "requirement": {"idea": "AI 健身应用", "goals": ["个性化训练"]},
        "research": {
            "market_size": {"summary": "百亿市场"},
            "competitors": [{"name": "Keep", "positioning": "大众健身"}],
            "customer_pain_points": ["不会安排计划"],
            "industry_trends": ["AI 教练化"],
        },
        "competitor_analysis": {
            "competitors": [{"name": "Keep", "positioning": "大众健身"}],
            "matrix": {"dimensions": ["定位"], "profiles": [{"name": "Keep", "positioning": "x"}]},
            "competitive_landscape": "头部集中",
            "differentiation_opportunities": ["个性化"],
        },
        "strategy": {
            "positioning": "AI 私教",
            "personas": [{"name": "小雅", "role": "新手"}],
            "features": [{"name": "智能计划", "priority": "P0"}],
            "roadmap": [{"phase": "Phase 1", "title": "MVP"}],
            "prd_sections": [{"title": "产品概述", "content": "正文"}],
        },
        "design": {
            "user_flow": [{"step": "注册"}],
            "pages": [{"name": "首页"}],
            "components": [{"name": "滑块", "kind": "input"}],
        },
        "presentation": {
            "topic": "AI 健身应用",
            "slides": [
                {"id": "s1", "title": "封面", "layout_type": "cover"},
                {"id": "s2", "title": "市场", "layout_type": "bullets",
                 "blocks": [{"id": "b1", "block_type": "bullets", "content": "趋势一\n趋势二"}]},
            ],
            "sections": [{"title": "市场", "slide_ids": ["s1", "s2"]}],
        },
        "meta": {
            "idea": "AI 健身应用",
            "created_at": "2026-01-01T00:00:00+00:00",
            "node_status": {"research": "completed"},
            "errors": {},
        },
    }


async def _insert_completed_product(db, package: dict | None = None) -> StudioProduct:
    product = StudioProduct(
        idea="AI 健身应用",
        status=StudioProductStatus.COMPLETED,
        asset_package=json.dumps(package or _package_payload(), ensure_ascii=False),
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


@pytest.mark.asyncio
async def test_create_product(client: AsyncClient):
    with mock_pipeline:
        resp = await client.post(
            "/api/v1/product/create", json={"idea": "Build an AI fitness application"}
        )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["idea"] == "Build an AI fitness application"
    assert data["status"] == "queued"
    uuid.UUID(data["product_id"])  # 合法 UUID


@pytest.mark.asyncio
async def test_create_product_is_idempotent(client: AsyncClient):
    """重复点击或重复投递相同想法只返回原产品，不再派发 Celery 任务。"""
    with mock_pipeline:
        first = await client.post(
            "/api/v1/product/create", json={"idea": "  AI 睡眠助手  "}
        )
        second = await client.post(
            "/api/v1/product/create", json={"idea": "AI   睡眠助手"}
        )

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["product_id"] == first.json()["product_id"]


@pytest.mark.asyncio
async def test_create_product_validates_idea(client: AsyncClient):
    resp = await client.post("/api/v1/product/create", json={"idea": ""})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_product_queued(client: AsyncClient):
    with mock_pipeline:
        created = await client.post("/api/v1/product/create", json={"idea": "AI 教育助手"})
    product_id = created.json()["product_id"]

    resp = await client.get(f"/api/v1/product/{product_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "queued"
    assert data["research"] is None
    assert data["presentation"] is None


@pytest.mark.asyncio
async def test_get_product_completed_returns_assets(client: AsyncClient, test_session):
    async with test_session as session:
        product = await _insert_completed_product(session)
        product_id = str(product.id)

    resp = await client.get(f"/api/v1/product/{product_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["research"]["market_size"]["summary"] == "百亿市场"
    assert data["strategy"]["positioning"] == "AI 私教"
    assert data["design"]["pages"][0]["name"] == "首页"
    assert data["presentation"]["slides"][0]["layout_type"] == "cover"
    assert data["node_status"]["research"] == "completed"


@pytest.mark.asyncio
async def test_list_products(client: AsyncClient):
    with mock_pipeline:
        await client.post("/api/v1/product/create", json={"idea": "产品 A"})

    resp = await client.get("/api/v1/product")
    assert resp.status_code == 200
    items = resp.json()
    assert any(item["idea"] == "产品 A" for item in items)


@pytest.mark.asyncio
async def test_get_product_404(client: AsyncClient):
    resp = await client.get(f"/api/v1/product/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_export_pdf(client: AsyncClient, test_session):
    from app.core.config import get_settings

    async with test_session as session:
        product = await _insert_completed_product(session)
        product_id = str(product.id)

    resp = await client.post(f"/api/v1/product/{product_id}/export-pdf")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["pdf_url"].endswith(f"{product_id}.pdf")

    # 验证 PDF 真实落盘并清理
    pdf_path = Path(get_settings().OUTPUT_DIR) / "studio_assets" / f"{product_id}.pdf"
    assert pdf_path.is_file() and pdf_path.stat().st_size > 1000
    pdf_path.unlink()


@pytest.mark.asyncio
async def test_export_pdf_rejects_queued(client: AsyncClient):
    with mock_pipeline:
        created = await client.post("/api/v1/product/create", json={"idea": "未完成"})
    product_id = created.json()["product_id"]

    resp = await client.post(f"/api/v1/product/{product_id}/export-pdf")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_update_presentation(client: AsyncClient, test_session):
    """编辑器保存：PATCH 回写 Presentation DSL。"""
    async with test_session as session:
        product = await _insert_completed_product(session)
        product_id = str(product.id)

    updated = {
        "title": "更新后的演示",
        "theme": {"id": "default"},
        "pages": [
            {"id": "p1", "type": "cover", "layout": "cover", "title": "新封面",
             "components": [{"id": "c1", "type": "text", "data": {"text": "编辑后的内容"}}]},
        ],
    }
    resp = await client.patch(
        f"/api/v1/product/{product_id}/presentation",
        json={"presentation": updated},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["detail"] == "演示已更新"

    get_resp = await client.get(f"/api/v1/product/{product_id}")
    data = get_resp.json()
    assert data["presentation"]["title"] == "更新后的演示"
    assert data["presentation"]["pages"][0]["title"] == "新封面"


@pytest.mark.asyncio
async def test_update_presentation_404(client: AsyncClient):
    resp = await client.patch(
        f"/api/v1/product/{uuid.uuid4()}/presentation",
        json={"presentation": {"title": "x", "pages": []}},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_search_product_images(client: AsyncClient, test_session):
    """编辑器素材搜索：无状态 DuckDuckGo，结果不持久化。"""
    async with test_session as session:
        product = await _insert_completed_product(session)
        product_id = str(product.id)

    fake_results = [
        {"title": "国潮床品图", "image": "https://img.example.com/a.jpg", "url": "https://src.example.com/a"},
        {"title": "无效条目", "image": "", "url": "https://src.example.com/b"},
    ]
    with patch("app.search.image_search.search_images", return_value=fake_results):
        resp = await client.post(
            f"/api/v1/product/{product_id}/search-images",
            json={"query": "国潮床品", "max_results": 8, "search_depth": 5},
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total_count"] == 1  # 空 image 条目被过滤
    assert data["images"][0]["image_url"] == "https://img.example.com/a.jpg"
    assert data["images"][0]["query"] == "国潮床品"


@pytest.mark.asyncio
async def test_search_product_images_404(client: AsyncClient):
    resp = await client.post(
        f"/api/v1/product/{uuid.uuid4()}/search-images",
        json={"query": "测试"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_upload_product_asset(client: AsyncClient, test_session):
    """编辑器本地上传：文件落盘并返回公开 URL。"""
    async with test_session as session:
        product = await _insert_completed_product(session)
        product_id = str(product.id)

    resp = await client.post(
        f"/api/v1/product/{product_id}/assets",
        files={"file": ("local.png", b"\x89PNG\r\n\x1a\nfake-image-bytes", "image/png")},
    )
    assert resp.status_code == 200, resp.text
    url = resp.json()["url"]
    assert url.startswith(f"/api/v1/files/assets/{product_id}/")
    assert url.endswith(".png")

    # 静态文件可访问（conftest 挂载 output dir）
    static = await client.get(url)
    assert static.status_code == 200


@pytest.mark.asyncio
async def test_upload_product_asset_404(client: AsyncClient):
    resp = await client.post(
        f"/api/v1/product/{uuid.uuid4()}/assets",
        files={"file": ("local.png", b"data", "image/png")},
    )
    assert resp.status_code == 404
