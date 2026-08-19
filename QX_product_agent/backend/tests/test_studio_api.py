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


# ================================================================
# Key Words —— 产品关键词组（AI 总结 + 用户编辑）
# ================================================================

@patch("app.services.product_keywords.generate_keywords")
@patch("app.services.product_keywords._save_keywords")
async def test_generate_and_save_keywords_skips_existing(
    mock_save, mock_generate, client: AsyncClient, test_session
):
    """已有关键词（AI 生成或用户编辑）时跳过重新生成，不覆盖用户修改。"""
    from app.services.product_keywords import generate_and_save_keywords

    async with test_session as session:
        product = await _insert_completed_product(session)
        product.keywords = json.dumps(
            {"design": ["用户自定义"], "function": [], "appearance": [],
             "audience": [], "scenario": []},
            ensure_ascii=False,
        )
        await session.commit()
        product_id = str(product.id)

    result = generate_and_save_keywords(product_id, _package_payload(), llm=object())
    assert result["design"] == ["用户自定义"]
    mock_generate.assert_not_called()
    mock_save.assert_not_called()


async def test_generate_and_save_keywords_writes(client: AsyncClient, test_session):
    """生成路径：LLM 输出 → 规范化去重 → 写入 keywords 列与资产包。"""
    from app.services.product_keywords import generate_and_save_keywords

    async with test_session as session:
        product = await _insert_completed_product(session)
        product_id = str(product.id)

    class FakeLLM:
        def complete_json(self, messages, **kwargs):
            return {
                "design": ["极简", "圆角"],
                "function": ["AI 提醒"],
                "appearance": [],
                "audience": ["上班族"],
                "scenario": ["睡前", "睡前"],
            }

    groups = generate_and_save_keywords(product_id, _package_payload(), llm=FakeLLM())
    assert groups["design"] == ["极简", "圆角"]
    assert groups["scenario"] == ["睡前"]  # 去重

    detail = await client.get(f"/api/v1/product/{product_id}")
    assert detail.status_code == 200
    assert detail.json()["keywords"] == groups


async def test_update_product_keywords(client: AsyncClient, test_session):
    """用户编辑关键词：PUT 保存后 GET 返回最新值，且同步写入资产包。"""
    async with test_session as session:
        product = await _insert_completed_product(session)
        product_id = str(product.id)

    groups = {
        "design": ["极简", "圆角"],
        "function": ["AI 提醒", "睡眠监测"],
        "appearance": ["雾面质感"],
        "audience": ["上班族"],
        "scenario": ["睡前"],
    }
    resp = await client.put(f"/api/v1/product/{product_id}/keywords", json={"keywords": groups})
    assert resp.status_code == 200, resp.text
    assert resp.json()["keywords"] == groups

    detail = await client.get(f"/api/v1/product/{product_id}")
    assert detail.status_code == 200
    assert detail.json()["keywords"] == groups

    # 资产包同步包含 keywords（作为产品资产的一部分）
    async with test_session as session:
        product = await session.get(StudioProduct, uuid.UUID(product_id))
        package = json.loads(product.asset_package)
    assert package["keywords"] == groups


async def test_update_product_keywords_normalizes_and_404(client: AsyncClient, test_session):
    """编辑保存时清洗空白/重复；非法结构由 schema 拒绝；产品不存在返回 404。"""
    async with test_session as session:
        product = await _insert_completed_product(session)
        product_id = str(product.id)

    resp = await client.put(
        f"/api/v1/product/{product_id}/keywords",
        json={"keywords": {"design": [" 极简 ", "", "极简"], "bogus": ["保留"], "function": []}},
    )
    assert resp.status_code == 200, resp.text
    saved = resp.json()["keywords"]
    assert saved["design"] == ["极简"]  # 去空白 + 去重
    assert saved["function"] == []
    assert saved["bogus"] == ["保留"]  # 未知分组键不丢弃

    # 非字符串 / 非列表结构：schema 层直接 422（防御非法输入）
    resp = await client.put(
        f"/api/v1/product/{product_id}/keywords",
        json={"keywords": {"design": [3], "function": "非列表"}},
    )
    assert resp.status_code == 422

    resp = await client.put(
        f"/api/v1/product/{uuid.uuid4()}/keywords",
        json={"keywords": {"design": ["x"]}},
    )
    assert resp.status_code == 404


def test_normalize_keywords_service():
    """服务层规范化：固定五组、去空白/去重/限长、丢弃非法项。"""
    from app.services.product_keywords import _normalize_keywords

    out = _normalize_keywords({
        "design": [" 极简 ", "", "极简", 3, None],
        "function": "非列表",
        "bogus": ["x"],
    })
    assert out["design"] == ["极简"]
    assert out["function"] == []
    assert set(out.keys()) == {"design", "function", "appearance", "audience", "scenario"}
    assert "bogus" not in out


async def test_list_products_includes_keywords(client: AsyncClient, test_session):
    """列表接口轻量返回关键词（侧边栏每行展示）。"""
    async with test_session as session:
        product = await _insert_completed_product(session)
        product.keywords = json.dumps({"design": ["极简"], "function": ["AI 提醒"]}, ensure_ascii=False)
        await session.commit()

    resp = await client.get("/api/v1/product")
    assert resp.status_code == 200
    item = next(i for i in resp.json() if i["product_id"] == str(product.id))
    assert item["keywords"] == {"design": ["极简"], "function": ["AI 提醒"]}
