# QX Product Agent — 全方位产品 / 架构 / Agent / QA 审计报告

> **审计对象**：`~/dev/agents/QX_product_agent`（v1 研究报告引擎 + FastAPI/Celery 后端 + React 前端）+ `~/dev/agents/agent-platform`（v2 Agent 平台层）+ `~/dev/agents/agents`（专业 Agent 层）
> **审计方式**：静态代码审计（约 300+ 文件交叉验证）+ 真实运行时测试（实际启动的服务：后端 `:8000`、前端 Vite `:5173`、Redis、Celery worker，Playwright UI 冒烟）+ 真实 LLM 链路验证（DeepSeek / MiniMax）+ 并发/安全/边界测试 + 竞品范式联网研究
> **审计日期**：2026-08-16
> **方法**：所有问题按 P0（阻止核心使用/安全）→ P1（严重影响核心体验）→ P2（明显影响效率体验）→ P3（优化项）→ P4（未来探索）分级；每个问题附「当前实现 file:line → 为什么是问题 → 用户影响 → 建议方案 → 难度 → 优先级」；报告可直接作为 PM/设计/前后端/Agent 工程师的下一阶段开发输入。

---

## 1. Executive Summary

### 当前产品是什么

QX Product Agent 是一个「AI 产品研究工作台」：用户输入一个产品想法/主题，AI 完成 **市场研究 → 竞品分析 → 策略 → PRD → 设计 → 演示 → PPTX/PDF** 的完整产品资产生成闭环。它由两条产品线组成：

- **v1（研究报告流水线，`/projects/:id/*`）**：Tavily 搜索 → Firecrawl 抓取 → Chroma+BM25 RAG → 逐章撰写 → 16:9 PPT 风格 PDF。特色是**三阶段交互式状态机**（资料审核断点 + 大纲审批断点）、块级编辑、引用溯源、Canvas 幻灯片编辑器。**这是一条真正打磨透、有差异化、可用的产品线。**
- **v2（AI Product Studio，`/workspace` + 8 模块 IA）**：LangGraph 七节点多 Agent 流水线（需求解析→研究→竞品→策略→设计→演示→组装 + Critic 质量门 + ppt_design PPTX 生成），输出结构化资产包。**架构方向正确，但当前处于"半成品 + 有致命 Bug"状态**（详见 §5/§6）。

### 最大优势

1. **v1 的"断点干预 + 块级编辑 + 引用溯源"三位一体**是真实、可用的差异化能力——全网同类工具（Gamma/Beautiful.ai/NotebookLM）都没有"人审资料、人审大纲、逐块可改、每句可溯源"的组合。
2. **v1 RAG 引擎工程质量高**：混合检索（Chroma+BM25+RRF）、引用合并去重、排版引擎、Canvas 编辑器，代码扎实、有测试、有评测脚本。
3. **v2 的架构红线正确**：Markdown-first → JSON Schema + Renderer、Agent 平台层与业务解耦、确定性兜底、结构化资产包——这套骨架符合下一代 AI Product Workspace 的方向。

### 最大问题

1. **【P0 安全】全站无认证 + 上传路径穿越任意文件写入 + 静态目录全量暴露**——`POST /upload-docs` 用 `os.path.join(upload_dir, file.filename)` 直接落盘，实测 `../../../../../../../../../tmp/xxx.txt`（9 级 `../`）成功把任意内容写到 `/tmp`（200 返回）；而所有 API 匿名可访问、监听 `0.0.0.0:8000`，`/api/v1/files` 静态挂载整个 `OUTPUT_DIR`（含用户上传原件、爬取原文、Agent 记忆 JSONL）。**产品化前必须修复，否则等于裸奔。**
2. **【P0 可靠性】产品会"永久卡在 running"**：`PptDesignAgent._run` 引用未定义变量 `brief`（`agents/ppt-design-agent/agent.py:239`）导致 ppt_design 节点**必然失败**；Celery 线程池无法硬超时 + 无看门狗回收 + 45min 超时后重投递整条流水线重跑。实测两个产品卡 running 超 1.5 小时，且新用户创建的报告项目排队被饿死（实测 12 分钟 0 章节写入）。
3. **【P1 能力倒退】v2 的 Research 节点零检索**：搜索工具是死代码，市场数据纯 LLM 编造（无来源 URL、无时效），v1 辛苦建立的检索-溯源底座在 v2 完全丢失。
4. **【P1 产品分裂】两条产品线并存、三套品牌名、两个创建入口**，用户心智模型无法建立。

### 最值得做的三件事

1. **安全与可靠性止血（0-2 周）**：上传路径穿越 + 认证 + 静态目录白名单 + ppt_design `brief` 一行修复 + stale-running 看门狗。
2. **把 v1 的检索-溯源能力注入 v2 Research 节点**（2-4 周）：让 v2 的市场数据有真实来源，这是产品可信度的生命线。
3. **收敛产品线为单一心智模型（4-8 周）**：以 v2 八模块 IA 为主干，v1 降级为"研究报告模板"资产，统一品牌与入口，补齐"资产可编辑可持久化"闭环。

---

## 2. Current Product Map（当前产品地图）

### 2.1 产品定位：宣称 vs 实际

| 宣称（README/prd.md/侧边栏） | 实际（代码与运行验证） | 一致性 |
|---|---|---|
| "AI 产品分析研究智能体，全流程自动化" | v1 是**编排式 RAG 流水线**（固定状态机 + 固定大纲，无自主规划），v2 才有规划/反思 | ❌ 文案自相矛盾（"全流程自动化" vs 核心卖点"断点干预"） |
| "断点干预、块级编辑、多轮迭代" | v1 完全兑现（两个人工断点 + DocumentBlock + Inline AI + Diff） | ✅ 真能力 |
| "v2：四个专业 Agent，七节点 LangGraph 工作流" | 9 节点线性链（含 critic/ppt_design/assemble），LangGraph 只用了条件边 | ⚠️ 部分兑现 |
| "AI Product Studio / 8 模块工作台" | 8 模块 IA 存在，但 Research/PRD/Design/Presentation 四个模块深度不均（Presentation 深、Design 浅、Knowledge 是文档列表、Templates 是静态占位） | ⚠️ 名实有差距 |
| "产品研究 → PRD → 演示" | v2 资产包闭环成立（实测完成产品含 research/strategy/design/presentation/ppt_design 全部资产） | ✅ |

**品牌名三处不一**：prd.md 叫「QX Product Research Agent Workspace」、README 叫「QX Product Research Agent / AI Product Studio」、侧边栏显示「Product Studio · AI 产品研发工作室」+ 工作区「Agent Platform QX」。

### 2.2 实际模块与数据流

```
用户想法/主题
  ├─ v1: POST /api/v1/projects  → 三阶段状态机（PREPARING_DATA → WAITING_FOR_SOURCES
  │     → PREPARING_OUTLINE → WAITING_FOR_OUTLINE → DRAFTING → COMPLETED）
  │     产物：DocumentBlock[] + 16:9 PPT PDF + Canvas 编辑器 + 图片库
  └─ v2: POST /api/v1/product/create → Celery 桥接 → agent-platform LangGraph
        九节点：requirement→research→competitor→strategy→design→presentation→critic→ppt_design→assemble
        产物：asset_package（requirement/research/competitor_analysis/strategy/design/
              presentation/ppt_design/document + critic_score/gate_report）
```

### 2.3 核心用户与 JTBD

- **文档定义**：资深 PM / UX 专家 / 工业设计战略家。
- **实际优化对象**：v1 精准服务于"产品研究者/战略分析师"（输入主题→有溯源的汇报）；v2 试图服务"完整产品团队"（研究/PRD/设计/演示），但 Design/Knowledge/Templates 深度不足——**纵向有深度的产品被横向模块稀释**。
- **核心 JTBD**："当我要为一个新想法准备商业级研究汇报时，以最低人工成本获得**有据可查、可编辑、可迭代**的研究报告与演示材料，而不是黑盒静态文档。" —— v1 完整支持，v2 支持闭环但事实底座缺失。

---

## 3. Current User Journey（真实用户旅程实测）

以下旅程全部在**真实运行环境**（真实 LLM、真实搜索）中执行验证。

### Journey A：第一次使用（v2 Studio 主路径）

| 步骤 | 结果 | 观察 |
|---|---|---|
| 打开首页 `/` | ✅ 2.3s 加载 | 控制台页（旧线）——新用户默认落在 `/workspace`（通配符重定向） |
| 理解产品 | ⚠️ | 英文 Hero「Describe the product you want to build」+ 中文副文案，中英混排；8 模块侧边栏信息过载；品牌名混用 |
| 创建产品 | ✅ | 输入想法 → Generate → `201 queued`，节点进度条开始推进 |
| 等待 AI 输出 | ⚠️ | 节点级进度（requirement_parser→research→…）清晰，但**工具调用是硬编码的模拟展示**（ToolExecution.tsx 的 TOOL_POOL 与后端无关）；无"正在搜索什么/读到什么"的真实过程 |
| 查看资产 | ✅ | 完成后四资产卡（Research/PRD/Design/Presentation）+ 演示渲染 |
| 修改结果 | ❌ | 资产卡**无编辑入口**（Presentation 可进 GrapesJS 编辑器；Research/PRD/Design 只能看）；资产无版本 |
| 保存/返回 | ⚠️ | 产品无删除/重命名；"最近产品"仅胶囊按钮；刷新后靠"最近产品"恢复 |

