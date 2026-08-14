"""
============================================================
Knowledge Base API 测试 —— 全局文档聚合端点
============================================================
"""

import uuid

import pytest
from httpx import AsyncClient

from app.models.document import Document
from app.models.project import Project, ProjectStatus


@pytest.mark.asyncio
async def test_knowledge_documents_empty(client: AsyncClient):
    resp = await client.get("/api/v1/knowledge/documents")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_knowledge_documents_lists_project_docs(client: AsyncClient, test_session):
    async with test_session as session:
        project = Project(
            id=uuid.uuid4(),
            owner_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            topic="知识库测试项目",
            status=ProjectStatus.COMPLETED,
        )
        session.add(project)
        await session.flush()
        session.add(
            Document(
                project_id=project.id,
                section_title="市场分析章节",
                section_order=10,
                content="测试内容",
            )
        )
        await session.commit()

    resp = await client.get("/api/v1/knowledge/documents")
    assert resp.status_code == 200
    docs = resp.json()
    assert len(docs) == 1
    assert docs[0]["project_topic"] == "知识库测试项目"
    assert docs[0]["section_title"] == "市场分析章节"
    assert docs[0]["document_id"]
