"""
============================================================
API v1 主路由聚合器
—— 将所有 endpoint 模块注册到同一 Router
============================================================
"""

from fastapi import APIRouter, Depends

from app.api.v1.endpoints import projects
from app.api.v1.endpoints import editor
from app.api.v1.endpoints import product
from app.api.v1.endpoints import design_studio
from app.api.v1.endpoints import project_assets
from app.api.v1.endpoints import knowledge
from app.api.v1.endpoints import memory
from app.api.v1.endpoints import auth
from app.core.security import get_current_user

# ─── 创建 v1 主路由 ───────────────────────────────────────────
router = APIRouter(prefix="/api/v1")

# ─── 认证路由（无需鉴权） ─────────────────────────────────────
router.include_router(auth.router)

# ─── 业务路由（统一鉴权：AUTH_ENABLED=true 时要求 Bearer token） ──
_guard = [Depends(get_current_user)]
router.include_router(projects.router, dependencies=_guard)
router.include_router(editor.router, dependencies=_guard)
router.include_router(product.router, dependencies=_guard)
router.include_router(design_studio.router, dependencies=_guard)
router.include_router(project_assets.router, dependencies=_guard)
router.include_router(knowledge.router, dependencies=_guard)
router.include_router(memory.router, dependencies=_guard)