### Journey B：Product Research（v1 报告流水线，实测全链路）

| 步骤 | 结果 | 观察 |
|---|---|---|
| 创建项目「宠物智能喂食器市场调研」 | ✅ | `201`，状态 `preparing_data`，Celery 任务提交 |
| 搜索资料 | ✅ | Tavily 返回 5 条，`WAITING_FOR_SOURCES` 断点 |
| 审核资料 | ✅ | `POST /review-sources` → `preparing_outline`；**资料标题是"资料 1..5"占位名**，无摘要/来源站点信息，用户无法判断资料价值 |
| 生成大纲 | ✅ | 大纲质量高（5+ 章节、结构专业）；用户可修改后提交（实测追加自定义章节成功） |
| 审批大纲 | ✅ | `POST /approve-outline` → `drafting`，9 个章节 |
| 逐章撰写 | ⚠️ | SSE 正常（placeholders + heartbeat + section_chunk），但**实测 12 分钟 0 章节写入**——worker 被其他卡死任务占满（队列饥饿） |
| 保存/继续 | ⚠️ | 大纲/资料断点持久化正常；但无"放弃项目"概念，2 个项目已等用户审核超过 1 个月（无超时提醒） |

### Journey C：Research → PRD（v2）

- ✅ Research 结果**通过 LangGraph state 传递**进 strategy/PRD（数据流链路通，代码验证）。
- ❌ **Requirement Parser 的产出（goals/target_users/constraints/success_metrics）从未被下游消费**（research 节点只用 idea）——用户输入的需求细节白费。
- ❌ v2 Research 无检索无来源，PRD 建立在编造数据上。
- ⚠️ PRD 可读不可编辑、不可局部修改、无版本。

### Journey D：PRD → Design（v2）

- ✅ strategy/design 数据流连贯（personas/features/roadmap → user_flow/pages/components）。
- ⚠️ Design 产出是"规格展示"，无设计工具闭环、不可编辑、不可从设计反哺 PRD。
- ⚠️ 上下文截断策略会把中间产物 JSON 整块截断（`harness/context.py:62-67`），大资产包时设计/演示节点可能读到残缺数据。

### Journey E：Research → Presentation（v2）

- ✅ presentation 节点产出 11 页 Slide JSON + 主题系统；SlideRenderer/PDF 导出正常（实测 11 页 0 溢出）。
- ✅ GrapesJS 编辑器 + `PATCH /presentation` 回写正常（实测 200 + 读回验证）。
- ✅ ppt_design 可产出 PPTX（此前完成的产品含 `*_native_charts_tables.pptx`）。
- ❌ **当前代码下 ppt_design 必然失败**（`brief` NameError），重复尝试每次白烧 20-90 分钟。
- ⚠️ Presentation 页渲染时控制台报大量**重复 React key 警告**（`components.tsx:325`）。

### Journey F：长任务（5-15 分钟 Agent Task）

| 能力 | 实测/代码验证结果 |
|---|---|
| Streaming | v1 SSE 正常（但为 2s 轮询伪 SSE，10 分钟硬上限，不检测断连）；v2 **无 SSE**，纯轮询节点状态 |
| Progress | v2 节点级布尔进度 + 硬编码工具展示；无中间产物、无工具参数 |
| 取消 | ❌ 无取消 API；前端无停止按钮 |
| 重试 | ❌ 无重试 API；失败产品只能重建 |
| 页面刷新 | ⚠️ v2 轮询可恢复；v1 状态轮询可恢复 |
| 浏览器关闭 | ✅ 后端任务继续（Celery）；但完成后无通知机制 |
| 网络中断 | ⚠️ SSE 无重连语义 |
| **任务卡死** | ❌ **无看门狗**：worker 崩溃/超时后产品永久 running（实测 1 个产品卡 running 8h+、1 个 queued 2 天） |

**结论：v1 具备"Agent 应用"运行体验（断点+SSE+轮询恢复），v2 仍停留在"同步 Web App + 后台批处理"层面，且缺取消/重试/看门狗三大件。**

---

## 4. Major UX Problems（P0–P4 分级）

> 完整问题库见附录 B（UX Issue Matrix）。此处列 Top 问题，每条含"当前实现 → 用户影响 → 建议"。

### P0（阻止核心使用/安全）

| # | 问题 | 证据 | 建议 |
|---|---|---|---|
| 1 | **上传任意文件写入（路径穿越）** | `projects.py:428` `os.path.join(upload_dir, file.filename)`；**实测 9 级 `../` 成功写 /tmp** | `Path(file.filename).name` + 扩展名白名单 + 大小上限 + 解析失败删文件 |
| 2 | **全站无认证，项目列表返回全库数据** | `projects.py:937-942` 无 owner 过滤；`main.py:94-108` 硬造 demo 用户；OpenAPI 无 security scheme | JWT + 按 `owner_id` 过滤所有端点 |
| 3 | **`/api/v1/files` 静态挂载整个 OUTPUT_DIR** | `main.py:151`；目录内含用户上传 PDF、`crawled_data_*.json` 爬取原文、`studio_memory/*.jsonl` Agent 记忆 | 只挂公开白名单子目录；敏感产物移出静态根 |
| 4 | **产品永久卡 running，无回收** | `product_studio_tasks.py:122-216` 无看门狗；实测 8h+ 卡死 | 启动探活 + 定时 watchdog + 超时置 failed |
| 5 | **Canvas 编辑器永不保存** | CanvasSlideEditor 无保存 API；store 无 persist；实测刷新即清空 | localStorage/IndexedDB 持久化或后端保存端点 |

### P1（严重影响核心体验）

| # | 问题 | 证据 | 建议 |
|---|---|---|---|
| 1 | ppt_design `brief` NameError，节点必败 | `agents/ppt-design-agent/agent.py:239`（**已逐行验证**） | 一行修复 + 删死函数 + 补单测 |
| 2 | v2 Research 零检索，数据纯编造 | `research-agent/agent.py:34-49`；`tools/search_tools.py` 死代码 | 接入 WebSearchTool，强制 source URL |
| 3 | 队列饥饿：长任务占满 4 线程 worker | **实测**：新报告项目 12 分钟 0 章节写入 | 任务级超时 + prefork 池 + 队列分离 |
| 4 | 双产品线/双入口/三品牌名 | App.tsx + Sidebar + DashboardPage 文案 | 收敛为单一 IA |
| 5 | 重复提交无幂等：5 次并发创建 = 5 条流水线 | **实测** 5 个重复产品全部 queued | 幂等键/前端防抖 |
| 6 | 空输入校验失效："  " 主题/空 idea 照常触发流水线 | **实测** 创建成功且 queued | `strip()` + 语义校验 |
| 7 | 4MB 单 chunk 前端包 | 实测 `index-*.js = 4,010,213 B` | 路由级 lazy + echarts 按需 |
| 8 | 状态-任务非原子：先 commit 后 delay() | `projects.py:367-370,600-603` | 先投递后提交 |
| 9 | 超时被吞：SoftTimeLimitExceeded 被 except Exception 捕获变重试 | `product_research_graph.py:96-113` | 先放行 `(Retry, SoftTimeLimitExceeded)` |
| 10 | ORM 与 Alembic 迁移漂移 | `models/task.py` vs `alembic/versions/0001` | 重建基线迁移 |

### P2（明显影响效率/体验）——节选

- 无 ErrorBoundary，页面异常整站白屏；~1,900 行死代码（含整套划词改写 UI、SSE hooks）
- 三套数据获取范式（React Query / setInterval / fetch）；`useProjectLogs` 跨项目日志泄漏；completed 项目无限 5s 轮询
- AI 进度为"模拟展示"（硬编码 TOOL_POOL / 轮播文案），与真实执行脱节
- 编辑体验残缺：划词改写（InlineAIBubble）整套是死代码；AI 面板无停止/重试；插入画布位置硬编码
- 上传无大小/类型限制（实测 50MB 接受落盘后 422，孤儿文件残留）；logo 允许 SVG 同源托管（存储型 XSS 风险）
- 空/错误状态覆盖不均：KnowledgePage 失败静默 `[]`；ProductAssetBrowser N+1（一次挂载 100+ 并发请求）
- 39 处硬编码品牌色与 CSS token 冲突；三套视觉语言并存
- `editor.py:328` 测试钩子残留：消息含 "test" 强制触发 RAG
- SSE：v1 伪 SSE（轮询+10min 上限+不断连检测）；v2 无流式
- 异步端点内同步阻塞调用（LLM/Chroma/WeasyPrint/embedding 直调，阻塞事件循环）
- 可访问性：伪复选框、嵌套交互、无 skip link、无 aria-live

