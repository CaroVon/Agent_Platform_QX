"""
============================================================
FastAPI 应用入口工厂
—— 生产就绪的应用实例构建
============================================================
"""

from __future__ import annotations

import os
import sys
import asyncio
import logging
from pathlib import Path
from contextlib import asynccontextmanager

# ─── 确保 backend/ 和项目根目录均在 sys.path 中 ──────────
# backend/ 优先（保证 app.core/app.models/app.schemas 等新模块优先加载），
# 项目根目录次之（提供 app.rag/app.search/app.crawler 等旧业务逻辑包）。
# 两者均需在 sys.path 中，因为：
#   - 从 backend/ 运行时 CWD=backend/ → app=backend/app/（缺少 app.rag 等）
#   - 从项目根运行时 CWD=project_root → app=project_root/app/（缺少 backend/app 新增模块）
_backend_dir = Path(__file__).resolve().parent.parent
_project_root = _backend_dir.parent
for _d in (str(_project_root), str(_backend_dir)):
    if _d not in sys.path:
        sys.path.insert(0, _d)

# ─── Windows asyncio 兼容性修复 ─────────────────────────────────
# 注意：WindowsSelectorEventLoopPolicy 在 Python 3.14+ 中已弃用，
# 因为默认的 ProactorEventLoop 现已支持子进程。
if sys.platform == "win32" and sys.version_info < (3, 14):
    try:
        from asyncio import WindowsSelectorEventLoopPolicy
        asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())
    except ImportError:
        pass

from fastapi import FastAPI, Request, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.database import engine, get_db, AsyncSessionLocal
from app.models import Base
from app.api.v1.router import router as v1_router

