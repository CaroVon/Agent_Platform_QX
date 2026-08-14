# AI Product Studio 迁移文档（Migration Guide）

> 从「LLM 生成产品研究文档」到「AI Product Studio：多 Agent 结构化产品资产平台」的增量迁移记录。

**迁移原则**：不重写既有系统、保留全部现有能力、新架构通过独立平台层与新增 API 渐进落地。

---

## 1. 目标架构（现状）

```
                    Product Studio UI (/studio)
                          │  REST + SSE
                    QX Application Layer（FastAPI + Celery）
                          │  Python import（只做桥接，不内嵌框架）
                  Agent Platform Runtime（agent-platform/）
                          │
      ┌───────────────┬───────────────┬──────────────────┐
  Research Agent  Product Agent  Design Agent  Presentation Agent（agents/）
                          │
               Agent Harness Layer（规划/记忆/工具/上下文/Agent 循环）
                          │
             LangGraph Workflow Layer（状态管理/多 Agent 编排/执行）
                          │
       Model Layer（DeepSeek / Qwen / GPT 兼容接口，AGENT_PLATFORM_LLM_*）
```

三个关键架构决策（对应迁移 Prompt 的三条红线）：

1. **LangGraph/平台能力不进 QX_product_agent** —— 全部落在独立的 `agent-platform/`，业务侧只通过 Celery 任务桥接配置与目录。
2. **Markdown-first → JSON Schema + Renderer** —— 每个 Agent 输出经 Pydantic 校验的结构化 JSON；LLM 禁止生成 HTML/CSS，视觉由前端组件控制。
3. **不做一个超级 Agent** —— Research / Product / Design / Presentation 四个专业 Agent，由 LangGraph 七节点流水线编排。

---

## 2. 新增组件清单

### 2.1 平台层（新仓库内模块，独立可测试）

```
~/dev/agents/agent-platform/
├── agent_platform/
│   ├── harness/           # Agent 循环、规划、Prompt 管理、上下文、结构化输出
│   │   ├── agent_loop.py  #   规划 → 执行 → 评估 → 反思（Phase 5 能力）
│   │   ├── planner.py     #   LLM 目标分解（失败回退单步）
│   │   ├── runner.py      #   JSON → Pydantic 校验 + 错误回传自愈重试
│   │   ├── context.py     #   字符预算截断
│   │   └── prompt_manager.py
│   ├── workflows/
│   │   ├── state.py               # ProductStudioState（TypedDict）
│   │   └── product_research_graph.py  # 七节点 LangGraph 流水线
│   ├── schemas/           # requirement/research/product/design/presentation/package
│   ├── tools/             # Tavily 搜索、文档解析、工具注册表
│   ├── memory/            # FileMemoryStore（项目级持久记忆）
│   ├── config/settings.py # AGENT_PLATFORM_* 环境变量
│   └── llm/client.py      # OpenAI 兼容模型客户端（DeepSeek/Qwen/GPT）
├── tests/                 # 26 个测试（FakeLLM，零网络）
└── requirements.txt       # langgraph / pydantic / pydantic-settings / httpx
```

### 2.2 专业 Agent 层（旧 chat/task/tool-agent 目录为空的占位，按规范新建）

```
~/dev/agents/agents/
├── research-agent/       # 市场研究 + 竞品分析（两个工作流节点）
├── product-agent/        # 定位/画像/功能/路线图/PRD
├── design-agent/         # 用户旅程/信息架构/UI 结构
├── presentation-agent/   # Slide JSON（报告与幻灯片结构）
└── tests/                # 2 个全链路集成测试（真实 Agent 类 + FakeLLM）
```

> 目录名遵循规范使用连字符（`research-agent`），`agents/__init__.py` 内置包注册器把连字符目录注册为合法 Python 包名。

### 2.3 QX_product_agent 集成改动（外科手术式）