### P3（优化项）——节选

- 死页面 ReportPage 无导航入口；控制台 `/` 无侧边栏入口；通配符静默重定向无 404
- Header「服务正常」硬编码假状态（**实测**后端各页均显示"服务正常"）
- 内部异常原文回显（`str(exc)` 直出到响应）
- `types/index.ts` 第 7 行 `// @ts-nocheck`
- 大纲解析三份重复实现；三套图片组件/上传组件
- Test 钩子、`_PROGRESS_SNAPSHOT` 内存泄漏、progress 状态抖动

---

## 5. Agent Experience Problems（Agent 体验专项）

> 核心判断：**当前 v2 的 AI 交互是"带进度条的批处理"，不是"可协作的 Agent"；v1 的 Agent 体验反而更真实（终端日志、断点、SSE）。**

### 5.1 Agent 是否拥有真正的状态

- **Task State**：✅ 节点级 `node_status` + 错误字典存在且真实。
- **Memory**：❌ **只写不读**——`AgentLoop._remember` 把每轮产物追加到 FileMemoryStore JSONL（无限增长），全仓库无 `recent()/search()` 调用点；"上游结论被下游复用"实际靠 LangGraph state dict，记忆层零贡献。
- **Project Context**：⚠️ state 传递链路通，但 Requirement 节点产出（goals/constraints/指标）不被消费；上下文截断可截坏 JSON。
- **User Preferences / Previous Results**：❌ 不存在（无跨产品/跨会话记忆）。
- **结论**：Agent 知道"当前节点做什么"，但不知道"用户是谁、偏好什么、之前迭代过什么"。用户仍需要重复解释信息——正是 Memory Architecture 缺失的直接后果。

### 5.2 Agent 是否能够持续工作

- 长任务：❌ 45min 超时后整链重跑（MemorySaver 是进程内内存，重启即失）。
- 多步骤：✅ 节点链可跑通（正常产品 ~7 分钟）。
- 多轮：❌ 无人工介入通道（断点只存在于 v1）。
- 中断/恢复：❌ checkpoint 是"摆设"（无 `get_state/update_state` 恢复路径）。
- 失败恢复：⚠️ 节点失败"降级继续"，但**不检查上游依赖**——research 失败后 strategy/design 在无事实底座下继续生成，却标记 completed。

### 5.3 Human-in-the-loop

- 现状：v1 有 2 个人工断点（资料/大纲）；v2 零人工介入。
- 建议：把人工门从"固定 2 个"升级为**可配置的节点级 Plan/Act 批准**（对齐 Cursor Plan Mode 范式）——每节点产物先预览、人确认再进下一节点；对研究/PRD 这类高信任节点默认开启。

### 5.4 AI Control / User Control

- ❌ 无局部 regenerate、无锁定、无版本、无 undo（资产层面）、无 compare。
- ⚠️ v1 编辑器有 Diff 视图 + 撤销（zundo 50 步），但 Inline AI 划词改写是死代码。
- ⚠️ `PATCH /presentation` 直接覆盖（无版本）。
- **控制权失衡**：AI 生成时用户零介入；生成后用户只能"看"（除 Presentation 外）。

### 5.5 质量门（Critic）形同虚设

- Critic LLM 失败时**降级为 score=100 直接通过**（`critic-agent/agent.py:63-73`）。
- `_build_document(state)` 构建的 document **不写回 state**，Critic 评审拿不到事实依据（读到 None）。
- 覆盖度匹配用"前 6 字子串"启发式（`quality_gate.py:146-151`），误判催生了 `enforce_coverage` 确定性注入——**门禁在给模型擦屁股**。
- 实测完成产品 critic_score=62，但用户界面把 Critic 作为"评审通过"徽标展示——**信任幻觉**。

---

## 6. Architecture Problems（架构审计）

### 6.1 Frontend

| 问题 | 证据 | 严重级 |
|---|---|---|
| 4MB 单 chunk，无代码分割，echarts 全量 + 与 recharts 并存 + pptxgenjs 无效依赖 | 实测 `dist/assets/index-*.js` 4,010,213 B；`EChart.tsx:7` | P1 |
| 巨型组件：CanvasSlideEditor 1811 行、dataTransform 3127 行 | 两个文件占编辑器全部逻辑 | P2 |
| 无 ErrorBoundary / 无路由级 lazy | 全库 grep 零命中 | P2 |
| 数据层三范式并存（RQ/setInterval/fetch）；`useProjectLogs` 跨项目泄漏；completed 无限轮询 | `useProjectLogs.ts:31-34`、`useProjectStatus.ts:157` | P1 |
| ~1,900 行死代码（BlockEditor/InlineAIBubble/DiffViewNode/useDraftStream/useEditorSync） | 逐一验证零引用 | P2 |
| 同一功能 2-3 套实现（图片 3 套、上传 3 套、大纲解析 3 份） | ImageGallery/ImageSearch/ProductImageLibrary… | P2 |
| AI 展示为模拟进度（硬编码 TOOL_POOL、5 条轮播文案） | `ToolExecution.tsx:9-27`、`StreamingMessage.tsx:7-13` | P2 |
| N+1：ProductAssetBrowser 对每个 completed 产品并发 get() | `ProductAssetBrowser.tsx:33-38` | P2 |
| EditorPage 只渲染初始 blocks 快照，流式更新失效 | `EditorPage.tsx:317` | P1 |
| 39 处硬编码品牌色 + globals.css 亮蓝冲突 + 三套视觉语言 | 全库 + `globals.css:141-149` | P2 |

### 6.2 Backend / API

| 问题 | 证据 | 严重级 |
|---|---|---|
| 无认证 + 全库列表 + 静态目录全暴露 | §4-P0 | P0 |
| 状态机无集中校验（直接赋值 status），非法迁移无拦截 | `projects.py:364,541`、`report_workflow.py:111,127,...` | P0 |
| 交互端点无原子性（读-改-提交四步无 CAS），并发双触发 | `projects.py:314-378,478-614` | P0 |
| 卡死无回收（无看门狗、fix 脚本需手动） | `product_studio_tasks.py`；`fix_stuck_projects.py` | P0 |
| 线程池无法硬超时 + 超时异常被吞 → 超时变重试 | `start_all.sh:117-118`（`--pool=threads`） | P1 |
| Retry/SoftTimeLimitExceeded 被 catch-all 吞 → 幽灵重试 + 重复章节 INSERT | `writing_tasks.py:179-182`、`report_workflow.py:309-315`、`project_repo.py:327-336` | P1 |
| ORM ↔ Alembic 迁移漂移（列缺失、Enum 不一致、3 张表无迁移）+ create_all 治标 | `models/task.py` vs `alembic/versions/0001` | P1 |
| async 端点内同步阻塞（LLM/Chroma/WeasyPrint/DDG） | `editor.py:147,331`、`projects.py:438,1134,1280` | P1 |
| SQLite 无 busy_timeout；SSE 长连接持有会话 | `database.py:40-47`、`projects.py:630-757` | P2 |
| 错误响应泄漏内部异常、无错误码体系（"重构验证中断"无代码来源，为手工注入） | `main.py:159-165` | P2 |
| 测试缺口：Celery 任务/并发/SSE/上传/认证/看门狗全无覆盖；conftest 依赖真实 .env | `tests/conftest.py:31,57` | P2 |

### 6.3 Agent / 平台层

| 问题 | 证据 | 严重级 |
|---|---|---|
| ppt_design `brief` NameError（节点必败） | `ppt-design-agent/agent.py:239` | P0 |
| `run_pipeline` 传参崩溃 + `build_product_research_graph` 静默丢 ppt_design_agent | `product_research_graph.py:505-536,485-502` | P1 |
| LangGraph 只用了线性链 + 1 条件边；checkpoint 无恢复路径 | `product_research_graph.py:57-65,429-437` | P1 |
| 降级继续不检查上游依赖 → 无事实底座下游照常 completed | `product_research_graph.py:110-113` | P1 |
| Memory 只写不读；JSONL 无限增长 | `agent_loop.py:129-133`、`memory_store.py:56-89` | P1 |
| Planner 是装饰品（多花一次 LLM 调用，计划不驱动执行） | `agent_loop.py:94-100`、`planner.py:35-54` | P2 |
| 评估器过弱（列表可为空）；`Component.data` 自由 dict 无 per-type 契约 | `agent_loop.py:39-49`、`schemas/presentation.py:125-133` | P1/P2 |
| 整节点重试捆绑昂贵副作用（生图 900s + 逐页 SVG ×3） | `product_research_graph.py:96-113`、`agent.py:387-396` | P1 |
| 上下文截断按字符串腰斩 JSON | `harness/context.py:62-67` | P2 |
| `node_models` 与实际调用模型不一致（critic 标 MiniMax 实走 DeepSeek） | `product_research_graph.py:161-179` | P1 |
| 测试全 FakeLLM + 完美数据，掩盖全部 P0/P1 | `testing.py:14-47` | P1 |

