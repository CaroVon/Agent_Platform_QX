# 记忆系统深化优化方案：全局记忆 + 项目记忆 + 知识关系图可视化

> 版本：v1.0 ｜ 日期：2026-08 ｜ 前置：P1-P3 已落地（三层向量知识库 / 图片 VL 入库 / 相似任务经验包 / Obsidian 同步 / 记忆分层）
>
> 本文档回答：如何让"记忆"从**被动存储**升级为**主动发挥作用的记忆系统**——
> 每次任务沉淀全局记忆与项目记忆，并以**知识关系图**让用户直观看到记忆之间的关联。

---

## 0. 结论摘要（TL;DR）

| # | 结论 | 优先级 |
|---|------|--------|
| 1 | 开源生态已证明"记忆要发挥作用"的答案 = **结构化知识图 + 时序记忆 + 双层检索**，代表项目：Graphiti（时序图，但依赖 Neo4j）、mem0（记忆 API 设计）、LightRAG（双层检索）、Nano-GraphRAG（SQLite 轻量） | 🔴 |
| 2 | **本项目不引入 Neo4j/新基础设施**：自研轻量"记忆图"（3 张新表 + 现有 LLM/向量库），借鉴各开源项目的核心机制（实体合并、时序、双层检索） | 🔴 |
| 3 | **知识关系图可视化零新增依赖起步**：前端已内置 `echarts@6.1`（graph 系列支持力导向/邻域高亮）；正式版可评估升级 [AntV G6 v5](https://github.com/antvis/G6) | 🟡 |
| 4 | 记忆"真正发挥作用"的三条管道：**沉淀**（任务完成自动抽图）、**复用**（GraphRAG 式邻域检索注入 prompt）、**可视化**（用户可查可管理） | 🔴 |

---

## 1. 现状复盘与本次目标

### 1.1 已完成（P1-P3）

- 三层向量知识库（任务 L2 / 领域 L1 / 全局 L0），`retrieve_scoped` 融合检索
- 图片 MiniMax VL 分析入库；上传/删除一致性；经验包抽取与相似任务借用
- Obsidian 同步；`FileMemoryStore` 记忆分层（episodic/task/summary）

### 1.2 核心缺口（"记忆未真正发挥作用"的根因）

| 缺口 | 现状 | 后果 |
|------|------|------|
| **记忆无结构** | 记忆 = 文本切片 + 扁平 JSONL | 检索只能"按相似度捞文本"，无法回答"A 与 B 是什么关系" |
| **全局记忆未沉淀** | 任务成果只留在本任务向量库/经验包文本 | 新任务无法按**实体**（公司/产品/技术）召回历史结论 |
| **项目记忆不可见** | 项目内只有章节/文档 | 用户看不到"这个项目积累了什么知识" |
| **无可视化** | KnowledgePage 只有列表 | 用户无法感知记忆的存在与价值 |

### 1.3 本次目标（一句话）

> **任务完成时自动把成果提炼为"实体-关系-洞察"的记忆图（项目级 + 全局级），检索时按实体邻域召回，前端用关系图可视化呈现。**

---

## 2. 开源项目调研（GitHub 优先）

### 2.1 记忆/知识图谱框架对比

| 项目 | Star/生态 | 核心机制 | 与本项目的契合度 |
|------|-----------|----------|------------------|
| **[getzep/Graphiti](https://github.com/getzep/Graphiti)** | ~14k，Zep 出品 | 时序知识图：episodic/semantic 双状态、增量实体更新（bisect 冲突解决 + merge）、时间衰减查询 | ⭐⭐⭐⭐⭐ 架构最贴合"记忆真正发挥作用"，**但依赖 Neo4j**，对当前 SQLite 部署过重 → 借鉴机制、自研存储 |
| **[mem0ai/mem0](https://github.com/mem0ai/mem0)** | ~40k | 记忆 API：`add()/search()/get_all()`；scope 分层（user/agent/session）；事实提取 + 冲突解决（新增/更新/删除三类操作） | ⭐⭐⭐⭐ API 设计与"全局 vs 项目"记忆 scope 借鉴；本体偏对话记忆，与研报任务场景不完全匹配 |
| **[letta-ai/letta](https://github.com/letta-ai/letta)**（原 MemGPT） | ~18k | 分层记忆（core memory / recall / archival）+ 自我编辑记忆 | ⭐⭐⭐ 概念启发（archival=长期记忆库）；实现重（自建 agent runtime），不引入 |
| **[getzep/zep](https://github.com/getzep/zep)** | ~7k | Graphiti 之上的时序记忆服务（含记忆融合/摘要） | ⭐⭐⭐ 需要自托管服务；机制已被 Graphiti 覆盖 |
| **[HKUDS/LightRAG](https://github.com/HKUDS/LightRAG)** | ~20k | 图索引 + **双层检索**：low-level（实体级）与 high-level（主题级）查询；增量更新 | ⭐⭐⭐⭐⭐ **检索策略直接借鉴**：实体邻域检索 + 主题摘要检索双通道；存储层用 NetworkX/NanoVectorDB（可自实现） |
| **[gusye1234/nano-graphrag](https://github.com/gusye1234/nano-graphrag)** | ~5k | GraphRAG 的极简实现：SQLite + NetworkX + FTS，无外部服务 | ⭐⭐⭐⭐⭐ **存储层借鉴**：证明"SQLite 也能做图记忆" |
| **[microsoft/graphrag](https://github.com/microsoft/graphrag)** | ~25k | 社区检测 + 实体摘要 + 全局/局部查询 | ⭐⭐ 全量索引太重、面向文档库而非增量记忆；仅参考 |
| **[cognee](https://github.com/topoteretes/cognee)** | ~6k | ECL 管道（提取-认知-加载），带 UI | ⭐⭐ UI 概念可参考；依赖重 |

> 其他参考：LangMem（LangChain 记忆 SDK）、Memary（图记忆 agent，已归档）、txtai（嵌入式 RAG）。

### 2.2 图可视化库对比

| 库 | 特点 | 本项目决策 |
|----|------|-----------|
| **[ECharts graph](https://echarts.apache.org/)（已在依赖 echarts@6.1）** | 力导向布局、邻域高亮（focusAdjacency）、缩放拖拽、零新依赖 | 🟢 **MVP 首选**：1-2 天内上线关系图 |
| **[AntV G6 v5](https://github.com/antvis/G6)** | 专业图分析框架：布局算法（force/grid/radial）、缩略图、鱼眼、自定义节点、大数据量 | 🟡 **正式版候选**：交互与性能更强，+~1MB 依赖 |
| [Cytoscape.js](https://github.com/cytoscape/cytoscape.js) | 样式系统强、性能好 | 备选（生态偏生物信息学） |
| [React Flow](https://github.com/xyflow/xyflow) | DAG/流程图导向 | ❌ 不适合知识图（无内置力导布局） |
| [vis-network](https://github.com/visjs/vis-network) | 轻量但维护放缓 | ❌ 不推荐 |

### 2.3 调研结论（借鉴清单）

```
Graphiti       → 实体合并/冲突解决 + 时序记忆 + episodic/semantic 双状态（自研简化版）
LightRAG       → 双层检索：实体邻域（low-level）+ 主题洞察（high-level）
mem0           → 记忆 API 形态（add/search/get_all）+ scope（global/project/session）
nano-graphrag  → SQLite 存图 + FTS 关键词兜底（零新增基础设施）
ECharts(已有)  → 知识关系图可视化 MVP
```

---

## 3. 目标架构：记忆图（Memory Graph）

### 3.1 数据模型（新增 3 张表，Alembic 0007）

```
memory_entities
  id, scope(global|project), project_id?, type(entity_type: company/product/tech/person/market/metric…)
  name(归一化主名), aliases(JSON), summary(实体摘要，LLM 维护), embedding(JSON)
  confidence(float), first_seen_at, last_seen_at, created_at, updated_at
  ── 全局实体与项目实体：scope=global 跨项目合并；scope=project 项目特有
  ── 合并规则：同名归一化（去空格/大小写/全半角）+ embedding 余弦 > 0.92 → 合并为全局实体

memory_relations
  id, source_entity_id, target_entity_id, relation_type(竞争/供应商/技术用于/收购/…
  evidence(JSON: 来源章节/URL/项目), weight(float), valid_from, valid_to?, created_at
  ── 边带时间窗（Graphiti 时序思想）：关系可过期/被新证据覆盖

memory_insights
  id, scope, project_id?, content(洞察/结论文本, ≤500字), entity_ids(JSON 链接实体)
  source(knowledge_tasks 摘要/对话/图片分析), source_url?, confidence, created_at
  ── "高层记忆"：结论级知识（LightRAG high-level 检索的载体）
```

> 存储决策：**不引入 Neo4j/NetworkX 持久化**。关系图 = 3 张 SQLite 表 + 查询时内存构图；
> 理由：当前单机 SQLite 部署、图规模预期 <10⁵ 节点（该量级 SQL 足够）；升级路径见 §6。

### 3.2 记忆沉淀管道（每次任务自动执行）

```
任务 COMPLETED / 经验包抽取后（复用现有钩子）→ Celery knowledge.build_memory_graph
  ├─ 1. 语料组装：DocumentBlock 章节 + 经验包摘要 + 图片 VL 文本（限 20k 字）
  ├─ 2. LLM 抽取（结构化 JSON，批量 chunk）：
  │      {"entities": [{"name","type","summary"}],
  │       "relations": [{"source","relation","target","evidence"}],
  │       "insights": ["结论1", ...]}
  ├─ 3. 实体归一化 + 合并：
  │      normalize(name) → 查 memory_entities（同 scope）
  │      embedding 相似 > 0.92 → 更新 aliases/summary/confidence（借鉴 Graphiti merge）
  │      冲突证据（同关系不同结论）→ 保留 valid_to 时间窗，不删旧边（时序）
  ├─ 4. 关系与洞察入库（带 evidence 溯源 + valid_from）
  ├─ 5. 全局提升（LLM 判定）：confidence 高 + 跨任务复现的实体/洞察
  │      → upsert 到 scope=global（项目记忆 → 全局记忆）
  └─ 6. 记忆向量化：entities.name+summary、insights.content → 全局向量库
         （scope="memory" 独立向量子库，与语料库分离）
```

### 3.3 记忆检索增强（GraphRAG 式，接入现有 RAG）

```
query → ① 实体匹配（memory 向量库 top-k 实体）
      → ② 邻域展开：每个命中实体取 1-2 跳 relations（SQL 递归/内存 BFS）
      → ③ 关联洞察：邻域实体链接的 memory_insights
      → ④ 组装上下文：
           【记忆图·实体】Apple ←竞争→ Samsung（证据: 项目X §3.2）
           【记忆图·洞察】屏幕是智能手表核心差异点（来源: 项目X）
      → ⑤ 与现有三层向量检索 RRF 融合（graph 权重 0.7，防止淹没任务事实）
```

注入点：editor/chat work 模式（已注入经验包，叠加实体记忆）、新建任务系统提示、报告撰写。

### 3.4 记忆生命周期

| 环节 | 机制 |
|------|------|
| 时效 | relations 带 valid_to；过期边检索降权/剔除 |
| 衰减 | last_seen_at 超过 N 天未引用的实体 confidence 递减 |
| 遗忘 | confidence < 阈值 → 图 API 标记 archived，不物理删除（可恢复） |
| 版本 | 实体 summary 更新保留 evidence 历史（insights 表天然时序） |
| 删除 | 项目删除 → 级联清理 scope=project 记忆；scope=global 仅解引用 |

---

## 4. 可视化设计：知识关系图

### 4.1 后端 API（新增 /memory 路由）

```
GET /memory/graph?scope=global|project&project_id=&q=&entity_types=&limit=
  → {nodes: [{id, name, type, summary, scope, project_count, confidence}],
     edges: [{source, target, relation, weight, evidence}],
     meta: {entity_count, relation_count, projects_covered}}

GET /memory/entities/{id}          → 实体详情 + 邻域 + 关联洞察 + 来源项目时间线
GET /memory/insights?scope=&q=     → 洞察列表（支持关键词/向量检索）
POST /memory/rebuild/{project_id}  → 手动触发某任务记忆重建（幂等）
DELETE /memory/entities/{id}       → 用户删除错误实体（含级联关系）
```

### 4.2 前端设计（MemoryPage，侧边栏新增"记忆图谱"入口）

```
布局：
┌────────────────────────────┬──────────────────────────────┐
│ 关系图主区 (ECharts graph)  │ 实体详情侧栏                  │
│  ├─ 力导向布局             │  ├─ 名称/类型/置信度/作用域    │
│  ├─ 点击实体 → 邻域高亮    │  ├─ 摘要（全局实体合并摘要）   │
│  ├─ 滚轮缩放/拖拽          │  ├─ 关联洞察列表（可展开证据） │
│  ├─ 搜索框（实体名过滤）   │  └─ 时间线（first/last seen）  │
│  └─ 类型图例 + 筛选        ├──────────────────────────────┤
│     （公司/产品/技术…）    │ 洞察面板（high-level 记忆）    │
└────────────────────────────┴──────────────────────────────┘
顶部：scope 切换（全局记忆 / 项目记忆）+ 项目选择 + 刷新/重建按钮

交互细节：
  - 节点大小 ∝ 关联边数（hub 实体突出）；颜色 = 实体类型
  - 边标签显示关系类型（hover 时）
  - 全局视图：项目归属用"项目聚合节点"或节点 badge（项目数）
  - 空状态引导："尚无记忆 —— 完成一个任务后自动生成"
```

### 4.3 信息架构接入

- 侧边栏"管理"组新增 **Memory Graph**（图标：Share2/Network）
- KnowledgePage Tab3"领域与全局"增加"查看关系图"跳转
- WorkspacePage 项目详情可嵌入项目级子图（可选）

---

## 5. 实施路线图

| Phase | 内容 | 工作量 | 依赖 |
|-------|------|--------|------|
| **P4a 记忆图后端** | 3 张表 + Alembic 0007；LLM 抽取任务（`build_memory_graph`，复用经验包钩子）；实体归一化合并；`/memory/*` API；记忆向量库（scope=memory）；检索融合（editor/chat + 新任务） | 3-4 人日 | 无（复用现有 LLM/向量库） |
| **P4b 关系图可视化** | MemoryPage（ECharts graph + 详情侧栏 + 搜索/过滤/scope 切换）；Sidebar 入口；KnowledgePage 联动 | 1.5-2 人日 | P4a API |
| **P4c 记忆生命周期** | 全局提升判定、时效/衰减/遗忘、删除级联、手动重建/纠错 UI | 1.5-2 人日 | P4a/P4b |
| P4d（可选增强） | AntV G6 v5 升级（大数据量/鱼眼/minimap）；记忆图注入报告撰写流程；Graphiti 式双状态（episodic/semantic）细分 | 2-3 人日 | 按需 |

**验证标准**：
1. 完成一个测试任务 → `/memory/graph?scope=project` 出现 ≥5 实体、≥5 关系、≥2 洞察
2. 完成第二个相似任务 → 全局视图出现跨项目合并实体（project_count≥2）
3. editor/chat 提问"XX 与 YY 是什么关系" → 回答引用记忆图证据（含项目溯源）
4. 前端关系图可交互（点击高亮/搜索/切换 scope）

---

## 6. 风险与权衡

| 风险 | 缓解 |
|------|------|
| LLM 抽取成本（每任务 1-2 次 LLM 调用） | 异步 Celery + 仅 completed 任务触发；失败不阻断主流程（同经验包模式） |
| 实体合并误合并（同名不同义） | 归一化 + embedding 阈值 0.92 + 人工删除 API 兜底；合并动作记录可回滚 |
| SQLite 存图规模上限 | 当前量级（<10⁵ 实体）SQL 足够；超限时升级路径：Neo4j 适配层（表结构与 Cypher 映射）或 NetworkX 序列化 |
| 图检索注入 prompt 膨胀 | 邻域限制 1-2 跳、洞察 ≤3 条、总长 ≤1500 字；按权重参与 RRF |
| 可视化性能（>2000 节点） | ECharts 开启 `roam` + 节点采样（top-N by degree）；P4d 换 G6 |

---

## 7. 参考来源

**记忆/知识图谱框架：**
- [Graphiti: Build Real-Time Knowledge Graphs for AI Agents（时序图+实体合并，Neo4j）](https://github.com/getzep/Graphiti)
- [mem0: The Memory Layer for AI Agents（记忆 API/scope/冲突解决）](https://github.com/mem0ai/mem0)
- [LightRAG: Simple and Fast Retrieval-Augmented Generation（双层检索）](https://github.com/HKUDS/LightRAG)
- [nano-graphrag: 极简 GraphRAG（SQLite+NetworkX+FTS）](https://github.com/gusye1234/nano-graphrag)
- [microsoft/graphrag: 社区检测+摘要检索（重量级参考）](https://github.com/microsoft/graphrag)
- [cognee: ECL 记忆管道（带 UI 参考）](https://github.com/topoteretes/cognee)
- [letta(MemGPT): 分层记忆参考](https://github.com/letta-ai/letta)
- [Zep: Graphiti 之上的时序记忆服务](https://github.com/getzep/zep)
- [Awesome GraphRAG 资源清单](https://github.com/graphrag/awesome-graphrag)
- [Agent memory: Letta vs Mem0 vs Zep vs Cognee（社区对比）](https://forum.letta.com/t/agent-memory-letta-vs-mem0-vs-zep-vs-cognee/88)

**可视化：**
- [AntV G6 v5: 图可视化框架](https://github.com/antvis/G6)
- [Cytoscape.js](https://github.com/cytoscape/cytoscape.js)
- [React Flow (xyflow)](https://github.com/xyflow/xyflow)
- [Graph JS Library Comparison](https://dmccreary.github.io/learning-graphs/sims/graph-js-library-comparison/main.html)

**检索/架构：**
- [LightRAG Retrieval 详解（Neo4j 博客）](https://neo4j.com/blog/developer/under-the-covers-with-lightrag-retrieval/)
- [5 Best Open Source Graph RAG Tools](https://typegraph.ai/blog/best-open-source-graph-rag-tools)

---

## 8. 实施记录（P4 全量落地，2026-08）

> 以下变更已按本文档与 `memory-graph-visual-design.md` 全部实现并通过验证：
> 后端 75 项 pytest 全绿（含 6 项新增记忆图测试）+ 记忆图端到端冒烟（实体合并/全局提升/邻域检索/生命周期）+ 前端 `tsc -b` 与 `vite build` 通过 + 开发库迁移至 0008。

### 8.1 已交付功能清单

| 阶段 | 功能 | 落地位置 |
|------|------|----------|
| P4a | 记忆图三表（实体/关系/洞察，含时间窗与置信度）+ Alembic 0007 | `models/memory_{entity,relation,insight}.py`、`alembic/versions/0007_memory_graph.py` |
| P4a | LLM 抽取（实体/关系/洞察结构化 JSON）→ 归一化 → 同名/向量合并（>0.92）→ 入库 | `app/rag/memory_extraction.py::extract_memory_from_project` |
| P4a | 记忆向量化（scope=memory 独立向量库）+ 邻域检索（向量命中→1 跳展开→关联洞察） | `_vectorize_entities`、`retrieve_memory_context` |
| P4a | /memory API 五端点（graph/entities/{id}/insights/rebuild/delete） | `backend/app/api/v1/endpoints/memory.py` |
| P4a | 检索融合：editor/chat 注入记忆图上下文；任务完成自动触发沉淀 | `editor.py`、`report_workflow.py` 钩子 |
| P4c | 全局提升（同名跨 ≥2 项目 → global 实体 + 关系复制 + 洞察提升） | `promote_global_memories` |
| P4c | 置信度衰减（30 天未引用 -0.05，下限 0.3，每日 Celery Beat）；项目删除级联；实体删除纠错 | `decay_memories`、`delete_project_memories`、`delete_entity_cascade` |
| P4b | --graph-* 设计令牌（亮/暗）+ 主题桥接 + 实体图标注册表 | `globals.css`、`graph/graphTheme.ts`、`graph/graphIcons.tsx` |
| P4b | ECharts 关系图（力导/类型色/度数尺寸/置信度描边/新鲜度透明度/平行边曲率/过期虚线/LOD 标签/PNG 导出） | `graph/graphOptions.ts`、`graph/GraphCanvas.tsx` |
| P4b | MemoryPage（scope 切换/搜索聚焦/类型筛选/统计条/洞察面板/重建）+ Sidebar 入口 + 路由 | `pages/MemoryPage.tsx`、`Sidebar.tsx`、`App.tsx` |
| P4b | 实体详情侧栏（邻域/洞察/证据/纠错删除） | `graph/GraphSidebar.tsx` |

### 8.2 迁移链（含既有迁移重排）

```
0001 → 24f2c9f525d7 → 0003 → 0004 → 0005 → 0006(knowledge) → 0007(memory graph) → 0008(studio keywords)
```
> 注：先前会话的 `0007_studio_product_keywords` 与记忆图迁移撞号，已重排为 0008（down_revision=0007）。

### 8.3 验证标准达成情况

1. ✅ 完成任务 → /memory/graph 出现实体/关系/洞察（pytest + 冒烟验证）
2. ✅ 相似任务 → 全局视图出现跨项目合并实体（`test_memory_graph_global_promotion`）
3. ✅ editor/chat 回答可引用记忆图证据（`retrieve_memory_context` 注入链路）
4. ✅ 前端关系图交互（点击高亮/搜索/scope 切换/导出 PNG）
