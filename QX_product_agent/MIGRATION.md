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

---

## 8. P0-P5 完整改造记录（2026-08）

按 `prompts/presentation_pipeline_plan.md` 实施完成：

### P0 渲染完整度修复（WeasyPrint 兜底路径）
- `studio_render.py`：grid/flex → table-cell 兼容布局（two_column 塌陷根治）、
  移除固定高度 + overflow:hidden 截断 → 自动分页（内容永不丢失）、
  密度分级字号（density-mid/compact 估算缩放）
- 审计测试 `backend/tests/test_studio_render.py`：真实资产包 + 合成压力用例
  （标题无缺、逐行可寻回、two_column 不塌陷）

### P1 Canonical Product Document
- 新增 `agent_platform/schemas/product_document.py`：`ProjectInfo` + `ProductDocument`
  （research/competitor_analysis/strategy/design，**无排版字段**）
- `ProductAssetPackage` 新增 `document` 字段；assemble 节点同时产出语义层与叙事层

### P2 Presentation DSL
- `schemas/presentation.py` 重写：`Presentation`(title/theme/pages) →
  `Page`(type/layout/title/insight/components) → `Component`(type/data/emphasis)
  - 10 语义页型、10 布局枚举、9 组件类型，全部 Literal 强约束
  - `LAYOUT_LIBRARY`：10 布局栅格定义（模型只选不造）
  - 旧 `SlideDeck/Slide/SlideBlock` 保留为 deprecated 兼容层

### P3 视觉规范 Skill + 信息设计 Agent
- `agent_platform/skills/presentation-design/`：SKILL.md（8 原则）+ layout_rules +
  typography + chart_selection + information_hierarchy（SkillLoader 注入 Prompt）
- Presentation Agent 重写：输出新 DSL、专用评估器（页数/组件密度/布局多样性）
- Kimi 可选：`AGENT_PLATFORM_PRESENTATION_LLM_*` 配置即切换专用模型（默认 DeepSeek）

### P4 单一 React 渲染源 + Playwright 导出
- `frontend/src/components/presentation/`：`components.tsx`（9 组件，recharts 图表 +
  quadrant 散点）、`layouts.tsx`（10 布局 PageFrame）、`PresentationViewer.tsx`
- `/export/:productId` 导出路由（无 UI 外壳，@page 1280×720 打印分页）
- `frontend/scripts/export-pdf.mjs`：Playwright 打印 PDF（preferCSSPageSize）+
  PptxGenJS 导出 PPTX + **浏览器侧溢出质量门**（scrollHeight 检测 + 逐级缩字号自适配）
- 后端 `POST /api/v1/product/{id}/export-pdf` 双路径：新 DSL → Playwright；
  旧 slides → WeasyPrint 兜底；新增 `POST /api/v1/product/{id}/export-pptx`

### P5 Critic Agent + 质量门 + 修订循环
- `agents/critic-agent/`：六维度评审（density/hierarchy/consistency/variety/
  overflow/duplicate）→ `CritiqueResult{score, issues}`
- `agent_platform/harness/quality_gate.py`：确定性检查（页数 8-14、组件 2-6、
  ID 唯一、标题/insight、文本密度、重复信息、metric/chart 数据完整性）
- 图循环：presentation → critic →（score≥80 或修订上限 → assemble；
  否则带 issues 反馈回到 presentation）—— 质量门 error 每项压 20 分
- 可配置：`PRESENTATION_SCORE_THRESHOLD=80`、`PRESENTATION_MAX_REVISIONS=2`

### 测试结果
| 套件 | 数量 |
|------|------|
| agent-platform（含 P5 循环 6 用例 + DSL 契约 4 用例） | ✅ 39 passed |
| agents 集成 | ✅ 2 passed |
| backend（含 P0 渲染审计 4 用例） | ✅ 48 passed |
| 前端 tsc + vite build | ✅ 0 错误 |

---

## 9. 前端产品化改造记录（productize.md，2026-08）

### 信息架构（8 模块侧边栏）
```
WORKSPACE  Product Workspace (/workspace, 四段式主工作区)
STUDIO     Research Hub (/research) · PRD Studio (/prd)
           Design Studio (/design) · Presentation (/presentation)
MANAGE     Knowledge Base (/knowledge) · Templates (/templates) · Settings (/settings)
```
- 侧边栏可折叠（localStorage 持久化 + 200ms 过渡动画，Notion/Linear 风格）
- `/studio` 重定向 `/workspace`（兼容旧链接）；旧工作台 `/projects/:id/*` 与 `/` 控制台保留不动
- 每个模块：路由 + UI 结构 + 空状态 + 扩展点（ModulePlaceholder 通用壳）

### Product Workspace 四段式
1. Project Information：想法输入 + Generate + 最近产品
2. Agent Workflow：八节点进度（含 Critic 评分徽标）
3. Generated Assets：四大资产卡（研究/PRD/设计/演示）→ 跳转对应模块
4. Related Knowledge：研究项目绑定 + 文件上传 + 图片搜索

### 恢复缺失功能
- **FileUploader**：拖拽/进度(XHR)/预览/移除；文本类 → upload-docs 入库检索，图片类 → assets 素材
- **ImageSearch**：DuckDuckGo 搜索 → 自动入库项目图片库 → 网格预览/删除（复用既有 API）