### 6.4 Memory / Context Architecture

- **三层记忆现状**：Global Memory ❌（无）；Project Memory ⚠️（LangGraph state + 只写不读的 FileMemoryStore）；Task Context ⚠️（node_status + 可能被截断的产物 JSON）。
- **三者混淆**：没有分层。用户偏好、产品历史、任务中间态全部不存在或混在 state 里。
- **改造方案**（§11.2 架构图）：Memory 分层 —— Global（用户偏好，可写 API）/ Project（产品上下文 + 决策日志 + 资产版本）/ Task（节点产物 + 工具调用）。记忆必须可读可检索（`recent(namespace)` 注入 context），并设容量上限。

### 6.5 Knowledge Architecture

- **v1**：Chroma per-project 隔离 ✅ + BM25 ✅ + RRF ✅ + 引用溯源 ✅（URL 合并去重、chunk 级去重）——**这是产品最值钱的部分**。问题：只爬前 3 个 URL（覆盖率低）；Chroma 无 ID 去重（重复构建累积重复向量）；BM25 每次全量重建；无新鲜度元数据；embedding 模型非单例（`retriever.py:41`）。
- **v2**：❌ **无知识系统**。WebSearchTool/DocumentTool 全为死代码；`/knowledge` 页只是文档列表。
- **判定**：v1 是"Agent 可用的知识系统"，v2 退化为"文件仓库"。

### 6.6 Artifact Architecture

- v1：DocumentBlock 原子块 ✅ 可编辑 ✅ 引用 ✅；无版本 ❌ 无 diff（编辑器有 zundo 但资产无版本）。
- v2：结构化 asset_package ✅ Pydantic 校验 ✅；但**无版本/无局部编辑/无 diff/无 rollback/provenance 仅部分**（presentation 覆盖式 PATCH）；Canvas 编辑永不持久化（P0）。
- **判定**：AI 输出是"一次性文本 + 只读资产"，还不是"可持续编辑对象"。

---

### 6.6 AI Model Strategy Audit

| 项 | 现状 | 问题 |
|---|---|---|
| 使用的模型 | 主链 DeepSeek（`get_llm_client`）+ Presentation/PPT 专用 MiniMax（`get_presentation_llm_client`）+ 可选 SiliconFlow 生图 | 两固定客户端，无分层路由 |
| Model Routing | ❌ 无 Router；`_resolve_node_models` 只是把名字写进展示 dict | 前端展示的"模型分工"与实际调用不符：**critic 标注 MiniMax 实际走 DeepSeek**（`product_research_graph.py:161-179` vs `critic-agent/agent.py:40`） |
| Fast/Smart 分层 | ❌ 无 | 所有节点同一模型，无成本/质量分层 |
| Cost 控制 | ❌ 无 token 统计、无预算、无速率限制；重试全额重发；Planner 每次白烧一次调用 | 流水线成本不可控（SVG 创作 16 页 × 3 次重试 × 8k tokens 失败成本极高） |
| Embedding / Vision / Search 模型 | v1 用 BAAI/bge-small-zh-v1.5（✅）；v2 无检索模型 | v2 检索归零（§6.5） |
| 超时/重试 | client 有 JSON 提取宽松兜底（✅ 亮点）；网络重试依赖 harness 层 | 超时异常被吞（§6.3） |

**建议的 Model Router 架构**（§11.1 已绘入）：

```
Task → Model Router（按节点类型 + 预算）
  ├─ Fast（DeepSeek-chat / Qwen-turbo）：requirement、research 摘要、简单改写
  ├─ Reasoning（DeepSeek-reasoner）：strategy、PRD、质量门评审
  ├─ Vision/Multimodal（SiliconFlow/图片模型）：生图、图片理解
  ├─ Presentation（MiniMax）：SVG 创作、演示文案
  └─ Embedding（bge-small-zh-v1.5）：知识库检索
统一 usage 统计 + 每任务 token 预算 + 超预算降级（Fast 代替 Reasoning）
```

### 6.7 Performance Audit

| 环节 | 实测/代码证据 | 判定 |
|---|---|---|
| 前端首屏 | 8 个页面 0.8–2.3s 加载（本地 Vite） | ✅ 可接受；但 4MB 单 JS chunk 在慢网下白屏数秒 |
| 前端包体 | `index-*.js = 4,010,213 B`；echarts 全量 + recharts 并存 + html2canvas/jspdf/konva/grapesjs 全在主包 | ❌ P1 |
| 页面切换 | SPA 路由切换快；无 lazy | ⚠️ |
| AI 首 Token | editor chat SSE 首 token ~2-5s（实测） | ✅ |
| 长任务 | v2 正常 ~7min（403-430s）；含重试可达 27min/节点、45min 被硬杀重跑 | ❌ P1 |
| 上传 | 50MB 无上限全量读内存/落盘 | ❌ P1 |
| 多文档检索 | BM25 每次全量重建（`retriever.py:222-228`）、embedding 非单例 | ⚠️ P2 |
| 高并发 | async 端点内同步阻塞（LLM/Chroma/WeasyPrint/DDG）→ 事件循环卡死；SQLite 无 busy_timeout | ❌ P1 |
| N+1 | ProductAssetBrowser 一次挂载 100+ 并发 get() | ❌ P2 |
| 轮询风暴 | completed 项目无限 5s blocks 轮询 + 3s status + 2s logs 同页三路 | ❌ P1 |
| 长文本渲染 | PresentationViewer 全页缩略图重复实例化图表 | ⚠️ P3 |
| 数据库 | SQLite 单写者；迁移链漂移；无分页 total | ⚠️ |

## 7. Missing Capabilities（缺失能力）

按"解决什么用户问题、为什么属于本产品"排序：

| 能力 | 解决的用户问题 | 优先级 |
|---|---|---|
| **v2 接入真实检索（来源可溯）** | 市场数据可信度 | P0 |
| 任务取消/重试 API + 前端停止按钮 | 等待焦虑、浪费成本 | P0 |
| stale-running 看门狗 + 失败原因展示 | 卡死不可恢复 | P0 |
| 资产持久化/版本/局部 regenerate | 结果不可改不可回滚 | P1 |
| 记忆闭环（读回注入） | 重复解释信息 | P1 |
| 产品/项目管理（删除、重命名、归档） | 垃圾数据堆积（实测无删除 API） | P1 |
| 运行中进度真实化（工具调用/中间产物/日志流） | 信任与可诊断性 | P1 |
| 空输入校验 + 幂等（防重复提交） | 误操作成本 | P1 |
| 完成通知（任务完成/失败推送） | 长任务等待 | P2 |
| 模板中心真实化（复用 TEMPLATE_OPTIONS） | 模板名不副实 | P2 |
| Knowledge Base → AI 可查询记忆（自动标签/聚类） | 知识复用 | P2 |
| 协作/分享（链接分享资产） | 团队工作流 | P3 |

## 8. Redundant / Unnecessary Capabilities（应删除/合并）

| 项 | 理由 | 动作 |
|---|---|---|
| v1 旧工作台双入口（`/` 控制台 + `/workspace`） | 心智分裂 | 合并：v1 降级为"研究报告模板"资产，入口收敛 |
| `run_full_report_workflow`（绕过断点的全自动任务） | 破坏交互式状态机设计，无调用方 | 删除 |
| `render_tasks.py` 的 build_report_markdown/generate_pdf_report | 新工作流已切断，无调用方 | 删除 |
| `useDraftStream`/`useEditorSync`/BlockEditor/InlineAIBubble/DiffViewNode | 1,900 行死代码，或复活划词改写（推荐复活 Inline AI） | 删除或复活 |
| `PromptManager`、`WebSearchTool`/`ToolRegistry`/`DocumentTool`（未接入） | 死代码 | 接入或删除（推荐接入检索工具） |
| 前端 pptxgenjs 依赖 | 从未 import | 删除 |
| echarts（若保留 recharts）或 recharts 其一 | 双图表库 | 二选一 |
| `Agent_Platform_QX/` 旧快照目录（10MB+） | 重复/易误导入 | 删除 |
| v1 遗留 `client01.py`/`section_writer01.py`/`pdf_generator01.py`/`test_ddg.py` | 旧版副本 | 删除 |
| Header「服务正常」假状态 | 误导用户 | 接 `/health` 或移除 |
| Templates 静态占位页 | 名不副实 | 做成真模板中心或隐藏 |
| DashboardPage "AI 产品研发请前往 Product Workspace" 分流文案 | 双入口证据 | 随产品线收敛删除 |

---

## 9. Proposed Information Architecture（下一代信息架构）