| 文件 | 改动 | 说明 |
|------|------|------|
| `backend/app/models/studio_product.py` | **新增** | `studio_products` 表（idea/status/asset_package/error） |
| `backend/app/models/__init__.py` | 修改 | 注册 StudioProduct（create_all 自动建表） |
| `backend/app/schemas/studio.py` | **新增** | Product Studio 请求/响应契约 |
| `backend/app/schemas/__init__.py` | 修改 | 导入 studio schemas |
| `backend/app/api/v1/endpoints/product.py` | **新增** | `/api/v1/product/create`、`GET /{id}`、`GET`（列表）、`POST /{id}/export-pdf` |
| `backend/app/api/v1/router.py` | 修改 | 注册 product 路由 |
| `backend/app/tasks/product_studio_tasks.py` | **新增** | Celery 桥接任务（env 桥接 + sys.path + 工作流执行 + 持久化） |
| `backend/app/core/config.py` | 修改 | 新增 `AGENT_PLATFORM_PATH/AGENTS_PATH/AGENT_PLATFORM_MEMORY_DIR/AGENT_PLATFORM_MAX_RETRIES` |
| `backend/app/core/celery_app.py` | 修改 | include 新任务模块 |
| `backend/app/services/studio_render.py` | **新增** | Slide JSON → 结构化 HTML → WeasyPrint PDF |
| `backend/tests/test_studio_api.py` | **新增** | 8 个端点测试 |
| `backend/tests/conftest.py` | 修复 | 既有 `User(name=...)` → `username=`（阻塞整个测试套件的既有缺陷） |
| `frontend/src/types/studio.ts` | **新增** | 与 Pydantic Schema 同步的 TS 类型 |
| `frontend/src/lib/api.ts` | 修改 | `productApi`（create/get/list/exportPdf） |
| `frontend/src/components/MarketCard.tsx` 等 7 个组件 | **新增** | 结构化 JSON 渲染组件（见 3.3） |
| `frontend/src/pages/ProductStudioPage.tsx` | **新增** | Product Studio 工作台（/studio） |
| `frontend/src/App.tsx` / `components/layout/Sidebar.tsx` | 修改 | 路由与导航 |
| `scripts/studio_pipeline_smoke.py` | **新增** | 绕过 Celery 的真实 LLM 冒烟测试工具 |
| `MIGRATION.md` | **新增** | 本文档 |

**既有能力零改动**：三阶段状态机、Canvas 编辑器、RAG 检索、AI 对话面板全部保留，旧 API 路径不变。

---

## 3. 关键设计

### 3.1 LangGraph 七节点流水线

```
Requirement Parser → Research → Competitor Analysis → Strategy → UX Design → Presentation → Assemble
```

- **节点协议**：接收 `ProductStudioState`（TypedDict），返回更新 dict（LangGraph 规范），产物先过 Pydantic 再写入状态。
- **重试机制**：`_with_retry` 包装器，默认 `AGENT_PLATFORM_MAX_RETRIES + 1` 次尝试。
- **失败处理**：重试耗尽后节点标记 `failed`、错误结构化写入 `meta.errors`，流水线**降级继续**，其余资产照常交付（前端呈现部分成功 + 失败原因）。
- **Checkpoint**：内存 MemorySaver（`thread_id = product_id`），为断点续跑预留。

### 3.2 Agent Harness（Phase 5 能力）

每个专业 Agent 继承 `BaseAgent`，由 `AgentLoop` 驱动：

- **Planning**：LLM 把目标分解为 2-6 步（失败回退单步，不阻塞）
- **Execution**：`StructuredRunner` 强制 JSON + Pydantic 校验
- **Evaluation**：默认评估器检查关键字段非空（可注入自定义评估器）
- **Reflection**：评估未通过 → 差距回写 Prompt → 下一轮（最多 `AGENT_MAX_TURNS` 轮）
- **Retry**：校验失败把 Pydantic 错误详情回传 LLM 自愈（最多 `AGENT_MAX_RETRIES` 次）
- **Memory**：每轮产物写入 `FileMemoryStore`（按 product_id 隔离），上游结论被下游 Agent 复用

### 3.3 结构化输出 → 前端渲染（替代 Markdown-first）

| Agent 输出（Pydantic） | 前端渲染组件 |
|------------------------|--------------|
| `MarketResearch` | `MarketCard.tsx` |
| `CompetitorAnalysis` | `CompetitorMatrix.tsx` |
| `ProductStrategy.personas` | `PersonaCard.tsx` |
| `ProductStrategy.features` | `FeatureMatrix.tsx` |
| `ProductStrategy.roadmap` | `RoadmapTimeline.tsx` |
| `ProductStrategy.prd_sections` | `PRDViewer.tsx`（react-markdown 渲染纯 Markdown 正文） |
| `SlideDeck`（Slide JSON） | `SlideRenderer.tsx`（16:9 Web 演示 + PDF 导出） |

