# 🔬 QX Product Research Agent

> **v1** — 一款具备「断点干预、块级编辑、多轮迭代」能力的 AI 产品分析研究智能体。从全网搜索、本地文档上传、知识库构建、大纲规划到逐章 AI 撰写与 16:9 横版 PPT 风格 PDF 输出，全流程自动化，并提供 Canvas 幻灯片编辑器 + 图片素材库 + 图片裁剪 + 幻灯片管理。

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136-green.svg)](https://fastapi.tiangolo.com/)
[![Celery](https://img.shields.io/badge/Celery-5.6-purple.svg)](https://docs.celeryq.dev/)
[![React](https://img.shields.io/badge/React-18.3-blue.svg)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-6.0-yellow.svg)](https://vitejs.dev/)
[![Redis](https://img.shields.io/badge/Redis-7.0-red.svg)](https://redis.io/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-orange.svg)](https://www.sqlalchemy.org/)
[![LangChain](https://img.shields.io/badge/LangChain-1.4-teal.svg)](https://www.langchain.com/)
[![Chroma](https://img.shields.io/badge/Chroma-1.5-purple.svg)](https://www.trychroma.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📖 定位与愿景

将传统的 **"输入主题 → 黑盒等待 → 静态输出"** 线性产品分析工具，升级为具备 **断点干预、块级编辑、多轮迭代** 能力的现代 SaaS 产品研究工作台。

**v0.7 亮点更新：**
- 🎨 **Canvas 幻灯片编辑器** — React-Konva 声明式画布，拖拽编辑、裁剪、图层管理
- 🖼️ **图片素材库** — DuckDuckGo 图片搜索 (ddgs v9.x) + 缩略图网格 + 拖拽到画布 + 上下文空状态引导 + DRAFTING 自动轮询
- ✂️ **图片裁剪** — 内置裁剪模式（四角缩放 + 拖拽移动 + 实时预览）
- 📋 **幻灯片管理** — 复制/粘贴/新增/删除幻灯片 + 键盘快捷键
- 🔄 **跨页剪贴板** — Ctrl+Shift+C/V 跨页复制粘贴幻灯片
- 🧩 **Zustand 状态管理** — clipMode/image clipping/copiedSlide 等原子化状态 + zundo Undo/Redo

**v0.7.1 修复：**
- 🔧 ddgs 图片搜索库升级至 v9.14.x（修复 `import` 路径和 API 参数兼容性）
- 🎯 ImageGallery 空状态按项目阶段显示上下文引导提示
- 🔍 搜索失败与无结果区分提示（HTTP 错误 vs 空结果）
- 🔄 DRAFTING 阶段 15s 自动轮询刷新图片列表

**v0.7.2 排版引擎重构：**
- 🔗 **引用合并去重** — `build_context_with_citations()` 同 URL 多 Chunk 合并为单一上下文块，URL 内 chunk 级去重
- 📝 **Prompt 格式规则重构** — 单 bullet 单结论 + 2-3 行限制 + 4+ 要点表格化 + 同事实去重 + 规则编号 2→9 重新编排
- 🔤 **字符宽度模型重构** — `isWideChar()` 统一字符宽度判定 + CJK 1.0×/空格 0.32×/大写数字 0.62×/其他 0.58× + 行高 1.35→1.48 + `safeWidth` 除零防护 + `Math.ceil()` 底线对齐
- 🎨 **排版引擎增强** — 上下文感知排版选择 + 溢出回退 vertical + `ensureSpace` 预检回调 + `buildLineElement()` 工厂 + 列表项去重渲染
- 📐 **Canvas 编辑器修复** — 所有 Konva Text 统一 `lineHeight=1.4` + `clipFunc` 类型断言修复
- 📄 **PDF CSS 修正** — `.slide` 高度 `100%` → `180mm` + `max-height` + `overflow:hidden`

**v1 开发工具链：**
- 🧪 **dev_section_loop.py** — 绕过 Celery/Redis，直接调用 section_writer → DocumentBlock → Canvas 渲染全链路，秒级验证排版修改效果
- 📚 **DEV_SECTION_LOOP.md** — 开发循环工具完整文档（checkpoint 管理、增量重跑、diff 对比）
- 🏗️ **Prompt 层级结构增强** — product/design 双模板 "分组 + 并列项" 结构指导 + 分页安全规则 + 表格优先级强化

**目标用户：** 资深产品经理 (PM)、用户体验专家 (UX)、工业设计战略家。

**🚀 v2（AI Product Studio）:**
- 🧩 **agent-platform 平台层** — 独立的 Agent Runtime（LangGraph + Agent Harness），不侵入既有业务代码
- 🤖 **四个专业 Agent** — Research / Product / Design / Presentation，由七节点 LangGraph 工作流编排
- 📐 **结构化输出** — 全部 Agent 输出经 Pydantic Schema 校验（Markdown-first → JSON + Renderer）
- 🎛️ **Product Studio 工作台** — `/studio`：输入想法 → 七节点进度 → 市场分析/竞品矩阵/画像/PRD/路线图/演示 输出工作区
- 🎬 **Slide JSON 演示** — SlideRenderer 16:9 Web 演示 + PPT 风格 PDF 导出
- 详见 [MIGRATION.md](./MIGRATION.md) 与 `~/dev/agents/agent-platform/`

---

## 🏗️ 系统架构

```
┌────────────────────────────────────────────────────────────────────┐
│                     Frontend  (React 18 + Vite + TypeScript)       │
│        三栏工作台 · Tiptap 编辑器 · SSE 流式渲染 · AI 对话面板       │
│                         http://localhost:5173                       │
└────────────────────────────┬───────────────────────────────────────┘
                             │  HTTP REST + SSE (POST & GET)
┌────────────────────────────▼───────────────────────────────────────┐
│                   Backend  (FastAPI + Celery + SQLAlchemy 2.0)     │
│             状态机编排 · 异步任务队列 · REST API · 持久化存储         │
│                         http://localhost:8000                       │
└────────────────────────────┬───────────────────────────────────────┘
                             │  Python import (同步引擎 + 本地解析)
┌────────────────────────────▼───────────────────────────────────────┐
│                  Research Engine  (app/)                            │
│   搜索(Tavily) → 抓取(Firecrawl) → 本地解析(PyMuPDF)               │
│   → 向量库(Chroma) → 混合检索(BM25+RRF) → 图片搜索(DuckDuckGo)     │
│   → 大纲规划 → RAG 深度撰写(DeepSeek) → 16:9横版PPT PDF(WeasyPrint) │
└────────────────────────────────────────────────────────────────────┘
```

### 三大组件

| 组件 | 技术栈 | 说明 |
|------|--------|------|
| **🧠 研究引擎** `app/` | LangChain + Chroma + BM25 + PyMuPDF + DuckDuckGo + DeepSeek | 核心 RAG 管道：搜索→抓取→本地解析→切片→向量化→混合检索→大纲→撰写→PDF |
| **⚙️ 后端服务** `backend/` | FastAPI + Celery + SQLite/PostgreSQL | REST API + 异步任务队列 + SSE 实时对话 + 状态机编排 + 数据持久化 |
| **🎨 前端界面** `frontend/` | React 18 + Vite + TypeScript + Tailwind CSS + Radix UI + React-Konva + Zustand/zundo | Canvas 幻灯片编辑器 + 图片素材库 + AI 对话面板 + 裁剪工具 |

---

## 🔄 交互式状态机

放弃一键到底的批处理模式，引入 **三阶段六状态** 交互式状态机：

```
                    POST /projects
                         │
                         ▼
              ┌─────────────────────┐
              │   PREPARING_DATA    │  Celery: 网络搜索 + Firecrawl 深度抓取
              └────────┬────────────┘       + 支持本地上传文档 (upload-docs)
                       │ (自动完成)
                       ▼
              ┌─────────────────────┐
              │  WAITING_FOR_SOURCES │  🛑 交互节点 1：用户审核资料
              └────────┬────────────┘       GET /sources → POST /review-sources
                       │ (用户确认筛选结果)     📎 POST /upload-docs 追加本地文件
                       ▼
              ┌─────────────────────┐
              │  PREPARING_OUTLINE  │  Celery: 知识库构建(Chroma+BM25) + LLM 大纲生成
              └────────┬────────────┘
                       │ (自动完成)
                       ▼
              ┌─────────────────────┐
              │  WAITING_FOR_OUTLINE │  🛑 交互节点 2：用户确认/修改大纲
              └────────┬────────────┘       GET /status → POST /approve-outline
                       │ (用户确认大纲)
                       ▼
              ┌─────────────────────┐
              │      DRAFTING       │  Celery: RAG 逐章撰写 + SSE 流式推送
              └────────┬────────────┘       + 手动导出 PDF (export-pdf)
                       │ (自动完成)
                       ▼
              ┌─────────────────────┐
              │     COMPLETED       │  ✅ 完成 — PDF 可下载，报告可编辑
              └─────────────────────┘
```

### 状态感知轮询

前端 React Query 在交互节点（`waiting_for_sources`、`waiting_for_outline`、`completed`、`failed`）**主动暂停轮询**，仅在运行中状态以 3 秒间隔拉取进度。避免多余网络请求，减少后端压力。

---

## 🧠 研究引擎详解

### 1. 信息采集层

| 步骤 | 组件 | 说明 |
|------|------|------|
| 🔍 全网搜索 | **Tavily Search API** | 输入主题，返回高相关性网页列表及摘要 |
| 🖼️ 图片搜索 | **DuckDuckGo Images (ddgs v9.x)** | 免 API Key，返回产品相关图片直链 |
| 🕷️ 深度抓取 | **Firecrawl** | 将网页转为结构化 Markdown，保留标题、正文、链接 |
| 📎 本地解析 | **PyMuPDF (fitz)** | 解析本地上传的 PDF 文件，提取全文文本 |
| ✂️ 文本切片 | `app/rag/chunker.py` | 1200 字符块 + 200 字符重叠，保持语义连贯 |
| 📊 向量嵌入 | `BAAI/bge-small-zh-v1.5` | 中文优化嵌入模型，SentenceTransformers 本地加载 |

### 2. 混合检索引擎

```
用户查询
    │
    ├──→ Chroma 向量检索 (语义匹配) ──→ Top-K×2 候选
    │
    └──→ BM25 关键词检索 (精确匹配) ──→ Top-K×2 候选
                    │
                    ▼
           RRF (Reciprocal Rank Fusion) 融合排序
                    │
                    ▼
                Top-K 最终结果
```

- **Chroma** — 持久化向量库，支持 per-project 隔离
- **BM25** — 基于 jieba 分词 + scikit-learn 的关键词检索，弥补向量检索在精确术语匹配上的不足
- **RRF 融合** — Reciprocal Rank Fusion 算法，综合两种检索信号的排名，无需调参权重

### 3. LLM 撰写引擎

```
用户确认大纲
      │
      ▼
┌─────────────────────────────────────────────┐
│  对每个章节:                                  │
│    1. 以 章节标题 作为查询 → HybridRetriever   │
│    2. 检索 Top-5 相关文档 → 带编号引用 [^n]    │
│    3. DeepSeek Chat (temperature=0.7)       │
│       System Prompt: 资深产品经理 + UX 专家     │
│    4. 生成 Markdown → 保存为 DocumentBlock     │
│    5. SSE 推送 → 前端 Tiptap 流式渲染          │
└─────────────────────────────────────────────┘
```

### 4. PDF 渲染引擎

- **渲染器**: WeasyPrint (无头浏览器，纯 Python)
- **画布**: `1440px × 810px` (16:9 横版，PPT 标准)
- **排版特性**:
  - 封面页（主题 + 概念图）
  - 每章强制分页 (`page-break-before: always`)
  - 学术级引用溯源角标
  - 中文字体栈: PingFang SC → Microsoft YaHei → sans-serif

---

## 🌐 API 接口

### 项目管理

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/projects` | 创建新项目，触发阶段1 资料搜集 |
| `GET` | `/api/v1/projects` | 获取项目列表 (分页) |
| `DELETE` | `/api/v1/projects/{id}` | 删除项目及全部关联数据 (级联清理) |
| `GET` | `/api/v1/projects/{id}/status` | 查询项目进度 + 大纲 + 任务列表 |

### 状态机交互 (两个断点)

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/projects/{id}/sources` | 🛑 **节点1**: 获取资料列表，供用户审核 |
| `POST` | `/api/v1/projects/{id}/review-sources` | 🛑 **节点1确认**: 提交筛选后的资料 URL |
| `POST` | `/api/v1/projects/{id}/upload-docs` | 📎 上传本地参考文件 (PDF/DOCX/TXT) 并入库 |
| `POST` | `/api/v1/projects/{id}/approve-outline` | 🛑 **节点2**: 提交确认的大纲 (可包含用户修改) |

### 内容与交付

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/projects/{id}/blocks` | 获取文档块列表 (Tiptap 编辑器加载) |
| `GET` | `/api/v1/projects/{id}/content` | 获取报告全文 (含引用溯源数据) |
| `GET` | `/api/v1/projects/{id}/stream-draft` | 🌊 SSE 流式草稿输出 (逐块推送) |
| `POST` | `/api/v1/projects/{id}/export-pdf` | 📄 手动导出 PDF (前端编辑器内容) |
| `POST` | `/api/v1/projects/{id}/search-images` | 🔍 图片搜索 (DuckDuckGo)，结果持久化到项目图片库 |
| `GET` | `/api/v1/projects/{id}/images` | 🖼️ 获取项目图片库（所有已搜索保存的图片） |
| `DELETE` | `/api/v1/projects/{id}/images/{image_id}` | 🗑️ 从图片库中删除单张图片 |
| `GET` | `/api/v1/projects/{id}/download` | 获取自动生成的 PDF 下载链接 |
| `GET` | `/api/v1/projects/{id}/logs` | 获取终端风格实时运行日志 |

### AI 编辑器服务

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/editor/revise` | 划词改写 (扩写/精简/润色/补充竞品/正式化) |
| `POST` | `/api/v1/editor/revise-block/{id}` | 块级精准改写 (基于 DocumentBlock 上下文) |
| `POST` | `/api/v1/editor/chat` | 🤖 SSE 流式 AI 对话 (支持 work/chat 双模式 + RAG) |

### 🚀 AI Product Studio（v2）

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/product/create` | 创建产品，异步触发多 Agent 流水线 (七节点) |
| `GET` | `/api/v1/product/{id}` | 产品资产包：`{research, strategy, design, presentation, ...}` + 进度/错误 |
| `GET` | `/api/v1/product` | 产品列表 (分页) |
| `POST` | `/api/v1/product/{id}/export-pdf` | Slide JSON → 16:9 PPT 风格 PDF |

---

## 📁 项目结构

```
QX_product_agent/
│
├── app/                              # 🧠 核心研究引擎 (独立可运行)
│   ├── search/
│   │   ├── tavily_search.py          #   Tavily 全网搜索
│   │   └── image_search.py           #   🆕 DuckDuckGo 图片搜索
│   ├── crawler/firecrawl_crawler.py  #   Firecrawl 网页转 Markdown
│   ├── rag/                          #   检索增强生成管道
│   │   ├── chunker.py                #     文本切片 (1200/200)
│   │   ├── vector_store.py           #     Chroma 持久化向量库
│   │   ├── retriever.py              #     混合检索 + RRF 融合
│   │   ├── rag_pipeline.py           #     知识库构建编排
│   │   ├── citation_utils.py         #     引用编号与溯源 (含 URL 合并去重)
│   │   └── local_parser.py           #     🆕 本地 PDF 解析 (PyMuPDF)
│   ├── planner/                      #   大纲规划
│   │   ├── outline_generator.py      #     LLM 大纲生成
│   │   ├── query_planner.py          #     查询规划
│   │   └── compare_query.py          #     查询对比
│   ├── report/                       #   报告生成
│   │   ├── section_writer.py         #     RAG 章节撰写 (含引用 + 多模态路由)
│   │   ├── markdown_formatter.py     #     Markdown 组装
│   │   └── pdf_generator.py          #     16:9 横版 PPT PDF
│   ├── llm/                          #   LLM 客户端
│   │   ├── client.py                 #     DeepSeek Chat 工厂
│   │   └── prompts.py                #     系统提示词模板 (product/design 双模板)
│   ├── orchestrator/workflow.py      #   端到端 CLI 工作流
│   └── shared/outline_parser.py      #   大纲 Markdown 解析器
│
├── backend/                          # ⚙️ FastAPI 后端服务
│   ├── app/
│   │   ├── main.py                   #   FastAPI 应用工厂 (lifespan/CORS/SPA/SSE)
│   │   ├── core/
│   │   │   ├── config.py             #     Pydantic V2 配置中心 (多源 .env)
│   │   │   ├── database.py           #     异步 SQLAlchemy 引擎 (SQLite/PostgreSQL)
│   │   │   ├── celery_app.py         #     Celery 应用实例
│   │   │   └── celery_db.py          #     Worker 同步数据库引擎
│   │   ├── api/v1/
│   │   │   ├── router.py             #     路由聚合器
│   │   │   └── endpoints/
│   │   │       ├── projects.py       #     核心业务 API (含 upload-docs / export-pdf)
│   │   │       └── editor.py         #     AI 编辑器 (revise / revise-block / chat SSE)
│   │   ├── models/                   #   SQLAlchemy ORM 模型
│   │   │   ├── base.py               #     声明式基类 + orm_to_dict + UUID
│   │   │   ├── project.py            #     项目 + 状态机枚举
│   │   │   ├── task.py               #     任务 + 类型枚举
│   │   │   ├── document_block.py     #     原子化可编辑内容块
│   │   │   ├── document.py           #     完整章节文档
│   │   │   ├── project_log.py        #     终端风格时间轴日志
│   │   │   ├── project_image.py      #     🆕 项目图片库 (图片搜索持久化)
│   │   │   └── user.py               #     用户模型
│   │   ├── schemas/__init__.py       #   Pydantic 请求/响应模型 (含 Chat/Upload/Export)
│   │   ├── tasks/                    #   Celery 异步任务
│   │   │   ├── report_workflow.py    #     ★ 三阶段状态机编排器
│   │   │   ├── search_tasks.py       #     搜索+抓取任务
│   │   │   ├── knowledge_tasks.py    #     知识库构建任务
│   │   │   ├── writing_tasks.py      #     大纲生成+章节撰写任务
│   │   │   └── render_tasks.py       #     Markdown组装+PDF渲染任务
│   │   └── repositories/             #   数据仓库 (依赖倒置)
│   │       └── project_repo.py       #     Celery Worker 同步数据库访问层
│   ├── fix_stuck_projects.py         #   异常项目修复脚本
│   ├── alembic/                      #   数据库迁移脚本
│   ├── .env.example                  #   配置模板
│   └── local_dev.db                  #   SQLite 开发数据库
│
├── frontend/                         # 🎨 React 前端
│   └── src/
│       ├── pages/                    #   页面组件
│       │   ├── DashboardPage.tsx     #     项目列表仪表盘
│       │   ├── ProductStudioPage.tsx #     🆕 v2: AI Product Studio 工作台 (/studio)
│       │   ├── WorkspacePage.tsx     #     ★ 三栏工作台 (核心, ~1287行)
│       │   ├── ReportPage.tsx        #     报告阅读器
│       │   └── ProgressPage.tsx      #     进度详情页
│       ├── components/               #   可复用组件
│       │   ├── MarketCard.tsx        #     🆕 v2: 市场分析卡片（渲染 MarketResearch JSON）
│       │   ├── CompetitorMatrix.tsx  #     🆕 v2: 竞品对比矩阵
│       │   ├── PersonaCard.tsx       #     🆕 v2: 用户画像卡片
│       │   ├── FeatureMatrix.tsx     #     🆕 v2: 功能清单矩阵
│       │   ├── RoadmapTimeline.tsx   #     🆕 v2: 路线图时间线
│       │   ├── PRDViewer.tsx         #     🆕 v2: PRD 阅读器
│       │   ├── SlideRenderer.tsx     #     🆕 v2: Slide JSON 演示渲染器 (Web + PDF 导出)
│       │   ├── layout/               #     布局: Sidebar / ThreePaneLayout
│       │   ├── projects/             #     项目: CreateProjectModal / SourcesReview
│       │   │                         #           OutlineApproval / ProgressTracker
│       │   │                         #           TerminalTimeline / ProjectCard
│       │   ├── editor/               #     编辑器: BlockEditor / InlineAIBubble / DiffView
│       │   │   │                       #            CanvasSlideEditor (Konva 画布) / ImageGallery
│       │   │   └── extensions/       #       Tiptap 扩展: Citation 标注
│       │   ├── report/               #     报告: CitationMarkdown
│       │   └── common/               #     基础组件 (Button/Dialog/Popover/Input/Badge)
│       ├── hooks/                    #   React Query hooks
│       │   ├── useProjectStatus.ts   #     状态感知轮询 (自动暂停)
│       │   ├── useDraftStream.ts     #     SSE 流式接收
│       │   ├── useEditorSync.ts      #     编辑器同步
│       │   ├── useProjectLogs.ts     #     增量日志拉取
│       │   └── useCitationStore.ts   #     引用溯源状态
│       ├── lib/api.ts                #   API 服务层 (fetch 封装, SSE chat 支持)
│       ├── types/api.ts              #   TypeScript 类型定义 (含 Chat/Upload/Export)
│       └── styles/globals.css        #   Tailwind CSS 全局样式
│
├── tests/                            # 测试与评测
│   ├── test_api_integration.py       #   集成测试
│   ├── eval_retrieval.py             #   检索精度评测
│   ├── eval_ranking.py               #   排序质量评测
│   └── eval_citation.py              #   引用溯源评测
│
├── scripts/                          # 🧪 开发工具脚本
│   ├── dev_section_loop.py           #   section_writer → Canvas 单点测试循环
│   └── studio_pipeline_smoke.py      #   🆕 v2: Product Studio 流水线真实 LLM 冒烟测试
│
├── MIGRATION.md                      # 🆕 v2: AI Product Studio 迁移文档
├── memory/                           # Claude Code 持久记忆
├── fix/                              # 问题修复记录
├── start_all.sh                      # WSL/Linux 全模块一键启动
├── start_project.bat                 # Windows 一键启动入口
├── stop_all.sh                       # 全模块停止
├── requirements.txt                  # Python 依赖清单
├── prd.md                            # 产品需求文档
├── command.txt                       # 快速启动命令备忘
├── DEV_SECTION_LOOP.md               # 开发循环工具文档
└── PROJECT_STRUCTURE.md              # 详细脚本架构文档
```

---

## 🚀 快速开始

### 环境要求

| 组件 | 版本要求 |
|------|----------|
| Python | 3.10+ |
| Node.js | 18+ |
| Redis | 推荐 7.0+ (Docker 部署) |
| Git | 2.0+ |

### 1. 克隆项目

```bash
git clone https://github.com/CaroVon/QX_Product_Research.git
cd QX_product_agent
```

### 2. 配置 API 密钥

```bash
cp backend/.env.example backend/.env
```

编辑 `backend/.env`，填入以下**必填**的 API Key：

```env
# ── 必填 ──
DEEPSEEK_API_KEY=sk-your-deepseek-key      # https://platform.deepseek.com/
TAVILY_API_KEY=tvly-your-tavily-key        # https://tavily.com/
FIRECRAWL_API_KEY=fc-your-firecrawl-key    # https://www.firecrawl.dev/

# ── 数据库（本地开发推荐 SQLite，开箱即用）──
DATABASE_URL=sqlite+aiosqlite:///./local_dev.db

# ── 可选：图像生成（不填则使用 CSS 渐变封面兜底）──
# SILICONFLOW_API_KEY=sk-your-siliconflow-key
```

### 3. 安装依赖

```bash
# Python 依赖
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 前端依赖
cd frontend && npm install && cd ..
```

### 4. 启动 Redis

```bash
# Docker 方式 (推荐，WSL 下免 sudo)
docker run -d --name redis-qx -p 6379:6379 --restart unless-stopped redis:7-alpine

# 或原生启动
redis-server
```

### 5. 一键启动

**Windows:**
```batch
双击运行 start_project.bat
```

**Linux / WSL:**
```bash
bash start_all.sh
```

脚本自动完成：Redis 保活 → FastAPI (8000) → Celery Worker → Vite 构建，日志输出到各自日志文件。

### 6. 手动启动 (分步调试)

```bash
# 终端1: FastAPI 后端
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# 终端2: Celery Worker (Windows 必须用线程池)
cd backend
celery -A app.core.celery_app.celery_app worker --loglevel=info --concurrency=4 --pool=threads

# 终端3: Vite 前端开发服务器 (端口 5173, HMR 热更新)
cd frontend && npm run dev
```

### 7. 浏览器访问

| 服务 | 地址 | 说明 |
|------|------|------|
| **前端工作台 (开发)** | **http://localhost:5173** | Vite HMR 热更新, 代理 API 到 8000 |
| **前端工作台 (生产)** | **http://localhost:8000** | FastAPI 托管 `vite build` 静态产物 |
| API 文档 (Swagger) | http://localhost:8000/docs | OpenAPI 交互文档 |
| API 文档 (ReDoc) | http://localhost:8000/redoc | 备选文档样式 |
| 健康检查 | http://localhost:8000/health | 服务存活检测 |
| 数据库健康检查 | http://localhost:8000/health/db | 数据库连接 + 表列表 |

> 💡 **开发建议**: 使用 5173 端口进行前端开发，Vite 自动检测文件变更并热更新；8000 端口用于后端 API 和 Swagger 文档调试。

---

## 🔧 关键设计决策

| 决策 | 原因 |
|------|------|
| **Celery `--pool=threads`** | Python 3.14 `spawn` 多进程导致 `trace._localized` 解包崩溃，Windows 强制线程池 |
| **SQLite NullPool + WAL 模式** | 单文件开发库零配置；WAL 提升并发读写；NullPool 避免连接池冲突 |
| **Chroma + BM25 双引擎** | 向量检索覆盖语义近似，BM25 覆盖关键词精确匹配，RRF 融合无需调参 |
| **SSE (非 WebSocket)** | 简化部署（无额外 WS 服务器），支持草稿流和对话流两种场景 |
| **SSE via POST** | AI 对话使用 POST 携带完整请求体 (project_id, history, chat_mode)，优于 GET+URL 编码 |
| **状态感知轮询停止** | 交互节点/终态自动停轮询，避免不必要的网络请求 |
| **`orm_to_dict()` 手动转换** | 避免 Pydantic `from_attributes=True` 的嵌套序列化陷阱 |
| **16:9 横版 PDF** | WeasyPrint CSS `@page size: 1440px 810px` 精确控制，符合商业汇报标准 |
| **Redis Docker 容器化** | 避免 WSL sudo 权限问题，`--restart unless-stopped` 自动保活 |
| **大纲解析器单一实现** | `app/shared/outline_parser.py` 消除 CLI/API/Celery 三处重复代码 |
| **ProjectRepo 依赖倒置** | Celery Worker 使用同步引擎的独立仓库层，消除散落的 raw SQL |
| **DuckDuckGo 图片搜索** | 免 API Key，降低第三方依赖成本；结果持久化到 project_images 表，支持跨会话恢复 |
| **Zustand + zundo Undo/Redo** | 原子化状态管理，`updateElement(page, id, {x,y})` 单字段更新，不触发全量序列化 |
| **canvasRef editorApi** | 父组件通过 ref 调用 addText/addImage 直连 Zustand store，AI 面板与编辑器松耦合 |
| **本地上传 + 远程搜索双通道** | 用户既可依赖全自动搜索，也可上传自有 PDF 参考文档 |
| **Flux 架构: Dispatch → Action → Store → View** | 前端状态管理遵循单向数据流，useProjectStatus 为中央 Dispatch |
| **引用 URL 合并去重** | 同源多 Chunk 合并为单上下文块，防止 LLM 因重复片段复述同一事实 |
| **dev_section_loop 快速迭代** | 绕过 Celery/Redis 直连 section_writer，秒级验证 LLM 输出 → Canvas 排版效果 |
| **上下文感知排版选择** | 按子项数量和文本长度分级选择排版策略，替代随机抽取；溢出时自动回退 vertical |
| **Prompt 层级结构 "分组+并列"** | 引导 LLM 输出稳定可预测的结构，提升卡片/对比列/时间轴等版式的触发率 |
| **🆕 v2: agent-platform 独立平台层** | LangGraph/Agent Harness 全部落在 `~/dev/agents/agent-platform`，业务侧仅桥接配置，杜绝框架侵入 |
| **🆕 v2: 结构化输出契约** | 每个 Agent 输出经 Pydantic 校验（LLM JSON → Schema → 前端渲染），LLM 禁止生成 HTML/CSS |
| **🆕 v2: 节点重试与降级** | 工作流节点失败重试后结构化记录错误并降级继续，其余资产照常交付 |

---

## 🔧 运维与修复

### 历史项目修复

当项目因异常中断卡在中间状态时：

```bash
cd backend && python fix_stuck_projects.py
```

### 手动清理

```bash
# 清理全部数据
rm -f backend/local_dev.db
rm -rf outputs/ chroma_db/ bm25_db/

# 仅清理向量缓存（保留项目数据库）
rm -rf chroma_db/ bm25_db/
```

### 日志查看

```bash
# 各模块日志文件
tail -f backend/runtime/api.log        # FastAPI
tail -f backend/runtime/celery.log     # Celery Worker
tail -f backend/runtime/vite_build.log # Vite 构建
```

---

## 🧪 测试

```bash
# 后端集成测试
cd backend && python -m pytest tests/test_api_integration.py -v

# 评测脚本
python tests/eval_retrieval.py     # 检索精度评测
python tests/eval_ranking.py       # 排序质量评测
python tests/eval_citation.py      # 引用溯源评测

# 前端类型检查
cd frontend && npx tsc --noEmit
```

---

## 📊 数据模型 ER

```
┌──────┐        ┌─────────────────────┐        ┌──────────┐
│ User │───<│   │       Project       │───<│   │   Task   │
└──────┘        │  (状态机驱动)        │        │  (step)  │
                └──┬──────┬──────┬───┘        └──────────┘
                   │      │      │
          ┌────────┘      │      └────────┐
          ▼               ▼               ▼
   ┌─────────────┐ ┌──────────────┐ ┌──────────────┐
   │  Document   │ │DocumentBlock │ │ ProjectLog   │
   │  (完整章节)  │ │ (原子化块)    │ │ (时间轴日志) │
   └─────────────┘ └──────────────┘ └──────────────┘
                         ▼
                  ┌──────────────┐
                  │ ProjectImage │
                  │ (图片素材库)  │
                  └──────────────┘
```

- **Document** — 完整章节，含引用 URL 映射 JSON
- **DocumentBlock** — Tiptap 编辑器的原子化块，每个段落独立存储
- **ProjectLog** — 终端控制台风格的时间轴日志，支持增量拉取
- **Task** — 7 种子任务类型（SEARCH → KNOWLEDGE_BASE → OUTLINE → WRITE_SECTION → IMAGE_GENERATION → BUILD_REPORT → PDF），追踪每步状态

---

## 🎯 核心能力清单

| 能力 | 实现 | 说明 |
|------|------|------|
| 🔍 自动信息搜集 | Tavily Search API | 全网搜索最新行业资讯 |
| 🖼️ 图片搜索 | DuckDuckGo Images (ddgs v9.x) | 免 API Key，产品概念图搜索，结果持久化到素材库 |
| 🖼️ 图片素材库 | ImageGallery + search-images API | 搜索→缩略图网格→拖拽到画布 + 上下文空状态 + 自动轮询 |
| ✂️ 图片裁剪 | Konva clipFunc + Transformer | 四角缩放的裁剪区域，非破坏性编辑 |
| 📋 幻灯片管理 | duplicateSlide / copySlide / pasteSlide | 复制/粘贴/新增/删除 幻灯片 + 键盘快捷键 |
| 🕷️ 网页深度抓取 | Firecrawl | 网页转结构化 Markdown |
| 📎 本地上传文档 | PyMuPDF + upload-docs API | PDF 解析切片，打入知识库 |
| 📚 双引擎知识库 | Chroma + BM25 + RRF | 语义 + 关键词混合召回 |
| 🧠 AI 深度撰写 | DeepSeek Chat | 基于检索资料生成专业研报 |
| 🤖 AI 对话面板 | SSE Chat + RAG | Work/Chat 双模式，流式打字机效果 |
| 📎 学术级引用溯源 | `citation_utils.py` | 自动编号 + `[^n]` 角标 + 参考资料章节 |
| 🎯 信息源分级 | 领域权威 > 行业媒体 > UGC | 自动加权排序 |
| 🎨 多模态概念图 | 硅基流动 FLUX.1 | AI 生成产品概念设计图 |
| 📄 横版 PPT PDF | WeasyPrint 1440×810px | 16:9 宽屏，商业汇报标准 |
| 📄 手动导出 PDF | export-pdf API | 从编辑器内容导出，drafting 阶段即可用 |
| 🖥️ 实时运行日志 | ProjectLog 时间轴 | 终端控制台风格，增量拉取 |
| 🔄 交互式状态机 | 三阶段六状态 | 两处断点：资料审核 + 大纲确认 |
| 🌐 三栏式工作台 | React + Tiptap | 大纲导航 + 块编辑器 + 日志/溯源/对话面板 |
| ✨ Inline AI | BubbleMenu | 划词改写: 润色/扩写/精简/正式化 |
| 📡 SSE 流式输出 | Server-Sent Events | 逐块推送草稿 + 实时对话 |
| 📋 报告模板选择 | TemplatePopover | 标准/竞品/投资三种分析视角 |
| 🗑️ 项目管理 | 级联删除 | 删除项目及所有关联数据 |

---

## 📄 License

MIT License — 详见 [LICENSE](LICENSE)

---

## 🔗 相关资源

- **源码仓库**: [https://github.com/CaroVon/QX_Product_Research](https://github.com/CaroVon/QX_Product_Research)
- **详细架构文档**: [PROJECT_STRUCTURE.md](./PROJECT_STRUCTURE.md)
- **产品需求文档**: [prd.md](./prd.md)
- **🆕 v2 迁移文档**: [MIGRATION.md](./MIGRATION.md)（AI Product Studio 架构、组件清单、测试结果与风险）