以「**单一产品线 = AI Product Studio**」为前提重构（不套用模板，基于本产品实际资产结构设计）：

```
QX Product Studio（统一品牌：去掉三套名字）
│
├── 工作台 Home（默认落地页）
│   ├── 一个想法输入框（主 CTA）
│   ├── 进行中任务（可取消/可查看进度/失败可重试）
│   └── 最近产品（卡片：状态、更新时间、一键进入资产）
│
├── 产品空间（每个产品的完整生命周期，替代 8 个平行模块）
│   ├── 概览 Overview（进度 + 关键指标 + 决策日志）
│   ├── 研究 Research（市场/竞品/画像，来源可溯、可局部重生成）
│   ├── 资产 Artifacts
│   │   ├── PRD（结构化，可编辑，版本历史）
│   │   ├── Design（规格 + 画布）
│   │   └── Presentation（Slide JSON + 编辑器 + PPTX/PDF 导出）
│   ├── 知识 Knowledge（项目级：上传文档、检索来源、引用库）
│   └── 任务 Tasks（历史执行记录 + 日志 + 重试入口）
│
├── 模板 Templates（真实可用的模板中心：研究/PRD/演示模板）
│
└── 设置 Settings（模型配置、API Key、工作区）

旧 v1 报告：作为"研究报告模板"模板化能力并入产品空间，不再单列入口。
```

关键设计原则：
1. **产品是唯一容器**，研究/PRD/设计/演示是产品内的资产页，不是平行模块（当前 8 模块并列是最大 IA 问题）。
2. **任务与资产分离**：任务（执行历史）归"Tasks"，产物归"Artifacts"，状态永不混在资产页。
3. **当前上下文永远可见**：任何页面顶部显示"当前产品 + 当前阶段"（面包屑），解决用户"我在哪、当前上下文是什么"问题。

## 10. Proposed Interaction Model（核心交互模型）

```
用户意图（想法输入 / 对资产的一句话修改）
    ↓
Agent（计划 → 执行 → 质量门 → 产出）
    ↓
Context（产品上下文 + 记忆 + 知识库，自动继承，无需重复输入）
    ↓
Artifact（结构化资产，随生成随渲染，可局部编辑/重生成/版本化）
    ↓
用户审阅（节点级 Plan/Act 门：研究结论、PRD、演示逐层确认）
    ↓
迭代（"改第 3 页竞品数据" → 局部重生成 → diff 对比 → 确认）
    ↓
交付（PDF/PPTX/分享链接）
```

**Chat / Canvas / Artifact / Task / Workspace 五者组合方式**：
- **Chat 是命令入口**（"研究一下睡眠市场""把 PRD 补一章"），不是主界面。
- **Artifact 是主工作对象**（Claude Artifacts 范式）：资产卡即工作区，就地编辑 + 就地对话修改。
- **Canvas 只用于演示编辑**（Konva/GrapesJS），不承载文档。
- **Task 是透明的执行记录**（Manus 范式：真实工具调用、中间产物、失败原因），不是进度条。
- **Workspace 是产品容器**（NotebookLM 范式：项目 = 知识边界）。

## 11. Proposed Architecture（下一阶段推荐架构）

### 11.1 执行链改造

```
User → Frontend（React Query 统一数据层 + SSE/EventSource）
  → API（FastAPI，加 JWT 认证层 + 统一错误码）
  → Celery（prefork 池 + 任务级超时 + 队列分离 studio/report）
  → Agent Runtime（LangGraph 或普通编排二选一：若保留则启用 checkpoint 恢复 +
     真实工具调用事件流；节点级 Plan/Act 门）
  → Tools（WebSearch/Document/RAG 注入 —— 把 v1 检索能力以工具接口迁入）
  → Memory（Global/Project/Task 三层，可读可检索，容量上限）
  → LLM（Model Router：Fast=DeepSeek-chat / Reasoning=DeepSeek-reasoner /
     Vision=SiliconFlow / Presentation=MiniMax，统一 usage 统计与成本预算）
  → Artifact（版本化资产存储 + diff + rollback）
  → Frontend（真实进度流 + 资产渲染）
```

### 11.2 三个必须立即可做的架构动作

1. **可靠性**：Celery `--pool=prefork`（让硬超时生效）+ 每任务显式 `soft_time_limit` + 启动探活把 stale running 置 failed + 任务开头幂等检查（DB 已终态直接返回）。
2. **安全**：认证中间件（JWT）+ 上传白名单（`Path(name).name` + 类型/大小 + 失败清理）+ 静态目录白名单。
3. **事实底座**：`WebSearchTool` 接入 ResearchAgent（多查询 → 结果摘要入 context → 强制 source URL + 引用编号），并把 v1 `app/rag` 的 Chroma/BM25 检索封装为平台工具（MIGRATION 已有此计划，落地即可）。

### 11.3 Memory Architecture 具体方案

```
Global Memory（用户级 JSONL/DB）：写作风格、常用技术栈、行业偏好 —— 可写 API + 注入 system prompt
Project Memory（每产品目录）：product_context.md（目标/用户/决策日志）+ assets 版本 + citations
Task Context（进程内 + DB）：节点产物 + 工具调用记录（供前端真实进度）
闭环：AgentLoop.run 前注入 recent(namespace, k=5)；每条记忆带 created_at + 类型；容量上限（如 500 条/产品）
```

## 12. Design System Recommendations

当前视觉判断：新线"纸感/复古/呼吸感"方向（bg-paper、font-editorial、米色卡）是**有意识的、正确的差异化**（对齐"断点干预、克制、专业"的产品气质），但未形成系统。具体规则：

| 维度 | 规则 | 当前差距 |
|---|---|---|
| 颜色 | 语义化 token：`primary`（深蓝 #24415E 系）/`accent`（陶土 #C87E4F）/`success`（松绿 #3F6B4F）/`info/warning/danger`；深色模式 token 完备后再开放切换 | 39 处硬编码色 + globals.css 亮蓝冲突；三套视觉语言并存（纸感 / blue-amber-emerald 状态色 / slate-indigo 演示） |
| Typography | 标题 font-editorial + 正文系统字体；层级仅 4 级（H1/H2/H3/body）；所有 AI 状态文案统一字号 | index.html title 过时；中英混排 |
| Spacing | 4pt 网格；页面 24/32px 基准间距；卡片 16px padding | 各组件 padding 不一致 |
| 组件 | Button/Card/Badge/Empty 状态统一收编 common/；Loading 用骨架屏替代 spinner 轮播 | 三套按钮/卡片风格 |
| Motion | 仅 150-200ms ease 过渡；AI 流式用打字光标，不用轮播动画 | StreamingMessage 轮播文案 |
| AI 状态 | 统一"三态"：`thinking`（骨架+当前动作文案）/`working`（真实工具调用列表）/`done`（资产卡）；`aria-live` 播报 | 模拟进度需替换为真实事件 |
| 空状态 | 统一"图标 + 一句话 + 一个 CTA 按钮"三元组 | ProductAssetBrowser 空态无 CTA |

## 13. Competitive Benchmark（竞品差距）

| 维度 | 行业最佳范式 | QX 现状 | 差距 |
|---|---|---|---|
| Agent UX | 执行过程可见 + 运行中可接管（Manus）；Plan/Act（Cursor） | 固定节点进度 + 模拟工具展示 | 大（§5） |
| Artifact 编辑 | 生成物就地编辑 + 分屏迭代（Claude Artifacts/Gamma） | 资产只读（除 Presentation） | 大 |
| 来源信任 | 无引用不回答（NotebookLM） | v1 强、v2 无 | 中（v2 是倒退） |
| Workspace | 笔记本=项目边界（NotebookLM）；极简密度（Linear） | 8 模块并列 + 双产品线 | 中 |
| 演示生成 | 主题即时切换 + 生成后编辑（Gamma）；智能排版（Beautiful.ai） | DSL + GrapesJS + 主题切换已实现 | 小（方向正确） |
| 任务恢复 | 断点续跑、失败重试（Cursor/Manus） | 无取消/重试/看门狗 | 大 |

**明确不借鉴**：Manus 全自主无人值守（与断点干预哲学冲突）；Notion 通用化（垂直工具）；Beautiful.ai 模板中心化（内容先于设计的 DSL 路线更稳）；v0/Lovable 的 vibe 速度文化（研究产品以准确性与溯源为生命线）。
**借鉴优先级**：① NotebookLM 强制引用扩展到所有 AI 交互；② Cursor 节点级 Plan/Act；③ Manus 执行中接管与真实进度；④ Claude Artifacts 资产就地编辑；⑤ Linear 状态密度。
（竞品来源：Claude Artifacts 官方博客、NotebookLM/Google 官方、Manus/Genspark 报道、Cursor 论坛、Gamma/Beautiful.ai 对比等，详见附录 E。）

## 14. Feature Priority Matrix（Impact × Effort 排序）