### 资产聚合（零新增业务逻辑，复用 P0-P5 结构化资产）
- ProductAssetBrowser：产品列表（含 Critic 评分）→ 详情
- Research Hub 复用 MarketCard/CompetitorMatrix；PRD Studio 复用 PRDViewer/PersonaCard/
  FeatureMatrix/RoadmapTimeline；Design Studio 新写旅程/页面/组件规格展示；
  Presentation 复用 PresentationViewer（新 DSL）/SlideRenderer（旧格式兼容）
- 后端新增只读端点 `GET /api/v1/knowledge/documents`（全局文档聚合）

### Breathing UI 设计系统
- 大留白内容区（max-w-6xl + px-12 + py-10）、统一 Section 壳（step/标题/描述）
- 资产卡/模板卡 hover 抬升、平滑过渡、低噪音顶栏

### 测试结果
| 验证项 | 结果 |
|--------|------|
| 后端套件（含 knowledge 2 用例） | ✅ 50 passed |
| 前端 tsc + vite build | ✅ 0 错误 |
| UI 冒烟（ui-smoke.mjs，Playwright） | ✅ 8 路由全渲染、侧边栏折叠、0 控制台错误 |
| 深度验证 | ✅ 研究页 4 产品+MarketCard、演示翻页、知识库 108 文档、上传入库联通 |

---

## 10. PDF 内容完整度与美观度优化（2026-08，第二轮）

### 实证驱动的根因定位
- 渲染完整性：DSL vs PDF 文本 0 缺失（渲染层无截断）—— "内容缺失"的真相是
  **上游资产 → Presentation DSL 压缩率 11%**（9842 字 → 1090 字）：
  功能 12→1 组件、痛点 6→0 处、竞品 6→0 数据点、PRD 5 章→0 页
- 标题贴边：`PageFrame` exportMode 使用 `absolute inset-0` 脱离文档流、
  无视父级 padding → 标题从画布原点 (0,0) 开始（PDF span 坐标 x=0.0 实证）

### 修复内容
- **B1**（布局 bug）：exportMode shell 改为流式布局，屏幕/打印一致（WYSIWYG）
- **B2**：统一安全边距 56×48px；导出页显示页码（安全区内）
- **B3**：标题行距/insight 间距打磨
- **A1**：presentation-design skill 重写为「完整叙事」——组件 2-8 个、
  单组件 ≤150 字、页文本 ≤600 字、各页型必覆盖清单（market 全指标/
  痛点/趋势、matrix 全竞品、persona 全画像、features 全功能、roadmap 全阶段）
- **A2**：Presentation Agent Prompt 注入必覆盖字段清单（输出前逐项核对）
- **A3**：质量门新增 6 项信息覆盖度检查（功能 ≥70%、痛点 ≥60%、竞品 ≥70%、
  市场指标 ≥3/4、路线图/画像全覆盖、趋势 ≥60%）—— 不达标记 error 压分，
  自动触发 Critic 修订循环
- 新增通用审计脚本 `scripts/audit_presentation.py`（压缩率/覆盖度/渲染完整性/坐标审计）

### 测试
- 平台 41（含覆盖度 2 用例）/ agents 2 / 后端 50 / tsc+build 通过

### 第二轮补丁（覆盖度接线修复，实证驱动）
v2 真实流水线暴露三个深层问题并修复：
1. **覆盖度检查从未启用**：`document` 在 assemble 节点才构造，critic 运行时为 None
   → 抽取 `_build_document(state)` 供 critic/assemble 共用（critic 先行构造）
2. **评分 0 的 falsy 陷阱**：`critic_score or 100` 把压分到 0 的分数回退成 100 → 直接放行
   → 改为显式 None 判断；并增加 presentation 节点 failed 时强制收尾（防修订死循环）
3. **专有名词改写导致误判**：Agent 重述功能名（"AI睡眠监测与报告"→"睡眠监测"）
   → 匹配改为「原文 或 前 6 字核心词」双通道；skill/prompt 强制专有名词原文引用
   → 质量门语义修正：仅要求上游**实际提供**的字段（required = max(min(N, 条数), 60~70%)）

### 第三轮强化（确定性兜底，覆盖率 100%）
v3/v4 实证：Agent 结构达标但专有名词改写 + 长文本痛点难覆盖 + 组件 ID 重复。
「模型做叙事，代码保底线」最终方案：
1. **enforce_coverage 兜底层**（`agent_platform/harness/enforce_coverage.py`）：
   presentation 节点输出后确定性注入缺失信息 —— 市场指标 metric / 痛点要点 /
   趋势 / 竞品象限点 / 画像卡 / 功能表行 / 路线图阶段（全部取自上游原文）
   + 组件 ID 全局归一化
2. **AgentLoop 内覆盖度评估器**：build_deck 注入 coverage 闭包（含缺失清单反馈），
   模型每轮自检自修；质量门 coverage 反馈改为携带缺失项原文名单
3. **评分 falsy 修复**：`critic_score or 100` → 显式 None 判断；presentation 失败强制收尾防死循环
4. **导出终极兜底**：字号三级缩放（最低 64%）后仍溢出 → transform 视觉缩放（内容完整不截断）

### 最终验证（v5 真实 LLM 流水线）
| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| 上游→DSL 压缩率 | 11% | **31%**（3013 字） |
| 功能覆盖 | 12→1 组件 | **12/12** |
| 痛点覆盖 | 0 处 | **6/6** |
| 竞品覆盖 | 0 数据点 | **6/6** |
| 市场指标 | 0 | **4/4** |
| 路线图 | — | **3/3** |
| 质量门 errors | 4 项 | **0** |
| PDF 溢出 | — | **0 页** |
| 标题贴边 | x=0pt | **x=42pt（安全边距内）** |
| PDF 页数 | 9=9 | 10=10（渲染完整性 0 缺失） |

