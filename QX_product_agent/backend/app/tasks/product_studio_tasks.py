"""
============================================================
Product Studio 流水线任务
—— 桥接 QX 后端与 agent-platform（LangGraph 多 Agent 工作流）
============================================================

职责（对应迁移策略 Phase 1/2）:
  1. 把 QX Settings 的模型配置桥接为平台层环境变量（AGENT_PLATFORM_*）
  2. 把 agent-platform / agents 目录加入 sys.path（平台层独立于业务代码）
  3. 构建四个专业 Agent + LangGraph 工作流并执行
  4. 资产包（结构化 JSON）持久化到 studio_products 表
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

from celery import Task

from app.core.celery_app import celery_app
from app.core.celery_db import get_sync_engine
from app.core.config import get_settings
from app.models.studio_product import StudioProduct, StudioProductStatus

logger = logging.getLogger(__name__)

# 项目根: backend/app/tasks/xxx.py → parents[3] = QX_product_agent
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_WORKSPACE_ROOT = _PROJECT_ROOT.parent  # ~/dev/agents


class ProductStudioTask(Task):
    """惰性加载 Settings 单例（与 WritingTask 同一模式）。"""

    _settings = None

    @property
    def settings(self):
        if self._settings is None:
            self._settings = get_settings()
        return self._settings


def _bridge_env(settings) -> None:
    """把 QX 配置桥接为平台层环境变量（平台层只读自己的环境变量）。"""
    os.environ.setdefault("AGENT_PLATFORM_LLM_API_KEY", settings.DEEPSEEK_API_KEY)
    os.environ.setdefault("AGENT_PLATFORM_LLM_BASE_URL", settings.DEEPSEEK_BASE_URL)
    os.environ.setdefault("AGENT_PLATFORM_LLM_MODEL", settings.DEEPSEEK_MODEL)
    if settings.TAVILY_API_KEY:
        os.environ.setdefault("AGENT_PLATFORM_TAVILY_API_KEY", settings.TAVILY_API_KEY)
    # 记忆目录放在业务输出目录下，随项目输出一起管理
    os.environ.setdefault(
        "AGENT_PLATFORM_MEMORY_DIR",
        str(Path(settings.OUTPUT_DIR) / "studio_memory"),
    )


def _ensure_paths(settings) -> None:
    """把 agent-platform 与 agents 目录加入 sys.path（可配置覆盖）。

    注意：`import agents` 需要 agents/ 的父目录在 sys.path 上，
    而 `import agent_platform` 需要 agent-platform/ 目录本身。
    """
    platform_dir = Path(
        settings.AGENT_PLATFORM_PATH or (_WORKSPACE_ROOT / "agent-platform")
    ).resolve()
    # AGENTS_PATH 语义：包含 agents 包的父目录（默认工作区根）
    agents_parent = Path(
        settings.AGENTS_PATH or str(_WORKSPACE_ROOT)
    ).resolve()
    for _d in (str(platform_dir), str(agents_parent)):
        if _d not in sys.path:
            sys.path.insert(0, _d)
    logger.info(
        "[Product Studio] platform=%s agents_parent=%s", platform_dir, agents_parent
    )


def _parse_product_id(product_id: str) -> "uuid.UUID":
    """Celery 参数为字符串，SQLAlchemy Uuid 类型要求 uuid.UUID。"""
    import uuid

    return uuid.UUID(str(product_id))


def _update_product(product_id: str, **fields) -> None:
    """同步更新 studio_products 记录（Celery Worker 同步上下文）。"""
    from sqlalchemy.orm import Session

    engine = get_sync_engine()
    with Session(engine) as session:
        product = session.get(StudioProduct, _parse_product_id(product_id))
        if product is None:
            raise RuntimeError(f"产品不存在: {product_id}")
        for key, value in fields.items():
            setattr(product, key, value)
        session.commit()


@celery_app.task(bind=True, base=ProductStudioTask, max_retries=1, acks_late=True)
def run_product_studio_pipeline(self: ProductStudioTask, product_id: str):
    """
    执行 Product Studio 流水线：

    Requirement Parser → Research → Competitor Analysis
      → Product Strategy → UX Design → Presentation → Asset Package

    结果（ProductAssetPackage 结构化 JSON）写入 studio_products.asset_package；
    失败时状态置为 failed 并记录错误（工作流内部节点级失败不阻断整体）。
    """
    settings = self.settings
    _bridge_env(settings)
    _ensure_paths(settings)

    # ── 读取产品想法 ─────────────────────────────────────────
    from sqlalchemy.orm import Session

    with Session(get_sync_engine()) as session:
        product = session.get(StudioProduct, _parse_product_id(product_id))
        if product is None:
            raise RuntimeError(f"产品不存在: {product_id}")
        idea = product.idea

    _update_product(product_id, status=StudioProductStatus.RUNNING, error_message=None)

    # ── 构建平台层组件（此时才 import，避免模块级副作用） ──────
    from agent_platform.harness.agent_loop import AgentLoop
    from agent_platform.memory.memory_store import FileMemoryStore
    from agent_platform.workflows.product_research_graph import ProductResearchGraph

    from agents.design_agent.agent import DesignAgent
    from agents.presentation_agent.agent import PresentationAgent
    from agents.product_agent.agent import ProductAgent
    from agents.research_agent.agent import ResearchAgent

    memory = FileMemoryStore(base_dir=settings.AGENT_PLATFORM_MEMORY_DIR
                             if settings.AGENT_PLATFORM_MEMORY_DIR
                             else str(Path(settings.OUTPUT_DIR) / "studio_memory"))
    loop = AgentLoop(memory=memory)

    graph = ProductResearchGraph(
        research_agent=ResearchAgent(loop=loop),
        product_agent=ProductAgent(loop=loop),
        design_agent=DesignAgent(loop=loop),
        presentation_agent=PresentationAgent(loop=loop),
        llm=loop.llm,          # 需求解析复用同一模型客户端
        memory=memory,
        max_retries=settings.AGENT_PLATFORM_MAX_RETRIES
        if settings.AGENT_PLATFORM_MAX_RETRIES >= 0
        else 2,
    )

    # ── 执行工作流 ───────────────────────────────────────────
    try:
        package = graph.invoke(idea, memory_namespace=product_id)
    except Exception as exc:  # noqa: BLE001 —— 记录失败，允许 Celery 重试
        logger.exception("[Product Studio] product=%s 流水线失败", product_id)
        _update_product(
            product_id,
            status=StudioProductStatus.FAILED,
            error_message=str(exc)[:2000],
        )
        raise self.retry(exc=exc, countdown=30)

    _update_product(
        product_id,
        status=StudioProductStatus.COMPLETED,
        asset_package=json.dumps(package.model_dump(), ensure_ascii=False),
        error_message=None,
    )
    failed_nodes = package.meta.errors
    logger.info(
        "[Product Studio] product=%s 完成 | 失败节点=%s",
        product_id, list(failed_nodes) if failed_nodes else "无",
    )
    return {"product_id": product_id, "status": "completed",
            "failed_nodes": failed_nodes}
