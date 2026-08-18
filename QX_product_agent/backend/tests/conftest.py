"""
============================================================
测试配置与共享夹具
—— 为所有后端测试提供统一的数据库会话、客户端和 mock
============================================================
"""

import sys
import os
import uuid
import asyncio

# 测试环境关闭认证（认证行为由专门测试覆盖；避免每个用例携带 token）
os.environ.setdefault("AUTH_ENABLED", "false")
os.environ.setdefault("AUTH_BOOTSTRAP", "false")

# 测试数据库（与 Celery 同步引擎/API 异步引擎统一指向，保证 repo 层与端点一致）
TEST_DB_URL = "sqlite+aiosqlite:///./test_research.db"
os.environ["DATABASE_URL"] = TEST_DB_URL

# 确保 backend/ 在搜索路径中
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.main import create_app
from app.core.database import Base
from app.models import User

# ─── 测试数据库 ──────────────────────────────────────────────
test_engine = create_async_engine(TEST_DB_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class MockCeleryTask:
    """模拟 Celery AsyncResult —— 避免测试依赖 Redis"""
    _id = "mock-task-id-001"

    @property
    def id(self):
        return self._id

    def delay(self, *args, **kwargs):
        return self

    def get(self, timeout=None):
        return {"status": "completed"}


# ─── 应用实例（使用模块级 app，确保依赖覆盖生效） ──────────
from app.main import app


async def override_get_db():
    """覆写数据库依赖，使用测试数据库"""
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


app.dependency_overrides = {}  # 在 fixture 中设置


# ─── Fixtures ───────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    """为整个测试会话创建一个事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def setup_db():
    """每个测试前重建数据库表并插入默认用户"""
    # 先清空再建表：保证新增列（知识系统 P1-P3）在既有 DB 文件上生效
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        user = User(
            id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            email="admin@test.com",
            username="admin",
        )
        session.add(user)
        await session.commit()

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    """创建带覆写数据库依赖的 HTTP 测试客户端"""
    from app.core.database import get_db
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def test_session():
    """直接提供测试数据库会话（供测试直接写入/读取数据）。"""
    async with TestSessionLocal() as session:
        yield session