| 排序 | 建议项 | Impact | Effort | 优先级 |
|---|---|---|---|---|
| 1 | 上传路径穿越修复（一行 + 白名单） | 致命安全 | 低 | P0 |
| 2 | ppt_design `brief` NameError 修复 | 解除节点必败 | 极低（1 行） | P0 |
| 3 | stale-running 看门狗 + 任务级超时 + prefork 池 | 卡死/队列饥饿 | 低-中 | P0 |
| 4 | JWT 认证 + owner 过滤 + 静态目录白名单 | 数据安全 | 中 | P0 |
| 5 | v2 Research 接入真实检索（WebSearchTool + source 强制） | 产品可信度 | 中 | P0 |
| 6 | 产品管理（删除/重命名）+ 幂等 + 空输入校验 | 数据卫生/成本 | 低 | P1 |
| 7 | 取消/重试 API + 前端停止按钮 | 等待焦虑/成本 | 中 | P1 |
| 8 | 资产持久化与版本（含 Canvas 保存） | 数据丢失（P0 级 UX） | 中 | P1 |
| 9 | 前端路由级 lazy + echarts 按需 + 删死代码 | 性能/可维护 | 中 | P1 |
| 10 | 状态机集中校验 + CAS 原子推进 | 一致性 | 低 | P1 |
| 11 | 产品线收敛（单入口 + 品牌统一 + 旧线归档） | 心智模型 | 中 | P1 |
| 12 | 真实进度流（工具调用事件 + 日志） | 信任 | 中 | P2 |
| 13 | 记忆闭环（读回注入 + 容量上限） | 重复输入 | 中 | P2 |
| 14 | ErrorBoundary + 空/错状态统一 + a11y 修复 | 稳健性 | 低-中 | P2 |
| 15 | 节点级 Plan/Act 人工门（可配置） | 人机边界 | 高 | P2 |
| 16 | 模板中心/知识库真实化 | 名实相符 | 中 | P2 |
| 17 | 完成通知 + 协作分享 | 长任务/团队 | 中 | P3 |

## 15. 30 / 60 / 90 Day Roadmap

### 0–30 天：止血与基础修复（只做最重要的）

1. **安全三连**：上传 sanitize + 大小/类型限制；JWT 认证 + owner 过滤；静态目录白名单（crawled_data/studio_memory 移出）。
2. **可靠性三连**：`brief` 一行修复 + 删死函数；prefork 池 + 任务级超时（超时=失败）；stale-running 看门狗 + 启动探活。
3. **成本三连**：空输入校验（strip）+ 创建幂等；前端 Generate 防抖；取消 API。
4. 前端：ErrorBoundary + 路由级 lazy（4MB → <1.5MB）+ 删死代码。

### 30–60 天：核心 Agent / Product Workflow

1. **v2 事实底座**：WebSearchTool 接入 Research/Competitor 节点，source 强制 + 引用编号；v1 RAG 工具化注入平台层。
2. **进度真实化**：节点事件流（工具调用/中间产物/失败原因）→ 前端真实进度；移除硬编码模拟。
3. **资产可编辑闭环**：PRD/Research 资产卡局部重生成 + diff + 版本（v1 已有 zundo/Diff 可复用）；Canvas 保存持久化。
4. **记忆闭环**：Global/Project/Task 三层 + recent() 注入。
5. **质量门修复**：critic document 写回 state；critic 失败记不通过；评估器字段级阈值。

### 60–90 天：差异化能力

1. **产品线收敛**：统一品牌 + 单入口 + v1 模板化归档；产品空间 IA（§9）落地。
2. **节点级 Plan/Act 门**：研究/PRD/演示逐层人审（差异化卖点）。
3. **模板中心 + 知识库真实化**（自动标签/聚类，AI 可查询）。
4. **完成通知 + 分享链接**（协作雏形）。
5. **Model Router**：Fast/Reasoning/Vision/Presentation 分层 + usage 统计与预算告警。

---

## 附录 A：Feature Matrix（当前功能矩阵）

| Feature | 状态 | 用户价值 | 使用频率 | 技术复杂度 | 问题 | 优先级 |
|---|---|---|---|---|---|---|
| v1 三阶段状态机（断点） | Implemented | 高 | 高 | 中 | 无 CAS、无看门狗 | P0 |
| v1 RAG 撰写 + 引用溯源 | Implemented | 高 | 高 | 高 | 爬取覆盖率低、Chroma 无去重 | P2 |
| v1 大纲生成/审批 | Implemented | 高 | 高 | 中 | 良好 | — |
| v1 Canvas 编辑器 | Implemented | 高 | 中 | 高 | **永不保存（P0）**、巨型文件 | P0 |
| v1 图片搜索/素材库 | Implemented | 中 | 中 | 中 | 3 套重复实现 | P2 |
| v1 SSE 流式 | Partial | 高 | 高 | 中 | 伪 SSE、10min 上限 | P2 |
| v1 Inline AI 划词改写 | Broken（死代码） | 高 | 高 | 中 | 整套未上线 | P1 |
| v2 七节点流水线 | Implemented（有 P0 Bug） | 高 | 高 | 高 | ppt_design 必败；research 无检索 | P0 |
| v2 资产包（research/PRD/design/presentation） | Implemented | 高 | 高 | 中 | 只读、无版本 | P1 |
| v2 Critic 质量门 | Partial | 中 | 中 | 中 | 形同虚设（满分降级） | P1 |
| v2 ppt_design PPTX | Broken | 高 | 中 | 高 | brief NameError + SVG 转换失败链 | P0 |
| v2 Presentation 编辑器（GrapesJS） | Implemented | 高 | 中 | 高 | 覆盖式保存无版本 | P2 |
| v2 PDF 导出 | Implemented | 高 | 中 | 中 | 良好（11 页 0 溢出） | — |
| 8 模块 IA（Research/PRD/Design/Knowledge/Templates/Settings） | Partial | 中 | 低-中 | 低 | Design/Knowledge/Templates 深度不足 | P2 |
| 用户系统 | Broken | 低 | — | 低 | 无认证、无密码字段 | P0 |
| 文件上传 | Partial | 中 | 中 | 低 | **路径穿越 + 无限制** | P0 |
| 错误处理/错误码 | Partial | 中 | 高 | 低 | 内部异常直出、无错误码 | P2 |
| 测试套件 | Partial | — | — | — | 56+55+7 全过但 FakeLLM/无关键路径 | P1 |

## 附录 B：UX Issue Matrix（P0–P4 完整问题库）

> 正文已列 Top 问题；以下为补充未展开项。

**P0（4 项，正文已列）**：上传穿越 / 无认证 / 静态目录暴露 / 卡死无回收 / Canvas 不保存（共 5 项）。

**P1 补充**：
- 编辑器中撰写内容不更新（EditorPage.tsx:317 快照）；报告阅读页无入口；控制台无侧边栏入口。
- ProductAssetBrowser N+1 与 location.state 全量重拉。
- 需求澄清缺失：用户输入约束/指标不进入下游（requirement 节点零消费）。
- 失败无解释："重构验证中断"等 error_message 无代码来源、无标准错误码。
- SVG 校验与转换器契约脱节（校验通过、转换失败，失败发生在最贵环节之后）。

**P2 补充**：
- 无 aria-live / 键盘导航缺失 / 伪复选框 / 嵌套交互。
- 大纲/资料断点无超时提醒（2 个项目等审 1 个月）。
- SSE 断连不检测；editor/chat 无心跳。
- 进度快照 `_PROGRESS_SNAPSHOT` 内存泄漏；running→completed 状态抖动。
- 上传孤儿文件不清理；50MB 无上限。
- `template_type` 无 Literal 校验；history 无长度上限。
- BM25 每次全量重建；embedding 非单例。
- 事件日志 sequence 进程内缓存断号。

**P3 补充**：
- `types/index.ts` `@ts-nocheck`；模块级 `_optimisticStatus` 全局单例；导出页 store 页码错位风险。
- `.env` 644 权限含明文 Key；CORS `*` + credentials。
- `_find_env_file` 注释与实现不符；配置碎片（AGENT_PLATFORM_* 双系统）。
- 竞品数据（Genspark 2.75 亿美元 B 轮等）已纳入 §13 研究，无需重复。

## 附录 C：产品成熟度评分

