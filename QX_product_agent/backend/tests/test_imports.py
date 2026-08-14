"""
============================================================
导入测试 —— 验证所有关键模块能正常导入且基本功能正常
============================================================
"""

import uuid
import pytest


class TestCoreImports:
    """核心模块导入验证"""

    def test_config_import(self):
        from app.core.config import get_settings
        s = get_settings()
        assert s.APP_NAME == "Product Analysis Agent API"
        assert s.APP_VERSION == "1.0.0"

    def test_schemas_import_and_validation(self):
        from app.schemas import ProjectCreateRequest, ProjectResponse

        # Schema 校验
        req = ProjectCreateRequest(topic="AI眼镜行业")
        assert req.topic == "AI眼镜行业"

        # 最小 topic 长度校验
        with pytest.raises(Exception):
            ProjectCreateRequest(topic="")

        # 响应模型
        resp = ProjectResponse(
            id=uuid.uuid4(),
            topic="test",
            status="preparing_data",
            created_at="2024-01-01T00:00:00Z",
        )
        assert resp.topic == "test"

    def test_models_import(self):
        from app.models import (
            Base, User, Project, Task, Document, DocumentBlock,
            ProjectStatus, TaskType, TaskStatus, ProjectLog, LogLevel,
        )
        # 枚举值验证
        assert ProjectStatus.PREPARING_DATA.value == "preparing_data"
        assert ProjectStatus.COMPLETED.value == "completed"
        assert TaskType.SEARCH.value == "search"
        assert TaskType.WRITE_SECTION.value == "write_section"
        assert TaskStatus.PENDING.value == "pending"
        assert LogLevel.INFO.value == "info"

    def test_celery_app_import(self):
        from app.core.celery_app import celery_app
        assert celery_app.main == "research_agent"

    def test_fastapi_app_creation(self):
        from app.main import create_app
        app = create_app()
        routes = [r.path for r in app.routes if hasattr(r, 'path')]
        assert "/health" in routes
        assert "/health/db" in routes
        assert "/api/v1/projects" in routes
        assert "/api/v1/editor/revise" in routes

    def test_outline_parser_import(self):
        from app.shared.outline_parser import extract_sections
        sections = extract_sections("# Title\n## 1. 概述\n## 2. 分析")
        assert len(sections) == 2

    def test_project_repo_import(self):
        from app.repositories import ProjectRepo
        repo = ProjectRepo()
        assert repo is not None

    def test_database_engine_exists(self):
        from app.core.database import engine
        assert engine is not None
