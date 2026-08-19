"""
============================================================
记忆系统（P4）集成测试
—— 记忆图 API / 实体合并 / 全局提升 / 检索 / 生命周期
============================================================
"""

import json
import uuid

import pytest
from httpx import AsyncClient


async def _create_project(client: AsyncClient, topic: str = "智能手表分析") -> str:
    resp = await client.post("/api/v1/projects", json={"topic": topic})
    assert resp.status_code == 201, resp.text
    return resp.json()["project"]["id"]


def _seed_memory(project_id: str, name: str = "苹果", product: str = "Apple Watch"):
    """直接经 repo 注入模拟 LLM 抽取结果的记忆数据。"""
    from app.repositories import ProjectRepo
    repo = ProjectRepo()
    e1 = repo.save_memory_entity(
        scope="project", project_id=project_id, type="company",
        name=name, summary="消费电子巨头", confidence=0.8,
    )
    e2 = repo.save_memory_entity(
        scope="project", project_id=project_id, type="product",
        name=product, summary="旗舰智能手表", confidence=0.7,
    )
    repo.save_memory_relation(
        source_id=str(e1.id), target_id=str(e2.id), relation_type="推出",
        evidence=json.dumps([{"project_id": project_id}]),
    )
    repo.save_memory_insight(
        scope="project", project_id=project_id,
        content="屏幕是智能手表核心差异点",
        entity_ids=[str(e1.id), str(e2.id)],
    )
    return str(e1.id), str(e2.id)


# ══════════════════════════════════════════════════════════════
# P4: /memory API
# ══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_memory_graph_project_scope(client: AsyncClient):
    """项目记忆图：节点/边/洞察齐全"""
    pid = await _create_project(client)
    _seed_memory(pid)

    resp = await client.get(f"/api/v1/memory/graph?scope=project&project_id={pid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["meta"]["entity_count"] == 2
    assert data["meta"]["relation_count"] == 1
    names = {n["name"] for n in data["nodes"]}
    assert names == {"苹果", "Apple Watch"}
    edge = data["edges"][0]
    assert edge["relation"] == "推出"
    assert edge["expired"] is False


@pytest.mark.asyncio
async def test_memory_graph_global_promotion(client: AsyncClient):
    """跨项目同名实体 → 全局提升 + 全局图含邻接项目实体"""
    pid1 = await _create_project(client, "手表项目A")
    pid2 = await _create_project(client, "手表项目B")
    _seed_memory(pid1)
    _seed_memory(pid2, name="苹果", product="Apple Watch Ultra")

    from app.rag.memory_extraction import promote_global_memories
    assert promote_global_memories(pid2) >= 1

    resp = await client.get("/api/v1/memory/graph?scope=global")
    data = resp.json()
    globals_ = [n for n in data["nodes"] if n["scope"] == "global"]
    assert any(n["name"] == "苹果" for n in globals_)
    assert data["meta"]["relation_count"] >= 1


@pytest.mark.asyncio
async def test_memory_entity_detail_and_delete(client: AsyncClient):
    """实体详情 + 删除纠错"""
    pid = await _create_project(client)
    e1, e2 = _seed_memory(pid)

    resp = await client.get(f"/api/v1/memory/entities/{e1}")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["name"] == "苹果"
    assert detail["relations"][0]["relation"] == "推出"
    assert len(detail["insights"]) == 1

    del_resp = await client.delete(f"/api/v1/memory/entities/{e1}")
    assert del_resp.status_code == 200

    gone = await client.get(f"/api/v1/memory/entities/{e1}")
    assert gone.status_code == 404


@pytest.mark.asyncio
async def test_memory_insights_endpoint(client: AsyncClient):
    """洞察列表 + 关键词过滤"""
    pid = await _create_project(client)
    _seed_memory(pid)
    resp = await client.get(f"/api/v1/memory/insights?scope=project&project_id={pid}")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    filtered = await client.get(f"/api/v1/memory/insights?scope=project&project_id={pid}&q=屏幕")
    assert filtered.json()["total"] == 1
    none = await client.get(f"/api/v1/memory/insights?scope=project&project_id={pid}&q=不存在的词")
    assert none.json()["total"] == 0


@pytest.mark.asyncio
async def test_memory_rebuild_endpoint(client: AsyncClient):
    """手动重建任务投递（Celery 失败不影响响应）"""
    pid = await _create_project(client)
    resp = await client.post(f"/api/v1/memory/rebuild/{pid}")
    assert resp.status_code == 200
    assert resp.json()["project_id"] == pid


# ══════════════════════════════════════════════════════════════
# P4c: 生命周期
# ══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_decay_and_project_cleanup(client: AsyncClient):
    """置信度衰减 + 项目删除级联清理（全局实体保留）"""
    from datetime import datetime, timedelta, timezone
    from app.repositories import ProjectRepo
    from app.rag.memory_extraction import decay_memories, delete_project_memories

    pid = await _create_project(client)
    e1, _ = _seed_memory(pid)
    repo = ProjectRepo()

    # 造一个"久未引用"的实体
    stale = repo.save_memory_entity(
        scope="project", project_id=pid, type="market", name="旧市场数据",
        confidence=0.9,
        last_seen=datetime.now(timezone.utc) - timedelta(days=60),
    )
    assert repo.get_entity(str(stale.id)).confidence == 0.9
    count = decay_memories(days=30)
    assert count >= 1
    assert repo.get_entity(str(stale.id)).confidence == pytest.approx(0.85)

    # 项目删除 → 项目实体级联清理；全局实体保留
    delete_project_memories(pid)
    assert repo.get_entity(e1) is None
    assert repo.get_entity(str(stale.id)) is None
