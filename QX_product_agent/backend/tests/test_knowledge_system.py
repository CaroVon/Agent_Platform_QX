"""
============================================================
知识系统（P1-P3）集成测试
—— 图片入库 / 全局检索 / 相似任务 / 知识资产 / 领域经验 / 上传回写
============================================================
"""

import uuid

import pytest
from httpx import AsyncClient

# 1x1 像素 PNG（最小合法图片）
TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


async def _create_project(client: AsyncClient, topic: str = "AI眼镜行业") -> str:
    resp = await client.post("/api/v1/projects", json={"topic": topic})
    assert resp.status_code == 201, resp.text
    return resp.json()["project"]["id"]


# ══════════════════════════════════════════════════════════════
# P1: 图片知识库入库
# ══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_kb_images_upload(client: AsyncClient):
    """上传图片 → 私有落盘 + project_images 记录（status=pending，VL 异步分析）"""
    project_id = await _create_project(client)

    resp = await client.post(
        f"/api/v1/projects/{project_id}/kb-images",
        files=[("files", ("chart.png", TINY_PNG, "image/png"))],
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data["saved"]) == 1
    assert data["saved"][0]["status"] == "pending"

    # 图片库列表应包含该记录且带知识库字段
    list_resp = await client.get(f"/api/v1/projects/{project_id}/images")
    assert list_resp.status_code == 200
    images = list_resp.json()["images"]
    assert len(images) == 1
    assert images[0]["source"] == "upload"
    assert images[0]["status"] == "pending"
    assert images[0]["tags"] == []


@pytest.mark.asyncio
async def test_kb_images_rejects_bad_type(client: AsyncClient):
    """非图片扩展名 → 拒绝并返回 errors"""
    project_id = await _create_project(client)
    resp = await client.post(
        f"/api/v1/projects/{project_id}/kb-images",
        files=[("files", ("evil.txt", b"hello", "text/plain"))],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["saved"] == []
    assert len(data["errors"]) == 1


# ══════════════════════════════════════════════════════════════
# P1: 上传文档一致性修复（回写 Document 表）
# ══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_upload_docs_writes_document_row(client: AsyncClient):
    """TXT 上传 → 200 + 知识库文档列表可见（此前上传文件不回写 Document 表）"""
    project_id = await _create_project(client)
    resp = await client.post(
        f"/api/v1/projects/{project_id}/upload-docs",
        files={"file": ("note.txt", "智能手表核心差异点是显示技术。".encode("utf-8"), "text/plain")},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["chunk_count"] >= 1

    docs_resp = await client.get("/api/v1/knowledge/documents")
    assert docs_resp.status_code == 200
    titles = [d["section_title"] for d in docs_resp.json()]
    assert any("note.txt" in t for t in titles)


# ══════════════════════════════════════════════════════════════
# P1: 三层融合检索
# ══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_knowledge_search(client: AsyncClient):
    """全文检索：documents 文本兜底命中"""
    project_id = await _create_project(client)
    await client.post(
        f"/api/v1/projects/{project_id}/upload-docs",
        files={"file": ("ai.txt", "AI 眼镜的光学方案对比研究。".encode("utf-8"), "text/plain")},
    )

    resp = await client.get("/api/v1/knowledge/search", params={"q": "光学方案"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert any(h["source_url"].startswith("document://") for h in data["hits"])


# ══════════════════════════════════════════════════════════════
# P2: 相似任务判别 + 知识资产/领域经验端点
# ══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_similar_projects_endpoint(client: AsyncClient, test_session):
    """相似任务接口：返回结构完整（无历史任务时列表为空但不报错）"""
    pid1 = await _create_project(client, "智能手表产品分析")
    await _create_project(client, "新能源汽车电池分析")

    resp = await client.get(f"/api/v1/projects/{pid1}/similar")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["project_id"] == pid1
    assert isinstance(data["similar_projects"], list)
    assert isinstance(data["borrowable_experience"], str)
    # 画像已生成（topic_embedding 持久化）
    from sqlalchemy import select
    from app.models.project import Project
    result = await test_session.execute(select(Project).where(Project.id == uuid.UUID(pid1)))
    project = result.scalar_one()
    assert project.topic_embedding is not None


@pytest.mark.asyncio
async def test_knowledge_assets_and_domains_endpoints(client: AsyncClient):
    """知识资产与领域经验列表端点"""
    from app.repositories import ProjectRepo
    repo = ProjectRepo()
    repo.save_knowledge_asset(
        scope="global", title="企业规范.md", source="obsidian",
        source_url="obsidian://docs/企业规范.md", tags=["规范"], chunk_count=5,
    )
    project_id = await _create_project(client, "智能手表产品分析")
    repo.save_domain_experience(
        project_id=project_id, domain_tags=["industry:消费电子"],
        topic="智能手表产品分析", summary="显示技术是核心差异点。",
    )

    assets_resp = await client.get("/api/v1/knowledge/assets")
    assert assets_resp.status_code == 200
    assert assets_resp.json()["total"] >= 1

    domains_resp = await client.get("/api/v1/knowledge/domains")
    assert domains_resp.status_code == 200
    exps = domains_resp.json()["experiences"]
    assert len(exps) == 1
    assert exps[0]["summary"] == "显示技术是核心差异点。"


# ══════════════════════════════════════════════════════════════
# P2: 删除项目清理任务向量库/图片目录
# ══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_delete_project_cleans_kb_dirs(client: AsyncClient, tmp_path, monkeypatch):
    """删除项目 → chroma/bm25 任务库目录与 kb_images 目录被清理"""
    import os
    from app.core.config import get_settings

    chroma_base = str(tmp_path / "chroma")
    bm25_base = str(tmp_path / "bm25")
    out_dir = str(tmp_path / "out")
    monkeypatch.setattr(get_settings(), "CHROMA_PERSIST_DIR", chroma_base)
    monkeypatch.setattr(get_settings(), "BM25_PERSIST_DIR", bm25_base)
    monkeypatch.setattr(get_settings(), "OUTPUT_DIR", out_dir)

    project_id = await _create_project(client)
    # 制造任务库目录与图片目录
    os.makedirs(os.path.join(chroma_base, project_id), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "private", "kb_images", project_id), exist_ok=True)

    resp = await client.delete(f"/api/v1/projects/{project_id}")
    assert resp.status_code == 200

    assert not os.path.isdir(os.path.join(chroma_base, project_id))
    assert not os.path.isdir(os.path.join(out_dir, "private", "kb_images", project_id))