测试：平台 44（含 enforce 3 用例）/ agents 2 / 后端 50 / tsc+build 通过。

### 第四轮：导出排版一致性 + HTML 快照格式（2026-08）
用户反馈「网页预览 OK，导出 PDF 排版损失」→ 实证定位：
- transform 兜底把竞品矩阵页缩至字号 5.8-13.9pt（其余页 7.5-18pt）→ 页面缩水不一致
- 根治：matrix 布局改双栏（左象限图 190px / 右洞察卡）→ 不再触发 transform 兜底；
  重导出后全页字号统一 7.5-18pt、溢出 0
- 新增 **HTML 快照导出**（采纳用户建议的补充格式）：
  `POST /api/v1/product/{id}/export-html` → 单文件 HTML（全部样式内联，
  与网页预览 100% 一致，双击即可独立打开，10 页渲染验证通过）
- PresentationViewer 增加「导出 HTML」按钮；api.ts 增加 exportHtml/exportPptx
- 三种交付格式：PDF（最终视觉）/ PPTX（可编辑）/ HTML（独立展示快照）

---

## 11. 前端视觉重构记录（frontedUI.md，2026-08）

### 设计方向：Vintage + Breathable + Modern AI Workspace
- 色板重定义：暖白纸感背景（42 30% 97%）/ 米白卡片（40 26% 95.5%）/
  深蓝主色（212 46% 26%）/ 深绿 #3F6B4F / 柔和橙 #C87E4F 点缀；
  大圆角 0.9rem；软边框（无重阴影）；深墨蓝侧边栏（Linear 风格）
- 间距体系：页面 40-48px、区块 48px（space-y-12）、卡片 24-32px
- 编辑感字体层级：font-editorial（Iowan/Georgia/宋体 serif）用于标题与 Hero
- 微动画（CSS 实现，克制）：breathe（空态柔光）、soft-pulse（运行态）、
  StreamingMessage 打字轮换 —— 传达 AI 思考与进度，非装饰

### 组件架构（按规范目录落地）
- layout/：Sidebar（工作区选择器 + 当前项目指示 + 用户资料区）、
  WorkspaceLayout（bg-paper + 大留白）、Header（面包屑 + 状态徽标）
- ai/：AgentTimeline（八节点 → 四团队角色）、AgentStatus、ToolExecution
  （按活跃节点显示真实工具）、StreamingMessage
- workspace/：ProjectHeader、IdeaInput（Hero 大居中）、AssetPanel、KnowledgePanel
- research/：ResearchCard、CompetitorCard、InsightCard（研究页全部改用）
- product/：PRDViewer、FeatureMatrix、Roadmap（从根目录迁移）
- presentation/：新增 SlidePreview 缩略导航（与 PresentationViewer 联动翻页）

### Product Workspace 重构为 AI 创作画布
Hero 想法输入 → ProjectHeader（项目/行业/状态/Critic 分）→ AI 团队进度
（时间线+工具双栏 + 流式状态）→ 生成资产面板 → 新想法输入 → 知识上下文

### 测试
- tsc + vite build ✅；Playwright UI 冒烟 8 路由 + 折叠 + 0 console 错误 ✅
- 深度验证：色板 tokens 生效、画布 7 区块全渲染、演示缩略图 10 张、
  加载历史产品 → 团队画布完整 ✅
- 后端/API/LangGraph 零改动（仅前端）

---

## 12. Netlify 部署适配（2026-08）

架构：前端部署 Netlify（公网），后端本机运行。前端全部 API 走相对路径
`/api/v1/*`，由 Netlify Edge Function（`netlify/edge-functions/api-proxy.ts`）
转发到环境变量 `BACKEND_URL`；可选 Basic Auth（`auth.ts`，AUTH_USERNAME/PASSWORD）。

- 代码适配：`api.ts` 导出 `API_BASE`（`VITE_API_BASE` 可覆盖直连），
  FileUploader / KnowledgePage 统一改用，消除硬编码 `/api/v1`
- 配置：`netlify.toml`（vite build / dist / SPA 回退 / 两个 Edge Function / Node 22）
- 部署文档：`frontend/NETLIFY.md`（隧道暴露后端 → UI 配置 → CLI 联调 → 常见问题）
- **实测**：netlify dev（.env 注入 BACKEND_URL=http://localhost:8000）→
  静态站点 200、SPA 回退正常、API 代理打通（产品 10 条 / 文档 108 篇）

---

## 13. Presentation 质量提升（免费方案组合，2026-08）

### 内容完整性
- enforce_coverage 兜底层已保证上游覆盖 100%（功能/痛点/竞品/指标/路线图/画像）

### UI 与排版美观度（免费方案组合）
- **ECharts 接入**：象限图升级为 ECharts（双系列着色、十字中轴线、悬浮提示、
  名称标注；竞品灰点 vs 本产品主色点），PDF 导出作为位图嵌入（清晰完整）
- **排版优化**：标题 26px 层级 + insight 条间距 + 统一组件网格间距
- **品牌主题系统**：4 套预置主题（咨询蓝/复古编辑/森林绿/墨黑金）
  + PresentationViewer 主题切换器（实时切换，仅显示层，不改数据）

### HTML 导出升级为交互式演示快照（关键需求）
- `export-pdf.mjs --format html` 重写：单文件内嵌**原生 JS 播放器**
  （上一页/下一页按钮 + 键盘 ←→/PageUp/Down/Home/End + 进度点跳转 +
  fade+slide 过渡动效 + 自适应缩放 fit）——导出后与 Web 预览保持一致的
  翻页交互与完整呈现效果（验证：翻页/键盘/跳点/动效全部通过）