### 3.4 演示生成升级（替代 Markdown-to-PDF）

```
Presentation Agent → Slide JSON Schema → SlideRenderer（React）/ studio_render（WeasyPrint）
                                          → Web Presentation / PPT 风格 PDF
```

- **AI 生成**：内容结构、`layout_type`（cover/bullets/matrix/timeline/two_column/quote/closing...）、`visual_metadata`（视觉层级提示）
- **前端控制**：字体、间距、组件样式 —— 排版与视觉全部在渲染层

### 3.5 API

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/product/create` | `{"idea": "AI education assistant"}` → 异步触发流水线 |
| `GET` | `/api/v1/product/{id}` | 资产包：`{research, strategy, design, presentation, ...}` + 进度/错误 |
| `GET` | `/api/v1/product` | 产品列表 |
| `POST` | `/api/v1/product/{id}/export-pdf` | Slide JSON → PPT 风格 PDF |

> 创建为异步（流水线耗时 5-15 分钟），完成后 GET 返回的结构即目标响应形状
> `{research, strategy, design, presentation}`。

---

## 4. 分阶段迁移计划与完成状态

| Phase | 内容 | 状态 |
|-------|------|------|
| 1 | 创建 agent-platform + 安装 LangGraph + 工作流运行时 | ✅ 完成 |
| 2 | 专业 Agent 化 + Schemas | ✅ 完成 |
| 3 | Markdown-first → JSON + Renderer | ✅ 完成（旧 PDF 链路保留作兼容） |
| 4 | 前端产品化（Product Studio + 7 个渲染组件） | ✅ 完成 |
| 5 | memory / planning / self-reflection / evaluation / retry | ✅ 完成（harness 层） |

---

## 5. 测试结果

| 套件 | 命令 | 结果 |
|------|------|------|
| 平台层 | `agent-platform: python -m pytest tests/ -q` | ✅ 26 passed |
| 专业 Agent 集成 | `agents: python -m pytest tests/ -q` | ✅ 2 passed |
| 后端（含新增 8 个 studio 测试） | `backend: python -m pytest tests/ -q` | ✅ 44 passed |
| 前端类型检查 | `frontend: npx tsc --noEmit` | ✅ 0 错误 |
| 前端构建 | `frontend: npm run build` | ✅ 成功 |
| 真实 LLM 冒烟 | `scripts/studio_pipeline_smoke.py "AI 健身应用"` | ✅ 全链路走通 |

> 测试策略：平台层全部测试使用 `FakeLLM`（零网络、脚本化响应），
> 覆盖 Schema 契约、自愈重试、节点重试/降级、真实 Agent 接线。

---

## 6. 运行方式

```bash
# 1. 依赖
cd agent-platform && pip install -r requirements.txt
# 后端 venv 需补充: pip install langgraph pymupdf weasyprint

# 2. 启动既有系统（不变）
bash start_all.sh

# 3. Product Studio
#    浏览器打开 http://localhost:5173/studio
#    输入想法 → Generate → 观察七节点进度 → 结构化输出工作区 → 导出 PDF

# 4. 后端冒烟（绕过 Celery，真实 LLM）
cd backend && ../venv/bin/python ../scripts/studio_pipeline_smoke.py "AI 健身应用"
```

---

## 7. 剩余风险与后续工作

| 风险/事项 | 说明 | 建议 |
|-----------|------|------|
| 流水线耗时 | 7 节点 ×（规划 + 生成 + 评估）约 5-15 分钟 | 后续引入流式进度推送（SSE）与节点级缓存 |
| Search 工具覆盖 | 平台层仅实现 Tavily 搜索；QX 既有 Firecrawl 抓取/本地文档解析未迁入 | 需要时把 `app/rag` 能力以工具接口注入平台层 |
| PDF 版式 | `studio_render` 提供基础版式模板，复杂视觉需前端 Konva 编辑器承接 | 与既有 CanvasSlideEditor 打通（slide JSON → Canvas） |
| 模型层 | 当前走 DeepSeek；Qwen/GPT 仅需改 `AGENT_PLATFORM_LLM_*` | 增加模型路由与失败切换 |
| 多租户记忆 | FileMemoryStore 按 product_id 隔离 | 生产切换 Redis/Postgres 实现（接口已抽象） |
| 评估深度 | 默认评估器仅检查字段非空 | 引入评分模型/规则集做质量门禁 |
