"""
============================================================
API 集成测试 —— 验证所有核心路由和状态机流转
使用 SQLite 内存数据库，Mock Celery 任务
============================================================
"""

import uuid
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.project import Project, ProjectStatus
from app.models.task import TaskStatus


# ─── Mock Celery 任务 ─────────────────────────────────────────
class MockCeleryTask:
    _id = "mock-task-id-001"

    @property
    def id(self):
        return self._id

    def delay(self, *args, **kwargs):
        return self

    def get(self, timeout=None):
        return {"status": "completed"}


mock_sources = patch(
    "app.api.v1.endpoints.projects.prepare_sources_workflow",
    MockCeleryTask(),
)
mock_outline = patch(
    "app.api.v1.endpoints.projects.generate_outline_workflow",
    MockCeleryTask(),
)
mock_draft = patch(
    "app.api.v1.endpoints.projects.run_draft_sections_workflow",
    MockCeleryTask(),
)


# ══════════════════════════════════════════════════════════
# 基础 API 测试
# ══════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """健康检查接口"""
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["app"] == "Product Analysis Agent API"


@pytest.mark.asyncio
async def test_health_check_db(client: AsyncClient):
    """数据库健康检查接口"""
    resp = await client.get("/health/db")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert "projects" in data["tables"]


@pytest.mark.asyncio
async def test_create_project(client: AsyncClient):
    """创建项目 —— 验证返回 201 + 初始状态"""
    with mock_sources:
        resp = await client.post("/api/v1/projects", json={"topic": "AI眼镜行业"})
    assert resp.status_code == 201, f"创建失败: {resp.text}"
    data = resp.json()
    assert data["project"]["topic"] == "AI眼镜行业"
    assert data["project"]["status"] == "preparing_data"
    assert "celery_task_id" in data


