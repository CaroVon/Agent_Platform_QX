# QX Product Research Agent — 项目脚本架构文档

> **版本**: v1 | **更新**: 2026-07-02
>
> 本文档描述项目的完整脚本结构、每段脚本的核心代码片段及其在系统中的作用。
>
> **v0.7 新增**:
> - **Canvas 幻灯片编辑器**: 拖拽图片到画布 + 图片裁剪模式 (clipFunc + Transformer 四角缩放) + 幻灯片复制/粘贴/新增/删除 + 键盘快捷键 (Ctrl+M/Shift+D/Shift+C/Shift+V/Shift+Del)
> - **图片素材库**: ImageGallery 组件 (可折叠 + 搜索栏 + 强度选择器 + 拖拽缩略图到画布) + search-images/get-images/delete-image API + 🆕 v0.7.1 上下文空状态引导 (按项目状态显示不同提示) + DRAFTING 阶段 15s 自动轮询 + 手动刷新按钮
> - **Zustand 状态扩展**: clipX/Y/Width/Height 裁剪字段 + clipModeElementId/setClipMode 裁剪模式 + copiedSlide/copySlide/pasteSlide 跨页剪贴板
> - **ProjectImage 数据模型**: 图片搜索持久化 (project_id FK, query, image_url, search_depth)
> - **🆕 v0.7.1**: ddgs 图片搜索库升级至 v9.14.x (import `from ddgs import DDGS`, API: `DDGS().images(query, ...)`) + ImageGallery 空状态上下文提示 + 搜索失败与无结果区分提示
>
> **🆕 v0.7.2 更新** (2026-07-02):
> - **引用合并去重**: `build_context_with_citations()` 同 URL 多 Chunk 合并为单一上下文块，URL 内 chunk 级去重；空 chunk 跳过
> - **Prompt 格式规则重构**: bullet 拆分规则 (单 bullet 单结论，2-3 行) + 4+ 要点表格化 + 同事实去重 + 规则编号 2→9 重新编排
> - **字符宽度模型重构 (dataTransform)**: `isWideChar()` 统一字符宽度判定 + CJK 1.0×/空格 0.32×/大写数字 0.62×/其他 0.58× + 行高 1.35→1.48 + `safeWidth` 除零防护 + `Math.ceil()` 底线对齐
> - **排版引擎增强 (dataTransform)**: 上下文感知排版选择 (按子项数量和文本长度分级) + `shouldFallbackArrangement()` 溢出回退 vertical + `ensureSpace` 预检回调 + `buildLineElement()` 工厂统一装饰线 + 列表项去重渲染 (inlineText 合并到父节点)
> - **Canvas 编辑器**: 所有 Konva Text 元素统一 `lineHeight=1.4`（声明式 + 原生导出双路径）+ `clipFunc` 类型断言修复
> - **PDF CSS 修正**: `.slide` 高度 `100%` → `180mm` + `max-height` + `overflow:hidden`，防止幻灯片无限拉伸
>
> **🆕 v1 更新** (2026-07-02):
> - **dev_section_loop.py** (NEW ~520 行): 绕过 Celery/Redis，直接调用 `write_section()` → DocumentBlock → Canvas 渲染全链路，秒级验证排版修改效果。支持 checkpoint 管理、`--section` 单章重跑、`--dry-run` 预览、`--diff` 对比
> - **DEV_SECTION_LOOP.md** (NEW ~314 行): 开发循环工具完整文档（checkpoint 生命周期、常见工作流、FAQ）
> - **Prompt 层级结构增强 (prompts.py)**: product/design 双模板 "分组 + 并列项" 结构指导（并列要点组 / 顺序流程 / 短句集合 / 名称：说明格式），替代旧版机械层级要求；新增分页安全规则（超长 bullet 自动拆分）+ 表格优先级强化
> - **.gitignore 补充**: `scripts/.dev_checkpoint.json` 排除开发循环 checkpoint 文件
>
> **v0.6 新增**: 
> - **研究引擎**: 多模态绘图路由 `_write_image_section` + LLM 输出三阶段清理 `_clean_llm_output` + WritingTask Celery 基类 + Source Ranking 信息源分级权重 T0-T3 + Prompt 内容深度增强 (数据/事实密集度提升) + retriever_k 下限提升至 12 + 引用兜底 (LLM 不用引用时自动附加) + `max_tokens=4096`
> - **编辑器模块**: AI 面板直连 Zustand addElement + /chat RAG 自动注入 + /revise-block 块级上下文感知编辑 + 硅基流动图像引擎 generate_image + RenderPlaceholder 图片占位框 + pickAndUploadImage 上传持久化 + 图片 URL 修复 (/outputs/ → /api/v1/files/)
> - **排版引擎**: 图片占位框生成 + 目录单栏布局 + 引用区位置修正 + 超大块独占页 + 列表圆点对齐修复 + 表格样式注入 + resolveImageUrl 路径修正
> - **Canvas 编辑器**: RenderPlaceholder 双击替换 + RenderTable 表头/斑马纹 + 工具栏扩展 (矩形/字号/替换图片/置顶置底) + Transformer keepRatio 约束 + capturePage 表格样式导出
>
> **v0.5 新增**: Zustand/zundo Undo-Redo + CanvasElement 扩展 (circle/line/formatting/layers/clipboard) + DiffViewNode 差异预览 + 模板系统 (product/design) + search_depth 搜索强度
>
> **v0.4 新增**: React-Konva 替换 Fabric.js (序列化死循环根治) + 原生 Konva 离屏 JPEG 导出 + CanvasElement 统一数据模型 + stripMarkdown 纯文本转换 + MIT 全栈闭源合规
>
> **v0.3 新增**: Canvas 幻灯片编辑器 (React-Konva) + 前端 jsPDF 导出 + 专用 EditorPage + 数据转换层 (marked AST) + 多态模板系统
>
> **v0.2 新增**: AI 侧边栏对话面板 (SSE 流式) + 本地上传 PDF/DOCX/TXT 入库 + 手动导出 PDF + 图片搜索 (DuckDuckGo)

---

## 目录