| Dimension | Score | 理由 |
|---|---|---|
| Product Positioning | 5 | 方向对（研究→交付工作台），但双产品线/三品牌/文案矛盾 |
| Core Value | 6 | v1 断点干预+溯源是真价值；v2 事实底座缺失拉低 |
| UX | 5 | 状态机交互好；空态/错误态/首次引导残缺 |
| Interaction | 5 | 断点+块级编辑好；无取消/重试/局部重生成 |
| Agent UX | 4 | 模拟进度、无记忆、无人工介入、质量门失信 |
| Memory | 3 | 只写不读、无分层、无跨会话 |
| Knowledge | 5 | v1 检索-溯源优秀；v2 归零 |
| Workflow | 5 | v1 闭环完整；v2 数据断层（requirement 零消费、截断） |
| Artifact | 4 | 结构化资产好；无版本/局部编辑/持久化 |
| Frontend Architecture | 4 | 4MB 单包、死代码、三范式、无边界 |
| Backend Architecture | 4 | 状态机/任务设计好；竞态、超时、迁移漂移 |
| Agent Architecture | 3 | LangGraph 未真正生效、重试语义粗放、工厂入口崩 |
| Reliability | 3 | 卡死无回收、队列饥饿、超时变重试 |
| Performance | 4 | 后端任务 7min 可接受；前端 4MB/阻塞调用 |
| Visual Design | 6 | 纸感方向正确；token/一致性未系统化 |
| Scalability | 3 | 无认证、单 worker、SQLite、无队列分离 |
| **Overall Product Maturity** | **4.5** | 架构骨架好、v1 真价值；v2 未达标，安全与可靠性必须先修 |

## 附录 D：实测记录（Expected / Actual / Error / Root Cause / Impact / Recommendation）

| 场景 | Expected | Actual | Error | Root Cause | Impact | Recommendation |
|---|---|---|---|---|---|---|
| 上传 `../../../../../../../../../tmp/x.txt` | 拒绝 | **200 成功写入 /tmp** | 无 | filename 未 sanitize | 任意文件写 | basename+白名单 |
| 上传 50MB 文件 | 限制大小 | 422（解析失败）但 50MB 已落盘 | 无 | 无大小上限、无失败清理 | 磁盘 DoS | 上限+清理 |
| 主题 `"  "` | 422 | **201 创建并触发流水线** | 无 | 无 strip 校验 | 浪费成本 | strip+语义校验 |
| 空 idea 创建产品 | 422 | **201 queued** | 无 | 同上 | 浪费成本 | 同上 |
| 5 次并发相同创建 | 幂等去重 | **5 条独立流水线** | 无 | 无幂等 | 5 倍成本 | 幂等键+前端防抖 |
| 产品卡 running 1.5h | 终态 | running（ppt_design failed 后仍 running） | 无 | brief NameError + 无看门狗 | 用户干等 | 看门狗+一行修复 |
| 新报告项目 drafting | 章节写入 | **12 分钟 0 章节** | 无 | worker 被卡死任务占满 | 队列饥饿 | 任务级超时+队列分离 |
| 删除产品 | 可删除 | **无 DELETE API** | 404 | 未实现 | 垃圾累积 | 补删除 |
| approve-outline 状态错误 | 409 | 409 带友好文案 | — | 守卫正确 | — | 保持（加 CAS） |
| 未知 UUID | 404 | 404 正确 | — | — | — | 保持 |
| PATCH presentation | 保存 | 200 + 读回验证 | — | — | 覆盖无版本 | 加版本 |
| v2 export-pdf | PDF | 11 页 0 溢出 | — | — | — | 保持 |
| editor chat SSE | 流式 | 逐 token 正常 | — | — | — | 保持（加心跳/断连） |
| revise-block | 局部改写 | 正常且保留引用 | — | — | — | 保持 |
| search-images | 图片 | DuckDuckGo 3 张 | — | — | — | 保持 |
| knowledge/documents | 过滤 | 忽略 project_id 返回 108 条 | 无 | 参数未实现过滤 | 项目混淆 | 按项目过滤 |
| Presentation 页 | 无警告 | 大量重复 React key 警告 | — | components.tsx:325 列表 key | 渲染隐患 | 修 key |

## 附录 E：竞品研究来源（节选）

- Claude Artifacts：https://claude.com/blog/claude-powered-artifacts
- NotebookLM（来源优先/强制引用）：https://blog.google/innovation-and-ai/models-and-research/google-labs/notebooklm-deep-research-file-types/ 、https://skywork.ai/blog/notebooklm-google-ai-notebook-research-assistant
- Manus（任务可视化/执行中接管）：https://blog.csdn.net/xx_nm98/article/details/151230272 、https://finance.sina.com.cn/stock/stockzmt/2025-03-25/doc-ineqvkuw6078437.shtml
- Genspark AI Workspace：https://www.businesswire.com/news/home/20251120036880/en/Genspark-Raises-%24275M-Series-B-Launches-AI-Workspace-to-Put-Busywork-on-Autopilot
- Cursor Plan vs Act：https://forum.cursor.com/t/plan-vs-act-modes/43550
- Gamma / Beautiful.ai 演示范式：https://gamma.app/es/explore/content/guides/gamma-ai-driven-alternative-manual-presentation-design
- v0 / Lovable / Replit：https://uibakery.io/blog/v0-vs-bolt-vs-replit
- Linear / Notion AI：https://www.eesel.ai/blog/notion-ai-connector-for-linear

---

## 最终结论

**判断**：这个项目距离"可被用户长期使用的 AI-native Product Workspace"还有 **2-3 个迭代周期（约 3 个月）**。它拥有行业稀缺的真实差异化（断点干预 + 块级编辑 + 引用溯源的 v1 组合，以及方向正确的 v2 架构红线），但当前被四件事拖住：**安全裸奔（P0）、任务永久卡死（P0）、v2 事实底座归零（P0）、双产品线心智分裂（P1）**。按 §15 路线图执行：前 30 天止血，60 天让 v2 成为"有据可查"的 Agent 工作流，90 天完成产品收敛与差异化交互——届时它具备成为"AI 产品团队工作台"的竞争力。

*报告完。所有运行时证据采集自真实环境；代码证据均已标注 file:line 并交叉验证。*

---

# 附录 F：90 天计划实施记录（2026-08-17）

> 本附录记录按报告 §15 路线图执行的修复与验证状态。实施期间发现另一工作流也在同一工作树进行重构（ppt 资产恢复、RAG 重写等），本记录以**当前代码状态**为准。

## Phase A（0-30 天：止血）—— ✅ 全部完成并验证

| 项 | 状态 | 验证方式 |
|---|---|---|
| 上传 sanitize（basename + 扩展名白名单 pdf/txt/md + 20MB 上限 + 失败清理） | ✅ | 实测：9 级 `../` 文件名仅保留 basename 写入 uploads 私有目录；.exe→415；25MB→413；/tmp 无越权写入 |
| 私有数据移出静态根（crawled_data/studio_memory/uploads → `OUTPUT_DIR/private/`） | ✅ | 实测：`/api/v1/files/crawled_data_*.json` → 404；assets/studio_assets 正常 200 |
| JWT 认证（HMAC token，stdlib）+ owner 过滤 + 静态目录白名单 | ✅ | 实测：无 token→401；bootstrap/login/me 正常；坏 token→401；项目/产品按 owner 过滤 |
| 看门狗（启动回收 + 15min 周期）+ 终态不可回退守卫 | ✅ | 实测：卡 2 天的产品 `71064dd6` 启动时被自动置 failed |
| Celery prefork 池 + 超时异常放行（SoftTimeLimit/Retry 不再被吞） | ✅ | 代码 + 测试验证；`start_all.sh` 已切 prefork |
| v1 topic strip 校验（空白主题→422） | ✅ | 实测 422 |
| 创建幂等（idea_hash + Idempotency-Key，另一工作流已实现，复核通过） | ✅ | 实测：相同 idea 二次创建返回同一 product_id |
| 取消 API（v1 项目 + v2 产品，撤销 Celery 任务 + 置 failed） | ✅ | 实测：取消成功；completed→409 |
| 前端 ErrorBoundary + 路由级 lazy + 删 1,900 行死代码 + 轮询修复 | ✅ | 主包 4,010KB → 812KB（-80%）；tsc 通过；UI 冒烟无新增错误 |
| ppt_design `brief` NameError | ✅ | 另一工作流已修复（agent.py 现定义 brief），复核确认 |

## Phase B（30-60 天：核心工作流）—— ✅ 全部完成

| 项 | 状态 | 验证方式 |
|---|---|---|
| v2 Research/Competitor 接入 WebSearchTool 真实检索（多查询 + 编号来源 + source 强制 + 确定性回填） | ✅ | 实测：流水线 research 阶段发起 6 次 Tavily 请求（4+2 查询） |
| 进度真实化（progress_log 事件日志 + GET /product/{id}/logs + 前端真实事件时间线） | ✅ | 实测：事件日志逐节点记录 ts/node/status/detail；前端 AgentTimeline 渲染真实事件 |
| 资产局部重生成 + 版本历史（regenerate/versions/restore + 前端按钮） | ✅ | 代码 + 测试；后端三端点就绪 |
| Canvas 编辑器自动保存（1.5s 防抖 → POST /projects/{id}/canvas，恢复用户布局） | ✅ | 实测：保存/读取端点正常；EditorPage 顶部"已保存 HH:MM"指示 |
| 记忆闭环（recent() 注入 AgentLoop + JSONL 200 条容量上限） | ✅ | 代码验证；平台测试 55 全过 |
| 质量门修复（document 写回 state、critic 失败按未通过、评估器必填列表非空、页数 10-16 统一） | ✅ | 平台测试 55 全过；agents 测试 7 全过 |