@pytest.mark.asyncio
async def test_get_project_status(client: AsyncClient):
    """查询项目状态 —— 验证 progress + tasks"""
    with mock_sources:
        create_resp = await client.post("/api/v1/projects", json={"topic": "AI眼镜行业"})
    project_id = create_resp.json()["project"]["id"]

    resp = await client.get(f"/api/v1/projects/{project_id}/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == project_id
    assert data["progress"]["total_tasks"] > 0
    assert len(data["tasks"]) > 0


@pytest.mark.asyncio
async def test_download_before_complete_returns_409(client: AsyncClient):
    """未完成时下载应返回 409 Conflict"""
    with mock_sources:
        create_resp = await client.post("/api/v1/projects", json={"topic": "测试项目"})
    project_id = create_resp.json()["project"]["id"]

    resp = await client.get(f"/api/v1/projects/{project_id}/download")
    assert resp.status_code == 409
    assert "生成中" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_list_projects(client: AsyncClient):
    """项目列表 —— 按创建时间倒序"""
    with mock_sources:
        for topic in ["AI眼镜行业", "新国潮软床", "3维交互编辑器"]:
            await client.post("/api/v1/projects", json={"topic": topic})

    resp = await client.get("/api/v1/projects")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 3
    topics = [p["topic"] for p in data]
    assert "AI眼镜行业" in topics


@pytest.mark.asyncio
async def test_project_not_found_404(client: AsyncClient):
    """不存在的项目应返回 404"""
    fake_id = "00000000-0000-0000-0000-000000009999"
    resp = await client.get(f"/api/v1/projects/{fake_id}/status")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_schema_validation_422(client: AsyncClient):
    """Schema 校验 —— 空 topic 返回 422"""
    resp = await client.post("/api/v1/projects", json={"topic": ""})
    assert resp.status_code == 422

    resp = await client.post("/api/v1/projects", json={})
    assert resp.status_code == 422


# ══════════════════════════════════════════════════════════
# 🎯 状态机交互节点测试
# ══════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_source_review_state_constraint(client: AsyncClient):
    """交互节点1：非 waiting_for_sources 状态应阻断资料审核"""
    with mock_sources:
        create_resp = await client.post("/api/v1/projects", json={"topic": "状态机测试"})
    project_id = create_resp.json()["project"]["id"]

    # preparing_data 状态 — GET sources 应返回 409
    resp = await client.get(f"/api/v1/projects/{project_id}/sources")
    assert resp.status_code == 409

    # 审核资料也应被阻断
    resp = await client.post(
        f"/api/v1/projects/{project_id}/review-sources",
        json={"selected_urls": ["https://example.com"]},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_outline_approval_flow(client: AsyncClient):
    """交互节点2：大纲审批完整流程"""
    from app.core.database import get_db
    from conftest import TestSessionLocal

    with mock_sources:
        create_resp = await client.post("/api/v1/projects", json={"topic": "AI眼镜行业"})
    project_id = create_resp.json()["project"]["id"]

    # 手动推进到 WAITING_FOR_OUTLINE
    async with TestSessionLocal() as session:
        result = await session.execute(
            select(Project).where(Project.id == uuid.UUID(project_id))
        )
        project = result.scalar_one()
        project.status = ProjectStatus.WAITING_FOR_OUTLINE
        project.outline_content = "# 报告\n## 1. 概述\n## 2. 分析\n## 3. 结论"
        await session.commit()

    # 审批大纲
    with mock_draft:
        resp = await client.post(
            f"/api/v1/projects/{project_id}/approve-outline",
            json={"outline": "# 报告\n## 1. 行业概述\n## 2. 市场分析\n## 3. 竞品研究"},
        )
    assert resp.status_code == 200, f"审批失败: {resp.text}"
    data = resp.json()
    assert data["new_status"] == "drafting"
    assert data["sections_count"] == 3

    # 验证 DocumentBlock 占位已创建
    resp = await client.get(f"/api/v1/projects/{project_id}/blocks")
    assert resp.status_code == 200
    assert len(resp.json()["blocks"]) == 3

    # 重复审批应返回 409
    resp = await client.post(
        f"/api/v1/projects/{project_id}/approve-outline",
        json={"outline": "# Test\n## 1. S1"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_editor_revise_endpoint(client: AsyncClient):
    """Inline AI 编辑器改写 —— 润色 + 自定义指令 + 校验"""
    # 快速指令
    resp = await client.post(
        "/api/v1/editor/revise",
        json={
            "selected_text": "AI眼镜市场在2025年达到1000亿规模，增长迅速。",
            "instruction": "润色",
        },
    )
    assert resp.status_code == 200
    assert len(resp.json()["revised_text"]) > 0

    # 自定义指令
    resp = await client.post(
        "/api/v1/editor/revise",
        json={
            "selected_text": "The product has good features.",
            "instruction": "使表达更正式",
        },
    )
    assert resp.status_code == 200

    # 空文本校验
    resp = await client.post(
        "/api/v1/editor/revise",
        json={"selected_text": "", "instruction": "润色"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_full_state_machine_flow(client: AsyncClient):
    """🎯 端到端状态机流转测试"""
    from conftest import TestSessionLocal

    # 1. 创建项目
    with mock_sources:
        create_resp = await client.post("/api/v1/projects", json={"topic": "状态机端到端测试"})
    assert create_resp.status_code == 201
    project_id = create_resp.json()["project"]["id"]

    # 2. 模拟 → WAITING_FOR_SOURCES
    async with TestSessionLocal() as session:
        result = await session.execute(
            select(Project).where(Project.id == uuid.UUID(project_id))
        )
        p = result.scalar_one()
        p.status = ProjectStatus.WAITING_FOR_SOURCES
        await session.commit()

    # 3. 审核资料 → PREPARING_OUTLINE
    with mock_outline:
        resp = await client.post(
            f"/api/v1/projects/{project_id}/review-sources",
            json={"selected_urls": ["https://example.com/s1"]},
        )
    assert resp.status_code == 200
    assert resp.json()["new_status"] == "preparing_outline"

    # 4. 模拟 → WAITING_FOR_OUTLINE
    async with TestSessionLocal() as session:
        result = await session.execute(
            select(Project).where(Project.id == uuid.UUID(project_id))
        )
        p = result.scalar_one()
        p.status = ProjectStatus.WAITING_FOR_OUTLINE
        p.outline_content = "# 报告\n## 1. 概述\n## 2. 分析\n## 3. 结论"
        await session.commit()

    # 5. 审批大纲 → DRAFTING
    with mock_draft:
        resp = await client.post(
            f"/api/v1/projects/{project_id}/approve-outline",
            json={"outline": "# 报告\n## 1. 概述\n## 2. 分析\n## 3. 结论"},
        )
    assert resp.status_code == 200
    assert resp.json()["new_status"] == "drafting"
    assert resp.json()["sections_count"] == 3

    # 6. 验证 blocks + tasks
    resp = await client.get(f"/api/v1/projects/{project_id}/blocks")
    assert len(resp.json()["blocks"]) == 3

    resp = await client.get(f"/api/v1/projects/{project_id}/status")
    write_tasks = [t for t in resp.json()["tasks"] if t["task_type"] == "write_section"]
    assert len(write_tasks) == 3

    # 7. 模拟 → COMPLETED
    async with TestSessionLocal() as session:
        result = await session.execute(
            select(Project).where(Project.id == uuid.UUID(project_id))
        )
        p = result.scalar_one()
        p.status = ProjectStatus.COMPLETED
        await session.commit()

    # 8. 最终验证
    resp = await client.get(f"/api/v1/projects/{project_id}/status")
    assert resp.json()["project_status"] == "completed"