### 测试与验证
- 平台 44 / agents 2 / 后端 50 / tsc+build ✅
- HTML 快照：初始单页、键盘/按钮/跳点翻页、过渡动效 ✅（Playwright 实测）
- PDF：10 页=10 页、0 溢出、字号统一 7.5-19.5、ECharts 嵌入 ✅

---

## 14. Presentation 五处微调（2026-08）

1. **三端排版同构（根治预览/导出不一致）**：预览改为固定 1280×720 舞台 +
   scale 适配容器（ResizeObserver）；预览与导出 HTML/PDF 共用同一坐标系，
   文本换行/高度计算完全一致（实测 p5 三栏页预览与 HTML scrollH=720 一致）
2. **预览溢出自适应**：usePreviewAutoFit 对当前页逐级缩字号（与导出 autoFit
   同逻辑）；导出 HTML 抓取干净 DOM（不再受 autoFit inline 缩放副作用影响），
   播放器内独立做溢出缩放
3. **播放器米白底**：HTML 播放器底色深黑 → 米白 #f5f4f1 + 导航配色适配
4. **内容量扩展**：
   - 上游 prompt 详尽化：research（竞品 3-4 优劣势/痛点附数据/趋势附说明）、
     product（10-16 功能附详述/画像 3-5 目标痛点/PRD 每章 200-400 字）
     → 上游 9559 → **12281 字（+28%）**
   - 演示密度目标 50-65%、预算页 2000/组件 360、页数 10-16
   - 新增 `enrich_coverage` 确定性内容充实层（表格描述列/画像细节/核心结论/
     阶段信息注入，不依赖 LLM 波动）
   - 实测 v9：12 页、DSL 4325 字（vs v5 **+44%**）、密度 35%、无空白
5. **思源字体组合**：正文 Noto Sans SC / 标题 font-editorial 改
   Noto Serif SC（含 Source Han SC / 系统回退栈；HTML 播放器同步）

验证：platform 46 / agents 2 / backend 50 / tsc+build ✅；
三端一致性审计（预览=HTML 坐标一致）✅；v9 PDF 12 页 0 溢出 ✅

---

## 15. Presentation HTML 编辑器（GrapesJS，M1-M2，2026-08）

调研结论（`prompts/editor_research.md`）：免费开源方案选型 **GrapesJS 0.23.5**
（对比 Polotno 付费/Page 类库无 DSL 对接），自研 DSL 桥接层，编辑对象 =
Presentation DSL（canonical）——编辑保存回写 DSL，导出仍走既有
HTML/PDF/PPTX 管线，三端一致不变。

### 架构
- 路由 `/presentation/editor/:productId`（PresentationPage 加“在编辑器中打开”入口）
- `components/editor/studio/initGrapes.ts`：1280×720 单设备画布、面板
  appendTo 自定义容器（属性面板/样式/图层/块面板）
- `blocks.ts`：9 类 DSL 块（text/metric/card/image/table/quote/timeline/
  chart/matrix）+ 2 基础元素（分割线/矩形）；`isComponent` 按
  `data-dsl-type` 恢复自定义类型 → 选中即出 traits
- `dslBridge.ts`：DSL↔HTML 双向转换。组件元数据走 `data-dsl-*` 属性
  （**GrapesJS 会清理无前缀自定义属性，data-* 保留**）；trait 编辑 →
  model attributes → 画布实时同步（attrViews + change:attributes）
- 保存：`grapesToPage`（DOM 收集 + 模型匹配回退）→ PATCH
  `/product/{id}/presentation`（新端点 + PresentationUpdateRequest，
  回写 asset_package.presentation）
- 图片插入：ImageSearch 新增 selectable 模式（点击/拖拽插入），
  画布 drop 监听轮询挂载（canvas 文档异步就绪）
- 素材栏（产品级，无遗留 project 依赖）：新增 `POST /product/{id}/search-images`
  （无状态 DuckDuckGo 搜索，不持久化）+ `POST /product/{id}/assets`
  （本地上传 → 静态 URL）；ImageSearch 支持 productMode（搜索/上传/本地素材库）
- 文本编辑：GrapesJS RTE（contenteditable 双击编辑 → 保存回写 DSL text）
- 图片编辑：trait 替换（data-src/data-alt）+ style manager（尺寸/效果扇区：
  宽高/圆角/透明度/滤镜）；图层面板 + 撤销重做为 GrapesJS 内置能力
- 导出多选项：`components/presentation/ExportMenu.tsx`（HTML / PDF / PPT
  下拉菜单，编辑器与预览 viewer 共用）；PPT = 可编辑 .pptx（PptxGenJS，
  `POST /product/{id}/export-pptx`，实测 10 页 145KB）

### 关键坑与修复（Playwright 实测驱动）
1. **`setAttributes` 是替换语义**（`set('attributes', {...})` 清空原有属性）
   → data-dsl-* 元数据丢失、组件从收集中消失；真实 trait 输入走合并语义
   （addAttributes）安全。代码约定：只写 `addAttributes`
2. **面板容器须常驻挂载**：样式/图层/块面板 appendTo 的目标容器原本按
   Tab 条件渲染（init 时不存在 → BlockManager "appendTo not found"）
   → 改为双容器常驻 + `hidden` 类切换
3. **保存基准**：切页收集的编辑保存在 pagesRef，保存时以
   `{...dsl, pages: pagesRef}` 为基准，仅当前页从画布重收，避免丢页

