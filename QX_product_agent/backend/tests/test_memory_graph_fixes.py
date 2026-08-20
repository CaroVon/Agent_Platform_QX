"""
============================================================
记忆图谱修复测试（Phase D）
—— 双通道全局提升合并计数 / 手动 promote / rebuild-studio /
   Studio 记忆提取 / graph 过滤参数 / 空全局场景
============================================================
"""

import json
import uuid

import pytest
from httpx import AsyncClient


def _seed_studio_entity(product_id: str, name: str = "Anker",
                        product: str = "Anker 无线鼠标"):
    """直接经 repo 注入 Studio 任务记忆。"""
    from app.repositories import ProjectRepo

    repo = ProjectRepo()
    e1 = repo.save_memory_entity(
        scope="project", studio_product_id=product_id, type="company",
        name=name, summary="跨境电商 3C 品牌", confidence=0.8,
    )
    e2 = repo.save_memory_entity(
        scope="project", studio_product_id=product_id, type="product",
        name=product, summary="高性价比外设", confidence=0.7,
    )
    repo.save_memory_relation(
        source_id=str(e1.id), target_id=str(e2.id), relation_type="生产",
        evidence=json.dumps([{"studio_product_id": product_id}]),
    )
    return str(e1.id), str(e2.id)


def _seed_project_entity(project_id: str, name: str = "Anker"):
    from app.repositories import ProjectRepo

    repo = ProjectRepo()
    e = repo.save_memory_entity(
        scope="project", project_id=project_id, type="company",
        name=name, summary="research 项目实体", confidence=0.7,
    )
    return str(e.id)


async def _create_project(client: AsyncClient, topic: str) -> str:
    resp = await client.post("/api/v1/projects", json={"topic": topic})
    assert resp.status_code == 201, resp.text
    return resp.json()["project"]["id"]


# ══════════════════════════════════════════════════════════════
# 双通道合并计数：research + Studio 合计 ≥2 即可全局提升
# ══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_cross_channel_global_promotion(client: AsyncClient):
    """research 项目 1 次 + Studio 任务 1 次（各通道均 <2）→ 合并计数后提升。"""
    pid = await _create_project(client, "外设调研")
    spid = str(uuid.uuid4())
    _seed_project_entity(pid, name="罗技")
    _seed_studio_entity(spid, name="罗技", product="MX Master")

    from app.rag.memory_extraction import promote_global_memories

    assert promote_global_memories(pid) >= 1

    resp = await client.get("/api/v1/memory/graph?scope=global")
    globals_ = [n for n in resp.json()["nodes"] if n["scope"] == "global"]
    assert any(n["name"] == "罗技" for n in globals_)


@pytest.mark.asyncio
async def test_studio_promotion_merged_count(client: AsyncClient):
    """Studio 提升通道同样使用合并计数（1 Studio + 1 research → 提升）。"""
    pid = await _create_project(client, "无线鼠标研究")
    spid = str(uuid.uuid4())
    _seed_project_entity(pid, name="雷柏")
    e1, _e2 = _seed_studio_entity(spid, name="雷柏", product="雷柏 M300")

    from app.repositories import ProjectRepo
    from app.rag.studio_memory import promote_global_studio_memories

    repo = ProjectRepo()
    assert promote_global_studio_memories(repo, spid) >= 1
    assert repo.get_entity(e1) is not None  # 原实体保留
    assert repo.find_global_entity("雷柏") is not None


@pytest.mark.asyncio
async def test_single_channel_no_promotion(client: AsyncClient):
    """仅出现 1 次（任一通道）→ 不提升（保守语义保持）。"""
    spid = str(uuid.uuid4())
    _seed_studio_entity(spid, name="独有品牌XYZ", product="XYZ 产品")

    from app.repositories import ProjectRepo
    from app.rag.studio_memory import promote_global_studio_memories

    repo = ProjectRepo()
    assert promote_global_studio_memories(repo, spid) == 0
    assert repo.find_global_entity("独有品牌XYZ") is None


# ══════════════════════════════════════════════════════════════
# 手动 promote 端点（图谱侧栏「提升到全局记忆」）
# ══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_promote_entity_endpoint(client: AsyncClient):
    spid = str(uuid.uuid4())
    e1, _ = _seed_studio_entity(spid, name="手动提升品牌")

    resp = await client.post(f"/api/v1/memory/entities/{e1}/promote")
    assert resp.status_code == 200
    assert resp.json()["promoted"] is True

    # 幂等：已是全局 → promoted False 但不报错
    resp2 = await client.post(f"/api/v1/memory/entities/{e1}/promote")
    assert resp2.status_code == 200
    assert resp2.json()["promoted"] is False

    # 关系已复制到全局实体
    from app.repositories import ProjectRepo

    repo = ProjectRepo()
    g = repo.find_global_entity("手动提升品牌")
    assert g is not None
    rels = repo.list_relations_for_entity(str(g.id))
    assert len(rels) >= 1


@pytest.mark.asyncio
async def test_promote_entity_not_found(client: AsyncClient):
    resp = await client.post(f"/api/v1/memory/entities/{uuid.uuid4()}/promote")
    assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════
# rebuild-studio 端点（前端 studio: 前缀任务的重建入口）
# ══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_rebuild_studio_endpoint(client: AsyncClient, monkeypatch):
    """Studio 重建端点投递 Celery（mock 任务避免真实执行）。"""
    from conftest import TestSessionLocal

    from app.models.studio_product import StudioProduct, StudioProductStatus
    from app.tasks import knowledge_tasks

    async with TestSessionLocal() as session:
        product = StudioProduct(idea="记忆重建测试",
                                status=StudioProductStatus.COMPLETED)
        session.add(product)
        await session.commit()
        spid = str(product.id)

    submitted = {}

    class _FakeTask:
        def delay(self, product_id):
            submitted["product_id"] = product_id
            return type("R", (), {"id": "fake-task-id"})()

    monkeypatch.setattr(knowledge_tasks, "build_studio_memory_graph", _FakeTask())
    resp = await client.post(f"/api/v1/memory/rebuild-studio/{spid}")
    assert resp.status_code == 200
    assert resp.json()["product_id"] == spid
    assert submitted["product_id"] == spid


# ══════════════════════════════════════════════════════════════
# graph 过滤参数 + 空全局场景
# ══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_graph_entity_types_filter(client: AsyncClient):
    spid = str(uuid.uuid4())
    _seed_studio_entity(spid)
    resp = await client.get(
        f"/api/v1/memory/graph?scope=project&studio_product_id={spid}"
        "&entity_types=company")
    data = resp.json()
    assert data["meta"]["entity_count"] == 1
    assert data["nodes"][0]["type"] == "company"


@pytest.mark.asyncio
async def test_graph_empty_scope_no_fallback(client: AsyncClient):
    """scope=project 无 project_id/studio_product_id → 不回落 global（空结果）。"""
    resp = await client.get("/api/v1/memory/graph?scope=project")
    assert resp.status_code == 200
    data = resp.json()
    assert data["nodes"] == []
    assert data["meta"]["entity_count"] == 0