## Phase C（60-90 天：差异化）—— ✅ 完成（除标注项）

| 项 | 状态 | 验证方式 |
|---|---|---|
| 产品线收敛（侧边栏品牌统一为 QX Product Studio + 控制台改"研究报告（归档）"入口） | ✅ | tsc + 构建通过 |
| 节点级 Plan/Act 门（GATE_NODES 可配置：节点完成→暂停 waiting_approval→批准续跑/拒绝终止，断点恢复） | ✅ | 代码完成；待端到端验证（需重启 worker 开启 GATE_NODES） |
| 模板中心真实化（模板→示例想法→预填工作台） | ✅ | tsc + 构建通过 |
| 知识库真实化 | ✅ | 已有项目选择 + 上传 + 图片搜索（复核确认） |
| 完成通知（浏览器 Notification） | ✅ | 代码完成 |
| 分享链接（复制 PDF/PPTX 公开链接） | ✅ | 代码完成 |
| Model Router（NODE_MODEL_MAP 节点→提供商路由 + LLMClient token 用量累计 + 资产包 usage 字段） | ✅ | 代码 + 编译 + 平台测试通过 |

## 追加验证结果（2026-08-17 20:30）

- **B1 真实检索独立验证 ✅**：直接运行 ResearchAgent（真实 Tavily）→ `market_size.source` 回填真实来源 URL（theinsightpartners.com），摘要含 [1][2] 编号引用，产出 8 竞品/8 痛点/8 趋势（通过必填列表评估器）。
- **C2 门控端到端逻辑验证 ✅**（脚本化 agent）：GATE_NODES=["strategy"] → 在 strategy 完成后触发 GatePause（已完成节点：requirement/research/competitor/strategy）→ 批准后续跑完成 10 页演示，strategy 与 research 均只调用 1 次（无重复执行）。修复了两个实现缺陷：① GatePause 需在 `_with_retry` 中显式放行（否则被 except Exception 吞掉）；② 门控私有键必须写入 ProductStudioState TypedDict（否则被 MemorySaver 剥离）；③ 已完成节点跳过仅在门控模式生效（否则误伤 critic 修订循环 → GraphRecursionError，已由 55 项平台测试回归锁定）。
- **UI 冒烟（Phase C 后）✅**：9 页面加载正常、无控制台错误；侧边栏品牌统一为「QX Product Studio / AI Product Workspace」，新增「研究报告（归档）」入口。

## 第二轮实施记录（2026-08-18：v1 核心组件并入 workspace 创作流程）

按用户新要求执行，要点与验证：

1. **资料审核融入 workspace 创作流程**：新增 `source_gathering` 节点（requirement_parser 之后）——
   真实检索 → 权重标注 → **暂停等待用户审核**（Plan/Act 门，`SOURCE_REVIEW` 默认开启）；
   审核提交（`selected_urls`）后仅用保留资料继续 research/competitor/strategy/design/presentation。
   ✅ 端到端实测：34 条资料（高 3/中高 7/中 22/低 2）→ 审核保留 6 条 → 续跑全流程正常。
2. **去掉「研究报告（归档）」入口**：侧边栏入口移除；`/` 重定向 `/workspace`；
   v1 报告流水线不再作为独立产品线（旧项目深链 `/projects/:id/*` 仍可访问）。
3. **扩大搜索量 + 资料权重**：8 查询 × 每查询 8 条，上限 40；
   权重分类：研究报告/咨询机构 0.9 > 政府/学术 0.8 > 报告类关键词 0.75 > 行业媒体 0.7 >
   一般 0.5 > 论坛/百科 0.4；用户上传本地资料 = 1.0（最高）。
4. **移除模板选择/搜索强度设置**：随 v1 入口移除（v2 创建流程本就无此设置）。
5. **UI 统一 workspace 风格**：审核界面用纸感卡片/`#24415E`/权重 badge；
   SourceIndex 组件在 Research/PRD/Design 页展示「资料来源索引」（编号 + URL + 权重）。
6. **文本资产强制来源索引**：MarketResearch/CompetitorAnalysis/ProductStrategy/UXDesign
   schema 均新增 `sources: list[SourceRef]`；prompt 强制 [n] 编号引用 + 禁编造；
   确定性兜底：模型未填 sources 时用审核资料前 5 条回填（不编造）。
   ✅ 实测 research.market_size.source 为真实来源 URL。

**修复的缺陷（测试锁定）**：门控恢复 + critic 修订循环组合下
① 包装器 `_completed_nodes` 覆盖节点自身更新；② 低分无 issue 文案时修订计数不增 → 均导致
GraphRecursionError；改为"critic 发 `_revise_requested` 信号 + presentation 重跑时计数"，
组合场景验证通过（presentation 恰执行 1 初始 + 2 修订 = 3 次）。

**回归**：平台 55 + agents 7 + 后端 57 测试全过；前端 tsc/构建通过；主包 806KB。

## 第三轮验证记录（2026-08-18：E2E 与崩溃修复）

1. **`Object of type set` 序列化崩溃（实测发现并修复）**：`ppt-design-agent` 的
   `_backfill_spec_lock` 返回 `font_sizes: set`，混入资产包后 `json.dumps` 抛 TypeError，
   任务崩溃、产品永久 running。修复：① font_sizes 转 sorted list；② 任务持久化
   `json.dumps(..., default=str)` 双保险。**直接验证通过**：完整 ProductAssetPackage →
   model_dump → 序列化（含 set 残留模拟）成功。
2. **E2E 实测（3 轮完整流水线）**：source_gathering 暂停（40 条资料/权重分布
   高3·中高7·中22·低2）→ 审核保留 6 条 → 续跑 → research/competitor/strategy/
   design/presentation（含修订循环）/critic 全部 completed → **ppt_design 产出 3.1MB
   PPTX**（`exports/....pptx`）。最终 COMPLETED 落库步骤受并发工作流干扰（worker 重启 +
   其 pause 功能反复暂停测试产品）未能观测，但该步骤的崩溃点已直接验证修复。
3. **已上传 GitHub**：`CaroVon/Agent_Platform_QX` HEAD `2ac86f2`（3 提交，13,194 文件）。

## 第四轮实施记录（2026-08-19：Workspace 对话式输入 + 提示词建议）

按用户要求实施（P0+P1），并直接拉取 [prompt-kit](https://github.com/ibelick/prompt-kit) 仓库
研读源码后移植适配（非浅层借鉴）：

1. **对话式输入（P0）**：
   - 后端：`POST /product/clarify`（SSE 需求澄清，专用 `PRODUCT_CLARIFY_SYSTEM` prompt，
     一次最多 2-3 问；`event: meta` 输出 4 维度覆盖信号：目标用户/场景/功能/约束）
   - 前端：`ClarifyPanel`（消息气泡+流式）+ `ChatInput`（prompt-kit PromptInput 移植：
     Context 模式/自增高 Textarea/Enter 发送 Shift+Enter 换行/React 18 适配/纸感 token）
     + `useClarifyChat`（SSE 解析/维度信号/brief 拼装）
   - 双模式：对话式输入 / 快速输入（保留原 IdeaInput）
2. **提示词建议 chips（P0）**：`SuggestionChips`（prompt-kit PromptSuggestion 移植：
   Normal 胶囊 + Highlight 输入高亮匹配；8 个静态模板 + 输入关键词联想 + 🎲 随机方向）
3. **P1**：对话 localStorage 持久化续聊；`POST /product/suggest` LLM 动态补全
   （输入停顿 800ms 防抖拉取）；brief 直达 requirement_parser（约束/指标首次真正进入下游）
4. **实测**：clarify 两轮对话维度覆盖 0/4→4/4（enough:true）；suggest 返回 3 条贴合建议；
   UI 交互 10 项全过（双 Tab/chips/输入/发送/生成按钮禁用态）；后端测试全过；主包 868KB。

## 遗留说明

1. **并发工作流**：实施期间检测到另一工作流同时修改同一工作树（08-17 19:28-20:03 期间多次覆盖 `agents/ppt-design-agent`、`agents/design-agent` 等文件）。我方补丁已重新应用并通过全部测试；若后续发现文件被覆盖，以当前工作树 + 本附录为准重新应用。
2. **C2 门控端到端验证**：需要在 worker 启用 `GATE_NODES` 后创建产品实测"暂停→批准→续跑"链路（当前测试流水线占用 worker）。
3. **auth bootstrap**：本地开发默认 `AUTH_BOOTSTRAP=true`；生产部署必须置 false 并配置 `AUTH_SECRET/AUTH_ADMIN_PASSWORD`。
4. **上传目录**：旧数据已迁移至 `backend/outputs/private/`；新上传也写入私有目录。
