"""
============================================================
API v1 主路由聚合器
—— 将所有 endpoint 模块注册到同一 Router
============================================================
"""

from fastapi import APIRouter

from app.api.v1.endpoints import projects
from app.api.v1.endpoints import editor
from app.api.v1.endpoints import product
from app.api.v1.endpoints import knowledge

# ─── 创建 v1 主路由 ───────────────────────────────────────────
router = APIRouter(prefix="/api/v1")

# ─── 注册子路由 ───────────────────────────────────────────────
router.include_router(projects.router)
router.include_router(editor.router)
router.include_router(product.router)
router.include_router(knowledge.router)