# ─── 日志配置 ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ================================================================
# 生命周期管理
# ================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期钩子：
    - 启动时：创建数据库表（生产环境应使用 Alembic 迁移）
    - 关闭时：关闭数据库引擎
    """
    settings = get_settings()

    # ─── 启动 ──────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("  %s v%s 启动中...", settings.APP_NAME, settings.APP_VERSION)
    logger.info("  Debug 模式: %s", settings.DEBUG)
    logger.info("=" * 60)

    # 配置校验（fail-fast：在启动阶段曝光所有缺失的关键配置）
    try:
        settings.validate_critical_config()  # type: ignore[attr-defined]
        logger.info("✅ 关键 API Key 配置校验通过: DEEPSEEK=✓ TAVILY=✓ FIRECRAWL=✓")
    except ValueError as e:
        logger.critical("❌ 配置校验失败，应用无法启动:\n%s", e)
        raise

    # 创建输出目录（如果不存在）
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)

    # 自动创建数据库表（create_all 是幂等的，不会删除已有数据）
    # 生产环境如需精细迁移控制，可切换为 Alembic migrate
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        logger.info("[DB] 数据库表已就绪（create_all 幂等操作）")

    # 轻量 schema 演进：为既有运行库补充新增列（owner_id/celery_task_id/progress_log 等）
    from app.core.schema_evolve import ensure_columns
    await ensure_columns(engine)

    # 确保 demo 用户存在（否则外键约束会导致项目创建失败）
    from sqlalchemy import text as sa_text
    async with engine.connect() as conn:
        result = await conn.execute(
            sa_text("SELECT id FROM users WHERE id = '00000000000000000000000000000001'")
        )
        if result.fetchone() is None:
            await conn.execute(
                sa_text("INSERT INTO users (id, username, email) VALUES "
                        "('00000000000000000000000000000001', 'demo', 'demo@qx-agent.local')")
            )
            await conn.commit()
            logger.info("[DB] Demo 用户已创建 (id: 0000...0001)")
        else:
            logger.info("[DB] Demo 用户已存在")

    # 启动时立即执行一次卡死任务回收
    from app.services.watchdog import recover_stale_tasks
    async with AsyncSessionLocal() as db:
        await recover_stale_tasks(db)

    # 周期性看门狗（后台任务，进程退出自动停止）
    from app.services.watchdog import watchdog_loop
    watchdog_task = asyncio.create_task(watchdog_loop())

    yield  # 应用运行中...

    # ─── 关闭 ──────────────────────────────────────────────────
    watchdog_task.cancel()
    await engine.dispose()
    logger.info("[APP] 数据库连接已关闭，应用退出")


# ================================================================
# 应用工厂
# ================================================================

def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="AI 产品分析 Agent —— 高并发异步 API 服务\n\n"
        "支持异步任务队列、混合检索增强生成（RAG）、多模态生图、PDF 渲染",
        lifespan=lifespan,
        docs_url="/docs",          # Swagger UI
        redoc_url="/redoc",        # ReDoc
    )

    # ─── CORS 中间件 ──────────────────────────────────────────
    # 允许前端跨域访问
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # TODO: 生产环境限制具体域名
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ─── 注册路由 ──────────────────────────────────────────────
    app.include_router(v1_router)

    # ─── 静态文件服务 ──────────────────────────────────────────
    # 提供输出文件（PDF/Markdown/图片）的 HTTP 访问
    outputs_path = Path(settings.OUTPUT_DIR)
    outputs_path.mkdir(parents=True, exist_ok=True)
    app.mount("/api/v1/files", StaticFiles(directory=str(outputs_path)), name="files")

    # 托管前端构建产物 (React SPA)
    _frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
    if _frontend_dist.exists():
        app.mount("/assets", StaticFiles(directory=str(_frontend_dist / "assets")), name="assets")

    # ─── 全局异常处理 ──────────────────────────────────────────
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error("未捕获的全局异常: %s | URL: %s", str(exc), request.url, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": f"服务器内部错误: {str(exc)}", "error_code": "INTERNAL_ERROR"},
        )

    # ─── 根路径 —— 前端 SPA ──────────────────────────────────
    _frontend_index = Path(__file__).parent.parent.parent / "frontend" / "dist" / "index.html"

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def index():
        """返回 React SPA 首页"""
        if _frontend_index.exists():
            return HTMLResponse(content=_frontend_index.read_text(encoding="utf-8"))
        # 兜底
        return HTMLResponse(content="<h1>QX Product Research Agent API</h1><p>前端未构建，请运行 npm run build，或访问 <a href='/docs'>Swagger 文档</a></p>")

    # ─── 健康检查 (必须在 SPA catch-all 之前注册) ──────────────
    @app.get("/health")
    async def health_check():
        return {
            "status": "ok",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
        }

    @app.get("/health/db")
    async def health_check_db(db: AsyncSession = Depends(get_db)):
        """数据库连接健康检查 —— 使用依赖注入确保测试隔离"""
        from sqlalchemy import text
        try:
            result = await db.execute(text("SELECT 1"))
            result.all()  # 消费结果验证连接
            # 验证核心表存在
            tables_result = await db.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                if "sqlite" in settings.DATABASE_URL_ASYNC
                else text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' ORDER BY table_name"
                )
            )
            rows = tables_result.all()
            tables = [row[0] for row in rows]
            return {
                "status": "ok",
                "database": "connected",
                "engine": "sqlite" if "sqlite" in settings.DATABASE_URL_ASYNC else "postgresql",
                "tables": tables,
            }
        except Exception as e:
            return {
                "status": "error",
                "database": "disconnected",
                "detail": str(e),
            }

    # ─── SPA 兜底：非 API 路径 → index.html (必须最后注册) ───
    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(request: Request, full_path: str):
        """React SPA client-side routing fallback"""
        if full_path.startswith(("api/", "docs", "redoc", "openapi.json", "health", "assets/", "outputs/")):
            raise HTTPException(status_code=404)
        if _frontend_index.exists():
            return HTMLResponse(content=_frontend_index.read_text(encoding="utf-8"))
        raise HTTPException(status_code=404)

    logger.info("[APP] FastAPI 应用初始化完成")
    return app


# ─── 应用实例（用于 uvicorn 直接启动） ──────────────────────
app = create_app()