### 验证
- backend 56（+2 编辑器保存端点 + 素材搜索/上传 4）/ platform 46 /
  agents 2 / tsc+build ✅
- Playwright 全链路：块拖入（dragstart→dragenter→dragover→drop→插入，
  类型恢复 dsl-metric + traits 出现）→ trait 输入改数值 → 画布实时更新 →
  保存 → DSL 组件全量持久化（5 组件页 → 拖入 metric + image 共 7 组件，
  值 7777 保留）→ 导出 HTML 含编辑后内容 ✅；其他页组件零丢失 ✅
- 素材栏：本地上传 → 素材库出现 → 点击插入画布 → 保存持久化 ✅；
  在线搜索 12 图 ✅；图片 trait 替换（model+img tag 同步）✅
- RTE 双击编辑 → 保存回写 DSL text ✅；style manager 尺寸/效果扇区 ✅；
  图层面板（35 项）✅；撤销/重做（undo/redo 均生效）✅

---

## 16. CyberPPT 咨询风集成（适配框架 + 上游数据喂料，2026-08）

来源：[crazyykhllc-bit/CyberPPT](https://github.com/crazyykhllc-bit/CyberPPT)（MIT，Codex Skill）。
不是整体替换生成器（其产物为 .pptx 而非 DSL），而是**方法论吸收 + 数据适配 +
生产验证**三件套，产物仍为 Presentation DSL（编辑器/三端导出不变）。

### 适配框架（新增）
- `agent_platform/skills/presentation-cyberppt/`（MIT 声明见 NOTICE.txt）：
  SKILL.md（SCR 叙事 + 证据链 + 密度 + 风格锁定的总纲）、scr-narrative.md
  （S 现状→C 矛盾→R 解法 三幕页型映射）、density-planning.md（页型组件预算）、
  visual-system.md（8 套咨询风色板 → theme palette tokens）
- 8 套咨询风写入 `THEME_PRESETS`（schema）与前端 `THEMES`（渲染一致）：
  cyber-crimson / burgundy / ivory-wine / ivory-navy / grey-green /
  paper-copper / black-gold / deep-purple
- `ensure_consulting_theme`（确定性风格锁定）：模型未决策主题时按
  product_id 哈希轮换分配一套 cyber 风格；palette 缺失时从预置补全
- `evidence_pack.py`（上游数据喂料）：把上游语义层确定性转换为
  「证据表（E001… 带来源/数值/口径）+ 关键数字 + SCR 叙事提示 +
  每页组件预算」材料包，注入 Presentation Agent（artifact:
  cyberppt_evidence_pack），prompt 要求按证据 ID 引用、关键数字必入页
- PresentationAgent system prompt 组装：信息设计角色 + 视觉规范 +
  CyberPPT skill + Layout Library + 预置主题列表

### 生产验证（Playwright/Celery 实测）
- 新产品 11 页：cover→summary→market(S)→matrix/persona/journey(C)→
  features/architecture/roadmap/closing(R)，SCR 三幕齐全
- 质量门全绿：覆盖（指标/痛点/竞品/趋势/画像/路线图/功能）✓；
  主题经风格锁定落入 8 套咨询风之一（palette 六键完整）
- 证据包：材料包注入成功（证据表 + 关键数字 + SCR 提示进入上下文）
- **主题全链路传导**：viewer 初始主题取自 DSL theme（生成风格直接呈现）；
  HTML/PDF 快照与 PPTX 生成器均读取 theme.palette（实测 HTML
  --p-primary=#12355B、PPTX slide XML 内嵌 #12355B）
- **生产验证（新 worker 实测）**：12 页 SCR 三幕齐全，证据 ID 引用 20 处，
  主题自动锁定 cyber-ivory-navy（palette 六键完整），critic 62→72；
  PPTX 12 页经 CyberPPT validate_pptx.py：0 errors
- 测试：platform 54（+5 证据包 +3 主题锁定）/ agents 2 / backend 56 /
  tsc+build ✅

---

## 17. CyberPPT P1-P3：内容保真 + 视觉层 + 结构化适配（2026-08）

针对「生成 PPT 与 demo 差距」「research hub / PRD studio 模块化文本缺失」双问题，
按 P1→P3 实施（结构性调整：ImageGen 蓝图以确定性构图层替代，成本 0，未来可插拔）。

### P1 内容保真（确定性，不依赖 LLM 自觉）
- `evidence_pack.py`：模块化文本块（PRD 章节全文/画像三段/竞品定位·定价·强弱项/
  旅程步骤描述）截断上限 80→300 字符，保结构「标题：正文」入包（实测包 11KB）
- Prompt：新增【模块化内容入页清单】+【组件清单声明】（生成规划=还原清单，
  card items/timeline milestones/chart items 逐项兑现）
- `enforce_coverage._inject_modular_content`（代码保底线）：竞品短板/定价未入页 →
  competitor_matrix 补「竞品短板与定价」卡；PRD 章节未入页 → features/architecture
  补「PRD 核心结论」卡。实测：PRD 三章全文 + 6 家竞品弱点/定价确定性入 DSL
- PPTX 渲染器补全组件：card（标题+items+desc）、timeline（阶段+里程碑）、
  quote、**chart/matrix 用本地 ECharts 渲染 PNG 嵌入**（与 Web 预览同图表语言，
  primary/accent 双色、象限双系列）

### P2 视觉层 + QA 门禁
- 渲染器按 theme.palette 确定性构图层：页背景、标题强调条、指标/卡片圆角容器、
  分隔线、封面居中+色条（8 套咨询风全链路：HTML/PDF/PPTX 一致）
- 溢出保护：每组件前校验剩余版面（>6.4in 截断），高组件按余量收缩
- `slide_manifest.json` 随导出生成（slide 键/组件清单/qa_expectations/
  generation_engine=pptxgenjs/page_execution/image_assets）
- **CyberPPT validate_pptx.py 收编**至 `backend/scripts/pptx_qa/`（MIT，附 LICENSE），
  export-pptx 端点自动执行并回写响应 message：`QA:10页/errors 0/warnings 65`
  （剩余 warnings 均为 agent 工作流产物类提示：blueprint/content-lock/final-merge
  等，0 errors；结构检查含 SHAPE_OUTSIDE_SLIDE 已清零）

### P3 结构化适配（蓝图层预留）
- SKILL 更新：还原链路 = 确定性视觉层（palette+页型）+ ECharts PNG + manifest QA；
  ImageGen 整页蓝图接口预留（未来接图像模型时替换构图层即可）

### 验证
- 实测：10 页 PPTX 含 chart PNG（slide4 象限图 16KB）、卡片内容完整 9/9、
  时间线里程碑 2/2；HTML/PDF 导出正常；QA errors 0
- 测试：platform 55 / agents 2 / backend 56 / tsc+build ✅

---

## 18. PPT 模型分工与 skill 调研（MiniMax + DeepSeek，2026-08）

### MiniMax 分工（已支持，配置即用）
- 平台本就支持 Presentation 专用模型（AGENT_PLATFORM_PRESENTATION_LLM_*）：
  DeepSeek 承接 research/strategy/design/critic，MiniMax 承接 Presentation
  节点与 PPT skill（presentation-cyberppt），零代码改动
- MiniMax OpenAI 兼容端点（官方文档 platform.minimax.io/docs/api-reference/
  text-chat-openai.md）：国内 https://api.minimax.chat/v1、国际
  https://api.minimaxi.com/v1；模型 MiniMax-Text-01 / MiniMax-M2 / abab6.5s-chat；
  JSON 输出由 harness 自愈重试兜底
- 配置与验证步骤见 `agent-platform/docs/ppt-model-routing.md`

### ppt-master-skill 嵌入调研
- **hugohe3/ppt-master（正确调研对象，MIT，47k★）**：AI 演示工作流 Skill，
  核心 = 逐页手写 SVG → svg_to_pptx 编译器导出**原生可编辑 PPTX**
  （DrawingML 形状/真实图表/动画/旁白/公式），模型无关；依赖轻量
  （多数脚本纯标准库），详见 `agent-platform/docs/ppt-master-research.md`
- 结论：主路径 = 自有 presentation-cyberppt skill + MiniMax 分工；
  ppt-master 方法论吸收（SVG 页设计契约/设计系统分层/门禁纪律）免费可行；
  svg_to_pptx 编译器收编作为 export-pptx 的 `--backend svg` 实验模式（P3+，
  DSL 仍是唯一事实源，SVG 为导出中间产物）——不整体替换流水线

---

## 19. hugohe3/ppt-master 嵌入调研（2026-08）

见 `agent-platform/docs/ppt-master-research.md`（§18 曾误引 macrochen/ppt-master-skill，
已更正为 hugohe3/ppt-master）。

要点：
- **MIT ✅ 可嵌入**；47k★、v4.7.0、模型无关、依赖轻量（svg_to_pptx 编译器 239 个 .py）
- 管线：材料 → 事实调研 → 模板确认 → **逐页手写 SVG** → svg_to_pptx 导出
  原生 DrawingML 形状（含真实图表/动画/旁白/公式）
- 与我们架构：**方法论吸收免费可行**（SVG 页设计契约/设计系统分层/门禁纪律）；
  **svg_to_pptx 收编**为 export-pptx `--backend svg` 实验模式（P3+，DSL 唯一事实源）；
  不整体替换流水线（agent 逐页手写 + 用户确认门与自动化冲突）
- MiniMax 分工不变：MiniMax-Text-01 承接 PPT skill 制作（PRESENTATION_LLM_*），
  DeepSeek 主流水线；启用图片阶段时 MiniMax-Image-01 可接其 image_backends

---

## 20. ppt-master 完整吸收 + PPT Design Agent + MiniMax 分工（2026-08）

### 完整吸收（hugohe3/ppt-master，MIT）
- `agents/ppt-design-agent/vendor/ppt-master/`：完整 skill 收编（SKILL.md/
  workflows/scripts 239 个 py/templates 设计系统/references），保留 LICENSE；
  依赖装入 venv：python-pptx/XlsxWriter/PyMuPDF/edge-tts/uharfbuzz（skia-pathops
  可选未装）；已裁剪 references/ai-image-comparison（44MB 对比图，可从上游恢复）

### 框架与过程适配
- 新增独立成员 **PptDesignAgent**（agents/ppt-design-agent/，注册进 agents 包）：
  输入 Presentation DSL → ppt-master 项目（设计规范与内容大纲.md + spec_lock.md
  执行锁）→ **逐页确定性 SVG**（dsl_to_svg.py：1280×720、theme 驱动、原生
  柱/折线/饼/象限图、文本换行防溢出、遵守页设计闭合契约）→ finalize_svg +
  svg_to_pptx → **原生可编辑 PPTX**（DrawingML 形状）
- LangGraph 新节点 `ppt_design`：critic 门后执行（presentation → critic →
  ppt_design → assemble）；节点失败降级（retry → 跳过，不阻塞交付）
- `export-pptx` 优先返回 ppt-master 产物（asset_package.ppt_design.pptx_relative），
  无则回退 PptxGenJS 管线
- 资产包/API 新增 `ppt_design` + `node_models`（节点→模型映射）

### MiniMax 分工（已配置生效）
- key 位置：`QX_product_agent/backend/.env`
  （AGENT_PLATFORM_PRESENTATION_LLM_BASE_URL/MODEL/API_KEY 三行，模板已写入）
- 实测：presentation/ppt_design/critic 走 MiniMax（api.minimax.chat），
  其余节点 DeepSeek；前端 AgentTimeline 显示「模型：xxx」（5 位成员含
  PPT Design Agent）
- **MiniMax 适配修复**：
  - 输出带 `<think>` 推理前缀 → `_extract_json_block` 先剥离 think 块
  - M3 默认开启推理 → 新增 `AGENT_PLATFORM_PRESENTATION_LLM_EXTRA_JSON=
    {"thinking":{"type":"disabled"}}`（官方参数，直出 JSON；LLMClient 支持
    extra_body，配置在 backend/.env）
  - 长文含字面换行/推理中花括号 → `complete_json` strict=False 阶梯 +
    多 `{` 起点尝试
  - 循环内覆盖评估器放宽为结构性检查（MiniMax 会改写表述；逐字覆盖由
    critic 门在确定性注入后把关，避免无限修订）

### 验证
- platform 55 / agents 6（+4 PPT 设计） / backend 56 / tsc+build ✅
- 端到端（MiniMax-M3 分工实测）：DeepSeek 主链 + MiniMax 三节点
  （presentation/critic/ppt_design），node_models 入 API；ppt_design 产出
  10 页 SVG → svg_to_pptx 原生 PPTX（243 文本/377 图形形状，CyberPPT QA
  0 errors）；export-pptx 优先返回原生 PPTX（message 含模型名）

---

## 21. PPT 质量改进 A/B/C 完成（2026-08）

### A 溢出修复 + 图表增强
- dsl_to_svg v2：页面预算器（字号阶梯 1.0→0.9→0.8 → 内容自适应截断 → 溢出
  标记，不再静默丢内容）；换行校准（CJK 全角 1.0em）；表格独立最小缩放
  (0.92) + 行数封顶 + "其余行见报告"；卡片/时间线绘制前余量检查；页脚上移
- 图表库扩展：column/line/pie(donut)/radar/stacked 多系列 + 图例 + 数据标签；
  高度随剩余空间收缩
- 生成侧：cyberppt skill 增加【图表入页规则】；enrich_coverage 确定性注入
  「功能优先级分布」柱状图（真实计数）
- **实测：SHAPE_OUTSIDE_SLIDE 28 → 0；所有页面 max_y ≤ 700**

### B 视觉系统（ppt-master 完整使用）
- 图标系统：chunk-filled 图标内联（组件语义映射，currentColor→实际色值）
- **原生图表 markers**：`data-pptx-replace-with="chart"` + JSON payload +
  EMU bounds → svg_to_pptx `--native-charts-and-tables` 导出**真 PowerPoint
  图表**（实测 2 个 chart parts）
- 版式脚手架：封面 Hero 图槽、标题区配图、页脚页码、章节强调条、封面标题
  36px 两行自适应

### C MiniMax 生图 + 资产库
- 复用 ppt-master `image_gen.py` + `backend_minimax.py`（零自研）：
  backend/.env 配置 IMAGE_BACKEND=minimax / MINIMAX_MODEL=image-01 /
  MINIMAX_API_KEY / MINIMAX_BASE_URL=https://api.minimax.chat
- PptDesignAgent 生图阶段：image_prompts.json（封面 Hero + 每数据页 1 图）
  → 批量生成 → 插入 SVG（Hero 背景/标题区配图）→ finalize 内嵌 → 导出图片
- **资产库**：图片同步落盘 OUTPUT_DIR/assets/{product_id}/；新增
  GET /product/{id}/assets；DesignStudioPage 增加「图片资产库」网格
- 降级：生图失败（无 key/超时）自动跳过，不影响页面生产
- 实测：6 图生成（hero + 5 页，1280×720）、PPTX 嵌入 7 图片对象、
  资产库 API 返回 6 图

### 验证
- QA：errors 0；warnings 仅封面全幅背景类（Hero 设计使然）
- 文本 208 / 图形 433 / 图片 7 / 原生图表 2（vs 上轮 229/470/7/0）
- 测试：platform 55 / agents 6 / backend 56 / tsc+build ✅

---

## 22. ppt-master 完全重构（MiniMax 自由创作）+ 流水线实时进度（2026-08）

### PPT 设计与制作模块重构（放弃前置模板）
- **放弃确定性模板渲染**（dsl_to_svg 已删除）：PptDesignAgent v2 完全遵循
  hugohe3/ppt-master skill 的「Executor 逐页手写 SVG」范式
- **设计规范**：MiniMax（Strategist 角色）自由创作（设计简报/视觉方向/逐页大纲），
  确定性大纲仅作兜底
- **逐页 SVG**：MiniMax 按「页面 DSL + 视觉体系 + skill 硬性规则」逐页创作
  （svg_author.py：构图要求/原生图表 markers/禁用元素），校验（XML 可解析 +
  关键文本归一化匹配 + 越界 ≤715 + 无禁用元素）→ 带错误反馈重试 ×3 →
  极简兜底页（仅保内容不丢）
- **SVG 消毒层**：剔除 svg_to_pptx 不支持的文本属性（dx/dy/style/
  dominant-baseline 等 35+ 项），避免整节点重试
- 保留：MiniMax 生图 + 资产库、spec_lock、finalize、svg_to_pptx
  （--native-charts-and-tables 真图表）

### 流水线实时进度（前端可见当前步骤）
- 后端：StudioProduct 新增 node_status 列（SQLite 迁移已执行）；
  LangGraph 节点边界 progress_callback → 任务实时写库；GET 响应合并
- 前端：AgentTimeline 升级——整体进度条（斜纹流动动画）、「当前步骤」横幅
  （Agent + 说明 + 模型 + 打字动画）、每行步骤流转淡入（key=phase +
  step-fade-in）、运行中行高亮；AgentStatus 加 TypingDots 与相变动画；
  globals.css 新增 step-fade-in/typing-dot/progress-stripes
- 实测：任务运行中 API 实时返回
  {"requirement_parser":"completed",…,"presentation":"running"}

---

## 23. Design Studio v2：任务级「设计思路 + 图片」资产库（2026-08）

### 背景
旧 DesignStudioPage 仅重复展示 UX 设计文本（用户旅程/页面结构/UI 组件规格），
生图与文字分离、不可编辑、不可再生成。v2 重构为**任务级图片资产库**。

### 核心能力
- **结构化存储**：某任务的全部生图按「设计思路（文字）+ 图片」成对入库；
  生图模型返回的文本输出（MiniMax data.text，如有）以 sidecar 保留并展示
- **文字可改、图片可再生成**：任意条目修改附带文字 → 保存 → 按新文字重新生图
- **组件化架构**：组件1 文字+图 / 组件2 文字+图 / … / 组合总图；
  组件或整体文字可分别修改、分别重新生图；组合 prompt 自动聚合全部组件文字
- **保存图片**：单张下载 + 全部打包下载（ZIP）
- **其他优化**：LLM 智能拆解组件建议、版本历史（5 版）回滚、大图预览、
  流水线完成自动导入、旧任务磁盘对账恢复（assets/ + ppt_projects/ manifest）

### 存储与 API
- 资产库：`{OUTPUT_DIR}/design_studio/{product_id}/`（index.json + 图片文件），
  静态服务 `GET /api/v1/files/design_studio/{product_id}/{file}`
- 新路由 `/api/v1/design-studio/*`（见 backend/app/api/v1/endpoints/design_studio.py）：
  GET 资产库（惰性导入）｜POST suggest-components（LLM 拆解）
  ｜POST composite（原子创建 组件+组合）｜POST items（建条目）
  ｜PATCH items/{id}（改文字）｜POST items/{id}/generate（生成/重新生成）
  ｜POST items/{id}/restore（版本回滚）｜DELETE items/{id}｜GET download（ZIP）
- 生图执行：复用 ppt-master image_gen.py（IMAGE_BACKEND=minimax，image-01，
  16:9 / 1K），单图模式（--filename 指定输出名，规避长 prompt 文件名）
- 流水线集成：run_product_studio_pipeline 完成态自动
  import_from_product_package（幂等，失败不阻断完成）

### 兼容性修复（vendor）
- backend_minimax.py：响应 data.text 以 {图片}.txt sidecar 落盘（纯增量）
- workflow_transcript.py：_candidate_directory 对超长参数 stat 增加
  ENAMETOOLONG 保护（单图模式长中文 prompt 触发）
- app/rag/rag_pipeline.py：retrieve_task_context 参数默认值语法修复
  （project_id 移后并给默认值，阻塞后端启动，属他人 WIP 遗留）

---

## 24. 项目资产库：PPT 资产库 → 任务级全资产归档（2026-08）

### 背景
侧边栏「PPT 资产库」仅覆盖 PPTX 单一资产。调整为**项目资产库**：
每个任务（product）的全部资产归档到对应资产库，支持单文件下载与 ZIP 打包下载；
文本资产自动转化为 **PDF / MD** 产出，PPT 仍按现有模式产出（ppt-master 原生 PPTX）。

### 核心能力
- **任务资产库**：`{OUTPUT_DIR}/studio_assets/{product_id}/` 目录 + index.json
  审计索引；路径统一使用带连字符 UUID（与 design_studio 命名一致）
- **文本资产 → MD/PDF**：需求 / 市场研究 / 竞品分析 / 策略与PRD / UX设计 /
  演示文案 / 项目完整文档 结构化序列化为 Markdown（必产），weasyprint 渲染 PDF（尽力）；
  流水线完成态自动产出，历史任务读取资产库时惰性补产（幂等）
- **PPT 现有模式**：复用 ppt-master 原生 PPTX（ppt_projects 对账恢复 +
  磁盘 svg_final 预览），与 P7 恢复逻辑一致
- **聚合归档**：演示导出（PDF/HTML）、design_studio 设计图、编辑器上传素材一并入档
- **下载**：单文件直接走 /api/v1/files 静态地址；打包下载 ZIP 按
  `{任务名}/{类别}/` 分子目录（文档 / 演示文稿 / 设计图片 / 素材）

### 存储与 API
- 新路由 `/api/v1/project-assets`（见 backend/app/api/v1/endpoints/project_assets.py）：
  GET 列表（资产统计）｜GET {product_id}（明细，惰性补产）｜GET {product_id}/download（ZIP）
- 前端：侧边栏「PPT 资产库」→「项目资产库」（/ppt-assets 重定向到 /project-assets），
  ProjectAssetLibraryPage 任务卡片 + 分类资产清单 + 打包/单文件下载