1. [总览：三层架构](#1-总览三层架构)
2. [根目录文件一览](#2-根目录文件一览)
3. [启动与运维脚本](#3-启动与运维脚本)
4. [后端应用层 (backend/app/)](#4-后端应用层-backendapp)
5. [异步任务引擎 (backend/app/tasks/)](#5-异步任务引擎-backendapptasks)
6. [数据仓库层 (backend/app/repositories/)](#6-数据仓库层-backendapprepositories)
7. [数据库迁移 (backend/alembic/)](#7-数据库迁移-backendalembic)
8. [后端测试套件 (backend/tests/)](#8-后端测试套件-backendtests)
9. [研究引擎 (app/)](#9-研究引擎-app)
10. [前端架构 (frontend/src/)](#10-前端架构-frontendsrc)
11. [数据模型 (backend/app/models/)](#11-数据模型-backendappmodels)
12. [状态机流转全景](#12-状态机流转全景)
13. [测试与评测](#13-测试与评测)
14. [运维工具脚本](#14-运维工具脚本)

---

## 1. 总览：三层架构

```
┌──────────────────────────────────────────────────────────────────┐
│                    Frontend (React + Vite)                        │
│   WorkspacePage (项目管理) + EditorPage (Canvas 全屏编辑器)       │
│   React-Konva 声明式幻灯片 + Zustand 原子状态 + zundo Undo-Redo   │
│   原生 Konva 离屏 JPEG 导出 + jsPDF + SSE 流式对话                │
│                    http://localhost:8000                          │
└──────────────────────┬───────────────────────────────────────────┘
                       │ HTTP REST + SSE
┌──────────────────────▼───────────────────────────────────────────┐
│                 Backend (FastAPI + Celery)                        │
│    状态机编排 + 异步任务队列 + REST API + RAG 检索注入            │
│    DRAFTING→COMPLETED（不再自动生成 PDF，前端 Konva 接管导出）    │
│                    http://localhost:8000                          │
└──────────────────────┬───────────────────────────────────────────┘
                       │ Python import
┌──────────────────────▼───────────────────────────────────────────┐
│              Research Engine (app/)                               │
│  搜索→抓取→本地PDF解析→切片→向量库+BM25→RAG检索→大纲             │
│  →撰写 + 多态模板 (product/design) + 图片搜索 (DuckDuckGo)        │
└───────────────────────────────────────────────────────────────────┘
```

---

## 2. 根目录文件一览

```
QX_product_agent/
├── .claude/                    # Claude Code 配置（hooks / settings）
├── .gitignore
├── README.md                   # 项目 README
├── PROJECT_STRUCTURE.md        # 本文档
├── prd.md                      # 产品需求文档 (PRD)
├── requirements.txt            # Python 依赖清单
├── command.txt                 # 快速启动命令备忘
├── test_llm.py                 # LLM 连通性测试脚本
├── STRUCTURE_UPDATE_0623.md    # v0.2→v0.3 结构变更记录
├── STRUCTURE_UPDATE_0624.md    # v0.3→v0.4 结构变更记录
├── DEV_SECTION_LOOP.md          # 开发循环工具文档
│
├── start_all.sh                # WSL 全模块一键启动
├── stop_all.sh                 # WSL 全模块停止
├── start_project.bat           # Windows 桌面入口（双击→WSL）
├── start_project.bat.txt       # .bat 的文本备份
│
├── app/                        # 研究引擎（算法核心）
├── backend/                    # FastAPI 后端 + Celery 任务队列 + Alembic 迁移 + 测试
├── frontend/                   # React + Vite 前端
├── tests/                      # 评测脚本（检索/排序/引用质量）
├── scripts/                    # 开发工具脚本
├── fix/                        # 问题修复记录
├── memory/                     # Claude Code 持久记忆
└── venv/                       # Python 虚拟环境
```

---

## 3. 启动与运维脚本

### 3.1 `start_all.sh` — 全模块一键启动 (WSL)

**作用**: 依次检测并启动 Redis、Python venv、FastAPI、Celery Worker、Vite 前端。

```bash
# 核心片段：Redis 容器保活
if docker ps --format '{{.Names}}' | grep -q '^redis-qx$'; then
    ok "Redis 容器已运行"
else
    docker run -d --name redis-qx -p 6379:6379 --restart unless-stopped redis:7-alpine
fi

# 核心片段：清理端口冲突
OLD_PID=$(ss -tlnp | grep ':8000' | grep -oP 'pid=\K[0-9]+' | head -1)
[ -n "$OLD_PID" ] && kill "$OLD_PID"

# 核心片段：启动 FastAPI（后台 + 日志重定向，稳定模式 / 无 --reload）
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 \
    > "$RUNTIME_DIR/api.log" 2>&1 &

# 核心片段：启动 Celery（Windows 线程池模式，避免 spawn 崩溃）
nohup celery -A app.core.celery_app.celery_app worker \
    --loglevel=info --concurrency=4 --pool=threads \
    > backend/celery.log 2>&1 &

# 核心片段：启动 Vite 前端（端口 8000，与后端统一）
nohup npm run dev > frontend/vite.log 2>&1 &

# 核心片段：异步轮询等待后端就绪（ML 模型冷启动需 30-60s）
for i in $(seq 1 60); do
    curl -s http://localhost:8000/health > /dev/null 2>&1 && break
    sleep 1
done
```

### 3.2 `stop_all.sh` — 全模块停止

```bash
# 核心片段：按端口精准杀进程
PID=$(ss -tlnp | grep ':8000' | grep -oP 'pid=\K[0-9]+' | head -1)
[ -n "$PID" ] && kill "$PID"
pkill -f "celery.*worker"
```

### 3.3 `start_project.bat` — Windows 入口

```batch
@echo off
chcp 65001 >nul 2>&1
:: 通过 WSL 调用 bash 启动脚本
wsl -e bash /mnt/d/DEV/agents/QX_product_agent/start_all.sh
pause
```

**设计意图**: Windows 用户双击 bat → 内部委托 WSL 执行 bash 脚本。所有环境（Python、Node、Redis）均在 WSL 内运行。

### 3.4 `test_llm.py` — LLM 连通性快速验证

用于验证 DeepSeek API Key 配置是否正确、模型是否可达的小型诊断脚本。

### 3.5 `scripts/dev_section_loop.py` — section_writer → Canvas 单点测试循环（约 520 行）

**作用**: 绕过 Celery/Redis，直接调用 `write_section()` → DocumentBlock → Canvas 渲染全链路，秒级验证 LLM 撰写输出和排版修改效果。

```bash
# 查看当前检查点状态
python scripts/dev_section_loop.py status

# 重跑全部章节（使用已保存的检查点项目）
python scripts/dev_section_loop.py run

# 指定项目重跑（自动保存为检查点）
python scripts/dev_section_loop.py run --project <project_id>

# 只重跑单个章节
python scripts/dev_section_loop.py run --section "竞品分析"

# dry-run：预览输出但不写入数据库
python scripts/dev_section_loop.py run --dry-run

# 跳过图片搜索（加速迭代）
python scripts/dev_section_loop.py run --no-images

# 与上次运行对比差异
python scripts/dev_section_loop.py run --diff
```

**设计意图**: 全流程（创建项目 → Phase 1 搜索 → 审核 → Phase 2 大纲 → 审批 → Phase 3 撰写 → 编辑器）耗时 5-10 分钟，其中 Phase 1/2 在排版调试期间完全不需要变更。此工具将流程压缩为"一次性创建项目并审批到 WAITING_FOR_OUTLINE → 反复 `python scripts/dev_section_loop.py run` → 刷新浏览器"，每次迭代 30-60 秒。

**核心逻辑**:
```python
# 1. 加载检查点项目（或从 CLI --project 参数指定）
checkpoint = _load_checkpoint()  # 读取 scripts/.dev_checkpoint.json
project_id = checkpoint["project_id"]

# 2. 获取大纲 → 提取章节标题
repo = ProjectRepo()
project = repo.get_project(project_id)
sections = _extract_sections(project.outline_content)

# 3. 逐章重跑 write_section()
for section_title in sections:
    content = write_section(topic, section_title, project_id=project_id,
                           template_type=template_type, search_depth=search_depth)
    _save_section_as_blocks(repo, project_id, section_title, content, idx)
    # 可选：--dry-run 时不写入 DB，仅打印预览
    # 可选：--diff 时用 difflib 对比新旧输出

# 4. 保存运行记录 → scripts/.dev_checkpoint.json
_save_checkpoint(project_id, last_section=section_title, run_count=run_count + 1)
```

### 3.6 `DEV_SECTION_LOOP.md` — 开发循环工具文档（约 314 行）

**作用**: 完整说明 dev_section_loop 工具的工作原理、checkpoint 生命周期管理、常见工作流和 FAQ。

核心章节：
- **为什么需要这个工具？** — 对比全流程 5-10 分钟 vs 单点循环 30-60 秒
- **核心原理** — 架构图：绕过 Celery Worker，直连 `write_section()` + SQLAlchemy Session
- **checkpoint 管理** — `scripts/.dev_checkpoint.json` 文件结构 + `--save`/`--status` 命令
- **常见工作流** — 四种典型场景（初始设置 / 快速迭代 / 单章调试 / 排版验证）
- **FAQ** — 6 个常见问题解答

---

## 4. 后端应用层 (backend/app/)

### 4.1 `backend/app/main.py` — FastAPI 应用工厂

这是整个后端的**唯一入口**。

```python
# 核心片段：双路径注入 —— 同时加入 backend/ 和项目根目录
# backend/ 优先（app.core/app.models/app.schemas 等新模块），
# 项目根目录次之（app.rag/app.search/app.crawler 等研究引擎）。
# 两者缺一不可：从 backend/ 启动时 CWD=backend/ 找不到 app.rag；
# 从项目根启动时 CWD=project_root 找不到 backend/app 新增模块。
_backend_dir = Path(__file__).resolve().parent.parent
_project_root = _backend_dir.parent
for _d in (str(_project_root), str(_backend_dir)):
    if _d not in sys.path:
        sys.path.insert(0, _d)
# 结果：sys.path[0] = backend/（优先），sys.path[1] = 项目根目录

# 核心片段：Windows asyncio 兼容（Python 3.14+ 自动适配）
if sys.platform == "win32" and sys.version_info < (3, 14):
    asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())

# 核心片段：生命周期管理 —— 启动时自动建表
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("[DB] 数据库表已就绪（create_all 幂等操作）")
    yield
    await engine.dispose()

# 核心片段：注册路由 + CORS + 静态文件
app = FastAPI(title="Product Analysis Agent API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)
app.include_router(v1_router, prefix="/api/v1")
app.mount("/outputs", StaticFiles(directory=settings.OUTPUT_DIR))
```

### 4.2 `backend/app/core/config.py` — 配置中心

**作用**: Pydantic V2 Settings 单例，从 `.env` 自动加载所有配置项，启动时校验关键 API Key。

```python
# 核心片段：.env 文件搜索链
def _find_env_file() -> str:
    candidates = [
        Path(__file__).parent.parent.parent / ".env",       # backend/.env
        Path(__file__).parent.parent.parent.parent / "backend" / ".env",
        Path(".env"),
    ]

# 核心片段：异步/同步数据库 URL 双通道
@property
def DATABASE_URL_ASYNC(self) -> str:
    if self.DATABASE_URL:
        return self.DATABASE_URL
    return f"postgresql+asyncpg://{user}:{pwd}@{host}:{port}/{db}"

# 核心片段：启动时 fail-fast 校验关键 Key
@model_validator(mode="after")
def validate_critical_config(self):
    missing = []
    if not self.DEEPSEEK_API_KEY: missing.append("DEEPSEEK_API_KEY")
    if not self.TAVILY_API_KEY: missing.append("TAVILY_API_KEY")
    if missing:
        raise ValueError(f"❌ 关键 API Key 未配置：\n  • {'  • '.join(missing)}")
```

配置项涵盖：数据库 URL、Redis/Celery broker、DeepSeek API、Tavily Search、Firecrawl、Embedding 模型路径、Chroma/BM25 持久化目录、输出目录等。

### 4.3 `backend/app/core/database.py` — 异步数据库引擎

**作用**: 创建 SQLAlchemy 2.0 异步引擎，SQLite 与 PostgreSQL 双模式。

```python
# 核心片段：SQLite 特殊处理（NullPool + WAL 模式 + check_same_thread）
if _is_sqlite:
    engine = create_async_engine(
        settings.DATABASE_URL_ASYNC,
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")     # 提升并发写性能
        cursor.execute("PRAGMA foreign_keys=ON;")

# 核心片段：FastAPI 依赖注入 —— 自动 commit/rollback
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

### 4.4 `backend/app/core/celery_app.py` — Celery 应用实例

```python
# 核心片段：配置 Redis broker + 结果后端
celery_app = Celery("research_agent")
celery_app.conf.update(
    broker_url=settings.CELERY_BROKER_URL,
    result_backend=settings.CELERY_RESULT_BACKEND,
    task_serializer="json",
    result_expires=3600,
    task_acks_late=True,           # 任务完成后才确认
    worker_prefetch_multiplier=1,  # 公平调度
    worker_max_tasks_per_child=50, # 防止内存泄漏
)
# 自动发现所有 task 模块
celery_app.autodiscover_tasks([
    "app.tasks.search_tasks",
    "app.tasks.knowledge_tasks",
    "app.tasks.writing_tasks",
    "app.tasks.render_tasks",
    "app.tasks.report_workflow",
])
```

> **关键设计**: `--pool=threads` 是 Windows 必需参数。Python 3.14 的 `spawn` 多进程模式会导致 `trace._localized` 解包崩溃。

### 4.5 `backend/app/core/celery_db.py` — Celery Worker 数据库层

```python
# 核心片段：提供同步引擎（Celery worker 在同步上下文中运行）
@lru_cache()
def get_sync_engine():
    return create_engine(settings.DATABASE_URL_SYNC, echo=settings.DEBUG)

# 核心片段：爬取数据的临时文件路径
def get_crawled_data_path(project_id: str) -> str:
    return os.path.join(settings.OUTPUT_DIR, f"crawled_data_{project_id}.json")
```

### 4.6 `backend/app/api/v1/router.py` — 路由聚合

```python
router = APIRouter(prefix="/api/v1")
router.include_router(projects.router)   # /api/v1/projects
router.include_router(editor.router)     # /api/v1/editor
```

### 4.7 `backend/app/api/v1/endpoints/projects.py` — 核心业务 API（约 1200 行）

**状态机三节点**的 REST 实现 + 新增功能端点：

```python
# 节点1：创建项目 + 触发 Phase 1（搜索 → 等待审核资料）
@router.post("", response_model=ProjectCreateResponse, status_code=201)
async def create_project(body: ProjectCreateRequest, db: AsyncSession):
    project = Project(owner_id=current_user_id, topic=body.topic,
                      status=ProjectStatus.PREPARING_DATA,
                      template_type=body.template_type or "product",  # v0.5
                      search_depth=body.search_depth or 10)            # v0.5
    db.add(project)
    # 创建任务链：SEARCH → BUILD_KNOWLEDGE_BASE → GENERATE_OUTLINE
    for task_type, seq in [(TaskType.SEARCH, 1), ...]:
        db.add(Task(project_id=project.id, task_type=task_type, ...))
    # 提交 Celery 异步工作流
    celery_task = prepare_sources_workflow.delay(str(project.id))

# 节点1确认：用户审核资料 → 触发 Phase 2（大纲生成）
@router.post("/{project_id}/review-sources")
async def review_sources(project_id, body: SourceReviewRequest, db):
    # 状态校验：仅 WAITING_FOR_SOURCES 可操作
    if project.status != ProjectStatus.WAITING_FOR_SOURCES:
        raise HTTPException(409)
    # 筛选资料 + 保存 + 状态机推进 → PREPARING_OUTLINE
    project.status = ProjectStatus.PREPARING_OUTLINE
    celery_task = generate_outline_workflow.delay(str(project.id))

# 节点2确认：用户确认大纲 → 触发 Phase 3（逐章撰写）
@router.post("/{project_id}/approve-outline")
async def approve_outline(project_id, body: OutlineApproveRequest, db):
    if project.status != ProjectStatus.WAITING_FOR_OUTLINE:
        raise HTTPException(409)
    sections = _extract_sections_from_outline(body.outline)
    project.status = ProjectStatus.DRAFTING
    # 为每个章节创建 DocumentBlock 占位 + Task
    for idx, section_title in enumerate(sections):
        db.add(DocumentBlock(project_id=project.id, section_title=section_title,
                             order_index=(idx+1)*10, content=""))
    celery_task = run_draft_sections_workflow.delay(str(project.id))

# SSE 流式输出：轮询 DocumentBlock 表，逐条推送 section_chunk 事件
@router.get("/{project_id}/stream-draft")
async def stream_draft(project_id, db):
    async def event_generator():
        while wait_cycles < 300:
            await db.refresh(project)  # 强制刷新 —— 解决 ORM 状态过期死循环
            blocks = await db.execute(select(DocumentBlock).where(...))
            for block in blocks[last_block_count:]:
                yield f"event: section_chunk\ndata: {json.dumps(block_data)}\n\n"
            if project.status == ProjectStatus.COMPLETED:
                yield f"event: draft_complete\ndata: ...\n\n"
                return
            await asyncio.sleep(2)  # 2 秒轮询间隔
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

**完整端点列表**:

| 端点 | 方法 | 作用 |
|------|------|------|
| `/` | POST | 创建项目 (含 template_type + search_depth) |
| `/{project_id}/status` | GET | 获取项目完整状态 + 任务进度 |
| `/{project_id}/review-sources` | POST | 用户审核资料 → 触发 Phase 2 |
| `/{project_id}/approve-outline` | POST | 用户确认大纲 → 触发 Phase 3 |
| `/{project_id}/stream-draft` | GET | SSE 流式接收章节撰写 |
| `/{project_id}/upload-docs` | POST | 上传本地 PDF/DOCX/TXT → PyMuPDF 解析 → 切片入库 |
| `/{project_id}/export-pdf` | POST | 前端提交 HTML 内容 → 后端 WeasyPrint 渲染 PDF |
| `/{project_id}/sources` | GET | 获取搜索结果列表（供资料审核面板） |
| `/{project_id}/blocks` | GET | 获取所有 DocumentBlock（供 Canvas 编辑器加载） |
| `/{project_id}/content` | GET | 获取报告全文内容（按章节排列 + 引用映射） |
| `/{project_id}/logs` | GET | 获取项目时间轴日志（支持增量拉取 after_sequence） |
| `/{project_id}/download` | GET | 获取 PDF 下载链接（仅 COMPLETED 状态可用） |
| `/{project_id}/assets` | POST | 幻灯片图片暂存 (保存至 outputs/assets/{project_id}/，返回 `/api/v1/files/assets/...` 公开 URL) |
| `/{project_id}/search-images` | POST | 🆕 v0.7 图片搜索 (DuckDuckGo)，结果持久化到 project_images 表 |
| `/{project_id}/images` | GET | 🆕 v0.7 获取项目图片库（所有已搜索保存的图片） |
| `/{project_id}/images/{image_id}` | DELETE | 🆕 v0.7 删除项目图片库中的单张图片 |
| `/{project_id}` | DELETE | 软删除项目及其所有关联数据 |
| `/` | GET | 获取用户的所有项目列表 |
| `/blocks/{block_id}` | PATCH | 更新单个 DocumentBlock 内容 |

**🆕 v0.6: 幻灯片图片暂存端点**:

```python
@router.post("/{project_id}/assets")
async def upload_slide_asset(project_id: uuid.UUID, file: UploadFile):
    """
    接收用户上传的本地图片 → 保存至 outputs/assets/{project_id}/{uuid}.png
    → 返回 "/api/v1/files/assets/{project_id}/{uuid}.png" 公开访问 URL。
    🆕 v0.6 修复: 从 /outputs/assets/ 改为 /api/v1/files/assets/，
    匹配 main.py 中的 StaticFiles mount 点，根治图片 404 问题。
    """
```

### 4.8 `backend/app/api/v1/endpoints/editor.py` — Inline AI 编辑器 + 侧边栏对话（约 376 行）

**1. `/revise` — AI 改写选中文本 (Inline AI Bubble)**

```python
_INLINE_AI_SYSTEM = """你是一位资深产品经理兼技术文案专家...
原则：产品化思维、精确性、可读性、脚注保护、仅返回改写文本"""

# 快捷指令映射（支持中文自然语言指令）
_INSTRUCTION_HINTS = {
    "扩写": "请将以下段落扩写至原文的 1.5-2 倍长度...",
    "精简": "请将以下段落精简至原文的一半长度...",
    "润色": "请优化以下段落的表达，使其更具专业感...",
    "补充竞品案例": "请补充 1-2 个具体的竞品案例...",
    "语气改简练": "请将以下段落的语气改为更直接简练的风格...",
    "使表达更正式": "请将以下段落的语气升级为更正式的商业汇报风格...",
}

@router.post("/revise", response_model=EditorReviseResponse)
async def revise_text(body: EditorReviseRequest):
    hint = _INSTRUCTION_HINTS.get(body.instruction, body.instruction)
    # 自定义指令包装：f"请根据以下指令改写文本：{instruction}。注意保留所有脚注角标。"
    user_message = f"【指令】{hint}\n\n【原文】\n{body.selected_text}"
    if body.context:
        user_message += f"\n\n【上下文参考（仅用于理解语境）】\n{body.context}"
    # 使用 DeepSeek Chat, temperature=0.3
```

**2. `/revise-block/{block_id}` — 块级精准改写（上下文感知）**

```python
@router.post("/revise-block/{block_id}", response_model=EditorReviseResponse)
async def revise_block(block_id: uuid.UUID, body: BlockReviseRequest, db):
    """
    与 /revise 的区别：
    - /revise: 纯文本改写，无状态，不涉及数据库
    - /revise-block: 从数据库加载目标块 + 前后相邻块（同 project 内按
      order_index 排序）作为上下文 → LLM 改写 → 返回修订文本
    前端使用流程：
    1. 用户点击块旁边的 "AI 改写" 按钮
    2. 弹出指令输入框 → 调用此 API
    3. 后端读取块的完整上下文后改写
    4. 返回 revised_text → 前端展示 Diff 对比
    5. 用户接受 → PATCH /blocks/{block_id} 保存 / 拒绝 → 无操作
    """
```

**3. `/chat` — 侧边栏大模型流式对话（SSE + RAG 知识库注入）**

```python
_CHAT_WORK_SYSTEM = (
    "你是一个专业的产品分析师与报告撰写助手。"
    "请务必优先基于【项目知识库参考】或【编辑器选中文本参考】中的信息"
    "来客观、严谨地回答用户问题..."
)
_CHAT_GENERAL_SYSTEM = (
    "你是一个友好的 AI 助手，请自然、轻松地回答我的问题。"
)

@router.post("/chat")
async def chat_with_editor(body: EditorChatRequest):
    """
    侧边栏大模型对话（SSE 流式输出）。
    支持 work 模式（RAG 检索注入 + temperature=0.3）与
    chat 模式（通用闲聊 + temperature=0.7）切换。

    上下文拼接顺序（work 模式）:
    1. 对话历史 (body.history)
    2. 当前用户提问 (body.message)
    3. 编辑器选中文本 (body.selected_text)  ← 前端可传
    4. RAG 检索结果 (retrieve_context k=5, per-project 隔离)
    → SSE 流式返回: event: content / event: done / event: error
    """
```

> **设计意图**: `/chat` 在 work 模式下先调用 `retrieve_context()` 从项目隔离的 Chroma + BM25 向量库中召回 Top-5 相关文档切片，再注入到 LLM 上下文中。这打通了"本地上传 PDF → 切片入库 → 对话检索 → AI 生成内容 → 应用到画布"的完整闭环。

### 4.9 `backend/app/schemas/__init__.py` — Pydantic 数据契约

所有请求/响应模型约 350 行，定义 API 的类型契约：

```python
class ProjectCreateRequest(BaseModel):
    topic: str
    template_type: str = "product"  # 🆕 v0.5: product | design
    search_depth: int = 10          # 🆕 v0.5: 5/10/15/20

class ProjectStatusResponse(BaseModel):
    project_id: uuid.UUID
    topic: str
    template_type: str              # 🆕 v0.5
    search_depth: int               # 🆕 v0.5
    project_status: str
    outline_content: str | None
    logo_url: str | None            # 🆕 v0.4
    progress: dict       # {total_tasks, completed_tasks, percentage, ...}
    current_step: dict | None
    tasks: list[dict]

class EditorReviseRequest(BaseModel):
    project_id: uuid.UUID
    block_id: uuid.UUID
    selected_text: str
    instruction: Literal["expand", "simplify", "polish",
                         "add-competitors", "formalize"] | str

class EditorChatRequest(BaseModel):
    """侧边栏 AI 对话请求"""
    project_id: uuid.UUID
    chat_mode: Literal["chat", "work"]
    message: str
    selected_text: str | None
    history: list[ChatMessage]

class ExportPdfRequest(BaseModel):
    """手动导出 PDF 请求"""
    html_content: str

class SSEDraftEvent(BaseModel):
    event_type: Literal["section_start", "section_chunk",
                        "section_complete", "draft_complete", "error"]
    section_title: str | None
    block: DocumentBlockResponse | None
    error: str | None
```

### 4.10 `backend/app/shared/outline_parser.py` — Markdown 大纲解析

```python
def extract_sections(outline: str) -> list[str]:
    """
    从 Markdown 大纲中提取 ## 二级标题作为章节名。
    正确处理：制表符分隔、行内 # 字符、排除 ### 三级标题。
    """
    sections = []
    for line in outline.split("\n"):
        line = line.strip().lstrip("\t")
        if line.startswith("## ") and not line.startswith("### "):
            title = line[3:].strip()
            title = re.sub(r"(\d+)[、.，。,]\s*", r"\1. ", title)
            sections.append(title)
    return sections
```

### 4.11 `backend/app/services/__init__.py` — 服务层占位

预留的业务服务层模块，用于从 API 端点中抽离复杂业务逻辑。

---

## 5. 异步任务引擎 (backend/app/tasks/)

### 5.1 `report_workflow.py` — 三阶段状态机编排器（约 436 行）

这是整个系统的**核心编排逻辑**，实现三阶段交互式状态机。每个阶段都是独立的 Celery 任务，阶段间通过用户确认操作驱动。

```python
# ── 内部辅助函数 ─────────────────────────────────────────────
def _extract_sections(outline: str) -> list[str]:
    """从大纲 Markdown 中提取 ## 章节标题（委托给 shared/outline_parser.py）"""

def log_state(project_id: str, step: str, msg: str):
    """状态机日志打印，统一产品化标志格式"""

def _save_sources_to_project(project_id, search_result, repo):
    """将搜索结果序列化为 JSON 暂存到 outputs/crawled_data_{project_id}.json"""

def _load_sources_from_project(project_id) -> list[dict]:
    """从暂存文件读取搜索结果"""

def _save_section_as_blocks(repo, project_id, section_title, content, section_index):
    """
    章节级 Block 保存策略：每个章节保存为 1 个完整的 DocumentBlock，
    而非按段落拆分。这避免了每个 Block 都带装饰区（120-180px）导致碎片页。
    block_order = (section_index + 1) * 10，预留插入空间。
    """

# Phase 1：资料准备 → WAITING_FOR_SOURCES（等待用户审核）
@celery_app.task(bind=True, max_retries=1, acks_late=True)
def prepare_sources_workflow(self, project_id: str):
    repo = ProjectRepo()
    repo.append_project_log(project_id, "searching", "🔍 正在全网搜索相关资料...")
    repo.update_task_status(project_id, TaskType.SEARCH, TaskStatus.PROCESSING)
    # 委托 search_tasks.search_and_crawl() 执行 Tavily + Firecrawl
    search_result = search_and_crawl(project_id)
    repo.update_task_status(project_id, TaskType.SEARCH, TaskStatus.COMPLETED)
    _save_sources_to_project(project_id, search_result, repo)
    repo.update_project_status(project_id, ProjectStatus.WAITING_FOR_SOURCES)
    # 返回 { project_id, status: "waiting_for_sources", sources_count }

# Phase 2：大纲生成 → WAITING_FOR_OUTLINE（等待用户确认）
@celery_app.task(bind=True, max_retries=1, acks_late=True)
def generate_outline_workflow(self, project_id: str):
    repo = ProjectRepo()
    # 1. 知识库构建（向量 + BM25）
    repo.update_task_status(project_id, TaskType.BUILD_KNOWLEDGE_BASE, TaskStatus.PROCESSING)
    build_knowledge_base(project_id)
    repo.update_task_status(project_id, TaskType.BUILD_KNOWLEDGE_BASE, TaskStatus.COMPLETED)
    # 2. 大纲生成（透传 template_type 给 PromptFactory 路由）
    template_type = repo.get_project_template(project_id)
    outline = generate_outline_task(project_id, template_type=template_type)
    # 3. 暂存大纲 + 状态推进
    repo.update_project_outline(project_id, outline)
    repo.update_project_status(project_id, ProjectStatus.WAITING_FOR_OUTLINE)
    # 返回 { project_id, status: "waiting_for_outline", outline_length }

# Phase 3：逐章撰写 → COMPLETED（前端 Konva 接管 PDF 导出）
@celery_app.task(bind=True, max_retries=1, acks_late=True)
def run_draft_sections_workflow(self, project_id: str):
    repo = ProjectRepo()
    project = repo.get_project(project_id)
    section_titles = _extract_sections(project.outline_content)
    template_type = repo.get_project_template(project_id)
    for idx, section_title in enumerate(section_titles):
        repo.update_section_task_status(project_id, section_title, TaskStatus.PROCESSING)
        content = write_single_section(project_id, section_title, idx,
                                       template_type=template_type)
        _save_section_as_blocks(repo, project_id, section_title, content, idx)
        repo.update_section_task_status(project_id, section_title, TaskStatus.COMPLETED)
    repo.update_project_status(project_id, ProjectStatus.COMPLETED,
                               pdf_path=None, md_path=None)
    repo.append_project_log(project_id, "drafting_complete",
                           "🎉 AI 草稿分页生成完毕！已导入 Canvas 工作台。")

# 旧版兼容：一键全自动流水线（三阶段串联，无用户交互断点）
@celery_app.task(bind=True, max_retries=1, acks_late=True)
def run_full_report_workflow(self, project_id: str):
    prepare_sources_workflow(project_id)
    generate_outline_workflow(project_id)
    run_draft_sections_workflow(project_id)
```

> **关键设计**: 每个阶段独立为 Celery 任务，阶段间通过用户 POST 端点触发下一阶段（而非 Celery chain 自动串联）。`_save_section_as_blocks` 采用章节级保存策略（每章节 1 个 Block），避免段落级拆分导致过多碎片页。

### 5.2 `search_tasks.py` — 搜索 + 抓取

```python
@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def search_and_crawl(self, topic: str, search_depth: int = 10) -> list[dict]:
    """Tavily 搜索 + Firecrawl 深度抓取，search_depth 控制搜索强度 5/10/15/20"""
    max_results = min(search_depth, 20)
    search_results = tavily_search(topic, max_results=max_results)
    crawled = []
    for result in search_results[:max_results]:
        try:
            content = crawl_url(result["url"])  # Firecrawl 抓取
            crawled.append({"content": content, "url": result["url"],
                           "title": result.get("title", "")})
        except Exception:
            crawled.append({"content": result.get("content", ""),
                           "url": result["url"]})
    return crawled
```

### 5.3 `knowledge_tasks.py` — 知识库构建

```python
@celery_app.task(bind=True)
def build_knowledge_base(self, topic: str, project_id: str):
    """将爬取文本切片 → 嵌入 → 存入 Chroma 向量库 + BM25 索引"""
    data_path = get_crawled_data_path(project_id)
    with open(data_path) as f:
        sources = json.load(f)
    all_chunks = []
    for src in sources:
        chunks = chunk_text(src["content"], chunk_size=1200, chunk_overlap=200)
        all_chunks.extend(chunks)
    build_vector_store(all_chunks, project_id)  # Chroma 持久化
    build_bm25_index(all_chunks, project_id)    # BM25 持久化
```

### 5.4 `writing_tasks.py` — 大纲生成 + 章节撰写（约 157 行）

```python
class WritingTask(Task):
    """Celery 任务基类 —— 惰性加载 Settings 单例，避免模块级副作用"""
    _settings = None
    @property
    def settings(self):
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

@celery_app.task(bind=True, base=WritingTask, max_retries=2, acks_late=True)
def generate_outline_task(self: WritingTask, project_id: str,
                          template_type: str = "product") -> str:
    """通过 ProjectRepo 获取 topic，委托 outline_generator.generate_outline()"""
    repo = ProjectRepo()
    topic = repo.get_project_topic(project_id)
    from app.planner.outline_generator import generate_outline
    return generate_outline(topic, template_type=template_type)

@celery_app.task(bind=True, base=WritingTask, max_retries=3, acks_late=True,
                 autoretry_for=(Exception,), retry_backoff=True, retry_backoff_max=120)
def write_single_section(self: WritingTask, project_id: str, section_title: str,
                         section_order: int = 0,
                         template_type: str = "product") -> str:
    """
    撰写单个章节 —— 包含完整的检索+撰写+保存流水线：
    1. 从 Settings 注入环境变量 (DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL)
    2. 从 ProjectRepo 获取 topic 与 search_depth
    3. 委托 app.report.section_writer.write_section() 执行：
       - 检测章节关键词 → 路由到多模态绘图引擎或文本撰写引擎
       - 文本引擎: HybridRetriever 检索 → build_context_with_citations → LLM 撰写
       - 多模态引擎: LLM 生成英文 Prompt → 硅基流动 generate_image()
    4. 保存章节快照到 Document 表（完整 Markdown 正文 + source_urls）
    5. 异常时自动重试（指数退避，最大 120s）
    """
    settings = self.settings
    repo = ProjectRepo()
    os.environ["DEEPSEEK_API_KEY"] = settings.DEEPSEEK_API_KEY
    os.environ["DEEPSEEK_BASE_URL"] = settings.DEEPSEEK_BASE_URL
    topic = repo.get_project_topic(project_id)
    search_depth = repo.get_project_search_depth(project_id)
    content = write_section(topic, section_title, project_id=project_id,
                            template_type=template_type, search_depth=search_depth)
    repo.save_document(project_id=project_id, section_title=section_title,
                       content=content, source_urls=source_urls,
                       section_order=section_order)
    return content
```

> **关键设计**: `WritingTask` 基类避免在每个 Celery 任务中重复实例化 Settings。`write_single_section` 通过 `autoretry_for=(Exception,)` + `retry_backoff=True` 实现健壮的指数退避重试，最大退避 120 秒。章节内容同时保存到 Document 快照表（完整章节）和 DocumentBlock 表（由 report_workflow._save_section_as_blocks 负责）。

### 5.5 `render_tasks.py` — PDF 渲染（v0.3 起仅作历史记录 / 不再自动调用）

```python
@celery_app.task(bind=True)
def generate_pdf(self, project_id: str) -> str:
    """⚠️ v0.3 起不再自动调用。前端 Konva + jsPDF 接管 PDF 导出。"""
    sections = ProjectRepo().get_section_contents(project_id)
    md_content = build_report(topic, sections)
    pdf_path = markdown_to_pdf(md_content, project_id, topic)
    return pdf_path
```

---

## 6. 数据仓库层 (backend/app/repositories/)

### 6.1 `project_repo.py` — ProjectRepo 同步数据库仓库

**作用**: 为 Celery Worker 提供统一的同步数据库访问接口，消除散落在各任务中的 raw SQL 和 `asyncio.run()` 调用。

```python
class ProjectRepo:
    """同步数据库仓库——专供 Celery Worker 使用。"""

    def __init__(self):
        self._engine = get_sync_engine()

    # ── 项目查询 ──
    def get_project(self, project_id: str) -> Project          # 获取项目 ORM
    def get_project_topic(self, project_id: str) -> str        # 获取 topic
    def get_project_outline(self, project_id: str) -> str | None  # 获取大纲
    def get_project_template(self, project_id: str) -> str     # 🆕 获取 template_type
    def get_project_search_depth(self, project_id: str) -> int # 🆕 获取 search_depth

    # ── 状态更新 ──
    def update_project_status(self, project_id, status, ...)   # 更新项目状态
    def update_project_outline(self, project_id, outline)      # 保存大纲

    # ── 任务管理 ──
    def update_task_status(self, project_id, task_type, status) # 更新任务状态
    def update_section_task_status(self, ...)                  # 更新章节任务
    def create_section_tasks(self, project_id, titles)         # 动态创建章节任务

    # ── 文档块 (DocumentBlock) ──
    def save_document_block(self, project_id, section, content, citations, order)

    # ── 文档快照 (Document) ──
    def save_document(self, project_id, section, content, source_urls, order)

    # ── 时间轴日志 (ProjectLog) ──
    def append_project_log(self, project_id, step, message, level, icon)
```

> **设计意图**: Celery Worker 在同步上下文中运行。ProjectRepo 使用同步 SQLAlchemy 引擎 + ORM 查询，直接返回 ORM 对象（`session.expunge()` 后 detach），无需 `asyncio.run()` 或 `nest_asyncio`。

---

## 7. 数据库迁移 (backend/alembic/)

### 7.1 `alembic/env.py` — Alembic 运行环境

配置迁移引擎、导入 ORM Base 元数据，支持在线/离线两种迁移模式。

```python
from app.models import Base
target_metadata = Base.metadata

def run_migrations_online():
    connectable = engine_from_config(config.get_section(...), prefix="sqlalchemy.", poolclass=NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        context.run_migrations()
```

### 7.2 迁移版本一览

| 版本 | 文件名 | 内容 |
|------|--------|------|
| 0001 | `0001_initial_schema.py` | 初始表结构：users, projects, tasks, documents, document_blocks, project_logs |
| 0003 | `0003_search_depth_and_logo_url.py` | 🆕 v0.4: projects 表新增 search_depth (INT, default 10) + logo_url (VARCHAR 1000) |
| 24f2c9f525d7 | `24f2c9f525d7_add_template_type_to_projects.py` | 🆕 v0.5: projects 表新增 template_type (VARCHAR 50, default 'product') |

### 7.3 初始表结构 (0001)

| 表名 | 关键字段 |
|------|----------|
| `users` | id, email, username, hashed_password, is_active, is_superuser, monthly_project_limit, projects_used_this_month, total_pages_generated, is_deleted, deleted_at |
| `projects` | id, owner_id, topic, status (enum), outline_content, pdf_path, md_path, error_message, is_deleted, **template_type**, **search_depth**, **logo_url** |
| `tasks` | id, project_id, task_type (enum), status (enum), sequence_order, section_title, celery_task_id, retry_count, max_retries |
| `documents` | id, project_id, version, section_title, section_order, content, raw_content, source_urls |
| `document_blocks` | id, project_id, section_title, order_index, content, citations (JSON) |
| `project_logs` | id, project_id, sequence, level (enum), step, message, icon, created_at |

> **注意**: 实际运行时 FastAPI 生命周期通过 `Base.metadata.create_all` 自动建表，Alembic 主要用于版本化 schema 管理和生产环境部署。

---

## 8. 后端测试套件 (backend/tests/)

### 8.1 `conftest.py` — 测试配置与共享夹具

提供 SQLite 内存测试数据库、Mock Celery 任务、HTTP 测试客户端等共享夹具。

```python
TEST_DB_URL = "sqlite+aiosqlite:///./test_research.db"

class MockCeleryTask:
    """模拟 Celery AsyncResult —— 避免测试依赖 Redis"""
    _id = "mock-task-id-001"
    def delay(self, *args, **kwargs): return self
    def get(self, timeout=None): return {"status": "completed"}

@pytest.fixture(autouse=True)
async def setup_db():
    """每个测试前重建数据库表并插入默认用户"""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # 插入默认 admin 用户
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
async def client():
    """创建带覆写数据库依赖的 HTTP 测试客户端"""
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
```

### 8.2 测试文件一览

| 文件 | 覆盖范围 |
|------|----------|
| `test_imports.py` | 核心模块导入验证（config, schemas, models, celery_app, FastAPI app, outline_parser, ProjectRepo, engine） |
| `test_state_machine.py` | ProjectStatus 枚举完整性、终态验证、交互状态验证、状态流转路径、API 层约束 |
| `test_outline_parser.py` | Markdown 大纲解析（标准标题、空串、Tab 分隔、行内 #、三级标题过滤、中文标题、前后空白、真实大纲格式） |
| `test_api_integration.py` | 端到端 API 集成测试：健康检查、项目 CRUD、Schema 校验 (422)、状态机流转 (+ Mock Celery)、资料审核阻断、大纲审批、编辑器 AI 改写、404 处理 |

---

## 9. 研究引擎 (app/)

> 这是项目的**算法核心**，独立于 FastAPI 后端，可单独作为 Python 模块运行。

### 9.1 `app/llm/client.py` — LLM 客户端工厂（约 270 行）

**文本引擎 —— DeepSeek Chat（惰性初始化单例）**:

```python
_llm_instance = None

def get_llm():
    """惰性初始化 —— 首次调用时创建并缓存实例，避免模块 import 副作用"""
    global _llm_instance
    if _llm_instance is not None:
        return _llm_instance
    cfg = _get_config()
    _llm_instance = ChatOpenAI(
        api_key=cfg["deepseek_api_key"],
        base_url=cfg["deepseek_base_url"],
        model=cfg["deepseek_model"],       # deepseek-chat
        temperature=0.2,
        max_tokens=4096,  # 显式给足输出预算，避免内容被默认上限截断
    )
    return _llm_instance
```

**图像引擎 —— 硅基流动 (SiliconFlow) 图像生成**:

```python
SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"

def _wrap_prompt(raw_prompt: str) -> str:
    """风格强化：将原始描述包装为高规格商业 PPT 封面 Prompt
    → "Premium business presentation cover slide, cinematic 16:9 widescreen,
       minimalist corporate aesthetic, futuristic technology atmosphere..."
    """

def generate_image(prompt: str, output_path: str, retries: int = 2,
                   timeout: int = 120) -> bool:
    """
    调用硅基流动图像生成模型生成 16:9 横版概念图。
    返回 bool —— 成功返回 True，失败返回 False（调用方使用 CSS 渐变兜底）。
    支持: URL 下载 + Base64 解码 双通道输出。
    重试策略: 429 指数退避 / 5xx 线性退避 / Timeout 线性退避。
    """
```

**配置解析 —— `_get_config()`**:
优先从 Settings 单例读取，CLI 模式回退到环境变量。返回字典包含：
- `deepseek_api_key/base_url/model` — 文本引擎
- `siliconflow_api_key/image_model` — 图像引擎
- `image_width/image_height` — 出图尺寸 (默认 1024×576, 16:9)

### 9.2 `app/llm/prompts.py` — 🆕 v0.5 PromptFactory 多态模板中枢 + v0.6 内容深度增强

集中管理 4 套 LLM System Prompt（product/design × 大纲/章节），通过 `PromptFactory` 按模板类型分发。

**🆕 v0.6 Prompt 增强**：章节 Prompt 新增「内容深度与覆盖度（最高优先级）」区块：
- 强制 LLM 充分综合全部参考资料，不得遗漏关键数据（数字、型号、价格、规格、份额、时间）
- 每个要点必须言之有物，包含具体数据/事实/案例/来源
- 排版规则放宽为"精炼但充实"：段落 2-4 行（约 100 字），可使用多个要点充分展开
- product 与 design 两套 Prompt 均同步升级

```python
class PromptFactory:
    """
    Prompt 工厂 —— 根据 template_type 返回对应的 System Prompt。

    用法:
        sys_prompt = PromptFactory.get_outline_prompt("design")
        sys_prompt = PromptFactory.get_section_prompt("product")
    """

    @staticmethod
    def get_outline_prompt(template_type: str = "product") -> str:
        """product: 产品战略总监 Persona / design: 工业设计师 Persona"""
        if template_type == "design":
            return DESIGN_OUTLINE_SYSTEM
        return PRODUCT_OUTLINE_SYSTEM

    @staticmethod
    def get_section_prompt(template_type: str = "product") -> str:
        """product: 商业咨询顾问 Persona / design: 工业设计评论家 Persona"""
        if template_type == "design":
            return DESIGN_SECTION_SYSTEM
        return PRODUCT_SECTION_SYSTEM
```

**模板对比**:

| 维度 | product (产品预研) | design (工业设计推演) |
|------|---------------------|------------------------|
| 定位 | 产品定位、功能、CMF、竞品、定价 | 设计语言、人机工程、CMF、结构堆叠 |
| 视角 | 商业分析师 | 工业设计师 |
| 章节数 | 7-8 | 7-8 |
| 侧重 | 市场竞争力、技术可行性、定价策略 | 造型美学、UX 可触达、制造可行性 |

### 9.3 `app/search/tavily_search.py` — Tavily 搜索封装

```python
def tavily_search(query: str, max_results: int = 5):
    """调用 Tavily Search API，返回结构化搜索结果"""
    client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    return client.search(query=query, max_results=max_results)
```

### 9.4 `app/search/image_search.py` — 图片搜索（DuckDuckGo，免 API Key / ddgs v9.x）

```python
from ddgs import DDGS  # 🆕 v0.7.1: ddgs v9.14.x, API 参数变更

def search_images(query: str, max_results: int = 3) -> list[dict]:
    """
    基于 DuckDuckGo 图片搜索，免 API Key。
    返回：[{"title": "...", "image": "https://...", "url": "..."}]
    """
    ddgs = DDGS()
    results = ddgs.images(query, region="wt-wt",   # v9.x: query 为位置参数，不再用 keywords=
                          safesearch="moderate", max_results=max_results)
    return [{"title": r.get("title", ""), "image": r.get("image", ""),
             "url": r.get("url", "")} for r in results if r.get("image")]
```

### 9.5 `app/crawler/firecrawl_crawler.py` — Firecrawl 深度抓取

```python
def crawl_url(url: str):
    """调用 Firecrawl API 抓取网页，返回 Markdown 格式的正文内容"""
    app = FirecrawlApp(api_key=os.getenv("FIRECRAWL_API_KEY"))
    return app.scrape(url=url, formats=["markdown"])
```

### 9.6 `app/context/context_builder.py` — 搜索上下文构建

将 Tavily 返回的原始搜索结果格式化为 LLM 可消费的结构化上下文块（含来源 URL 和编号）。

### 9.7 `app/rag/chunker.py` — 文本切片

```python
def chunk_text(text: str, chunk_size: int = 1200, chunk_overlap: int = 200):
    """使用 RecursiveCharacterTextSplitter 将长文本切分为重叠片段"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return splitter.split_text(text)
```

### 9.8 `app/rag/local_parser.py` — 本地 PDF 解析

```python
def parse_local_pdf(file_path: str, filename: str) -> list[dict]:
    """
    使用 PyMuPDF (fitz) 解析本地 PDF 文件，提取全文文本，切片后返回。
    每条切片以 local://{filename} 作为伪装 URL。
    Returns: [{"content": "...", "url": "local://xxx.pdf"}, ...]
    """
    doc = fitz.open(file_path)
    full_text = "\n".join(page.get_text() for page in doc if page.get_text())
    doc.close()
    chunks = chunk_text(full_text)
    return [{"content": c, "url": f"local://{filename}"} for c in chunks]
```

> **设计意图**: 配合 `/projects/{id}/upload-docs` 端点，用户上传的 PDF 通过此模块解析 → 切片 → 存入项目隔离的 Chroma + BM25 知识库，最终在 AI 对话和撰写时作为 RAG 参考上下文注入。

### 9.9 `app/rag/vector_store.py` — 向量 + BM25 双引擎持久化

```python
class LocalEmbeddingModel:
    """Embedding 模型封装 —— 线程安全单例（SentenceTransformer）"""

def build_vector_store(chunk_data_list: list[dict], project_id: str | None = None):
    """
    接收带元数据的切片列表，构建：
    1. Chroma 向量库（per-project 子目录隔离）
    2. BM25 语料 pickle 持久化
    杜绝多项目并发覆盖。
    """
```

> **关键设计**: 每个项目使用独立子目录 (`chroma_db/<project_id>/`, `bm25_db/<project_id>/`)，杜绝多项目并发时的数据覆盖问题。Embedding 模型路径从配置中心读取，默认使用 `BAAI/bge-small-zh-v1.5`。

### 9.10 `app/rag/retriever.py` — 混合检索引擎（约 250 行）

```python
class LocalEmbeddingModel:
    """Embedding 模型封装 —— 线程安全模块级单例（SentenceTransformer）"""

class HybridRetriever:
    """Chroma 向量检索 + BM25 关键词检索 + RRF 融合"""

    def retrieve(self, query: str, k: int = 5) -> list[Document]:
        # 向量检索
        vector_results = self.vector_store.similarity_search(query, k=k*2)
        # BM25 关键词检索
        bm25_results = self.bm25_retriever.search(query, top_k=k*2)
        # RRF (Reciprocal Rank Fusion) 融合排序
        fused = self._rrf_fusion(vector_results, bm25_results)
        return fused[:k]
```

**🆕 v0.6 Source Ranking Engine —— 信息源分级权重**:

```python
def get_source_weight(url: str) -> float:
    """
    权重档位（乘入 RRF 分数）：
      T0 (1.5x): 权威来源——PDF 报告、政府(.gov)、交易所(sse/szse/hkex)、
                 本地上传资料(local://)
      T1 (1.2x): 专业媒体——Bloomberg、36kr、财新、雪球、虎嗅、第一财经
      T2 (1.0x): 普通新闻——默认权重，不奖不惩
      T3 (0.5x): UGC/自媒体——知乎、B站、微博、贴吧、小红书（重度降权）
    """
```

**加强版 RRF 融合**:
```python
def reciprocal_rank_fusion(vector_results, bm25_results, k=60) -> list:
    """
    使用 (page_content + "|" + url) 作为唯一键，防止不同 URL
    引用同一段内容的文本被去重吃掉。
    base_score = 1.0 / (rank + k)
    final_score = base_score × get_source_weight(url)  # v0.6 引入 Source Ranking
    """
```

**公共检索接口**:
```python
def retrieve(query: str, k: int = 5, project_id: str | None = None) -> list:
    """
    对外暴露的统一混合检索接口。
    - 优先从 Settings 读取 chroma_db/<project_id>/ 和 bm25_db/<project_id>/
    - project_id=None 时发出 FutureWarning（多项目并发可能覆盖）
    - Chroma 检索失败 → 降级为空结果（不阻断）
    - BM25 pickle 加载失败 → 降级为纯向量检索
    """
```

### 9.11 `app/rag/rag_pipeline.py` — RAG Pipeline 编排

```python
def build_knowledge_base(query: str, project_id: str | None = None):
    """搜索 → 爬取 → 切片 → 向量化，构建项目知识库的完整流水线"""

def retrieve_context(query: str, k: int = 5, project_id: str | None = None) -> str:
    """检索并格式化为 LLM 可消费的上下文字符串（含来源 URL）"""
```

串联 Tavily 搜索 → Firecrawl 抓取 → chunker 切片 → vector_store 持久化的完整 RAG 构建流程。

### 9.12 `app/rag/citation_utils.py` — 引用溯源引擎

```python
def build_context_with_citations(documents: list[Document]) -> tuple[str, dict]:
    """
    将检索到的文档构建为带编号引用的上下文。
    🆕 v0.7.2: 同 URL 的多个 Chunk 合并为同一个上下文块，
    避免 LLM 因同源重复片段而反复复述同一事实。
    返回：(带 [^n] 标记的上下文字符串, {ref_num: {title, url, snippet}})
    """
    context_parts = []
    ref_map = {}
    url_to_id = {}
    url_to_chunks = {}  # 🆕 v0.7.2: 按 URL 分组 chunk，合并同源内容
    current_id = 1

    for doc in documents:
        url = doc.metadata.get("url", "unknown")
        chunk = (doc.page_content or "").strip()
        if not chunk:
            continue  # 🆕 跳过空 chunk

        # URL 去重：同 URL 共享同一编号
        if url not in url_to_id:
            url_to_id[url] = current_id
            ref_map[current_id] = url
            url_to_chunks[url] = []
            current_id += 1

        if chunk not in url_to_chunks[url]:
            url_to_chunks[url].append(chunk)

    # 按 URL 合并输出，每个 URL 一个上下文块
    for url, ref_id in url_to_id.items():
        merged_content = "\n\n".join(url_to_chunks.get(url, []))
        if merged_content:
            context_parts.append(f"[^{ref_id}] {merged_content}")

    context_str = "\n\n".join(context_parts)
    return context_str, ref_map


def resolve_and_append_citations(llm_output: str, ref_map: dict) -> str:
    """
    解析 LLM 输出中的 [^n] 引用标记，按出现顺序追加脚注定义块。
    🆕 v0.6 兜底：若 LLM 未使用任何引用，自动附加前 2 个来源的脚注定义，
    保证 Document 快照始终带有可溯源信息。
    """
```

### 9.13 `app/planner/outline_generator.py` — 大纲生成

```python
def generate_outline(topic: str, template_type: str = "product") -> str:
    """委托 PromptFactory 获取对应模板的 System Prompt，LLM 生成大纲"""
    sys_prompt = PromptFactory.get_outline_prompt(template_type)
    # 根据模板类型构造不同的 user_prompt
    if template_type == "design":
        user_prompt = f"请为产品「{topic}」生成一份工业设计推演大纲。要求：6-7 个章节..."
    else:
        user_prompt = f"请为产品「{topic}」生成一份产品研究报告大纲。要求：7-8 个章节..."
    llm = get_llm()  # temperature=0.2 (固定)
    response = llm.invoke([
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_prompt},
    ])
    outline = response.content.strip()
    # 确保以 # 标题开头，否则自动补全
    if not outline.startswith("#"):
        outline = f"# {topic}\n\n" + outline
    return outline
```

### 9.14 `app/planner/query_planner.py` — 检索词规划器

```python
def plan_section_queries(topic: str, section_title: str, num_queries: int = 3) -> list:
    """
    将宽泛的章节标题拆解为多个具体的检索问句 (Query Planning)。
    使用 LLM 生成高密度关键词搜索词组，避免宽泛噪音。
    如 "市场分析" → ["Meta Ray-Ban 华为 Xreal 销量 市场份额", ...]
    """
```

**设计价值**: 原始检索直接用章节标题，往往召回宽泛的噪音。Query Planning 用 LLM 将标题拆解为高密度关键词词组，在三方评测（`tests/eval_ranking.py`）中召回质量显著优于 baseline。

### 9.15 `app/planner/compare_query.py` — Query Planning 对比评测

```python
def run_comparison(topic, section):
    """对比原始检索 vs Query Planning 的检索质量。
    路径 A: 直接使用标题检索 (baseline)
    路径 B: Query Planning 拆解后检索
    输出覆盖度、相关性、耗时三维对比报告。
    """
```

### 9.16 `app/report/section_writer.py` — 章节撰写（约 222 行，含多模态路由 + 输出清理 + 模板路由）

**顶层入口 —— `write_section()` 多模态路由**:

```python
# 多模态绘图关键词（用于路由到生图策略）
_IMAGE_SECTION_KEYWORDS = ["生图", "图鉴", "概念图"]

def _is_image_section(section_title: str) -> bool:
    """判断是否为多模态绘图章节 —— 检测标题中的生图关键词"""
    return any(kw in section_title for kw in _IMAGE_SECTION_KEYWORDS)

def write_section(topic, section_title, project_id=None,
                  template_type="product", search_depth=10) -> str:
    """
    顶层路由：
    - 多模态绘图章节（标题含"生图/图鉴/概念图"）→ _write_image_section()
    - 普通文本章节 → _write_text_section()
    """
    if _is_image_section(section_title):
        return _write_image_section(topic, section_title)
    return _write_text_section(topic, section_title, project_id,
                               template_type, search_depth)
```

**`_write_text_section()` — RAG 检索 → LLM 深度撰写 → 引用溯源**:

```python
def _write_text_section(topic, section_title, project_id, template_type, search_depth):
    llm = get_llm()
    retriever_k = max(12, search_depth)  # 🆕 v0.6: 最少 12 篇，充分调用知识库
    docs = retrieve(f"{topic} {section_title}", k=retriever_k, project_id=project_id)
    context_str, ref_map = build_context_with_citations(docs)
    sys_prompt = PromptFactory.get_section_prompt(template_type)

    prompt = f"""{sys_prompt}
【产品研究主题】: {topic}
【当前撰写章节】: {section_title}
【参考资料】: {context_str}

【内容深度要求（最高优先级）】：
- 充分综合上方【参考资料】中的全部信息，覆盖关键数据与事实
- 每个要点都要有具体数据/事实/案例支撑，杜绝空泛口号

【格式要求（为 PPT 排版优化）】：
2. 以 Bullet points（无序列表 - ）为主拆解观点；单个 bullet 只表达一个主结论，
   尽量控制在 2-3 行内。若信息很多，拆成多个 bullet，禁止把多个并列事实塞进一个超长 bullet。
3. 单个段落控制在 2-4 行（约 100 字内）；优先使用短段落 + 多 bullet，而不是长段落堆叠。
4. 如有数据对比、参数差异、版本差异、竞品差异，强制使用 Markdown 表格输出。
5. 若某小节下存在 4 条以上并列要点，优先按"维度/结论/数据"方式组织为表格或更短的 bullet 序列。
6. 同一小节内，相同事实、相同参数、相同结论只表达一次；多来源支持同一事实时融合到同一 bullet。
7. 你的输出将直接转化为幻灯片，请兼顾排版呼吸感与内容充实度。
8. 【最高优先级：数据表格规范】绝不允许使用逗号分隔的 CSV 格式！
   绝不允许使用引号 " " 包围单元格内容！
   绝不允许输出 "The following table:" 这类前缀废话！
9. 【最高优先级：引用格式】文内引用必须严格使用 [^1] 的角标格式！"""
    response = llm.invoke(prompt)
    raw_content = _clean_llm_output(response.content, section_title)
    return resolve_and_append_citations(raw_content, ref_map)
```

**`_clean_llm_output()` — LLM 输出三阶段清理**:

```python
def _clean_llm_output(raw_content: str, section_title: str) -> str:
    """
    Step 1: 截断首个 ## 之前的寒暄语/前缀文本（"好的"、"以下是"等）
    Step 2: 移除重复的章节标题 ——
            检测首个 ## 之后再次出现的同数字前缀或同文本标题，
            使用数字前缀匹配 + 文本包含匹配双重判定
    Step 3: 正则移除残留的常见寒暄语模式
    """
```

**`_write_image_section()` — 多模态绘图引擎**:

```python
def _write_image_section(topic: str, section_title: str) -> str:
    """
    1. LLM 生成英文工业设计级 Prompt（材质/造型/光影/视角，16:9 构图）
    2. 调用 generate_image(img_prompt, output_path) → 硅基流动 API
    3. 成功 → 返回 Markdown 图片引用（![概念图](../outputs/images/...)）
    4. 失败 → graceful degradation（CSS 渐变兜底提示）
    """
```

> **关键设计**: `_clean_llm_output` 的三阶段清理是 v0.6 的质量保障核心——Step 1 解决 LLM 在正文前输出"好的，以下是..."的问题；Step 2 解决 LLM 在正文中重复输出章节标题的问题；Step 3 兜底清除残留寒暄。三重禁令（禁 CSV/禁引号/禁废话前缀）在 Prompt 和清理函数双保险。

### 9.17 `app/report/pdf_generator.py` — 16:9 横版 PDF

```python
def markdown_to_pdf(md_content: str, project_id: str, topic: str) -> str:
    """WeasyPrint 渲染 16:9 PPT 风格 PDF"""
    html = f"""
    <html><head><style>
        @page {{ size: 1440px 810px; margin: 80px 100px; }}
        body  {{ font-family: 'PingFang SC','Microsoft YaHei',sans-serif;
                 font-size: 16pt; color: #1e293b; }}
        h1    {{ font-size: 36pt; font-weight: 700; color: #0f172a; }}
        h2    {{ font-size: 24pt; font-weight: 600; page-break-before: always; }}
        .cover {{ text-align: center; padding-top: 250px; }}
        .citation {{ color: #3b82f6; font-size: 9pt; }}
    </style></head><body>
        <div class="cover"><h1>{safe_topic}</h1><p>产品分析报告</p></div>
        {markdown_to_html(md_content)}
    </body></html>"""
    pdf_path = f"outputs/{topic}_{datetime.now():%Y%m%d_%H%M%S}.pdf"
    HTML(string=html).write_pdf(pdf_path)
    return pdf_path

def render_custom_html_to_pdf(raw_html: str, topic: str, output_pdf_path: str):
    """🆕 v0.3: 接收前端自由编辑的 HTML → WeasyPrint 渲染 PDF
    🆕 v0.7.2: .slide CSS 修正 — height: 180mm + max-height + overflow:hidden
    替代 height:100%，防止幻灯片在 PDF 中无限拉伸"""
    # 确保输出目录存在（WeasyPrint 不会自动创建父目录）
    # 安全化 topic 中的 HTML 特殊字符（防 f-string 注入）
    safe_topic = topic.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
```

### 9.18 `app/report/markdown_formatter.py` — Markdown 报告组装

```python
def build_report(title: str, sections: list) -> str:
    """将标题 + 多个章节正文拼接为完整 Markdown 报告"""
    report = f"# {title}\n\n"
    for section in sections:
        report += section + "\n\n"
    return report
```

### 9.19 `app/retrieval/research_pipeline.py` — CLI 研究流水线

```python
def research_topic(query: str):
    """端到端研究流水线：搜索 → 抓取 → 返回带结构化的文档列表"""
    search_results = tavily_search(query)
    for item in search_results["results"][:3]:
        crawl_result = crawl_url(item["url"])
        collected_docs.append({"title": ..., "url": ..., "content": ...})
    return collected_docs
```

### 9.20 `app/orchestrator/workflow.py` — 端到端流程

```python
def run_workflow(topic: str) -> dict:
    """CLI 可调用的完整工作流（不使用 Celery）"""
    search_results = tavily_search(topic)
    crawled = [crawl_url(r["url"]) for r in search_results[:5]]
    chunks = []
    for c in crawled:
        chunks.extend(chunk_text(c.get("content", "")))
    build_vector_store(chunks, "cli_session")
    build_bm25_index(chunks, "cli_session")
    outline = generate_outline("cli_session", "product")
    sections = extract_sections(outline)
    written = []
    for s in sections:
        written.append(write_section("cli_session", s))
    md = build_report(topic, written)
    pdf = markdown_to_pdf(md, "cli_session", topic)
    return {"outline": outline, "sections": written, "pdf": pdf}
```

### 9.21 `app/shared/outline_parser.py` — Markdown 大纲解析（副本）

与 `backend/app/shared/outline_parser.py` 功能一致，供 app 层独立运行时使用。

### 9.22 `app/shared/time_utils.py` — 统一 UTC 时间戳

```python
def utcnow() -> datetime:
    """
    返回带 UTC 时区标记的当前时间。
    统一全项目时间处理，替代散落的 datetime.now() 调用。
    """
    return datetime.now(timezone.utc)
```

### 9.23 备份/实验版本

| 文件 | 说明 |
|------|------|
| `app/llm/client01.py` | LLM 客户端早期版本备份 |
| `app/report/pdf_generator01.py` | PDF 生成器早期版本备份 |
| `app/report/section_writer01.py` | 章节撰写器早期版本备份 |

---

## 10. 前端架构 (frontend/src/)

### 10.1 `main.tsx` — React 入口

```tsx
const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 5_000, gcTime: 5 * 60_000, retry: 2 },
  },
});
createRoot(document.getElementById("root")!).render(
  <BrowserRouter>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </BrowserRouter>
);
```

### 10.2 `App.tsx` — 路由定义

```tsx
<Routes>
  <Route element={<Layout />}>
    <Route path="/" element={<DashboardPage />} />
    <Route path="/projects/:projectId/workspace" element={<WorkspacePage />} />
    <Route path="/projects/:projectId/progress" element={<ProgressPage />} />
    <Route path="/projects/:projectId/report" element={<ReportPage />} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Route>
  {/* EditorPage 独立路由 —— 全屏沉浸式 Canvas 编辑器 */}
  <Route path="/projects/:projectId/editor" element={<EditorPage />} />
</Routes>
```

### 10.3 页面组件

| 文件 | 作用 |
|------|------|
| `pages/DashboardPage.tsx` | 首页仪表盘：项目列表 + 创建新项目 |
| `pages/WorkspacePage.tsx` | **项目管理页** (~900 行)：大纲审核、资料筛选、状态监控、"进入编辑器"入口 |
| `pages/EditorPage.tsx` | 🆕 **Canvas 编辑器页** (~500 行)：全屏沉浸式幻灯片编辑器 (React-Konva + AI 面板 + Zustand) |
| `pages/ProgressPage.tsx` | 项目执行进度全屏视图（实时任务状态 + 时间轴） |
| `pages/ReportPage.tsx` | 最终报告预览页（Markdown 渲染 + 引用角标） |

### 10.4 `pages/WorkspacePage.tsx` — 项目管理工作台（~900 行）

**v0.3 重构**: Canvas 编辑功能迁移到专用 `EditorPage`，WorkspacePage 回归纯项目管理职责。

**三栏布局**:

```
┌──────────────────────────────────────────────────────────────┐
│  ThreePaneLayout                                             │
│  ┌──────────┬──────────────────────────┬────────────────┐    │
│  │ 大纲目录 │  状态面板                │  日志 / 引用   │    │
│  │          │  - ProgressTracker       │                │    │
│  │          │  - SourcesReview ← 审核  │                │    │
│  │          │  - OutlineApproval ← 拦截 │                │    │
│  │          │  - 🎨 进入 Canvas 编辑器  │                │    │
│  └──────────┴──────────────────────────┴────────────────┘    │
│                                                               │
│  顶部工具栏: [⬅返回] [📎上传] [模板选择] [搜索强度] [状态标签]│
└──────────────────────────────────────────────────────────────┘
```

**v0.5 新增**: 模板选择器 (product/design)、搜索强度选择器 (5/10/15/20)。

### 10.5 `pages/EditorPage.tsx` — Canvas 沉浸式编辑器（约 487 行）

全屏独立路由（`/projects/:projectId/editor`），不嵌入 Layout 壳，提供专注的幻灯片编辑体验。

```
┌──────────────────────────────────────────────────────────┐
│ ← 返回工作台 │ 主题名 │ [状态标签] │ [导出 PDF] │ 🤖    │
├──────────┬───────────────────────────────┬───────────────┤
│ 缩略图   │                              │  AI 助手      │
│ 列表     │   React-Konva Canvas          │  (可折叠)     │
│          │   1280×720 (16:9)            │               │
│ [封面]   │                              │  SSE 流式对话 │
│ [P1]     │   声明式渲染 · 拖拽缩放       │  +            │
│ [+粘贴]  │   Transformer 选中框         │  应用到画布   │
├──────────┴───────────────────────────────┤  插入图片     │
│ 🆕 v0.7 图片素材库 (ImageGallery)        │               │
│  [搜索栏 + 强度]  [缩略图1] [缩略图2]... │               │
└──────────────────────────────────────────┴───────────────┘
```

**数据流**: `useProjectStatus` + `useProjectBlocks` → `convertBlocksToKonvaSlides(topic, blocks, logoUrl)` → `useCanvasStore.setSlides()` → `CanvasSlideEditor`
- 🆕 v0.7: 集成 ImageGallery 组件（`<ImageGallery projectId={projectId!} />`），位于 Canvas 编辑器下方
- 🆕 v0.6: Editor 向 CanvasSlideEditor 传递 `projectId`，使工具栏和占位框可以直接上传图片

**AiPanel 内嵌组件（约 220 行）**:
- SSE 流式对话：调用 `editorApi.chat({ chat_mode: 'work', ... })` → `ReadableStream` 解析 SSE 事件
- **应用到画布**：`useCanvasStore.getState().addElement(activePage, { type: 'text', ... })` 直连 Zustand
- **插入图片**：自动提取 AI 回复中的图片 URL，`addElement({ type: 'image', src: url })` 注入画布
- 支持 `chat_mode: 'work'`（RAG 知识库注入）和 `'chat'`（通用闲聊）

**PDF 导出 (v0.6 增强)**: 以 Zustand store 为准（AiPanel 等可能直接写入 store），回退到本地 slides。导出时 placeholder 元素自动跳过。

**PDF 导出**: 原生 Konva 离屏渲染 → `canvasRef.current.capturePage(elements, 1280, 720, 2)` → `jsPDF('landscape', 'px', [1280, 720])` → `pdf.addImage(dataUrl, 'JPEG', ...)` → `pdf.save()`

### 10.6 通用组件 (`components/common/`)

| 文件 | 作用 |
|------|------|
| `badge.tsx` | 状态徽章（pending / processing / completed / failed） |
| `button.tsx` | 通用按钮组件 |
| `dialog.tsx` | Radix UI 对话框封装 |
| `input.tsx` | 通用输入框组件 |
| `popover.tsx` | Radix UI 弹出层封装 |

### 10.7 布局组件 (`components/layout/`)

| 文件 | 作用 |
|------|------|
| `Layout.tsx` | 全局布局壳（侧边栏 + `<Outlet />`） |
| `Sidebar.tsx` | 侧边栏导航（项目列表 + Logo + 新建按钮） |
| `ThreePaneLayout.tsx` | 三栏可拖拽布局（左/中/右比例可调） |

### 10.8 项目组件 (`components/projects/`)

| 文件 | 作用 |
|------|------|
| `CreateProjectModal.tsx` | 新建项目弹窗（输入 topic + 选择 template_type + search_depth） |
| `ProjectCard.tsx` | 项目卡片（显示状态 + 进度条 + 点击进入工作台） |
| `ProgressTracker.tsx` | 任务进度追踪条（任务列表 + 状态图标 + 百分比） |
| `SourcesReview.tsx` | 资料审核面板（用户勾选保留/删除搜索到的来源） |
| `OutlineApproval.tsx` | 大纲审核面板（用户确认/编辑 AI 生成的大纲） |
| `TerminalTimeline.tsx` | 终端风格实时日志流（基于 ProjectLog 模型渲染） |

### 10.9 编辑器组件 (`components/editor/`)

**🆕 `CanvasSlideEditor.tsx`** — React-Konva 幻灯片编辑器（约 1670 行）：

```tsx
function CanvasSlideEditor({ slides, activeIndex, onActiveIndexChange,
    onSlidesChange, canvasRef, readOnly, showToolbar, projectId }: Props) {
  // 左侧缩略图列表：排序、删除、复制页面、粘贴幻灯片、添加页面
  // 中央 React-Konva Stage（1280×720，16:9 自适应缩放）
  //   Stage → Layer → Group/Rect/Text/Image/Circle/Line/Table/Placeholder + Transformer
  // 增强工具栏：
  //   元素插入：文本、图片(上传/URL)、矩形、圆形、直线、表格
  //   颜色拾取器：fill + stroke（扩展至 rect 类型）
  //   排版控制：Bold/Italic/Underline + AlignLeft/Center/Right + FontSize 数字输入
  //   图层排序：上移/下移/置顶/置底
  //   图片操作：替换图片 (RefreshCw) + 裁剪 (Crop)
  //   历史控制：Undo/Redo（zundo temporal → useTemporalStore）
  //   Ctrl+C/V 复制粘贴 + Delete 删除
  //   表格行列控制面板 (TableControlPanel)
  // 交互：
  //   Transformer 8 锚点选中框 + 拖拽缩放旋转
  //   双击文字 → Html textarea 悬浮层（react-konva-utils）
  //   双击表格单元格 → 内联编辑
  //   双击图片占位框 → pickAndUploadImage() 打开文件选择器 → 替换为真实图片
  // 同步：
  //   内部状态管理 + isInternalChange ref 防循环同步
  //   onSlidesChange 回调通知父组件
  // 暴露 editorApi: { addText, addImage } 给父组件
  // 导出：capturePage() → 原生 Konva 离屏 Stage → toBlob('image/jpeg', 0.92) → dataURL
  //   placeholder 元素导出时跳过，保持 PDF 干净
  //   🆕 v0.7.2: 所有 Text 元素统一 lineHeight=1.4（声明式渲染 + 原生导出双路径）
  //            clipFunc 类型断言修复 (imageNode as any).clipFunc(...)
  //   🆕 v0.7: 图片裁剪导出 — capturePage 中 image case 支持 clipFunc
}

// 🆕 v0.7: 拖拽到画布 — handleDragOver/handleDrop，解析 application/json，
//         使用 stage.setPointersPositions() 精确定位落点
// 🆕 v0.7: 图片裁剪模式 —
//         enterClipMode/exitClipMode/applyClip/resetClip
//         四个暗色遮罩矩形 + 虚线裁剪框（可拖拽 + 四角缩放 Transformer）
//         Ctrl+Shift+C/V 复制粘贴幻灯片 + Ctrl+M 新增 + Ctrl+Shift+Del 删除
//         boundBoxFunc 限制裁剪区域不超出图片边界
//         RenderImage clipFunc 坐标转换（边框坐标 → KonvaImage 局部坐标系）
// 🆕 v0.6: 图片占位框 RenderPlaceholder — 虚线框 + 提示文字，双击替换为真实图片
// 🆕 v0.6: pickAndUploadImage — 选图 → uploadAsset 持久化 → 返回 /api/v1/files/ URL
//           失败时自动回退 blob URL（本地预览不依赖后端）
// 🆕 v0.6: RenderTable 样式增强 — 表头填充色/文字色 + 斑马纹 + 边框颜色
// 可重用图片组件 RenderImage：Contain 等比缩放 (Math.min(w/imgW, h/imgH)) + 居中
```

**核心能力 (v0.7)**:
- 左侧缩略图列表（排序/删除/复制/粘贴幻灯片 + 添加页面）
- 中央 React-Konva Stage（1280×720，16:9 自适应缩放）
- 增强工具栏：图片裁剪 (Crop) + 拖拽图片到画布
- 键盘快捷键：Ctrl+Shift+D 复制幻灯片、Ctrl+Shift+C/V 复制粘贴幻灯片、Ctrl+M 新增、Ctrl+Shift+Del 删除
- 裁剪模式：四角缩放 + 拖拽移动 + 暗色遮罩 + Enter 应用 / Esc 取消
- v0.6: RenderImage Contain 等比缩放 + 图片上传持久化
- v0.4: 原生 Konva 离屏 Stage JPEG 导出（根治 `Invalid string length`）

**`BlockEditor.tsx`** — ⚠️ 已废弃（v0.3 起由 CanvasSlideEditor 替代）：
  原 Tiptap 块级编辑器，每 block 一个独立 Tiptap 实例，16:9 CSS 模拟幻灯片。
  保留用于向后兼容，不再被任何页面引用。

**`InlineAIBubble.tsx`** — ⚠️ 已废弃（Tiptap BubbleMenu，不再使用）：
  悬浮 AI 改写在 Canvas 架构中由 AI 助手面板的"应用到画布"按钮替代。

**🆕 v0.7.1 `ImageGallery.tsx`** — 图片搜索 + 素材库面板（约 420 行）：

```tsx
export function ImageGallery({ projectId, className, activePage, projectStatus, imagesPerPage }: Props) {
  // 可折叠面板（折叠状态持久化到 localStorage "imageGalleryCollapsed"）
  //   🆕 v0.7.1: 标题栏改为 <div role="button"> 避免 button 嵌套 DOM 错误
  // 搜索栏：文本输入 + 搜索强度选择器（快速/标准/深度/极致 → search_depth 5/10/15/20）
  //   调用 projectsApi.searchImages(projectId, { query, search_depth })
  //   🆕 v0.7.1: 搜索成功但无结果 → 黄色 hint "未找到相关图片"（5s 自动消失）
  //   🆕 v0.7.1: HTTP 5xx → "搜索服务异常" / 网络不通 → "网络连接失败"
  //   新搜索结果前置合并到 images 状态（按 id 去重）
  // 横向滚动缩略图网格：120×68 缩略图 + 拖拽到画布 (draggable + onDragStart)
  //   dataTransfer 格式: application/json { imageUrl, title, query }
  //   加载失败时显示占位 Icon
  // 悬停删除按钮（projectsApi.deleteProjectImage）
  // 挂载时自动加载 projectsApi.getProjectImages()
  // 🆕 v0.7.1: 上下文空状态 — 按 projectStatus 显示不同引导：
  //   preparing/waiting 早期阶段 → "项目尚未开始AI撰写，图片将在撰写阶段自动搜索添加"
  //   drafting 撰写中 → "AI 正在撰写报告并自动搜索相关图片，新图片将陆续出现"
  //   completed + imagesPerPage=0 → "自动图片搜索已关闭"
  //   completed + 无图片 → "未找到图片素材"
  // 🆕 v0.7.1: DRAFTING 阶段 15s 自动轮询刷新
  // 🆕 v0.7.1: 手动刷新按钮（标题栏 + 空状态区）
}
```

**`DiffViewNode.tsx`** — 🆕 v0.5 AI 改写差异预览：
  当 AI 返回改写结果后，在编辑器上方/下方渲染 Diff 面板：
  - 原始文本（红色/删除线）+ 新文本（绿色）
  - 行级 Diff 算法（`computeLineDiff`）
  - Approve ✓ / Discard ✗ 按钮
  - 临时浮层面板，不修改 DOM 结构

**`extensions/CitationMark.ts`** — Tiptap 自定义 Mark 扩展（保留）

**`extensions/Citation.tsx`** — 引用角标 React 组件（保留）

### 10.10 状态管理 (`store/`)

**🆕 `useCanvasStore.ts`** — Zustand 原子化 Canvas 状态管理（约 231 行）：

```tsx
export interface CanvasElement {
  id: string
  type: 'text' | 'rect' | 'image' | 'table' | 'circle' | 'line' | 'placeholder'
  x: number; y: number; width: number; height: number
  fill?: string; text?: string; src?: string; tableData?: string[][]
  // 🆕 v0.6 表格样式（带默认兜底）
  headerFill?: string; headerColor?: string; rowAltFill?: string; tableBorderColor?: string
  // 🆕 v0.5 排版字段
  fontWeight?: string; fontStyle?: string; textDecoration?: string
  align?: string; fontSize?: number
  // 🆕 v0.5 边框与装饰
  stroke?: string; strokeWidth?: number; radius?: number; points?: number[]
  // 🆕 v0.6 元素分类标记
  name?: string  // 'decor' = 不可选中的装饰元素；'placeholder' = 图片占位框
}

export interface CanvasState {
  slides: { [pageNumber: number]: CanvasElement[] }  // 按页索引的元素数组
  activePage: number
  selectedElementIds: string[]       // Transformer 多选
  editingElementId: string | null    // 双击文字编辑
  clipboard: CanvasElement | null    // Ctrl+C/V 元素级剪贴板
  clipModeElementId: string | null    // 🆕 v0.7 裁剪模式下的元素 ID (null = 非裁剪模式)
  copiedSlide: CanvasElement[] | null // 🆕 v0.7 跨页幻灯片剪贴板

  // 原子操作 —— 每次只修改单个元素，不触发全量序列化
  updateElement: (page, id, attrs) => void  // 单元素部分更新
  addElement: (page, element) => void       // 追加元素（自动生成 id）
  deleteElement: (page, id) => void         // 删除元素
  setSlides: (slides) => void              // 批量设置（初始化用）
  setActivePage: (page) => void            // 切页 → 自动清除选中/编辑状态
  // 高级操作
  setSelectedElements: (ids) => void
  setEditingElement: (id) => void
  duplicateSlide: (page) => void           // 深拷贝页面 + 重新分配所有 id
  copyElement: (id) => void                // 全局查找元素 → 深拷贝到 clipboard
  pasteElement: (page) => void             // clipboard → 新元素 (x+20, y+20 偏移)
  moveLayer: (page, id, direction) => void // up/down/top/bottom 图层排序
  // 🆕 v0.7 裁剪与跨页剪贴板
  setClipMode: (elementId: string | null) => void  // 进入/退出裁剪模式
  copySlide: (page: number) => void                // 深拷贝整页元素到 copiedSlide
  pasteSlide: (afterPage: number) => void          // 在指定页后插入 copiedSlide
}

// zundo temporal 中间件 —— 无侵入式 Undo/Redo
export const useCanvasStore = create<CanvasState>()(
  temporal(storeImpl, {
    limit: 50,  // 最多保留 50 步历史
    partialize: (state) => ({
      slides: state.slides,           // 只记录 slides 和 activePage
      activePage: state.activePage,   // 忽略选中/编辑/clipboard 状态
    }),
  })
)
```

**设计价值**:
- Fabric.js `fc.toJSON()` 每次全量序列化（所有对象 + 属性 + 样式）→ 拖拽卡顿
- Zustand `updateElement(page, id, { x, y })` 只更新单个元素的坐标，不触碰其他元素
- React-Konva 声明式渲染：React 自动 diff 最小化 DOM 更新
- zundo temporal 中间件：无侵入式 Undo/Redo，自动记录历史

### 10.11 数据转换层 (`lib/dataTransform.ts`) — v0.4 根治 + v0.5 扩展 + v0.6 排版精修 + v0.7.2 字符宽度模型重构（约 1350 行）

```tsx
export function convertBlocksToKonvaSlides(
  topic: string,
  blocks: Pick<DocumentBlockResponse, 'section_title' | 'content' | 'order_index'>[],
  logoUrl?: string,
): KonvaSlide[] {
  // Slide 0: 封面（深色背景 #0f1117 + 品牌色装饰 + 大标题 + 日期）
  // Slide 1: 目录页（🆕 v0.6: ≤7 项单栏居中，>7 项双栏）
  // Slide 2..N: marked AST 解析 → 前瞻式分页引擎 → CanvasElement[]
  // 🆕 v0.6: 每个章节首页右上角预留图片占位框 (placeholder 420×236)
  // 🆕 v0.6: 超大块独占页（单个长表格/长列表超出一页高度时自动换页）
  // 每个 token 通过 processToken() 内部闭环累加 currentY（v0.4 根治双重累加）
}
```

**v0.6 排版引擎精修**:

| 修复项 | 说明 |
|--------|------|
| **图片占位框** | 章节首页自动生成 placeholder 元素 (420×236, 右上角)，双击替换为真实图片 |
| **目录单栏布局** | ≤7 章节时使用单栏居中布局（大字号 18pt + 序号），>7 章节回退双栏 |
| **引用区位置修正** | CITATION_ZONE_Y = 632, CONTENT_END_Y = 624，引用区钉在页底，不再被正文侵入 |
| **引用区分隔线** | 全页宽分隔线 (CONTENT_WIDTH)，`Math.max` 确保不下移覆盖正文 |
| **超大块独占页** | 单 token 高度超出整页时，先换页再独占渲染（最大化可用空间） |
| **列表圆点对齐** | 圆点对齐首行文字垂直中心 (`BODY_FONT_SIZE * 0.675 - 4`)，解决多行项目圆点过高 |
| **元素间距微调** | 标题 height +16、正文 height +12、列表项 height +8，提升段落呼吸感 |
| **表格样式注入** | 自动生成表格继承品牌色表头 (headerFill=BRAND.primary) + 斑马纹 (rowAltFill) |
| **resolveImageUrl 修正** | `outputs/` 前缀映射到 `/api/v1/files/`，移除硬编码 `http://localhost:8000` |

**🆕 v0.7.2 字符宽度模型重构**:

| 修复项 | 说明 |
|--------|------|
| **isWideChar() 抽取** | CJK/全角字符检测正则提取为独立函数 `isWideChar()`，`estimateTextHeight` 与 `estimateTextWidth` 共享同一套字符宽度模型 |
| **字符宽度精调** | CJK: 0.95→1.0×, 空格: 0.3→0.32×, 大写/数字: 新增 0.62×, 其他: 0.55→0.58× |
| **行高计算修正** | `fontSize * 1.35` → `fontSize * 1.48` + `Math.ceil()` + 2px padding，消除底线截断 |
| **safeWidth 防护** | `safeWidth = Math.max(width, fontSize)` 防止窄容器除零导致行数爆炸 |
| **列表项去重渲染** | `buildListItemNode()` 不再为内联文本创建 paragraph child 节点，改为提取 `inlineText` 合并到父节点 text，消除同层内容重复渲染 bug |
| **排版溢出回退** | 新增 `shouldFallbackArrangement()`：非 vertical 排版预估超出页高时自动回退 vertical，避免内容溢出 |
| **上下文感知排版选择** | `getNodeArrangement()` 按子项数量 (≤2 / 3-6 / ≥7) 和平均文本长度 (≤20 / ≤60 / >60) 从候选集中确定性选择，替代原来从全量 LEAF_ARRANGEMENTS 随机抽选 |
| **ensureSpace 回调** | `renderTreeWalk()` 新增 `options.ensureSpace(requiredHeight)` 回调，节点渲染前预检空间，不足时自动触发换页 |
| **buildLineElement 工厂** | 装饰线条统一通过 `buildLineElement()` 创建，`toLinePoints()` 辅助坐标转换，消除散落的 inline 构造 |
| **类型安全升级** | `marked.Token` → `Token`，`marked.Tokens.X` → `Tokens.X`（从 marked 库直接 import 类型） |

**v0.4 排版引擎根治**:

| 修复项 | 说明 |
|--------|------|
| **双重累加消除** | `processToken` 返回 `void`（原返回 `consumedY` 导致外层 `+=` 再次累加），内部直接 `state.currentY += h`；🆕 v0.7.2 新增 `clampContentY()` 防止 currentY 溢出 CONTENT_END_Y |
| **空页断层防护** | 翻页条件增加 `state.currentY > START_Y`，禁止空页强制翻页 |
| **Logo URL 解析** | `buildSlideDecor` 中 `src: resolveImageUrl(logoUrl)` + `push`（修复 z-order 遮挡） |
| **Logo Contain 缩放** | Logo 容器 160×60（原 100×40），`safeX` 同步调整为 220 |
| **幽灵页正则升级** | `extractCitations` 匹配 `#{1,6}` 任意级别标题 + 中英文关键词 |
| **CSV 引号剥离** | `case 'table'` 中 header/rows 强制 `.replace(/^"\|"$/g, '').trim()` |
| **脚标平滑展示** | `stripMarkdown` 追加 `.replace(/\[\^(\d+)\]/g, '[$1]')` |

**v0.5 stripMarkdown 纯文本转换**:

| 模式 | 处理 |
|------|------|
| `# 标题` | 去除 `#` |
| `**粗体**` / `*斜体*` | 去除 `*` |
| `[链接](url)` | 保留文本 `[链接]` |
| `` `代码` `` | 去除反引号 |
| `- 列表` | 替换为 `•` |
| `> 引用` | 去除 `>` |

### 10.12 报告组件 (`components/report/`)

**`CitationMarkdown.tsx`** — 增强 Markdown 渲染器，将正文中的 `[^n]` 引用标记自动渲染为可交互的引用角标，点击弹出引用来源详情。

### 10.13 自定义 Hooks

| Hook | 作用 |
|------|------|
| `useProjects.ts` | 项目列表获取（含创建/删除 mutation） |
| `useProjectStatus.ts` | **状态感知轮询**：运行中 3 秒轮询，交互节点/终态自动停止 |
| `useProjectLogs.ts` | 项目时间轴日志轮询（前端渲染 TerminalTimeline） |
| `useDraftStream.ts` | SSE EventSource 流式接收章节撰写内容 (⚠️ 已废弃) |
| `useEditorSync.ts` | 编辑器内容与后端 DocumentBlock 双向同步 |
| `useCitationStore.ts` | 引用数据全局状态管理（ref_num → {title, url, snippet}） |

### 10.14 `hooks/useProjectStatus.ts` — 状态感知轮询

```tsx
function useProjectStatus(id: string) {
  return useQuery({
    queryKey: ["project-status", id],
    queryFn: () => projectsApi.getStatus(id),
    refetchInterval: (query) => {
      const status = query.state.data?.project_status;
      // 交互节点 + 终态 → 停止轮询（节省带宽）
      if (["waiting_for_sources", "waiting_for_outline",
           "completed", "failed"].includes(status))
        return false;
      return 3000;  // 运行中 → 3 秒轮询
    },
  });
}
```

### 10.15 `lib/api.ts` — API 服务层

```tsx
const projectsApi = {
  create: (topic: string, templateType = "product", searchDepth = 10) =>
    api.post("/projects", { topic, template_type: templateType, search_depth: searchDepth }),
  getStatus: (id: string) => api.get(`/projects/${id}/status`).then(r => r.data),
  approveOutline: (id: string, outline: string) =>
    api.post(`/projects/${id}/approve-outline`, { outline }),
  reviewSources: (id: string, selected_urls: string[]) =>
    api.post(`/projects/${id}/review-sources`, { selected_urls }),
  getSources: (id: string) => api.get(`/projects/${id}/sources`).then(r => r.data),
  getBlocks: (id: string) => api.get(`/projects/${id}/blocks`).then(r => r.data),
  getContent: (id: string) => api.get(`/projects/${id}/content`).then(r => r.data),
  getLogs: (id: string, afterSequence = 0) =>
    api.get(`/projects/${id}/logs?after_sequence=${afterSequence}`).then(r => r.data),
  getDownload: (id: string) => api.get(`/projects/${id}/download`).then(r => r.data),
  delete: (id: string) => api.delete(`/projects/${id}`).then(r => r.data),
  uploadDocs: async (projectId: string, files: FileList | File[]) => { ... },
  exportPdf: (projectId: string, data: ExportPdfRequest) =>
    api.post(`/projects/${projectId}/export-pdf`, data).then(r => r.data),
  uploadAsset: (projectId: string, file: File) => {
    // 🆕 v0.6: 使用原生 fetch + FormData（非 JSON），失败抛 ApiError
    const fd = new FormData(); fd.append('file', file);
    return fetch(`${API_BASE}/projects/${projectId}/assets`, { method: 'POST', body: fd })
      .then(async res => {
        if (!res.ok) throw new ApiError(res.status, (await res.json().catch(() => ({}))).detail ?? `HTTP ${res.status}`);
        return res.json();
      });
  },
};

const editorApi = {
  revise: (body: EditorReviseRequest) => api.post("/editor/revise", body).then(r => r.data),
  chat: async (data: EditorChatRequest): Promise<Response> => {
    const res = await fetch(`${API_BASE}/editor/chat`, { method: 'POST', ... });
    return res;  // 调用方通过 ReadableStream 读取 SSE
  },
};
```

### 10.16 `lib/utils.ts` — 通用工具函数

日期格式化、UUID 截断、状态标签映射等 UI 辅助函数。

### 10.17 类型定义 (`types/`)

| 文件 | 作用 |
|------|------|
| `types/api.ts` | API 请求/响应类型（330+ 行，含 `ProjectStatusEnum`, `TaskTypeEnum`, `TaskStatusEnum`, `SSEDraftEvent`, `SourceItem`, `ProjectLogResponse`, `SectionContent`, `EditorChatRequest`, `EditorChatMessage`, `ExportPdfRequest`, `UploadDocsResponse`, `STATE_MACHINE_STEPS`, `PROGRESS_STEPS` 等） |
| `types/index.ts` | 通用 UI 类型（`EditorBlock`, `ProgressStep`, `LogEntry`, `RightPanelView` 等） |

### 10.18 样式与配置

| 文件 | 作用 |
|------|------|
| `styles/globals.css` | Tailwind CSS 全局样式 |
| `vite-env.d.ts` | Vite 环境类型声明 |

### 10.19 前端配置文件

| 文件 | 作用 |
|------|------|
| `package.json` | 依赖管理（React 18, react-konva, konva, zustand, zundo, jspdf, marked, Tiptap [保留], Radix UI, TanStack Query, Tailwind CSS 等） |
| `vite.config.ts` | Vite 构建配置（含 API 代理到 localhost:8000） |
| `tailwind.config.ts` | Tailwind CSS 主题配置 |
| `tsconfig.json` | TypeScript 编译配置 |
| `postcss.config.js` | PostCSS 配置（Tailwind CSS 插件） |

### 10.20 前端依赖一览 (v0.5)

| 库 | 版本 | 用途 | 许可证 |
|----|------|------|--------|
| `react` | ^18.3.1 | UI 框架 | MIT |
| `react-konva` | ^18.2.10 | React 声明式 Canvas 绑定 | MIT |
| `konva` | ^9.3.18 | Canvas 2D 渲染引擎 | MIT |
| `zustand` | ^5.0.14 | 原子化状态管理 | MIT |
| `zundo` | ^2.3.0 | Zustand temporal undo/redo 中间件 | MIT |
| `marked` | ^12.0.0 | Markdown AST 解析 | MIT |
| `jspdf` | ^2.5.2 | 前端 PDF 生成 | MIT |
| `use-image` | ^1.1.0 | Konva Image 加载 hook | MIT |
| `react-konva-utils` | ^1.0.6 | Konva 工具集 | MIT |
| `@tanstack/react-query` | ^5.62.0 | 服务端状态管理 | MIT |
| `react-router-dom` | ^7.1.1 | 前端路由 | MIT |
| `@radix-ui/react-dialog` | ^1.1.4 | 无障碍对话框 | MIT |
| `@radix-ui/react-popover` | ^1.1.4 | 无障碍弹出层 | MIT |
| `lucide-react` | ^0.468.0 | 图标库 | ISC |
| `@tiptap/*` | ^3.23–3.24 | 🗑️ 保留（已废弃，不再被引用） | MIT |
| `tailwindcss` | ^3.4.17 | 原子化 CSS 框架 | MIT |

---

## 11. 数据模型 (backend/app/models/)

### 11.1 模型关系

```
User (1) ──< (N) Project (1) ──< (N) Task
                    │
                    ├──< (N) Document        (完整章节快照)
                    ├──< (N) DocumentBlock    (原子化编辑块)
                    └──< (N) ProjectLog       (时间轴日志)
```

### 11.2 `base.py` — 声明式基类

```python
class Base(DeclarativeBase):
    pass

def orm_to_dict(obj: Base) -> dict:
    """ORM 实例 → 纯字典。自动处理 UUID → str, enum → value, datetime → ISO"""
    result = {}
    for col in obj.__table__.columns:
        value = getattr(obj, col.key)
        if hasattr(value, "value"):       # enum
            result[col.key] = value.value
        elif isinstance(value, uuid.UUID): # UUID
            result[col.key] = str(value)
        elif isinstance(value, datetime):  # datetime
            result[col.key] = value.isoformat()
        else:
            result[col.key] = value
    return result
```

### 11.3 `user.py` — 用户

```python
class User(Base):
    __tablename__ = "users"
    id        = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    username  = mapped_column(String(100), unique=True, nullable=False)
    email     = mapped_column(String(255), unique=True, nullable=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())
```

### 11.4 `project.py` — 项目 + 状态枚举

```python
class ProjectStatus(str, enum.Enum):
    PREPARING_DATA        = "preparing_data"          # 初始
    WAITING_FOR_SOURCES   = "waiting_for_sources"     # 🛑 等用户审核资料
    PREPARING_OUTLINE     = "preparing_outline"       # 自动生成大纲
    WAITING_FOR_OUTLINE   = "waiting_for_outline"     # 🛑 等用户确认大纲
    DRAFTING              = "drafting"                # 自动逐章撰写
    COMPLETED             = "completed"               # ✅ 完成
    FAILED                = "failed"                  # ❌ 失败

class Project(Base):
    __tablename__ = "projects"
    id              = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    owner_id        = mapped_column(UUIDType, ForeignKey("users.id"))
    topic           = mapped_column(String(500))
    status          = mapped_column(Enum(ProjectStatus, ...), index=True)
    outline_content = mapped_column(Text, nullable=True)
    pdf_path        = mapped_column(String(500), nullable=True)
    md_path         = mapped_column(String(500), nullable=True)
    template_type   = mapped_column(String(50), default="product")      # 🆕 v0.5
    search_depth    = mapped_column(Integer, default=10)                # 🆕 v0.4
    logo_url        = mapped_column(String(1000), nullable=True)        # 🆕 v0.4
    error_message   = mapped_column(Text, nullable=True)
    created_at      = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at      = mapped_column(DateTime(timezone=True), nullable=True)
```

### 11.5 `task.py` — 任务

```python
class TaskType(str, enum.Enum):
    SEARCH                = "search"
    BUILD_KNOWLEDGE_BASE  = "build_knowledge_base"
    GENERATE_OUTLINE      = "generate_outline"
    WRITE_SECTION         = "write_section"
    BUILD_REPORT          = "build_report"
    GENERATE_PDF          = "generate_pdf"
    IMAGE_GENERATION      = "image_generation"

class TaskStatus(str, enum.Enum):
    PENDING    = "pending"
    PROCESSING = "processing"
    COMPLETED  = "completed"
    FAILED     = "failed"

class Task(Base):
    __tablename__ = "tasks"
    id             = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    project_id     = mapped_column(UUIDType, ForeignKey("projects.id"), index=True)
    task_type      = mapped_column(Enum(TaskType, ...))
    status         = mapped_column(Enum(TaskStatus, ...), default=TaskStatus.PENDING)
    sequence_order = mapped_column(Integer, default=0)
    section_title  = mapped_column(String(500), nullable=True)
    started_at     = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at   = mapped_column(DateTime(timezone=True), nullable=True)
    error_message  = mapped_column(Text, nullable=True)
```

### 11.6 `document_block.py` — 原子化内容块

```python
class DocumentBlock(Base):
    __tablename__ = "document_blocks"
    id            = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    project_id    = mapped_column(UUIDType, ForeignKey("projects.id"), index=True)
    section_title = mapped_column(String(500))
    order_index   = mapped_column(Integer, default=0)
    content       = mapped_column(Text, default="")         # Markdown 正文
    citations     = mapped_column(Text, nullable=True)      # JSON: {ref_num: {title,url}}
    created_at    = mapped_column(DateTime(timezone=True), server_default=func.now())
```

### 11.7 `document.py` — 章节文档快照

```python
class Document(Base):
    """报告章节文档 —— 每个 section 对应一条完整记录"""
    __tablename__ = "documents"
    id            = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    project_id    = mapped_column(UUIDType, ForeignKey("projects.id"), index=True)
    section_title = mapped_column(String(500))
    section_order = mapped_column(Integer, default=0)
    content       = mapped_column(Text, default="")
    source_urls   = mapped_column(Text, nullable=True)
    created_at    = mapped_column(DateTime(timezone=True), server_default=func.now())
```

> **Document vs DocumentBlock**: Document 是完整章节的一次性快照（用于报告全文组装），DocumentBlock 是流式撰写的原子化编辑块（SSE 逐块推送，Canvas 渲染）。

### 11.8 `project_log.py` — 项目时间轴日志

```python
class LogLevel(str, enum.Enum):
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    MILESTONE = "milestone"

class ProjectLog(Base):
    __tablename__ = "project_logs"
    id         = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    project_id = mapped_column(UUIDType, nullable=False, index=True)
    sequence   = mapped_column(Integer, nullable=False, default=0)
    level      = mapped_column(Enum(LogLevel, ...), default=LogLevel.INFO)
    step       = mapped_column(String(200), nullable=False)
    message    = mapped_column(Text, nullable=False)
    icon       = mapped_column(String(10), nullable=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())
```

### 11.9 `project_image.py` — 🆕 v0.7 项目图片库

```python
class ProjectImage(Base):
    __tablename__ = "project_images"
    id           = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    project_id   = mapped_column(UUIDType, ForeignKey("projects.id", ondelete="CASCADE"),
                                  nullable=False, index=True)
    query        = mapped_column(String(500), nullable=False)
    title        = mapped_column(String(500), nullable=False)
    image_url    = mapped_column(String(2048), nullable=False)
    source_url   = mapped_column(String(2048), nullable=True)
    thumbnail_url= mapped_column(String(2048), nullable=True)
    search_depth = mapped_column(Integer, default=10)
    created_at   = mapped_column(DateTime(timezone=True), server_default=func.now())
```

**作用**: 持久化 DuckDuckGo 图片搜索结果，按项目隔离。`POST /search-images` 创建记录；`GET /images` 返回列表；`DELETE /images/{id}` 删除。前端 ImageGallery 依赖此表加载素材库。

---

## 12. 状态机流转全景

```
用户创建项目 (topic + template_type + search_depth)
    │
    ▼
PREPARING_DATA ──(Celery: 搜索+抓取)──▶ WAITING_FOR_SOURCES  🛑
                                               │
                              POST /review-sources  (用户审核资料)
                                               │
                                               ▼
                                    PREPARING_OUTLINE ──(Celery: 知识库+大纲)──▶ WAITING_FOR_OUTLINE  🛑
                                                                                       │
                                                                      POST /approve-outline  (用户确认大纲)
                                                                                       │
                                                                                       ▼
                                                                              DRAFTING ──(Celery: 逐章撰写)──▶ COMPLETED ✅
                                                                                 │
                                                                                 │ SSE stream-draft
                                                                                 ▼
                                                                         [前端 Canvas 流式渲染]

v0.5: DRAFTING→COMPLETED 仅代表"草稿就绪，等待用户进入 Canvas 编辑器排版后手动导出 PDF"
     PDF 导出完全由前端 原生 Konva 离屏 JPEG + jsPDF 接管（100% 所见即所得）
```

### 关键设计决策

| 决策 | 原因 |
|------|------|
| Celery `--pool=threads` | Windows Python 3.14 `spawn` 多进程导致 `trace._localized` 崩溃 |
| SQLite NullPool + WAL | 单文件开发库，WAL 提升并发读写，NullPool 避免连接池冲突 |
| SSE 轮询而非 WebSocket | 简化部署（无需额外 WS 服务器），2 秒间隔可接受 |
| 🆕 React-Konva + Zustand | Stage/Layer 声明式架构，原子 `updateElement` 替代全量 `toJSON`，根治序列化死循环 |
| 🆕 zundo temporal middleware | Zustand 无侵入式 Undo/Redo，自动记录历史，limit 50 步 |
| 🆕 原生 Konva 离屏 JPEG 导出 | `canvas.toBlob('image/jpeg', 0.92)` + `FileReader`，根治 PNG `Invalid string length` |
| 🆕 CanvasElement 统一数据模型 | 引擎无关的类型安全数据，React-Konva + 原生 Konva 双消费 |
| 🆕 PromptFactory 多态模板 | product/design 双模板体系，不同 Persona + 不同 System Prompt |
| 🆕 search_depth 搜索强度 | 用户可调控的搜索精度 (5/10/15/20)，影响 RAG 质量与开销 |
| 🆕 marked AST 解析 + 前瞻分页 | 词法分析 token 流 → 精确高度预估 → processToken 内部闭环累加（v0.4 根治双重累加） |
| 🆕 RenderImage Contain 缩放 | `Math.min(w/imgW, h/imgH)` 等比缩放 + 居中，杜绝 Konva Image 默认拉伸 |
| 💀 Fabric.js v6.9.x | ~~序列化死循环 + GPL 风险~~ (v0.4: React-Konva MIT 全栈替换) |
| `orm_to_dict()` 手动转换 | 避免 Pydantic `from_attributes=True` 的嵌套序列化陷阱 |
| Chroma + BM25 双引擎 + RRF | 向量检索覆盖语义，BM25 覆盖关键词精确匹配，RRF 融合最优排序 |
| Per-project 向量库子目录 | 杜绝多项目并发时的数据互相覆盖 |
| Query Planning + Baseline 对比 | LLM 拆解宽泛标题为高密度关键词，召回质量显著优于直接检索 |
| 16:9 横版 PDF | ~~WeasyPrint~~ → 🆕 原生 Konva 离屏 JPEG → jsPDF，100% 所见即所得 |
| Canvas 幻灯片替代 Tiptap | React-Konva 提供绝对坐标拖拽、图文混排、多页缩略图，彻底解决 DOM 排版崩溃 |
| WorkspacePage → EditorPage 分离 | 项目管理与 Canvas 编辑分页，避免页面拥挤，全屏沉浸式编辑体验 |
| 前端接管 PDF 导出 | 后端 Phase 3 不再生成 PDF，DRAFTING→COMPLETED 仅代表"草稿就绪" |
| dataTransform 封面生成 | 后端 blocks 不含封面，前端转换层强制生成 Slide 0（深色背景 + 品牌装饰 + 大标题） |
| Redis 容器化部署 | 避免 WSL sudo 权限问题，`--restart unless-stopped` 保活 |
| 状态感知轮询停止 | 交互节点/终态自动停轮询，减少不必要的网络请求 |
| ProjectRepo 同步仓库 | 消除任务中散落的 raw SQL 和 `asyncio.run()`，统一 Celery 数据访问 |
| Document vs DocumentBlock 双模型 | Document 完整快照用于报告组装，DocumentBlock 原子化块用于流式编辑 |
| ProjectLog 时间轴 | 结构化日志持久化到 DB，前端渲染为终端控制台实时流 |
| `utcnow()` 统一时间戳 | 杜绝散落的 naive `datetime.now()`，确保全项目 UTC 一致性 |
| `main.py` 双路径注入 (`sys.path`) | 同时加入 `backend/` 和项目根目录，桥接 `backend/app/` 与项目根 `app/` 两套包体系 |
| `/editor/chat` RAG 上下文注入 | work 模式自动调用 `retrieve_context()` 从 Chroma + BM25 召回 Top-5 切片注入 LLM 上下文 |
| 🆕 PyMuPDF 本地 PDF 解析 | 替代需要 API Key 的云端解析方案，用户上传 PDF 后本地提取文本 → 切片 → 入库 |
| 🆕 DuckDuckGo 图片搜索 | 免 API Key 的图片搜索，可搜索产品相关图片素材 |
| 🆕 Alembic 数据库迁移 3 版本 | 版本化 schema 管理（初始 → template_type → search_depth + logo_url） |
| 🆕 DiffViewNode 行级差异 | AI 改写结果可视化对比（原始 vs 修改），Approve/Discard 确认机制 |
| 🆕 `rank-bm25` 依赖修复 | v0.2 BM25 检索因缺失依赖降级为纯向量检索，v0.3 正式修复完整 RRF 融合 |
| 🆕 `_clean_llm_output` 三阶段清理 | Step1 截断 ## 前寒暄 / Step2 移除重复标题 / Step3 正则兜底，彻底根治 LLM "好的，以下是..." 问题 |
| 🆕 Source Ranking 信息源分级 | T0(1.5x): PDF/政府/交易所/local:// / T1(1.2x): 专业媒体 / T2(1.0x): 普通新闻 / T3(0.5x): UGC 重度降权 ，权重乘入 RRF 分数 |
| 🆕 章节级 Block 保存策略 | `_save_section_as_blocks` 每章节 1 个 Block（非段落级拆分），避免装饰区重复开销导致碎片页 |
| 🆕 WritingTask Celery 基类 | 惰性加载 Settings 单例，避免每个 Celery 任务重复实例化；`autoretry_for=(Exception,)` + 指数退避最大 120s |
| 🆕 多模态绘图路由 | `_is_image_section()` 检测"生图/图鉴/概念图"关键词 → 硅基流动 `generate_image()` 16:9 横版概念图，失败 graceful degradation |
| 🆕 AI 面板直连 Zustand | EditorPage AiPanel: "应用到画布" 直接调用 `useCanvasStore.getState().addElement()`，无中间层 |
| 🆕 `/editor/chat` 双模式 | work 模式 (temperature=0.3 + RAG 注入) vs chat 模式 (temperature=0.7 + 通用)，SSE 流式返回 |

---

## 13. 测试与评测

### 13.1 `tests/eval_retrieval.py` — 检索质量评测

评测混合检索引擎（Chroma + BM25 + RRF）在不同查询类型下的召回率、精确率和 MRR。

### 13.2 `tests/eval_ranking.py` — 排序质量评测

评测 Query Planning vs 原始检索的排序效果对比，验证 RRF 融合权重和 Query Planning 的收益。

### 13.3 `tests/eval_citation.py` — 引用质量评测

评测引用溯源引擎的准确率：生成的 `[^n]` 脚注是否正确关联到对应的来源 URL 和内容片段。

### 13.4 `backend/tests/` — 后端单元/集成测试

详见 [第 8 节：后端测试套件](#8-后端测试套件-backendtests)：
- `test_imports.py` — 模块导入 + 基础功能验证
- `test_state_machine.py` — 状态机枚举/约束验证
- `test_outline_parser.py` — 大纲解析 9 个测试用例
- `test_api_integration.py` — 14 个 API 集成测试（健康检查、CRUD、状态机流转、Schema 校验、编辑器 AI）

---

## 14. 运维工具脚本

### 14.1 `backend/fix_project.py` — 数据库诊断与修复

```bash
python fix_project.py                    # 列出所有项目状态
python fix_project.py --fix <project_id> # 修复卡住的项目（重置 FAILED 任务 → COMPLETED）
python fix_project.py --reset <project_id> # 重置项目到初始状态
python fix_project.py --verify           # 验证数据库完整性（孤儿任务/文档块/卡住项目）
```

### 14.2 `backend/fix_stuck_projects.py` — 僵死项目批量修复

识别并重置卡在活跃状态的项目（因 Celery 崩溃导致的任务幽灵），重新投递到 Celery 队列。

```python
async def fix_stuck_projects():
    """扫描 → 重置状态 → 清理暂存文件 → 重新投递 prepare_sources_workflow"""
    active_statuses = [PREPARING_DATA, PREPARING_OUTLINE, DRAFTING]
    for project in stuck_projects:
        # 重置所有关联任务 → PENDING
        # 项目状态 → PREPARING_DATA
        # 清理 crawled_data_{project_id}.json 暂存文件
        # 重新投递 Celery 任务
```

### 14.3 `backend/reset_project.py` — 工作流重触发

将项目重置到指定阶段并自动重新触发对应的 Celery 工作流。

```bash
python reset_project.py <project_id> --stage sources   # 从资料搜集阶段开始
python reset_project.py <project_id> --stage outline   # 从大纲生成阶段开始
python reset_project.py <project_id> --stage drafting  # 从撰写阶段开始
```

### 14.4 `fix/` — 问题修复记录

| 文件 | 内容 |
|------|------|
| `fix/fix_start01.md` | 启动问题修复记录 |
| `fix/day1/fronted.md` | 前端问题修复 |
| `fix/day1/task1_fix.md` | 任务修复记录 |
| `fix/day1/task1_local_rag.md` | 本地 RAG 修复 |
| `fix/day1/task2_core_api.md` | 核心 API 修复 |
| `fix/day1/task3_img_search.md` | 图片搜索修复 |
| `fix/day3/fix_draft03.md` | v0.4 排版引擎根治方案（双重累加/空页断层/Logo Contain/CSV剥离/Prompt升级） |

---

> 完整源码：`https://github.com/CaroVon/QX_Product_Research`
>
> 相关文档：`STRUCTURE_UPDATE_0623.md` (v0.2→v0.3) | `STRUCTURE_UPDATE_0624.md` (v0.3→v0.4)
