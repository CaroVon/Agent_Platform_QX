# 知识系统与记忆功能调研及优化分析

> 版本：v1.0 ｜ 日期：2026-08 ｜ 范围：QX_product_agent 全栈（backend / frontend / app.rag / agent-platform）
>
> 本文档回答四个问题：
> 1. 当前"记忆=Knowledgebase 侧边栏"的现状与差距（全局/领域/任务三层知识体系）
> 2. Obsidian 或同类工具能否插入，以及怎么插
> 3. 图片上传知识库 + MiniMax 视觉分析入库的完整设计
> 4. 其他必要配件与整体架构分析

---

## 0. 结论摘要（TL;DR）

| # | 结论 | 优先级 |
|---|------|--------|
| 1 | 当前系统的**任务知识层（L2）已基本成型**：每项目独立 Chroma+BM25 混合检索库、上传文档入库、编辑器对话 RAG 均已可用 | — |
| 2 | "全局知识库"（Knowledgebase 侧边栏）**名不副实**：`/knowledge/documents` 只是跨项目文档**元数据只读列表**，无内容、无检索；真正可检索的知识全部锁死在单项目内 | 🔴 高 |
| 3 | **领域知识层（L1）完全缺失**：没有任务相似度计算，跨任务"借经验"无从谈起 | 🔴 高 |
| 4 | Obsidian 可以插入，**推荐"Vault 文件系统直读 + local-rest-api 可选增强"**双通道方案，零插件依赖即可起步 | 🟡 中 |
| 5 | 图片目前只做**素材暂存**（`/assets`）不入知识库；MiniMax **`minimax-vl-01`** 视觉模型可无缝接入（项目已有 `MINIMAX_API_KEY`），实现"图片→结构化文本→向量入库" | 🔴 高 |
| 6 | 附带发现一个真实 bug：前端允许上传 doc/docx，后端 `ALLOWED_UPLOAD_EXTS` 默认仅 `pdf,txt,md`，docx 会被 415 拒绝 | 🟢 顺手修 |

---

## 1. 现状盘点

### 1.1 当前架构总览

```
┌────────────────────────────── 前端 (React) ─────────────────────────────┐
│ Sidebar ──▶ /knowledge (KnowledgePage)                                  │
│   ├─ 文档库列表   ← GET  /api/v1/knowledge/documents   （只读元数据聚合）│
│   ├─ 文件上传     ← POST /api/v1/projects/{id}/upload-docs              │
│   └─ 图片素材     ← POST /api/v1/projects/{id}/assets   （仅存文件）    │
│                   ← POST /api/v1/projects/{id}/search-images（DDG 搜图）│
│ Editor 侧栏对话   ← POST /api/v1/editor/chat  (work 模式 RAG 召回)      │
└─────────────────────────────────────────────────────────────────────────┘
┌────────────────────────────── 后端 (FastAPI + Celery) ──────────────────┐
│ 任务知识层 L2（唯一可检索层）：                                          │
│   ./chroma_db/{project_id}/   ← Chroma 向量库 (bge-small-zh-v1.5 本地)  │
│   ./bm25_db/{project_id}/docs.pkl ← BM25 语料（(content,url) 去重追加） │
│   写入：build_vector_store() / app/rag/vector_store.py                  │
│   读取：retrieve() / app/rag/retriever.py（向量+BM25+RRF+来源权重）     │
│   上游：crawl→chunk→knowledge.build_knowledge_base（Celery）            │
│         upload-docs→PyMuPDF 解析→chunk→build_vector_store（同步）       │
│ 全局层 L0（名义存在）：                                                  │
│   GET /knowledge/documents → SELECT documents JOIN projects（无全文）    │
│ 平台记忆（agent-platform）：                                             │
│   FileMemoryStore：{OUTPUT_DIR}/private/studio_memory/{ns}.jsonl        │
│   （namespace=product_id，关键词搜索，MAX_ENTRIES=200，扁平无分层）     │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 各组件能力清单

| 组件 | 代码位置 | 能力 | 局限 |
|------|----------|------|------|
| 每项目向量库 | `app/rag/vector_store.py`、`backend/app/tasks/knowledge_tasks.py` | Chroma 持久化 + BM25 去重追加 | 仅限单项目内检索；无全局/领域入口 |
| 混合检索 | `app/rag/retriever.py` | 向量 + BM25 + RRF 融合 + 来源分级权重（`local://` 1.5x T0） | 必须传 `project_id`；无跨库检索 |
| 上传文档入库 | `backend/.../projects.py::upload_local_docs` | PDF/MD/TXT → 切片 → 入库 | ① 状态机守卫：仅 `PREPARING_DATA`/`WAITING_FOR_SOURCES` 可传；② 白名单 `pdf,txt,md` 与前端 `DOC_EXT`（含 doc/docx）不一致 → docx 实际 415；③ 不落 Document 表，知识页列表看不到上传文件 |
| 编辑器对话 RAG | `backend/.../editor.py::chat_with_editor` | work 模式召回 5 条项目切片注入 | 只查任务库；无领域/全局召回 |
| 全局知识 API | `backend/.../knowledge.py` | 跨项目文档元数据列表 | 无内容、无检索、无 scope 概念 |
| 图片素材 | `projects.py::upload_slide_asset` | 存 `outputs/assets/{pid}/` 返回 URL | 纯编辑器素材，**零分析、零入库** |
| 图片搜索 | `projects.py::search_project_images` + `app/search/image_search.py` | DDG 搜图 → `project_images` 表 | 网络图，无本地图分析 |
| 平台记忆 | `agent-platform/.../memory_store.py` | JSONL 追加、最近 N 条、关键词搜索 | 扁平；无分层（episodic/semantic/procedural）；无向量检索 |
| 模型路由 | `backend/.../product_studio_tasks.py` | NODE_MODEL_MAP：deepseek/minimax/siliconflow | MiniMax 仅文本模型 `MiniMax-M3`，**无视觉能力** |

### 1.3 关键差距清单（Gap Analysis）

- **G1（架构级）**：知识只有"任务级（L2）"和"名义全局（L0 只读列表）"两层，**没有领域级（L1）**——任务相似度、跨任务经验借用完全缺失。
- **G2（检索级）**：全局层不可检索。用户上传的企业文档、历史项目成果，无法在新建任务时被召回利用。
- **G3（模态级）**：图片不构成知识。上传的竞品图、UI 截图、图表只能当素材贴进报告，Agent 检索不到图中信息（无 OCR/视觉理解）。
- **G4（记忆级）**：平台记忆扁平化，无"会话记忆→任务记忆→全局知识"的沉淀路径。
- **G5（一致性）**：上传白名单前后端不一致；上传文件不回写 Document 表导致知识页列表与向量库不同步。
- **G6（权限）**：无知识资产可见性/范围控制（多用户时全局库会串数据）。

---

## 2. 目标架构：三层知识体系

预期优秀知识系统 = **全局知识（L0）+ 领域知识（L1）+ 任务知识（L2）**，检索时自下而上融合。

### 2.1 层定义与存储规划

| 层 | 内容 | 存储 | 现有资产 | 新增工作 |
|----|------|------|----------|----------|
| **L2 任务知识** | 单任务的爬取语料、上传文档、章节产出、图片分析、会话记忆 | `chroma_db/{project_id}` + `bm25_db/{project_id}` + documents/document_blocks/project_images 表 + `studio_memory/{product_id}.jsonl` | ✅ 已有 | 图片分析文本接入；会话记忆规范化 |
| **L1 领域知识** | 领域标签（行业×品类×模板类型）下的**经验包**：方法论、关键结论、数据口径、避坑记录；**任务相似度索引** | `chroma_db/_domain/{domain_tag}`（或单库加 scope 元数据）+ `domain_experiences` 表 + `task_similarity` 索引 | ❌ 无 | 相似度计算服务、经验包抽取任务、领域归档 |
| **L0 全局知识** | 企业文档、Obsidian Vault 同步、历史项目精华摘要 | `chroma_db/_global` + `knowledge_assets` 表（scope=global） | ⚠️ 仅 documents 元数据 | 全局向量库、全局检索 API、Vault 同步器、精华沉淀 |

> **设计原则（重要）**：三个层用**同一个向量库基础设施**（`build_vector_store`/`retrieve` 已按 project_id 分目录），只需把"库键"从 `project_id` 泛化为 `scope_id`（`global` / `domain:{tag}` / `{project_id}`），即可复用全部现有代码。**不要**为每层引入新的向量库技术栈。

### 2.2 任务相似度判别（L1 的核心机制）

"判别哪些任务相似度高可以互相借用"落地为三步：

```
① 任务画像（创建/完成时生成）
   topic embedding（复用 bge-small-zh-v1.5，零新增依赖）
   + template_type（product/prd/presentation…）
   + 领域标签（LLM 从 topic 抽取：行业、品类、场景，如 {"industry":"消费电子","category":"智能穿戴"}）
   → 写入 projects 表新列：topic_embedding(json)、domain_tags(json)

② 相似检索（新建任务时触发）
   sim(新任务, 历史任务) = 0.6·cos(topic_emb) + 0.3·标签重合率 + 0.1·模板一致
   阈值建议：sim ≥ 0.75 视为"可借用"；0.5~0.75 仅参考
   → GET /projects/{id}/similar 返回 top-k：{project_id, topic, sim, 可借用经验摘要}

③ 经验借用（检索注入）
   仅注入相似任务的【经验包摘要】（LLM 抽取的 lessons/结论/结构），
   **绝不**注入对方原始语料——避免污染当前任务向量库、避免上下文超限。
   editor/chat 与报告工作流的 system prompt 增加：
   【相似任务经验】<3-5 条领域经验包>
```

经验包抽取（任务完成时异步执行，Celery）：

```
complete 项目 → summarize_task_experience(project_id)
  ├─ 用 LLM 将 (大纲+各章节结论+数据亮点+失败/修正记录) 压缩为 ≤800字 经验包
  ├─ 落 domain_experiences 表（project_id, domain_tags, summary, created_at）
  └─ 写入 chroma_db/_domain/{tag}（供领域级检索）
```

### 2.3 三层融合检索编排

新建任务 / 编辑器对话的检索顺序（**先近后远**，成本递减）：

```
retrieve_context(query, project_id):
  1. L2 任务库    k=5   ← 现状已有
  2. L1 领域库    k=3   按当前项目 domain_tags 检索
  3. L0 全局库    k=2   企业文档/Vault/历史精华
  → RRF 融合（L2 权重 1.0，L1 0.8，L0 0.6，防止全局噪声淹没任务事实）
```

> 全局库必须**降权**而非排除——否则"竞品 A 的报告结论"会污染"竞品 B 的分析"。

---

## 3. Obsidian（及同类工具）集成调研

### 3.1 调研结论：Obsidian 完全可插入，且有四条成熟路径

Obsidian Vault 本质是**本地 Markdown 目录**（frontmatter + tags + `[[wiki links]]`），因此集成难度低、风险小。可选方案按"侵入性从低到高"排列：

| 方案 | 机制 | 优点 | 缺点 | 适用 |
|------|------|------|------|------|
| **A. Vault 文件系统直读**（推荐起步） | 后端直接扫描 vault 目录，解析 `.md` 的 frontmatter/tags/wiki-links，切片入全局库 | 零依赖、零插件、离线可用、可控性最强 | 无法感知 Obsidian 实时打开的文件（用文件 mtime 增量同步即可） | 后台定时同步、批量入库 |
| **B. obsidian-local-rest-api 插件** | 社区插件，本地起 REST 服务：`https://127.0.0.1:27124`（HTTPS）/ `27123`（HTTP），`Authorization: Bearer <key>`；端点 `/vault/{path}`（读写）、`/search/simple/`（全文搜索）、`/search/`（JsonLogic 结构化搜索）、`/vault/{path}/frontmatter/{key}` | 官方文件级 API + 全文搜索，比裸文件系统多出"搜索"能力；自带 MCP server（`/mcp/`） | 需用户安装插件并开 HTTP；自签名证书 | 需要实时全文搜索、需要把 Obsidian 暴露成 Agent 工具时 |
| **C. MCP Server（obsidian-mcp-rest / mcp-obsidian）** | 通过 MCP 协议把 vault 暴露给 Agent 当工具调用 | 与 Agent 工具生态天然融合（本项目 agent-platform 将来可接） | 引入 MCP 运行时依赖；适合"Agent 主动查笔记"而非"批量入库" | Phase 3：Agent 工具化 |
| **D. 云端/WebDAV/同步盘** | 通过 iCloud/坚果云/WebDAV 同步目录 | 多端 | 同步延迟、权限复杂 | 不推荐，除非多设备强需求 |

> 同类工具备选（如需图形化知识库 UI 而非笔记工具）：**NocoDB / AFFiNE / AppFlowy** 均可通过文件/API 导入，但成熟度与生态均不如 Obsidian，**建议直接选 Obsidian**。

### 3.2 推荐接入设计（方案 A 为主 + B 可选）

```
配置（config.py 新增）：
  OBSIDIAN_VAULT_PATH: str = ""        # 留空 = 功能关闭
  OBSIDIAN_SYNC_INTERVAL_MIN: int = 30
  OBSIDIAN_REST_API: str = ""          # 如 https://127.0.0.1:27124（可选增强）
  OBSIDIAN_REST_API_KEY: str = ""

同步管道（Celery 周期任务 obsidian.sync_vault）：
  1. 扫描 vault/**/*.md（跳过 .obsidian 配置目录）
  2. 增量：按 mtime > last_sync 过滤
  3. 解析 frontmatter（tags/topic/type）+ 正文 → 切片（复用 app/rag/chunker）
  4. metadata: {url: "obsidian://{relative_path}", scope: "global", tags: [...]}
  5. build_vector_store(chunks, project_id="global")   ← 全局库复用现有代码
  6. 记录 knowledge_assets 表（来源=obsidian，path，mtime，chunk_count）

可选增强（配置了 OBSIDIAN_REST_API 时）：
  - 用 /search/simple/ 做"实时全文搜索"兜底
  - 监听 vault 变更（轮询 mtime 即可，无需插件事件）
```

> **关键设计**：vault 条目统一落 **L0 全局库**，并以 `obsidian://` 为 source URL——现有来源权重（T0/T1/T2/T3）与 RRF 融合**自动生效**，`local://` 的 1.5x 权重逻辑可顺带扩展给 `obsidian://`。

### 3.3 数据模型映射

```yaml
Obsidian 笔记:
  frontmatter.tags      → knowledge_assets.tags（领域标签来源之一）
  frontmatter.type      → asset_type (note/knowledge/daily…)
  正文                   → 切片入全局向量库
  [[wiki links]]        → 暂不解析为图结构（Phase 3 可做知识图谱/GrapRAG）
  附件 images/          → 走第 4 节的图片分析管道
```

---

## 4. 图片上传知识库 + MiniMax 视觉分析入库

### 4.1 MiniMax 视觉能力调研结论（已验证）

- **模型**：`minimax-vl-01`（MiniMax VL-01，HuggingFace: `MiniMaxAI/MiniMax-VL-01`），官方用于图片理解/OCR/图表提取。
- **接入方式**：OpenAI 兼容 Chat Completions，图片以 `image_url` 内容块传入：
  - 端点：`https://api.minimax.chat/v1/text/chatcompletion_v2`（或 OpenAI 兼容 `/v1/chat/completions`）
  - 认证：`Authorization: Bearer {MINIMAX_API_KEY}` —— **项目已有该 Key，直接复用**
  - 图片格式：base64 data URL（`data:image/png;base64,...`）或 http(s) URL；单图 ≤20MB，单请求 ≤6 张
  - 消息结构（标准 OpenAI 多模态格式）：
    ```json
    {"model": "minimax-vl-01",
     "messages": [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}},
        {"type": "text", "text": "请分析这张图…"}]}]}
    ```
- **能力场景**：`describe`（描述）/ `ocr`（文字提取）/ `ui-review`（UI 评审）/ `chart-data`（图表数据提取）/ `object-detect`（主体识别）——官方 skills 已定义五种模式，直接映射为分析提示词模板。
- **注意**：`MiniMax_understand_image` 的 MCP 工具（Token Plan）需要特定套餐；**普通 `MINIMAX_API_KEY` 走 chatcompletion_v2 即可，无需 Token Plan**。

### 4.2 图片入库管道设计

```
前端（FileUploader / ImageSearch 增加"图片入库"按钮或勾选）
  │  POST /projects/{id}/kb-images  (multipart, 可多张)
  ▼
后端 projects.py::upload_kb_images
  ├─ 校验：扩展名 png/jpg/jpeg/webp、大小 ≤20MB/张（与 VL 限制对齐）
  ├─ 落盘：outputs/private/kb_images/{project_id}/{uuid}.{ext}（私有目录，不公开）
  ├─ 写 project_images 行（source='uploaded', status='analyzing'）
  └─ 触发 Celery：knowledge.analyze_image.delay(image_id)
  ▼
Celery knowledge_tasks.py::analyze_image
  ├─ 1. 读图 → base64
  ├─ 2. 调 MiniMax VL（结构化输出，response_format=json_object）：
  │     {
  │       "summary": "80-150字中文概述（主体、场景、关键信息）",
  │       "ocr_text": "图中全部文字，无则空串",
  │       "tags": ["竞品", "UI截图", "智能手表"],
  │       "subject": "核心主体/产品名",
  │       "scene": "使用场景",
  │       "chart_data": "图表类图片的数据要点，非图表则空"
  │     }
  ├─ 3. 文本化：summary + ocr_text + tags → 1~3 个切片
  │     metadata: {url: "image://{project_id}/{uuid}.{ext}", scope: project_id}
  ├─ 4. build_vector_store(切片, project_id)   ← 复用现有任务库
  ├─ 5. 更新 project_images：analysis_text / tags / status='ready'
  └─ 6. 失败重试 2 次（Celery autoretry），仍失败置 status='failed'（不阻塞项目）
  ▼
消费端
  ├─ editor/chat 与报告工作流：图片知识以文本切片形式被混合检索召回（零改动）
  ├─ KnowledgePage：图片卡片显示分析状态（待分析/已入库/失败）与摘要、标签
  └─ Phase 3 可选：CLIP/bge-visual 图文向量直查（图片语义检索）
```

### 4.3 配置项与代码改动点

```python
# config.py 新增（全部有默认值，不配即关闭）：
MINIMAX_VISION_MODEL: str = "minimax-vl-01"
MINIMAX_VISION_ENDPOINT: str = "https://api.minimax.chat/v1/text/chatcompletion_v2"  # 或 OpenAI 兼容
KB_IMAGE_MAX_MB: int = 20
KB_IMAGE_MAX_PER_BATCH: int = 6
```

改动点清单：

| 层 | 文件 | 改动 |
|----|------|------|
| 模型 | `app/llm/client01.py` 或新建 `app/llm/vision.py` | `analyze_image(image_b64, prompt, schema) -> dict`，httpx 直调 VL 端点（参考 agent-platform `LLMClient` 风格） |
| 任务 | `backend/app/tasks/knowledge_tasks.py` | 新增 `knowledge.analyze_image` Celery 任务 |
| API | `backend/app/api/v1/endpoints/projects.py` | 新增 `POST /projects/{id}/kb-images` |
| 模型 | `backend/app/models/project_image.py` | 新增列：`source`、`status`、`analysis_text`、`tags`、`file_path` |
| 迁移 | `backend/alembic/versions/` | 新增迁移（project_images 扩展列 + projects 的 topic_embedding/domain_tags） |
| 前端 | `FileUploader.tsx` / `ImageSearch.tsx` / `KnowledgePage.tsx` | 图片入库入口 + 分析状态展示 |

### 4.4 检索与消费示例

```
用户提问："我们的智能手表竞品 UI 有什么亮点？"
  → L2 任务库召回："image://.../xxx.png 概述：竞品主界面采用大圆角卡片…"（来自 VL 分析）
  → 回答可引用图片，且图片素材本来就在项目素材库里，可直接插入报告/PPT
```

---

## 5. 其他必要配件与架构分析

### 5.1 记忆分层升级（G4）

现状 `FileMemoryStore` 是扁平 JSONL（namespace=product_id）。升级为三级沉淀：

```
episodic（会话记忆）  : 运行中的 finding/decision/plan（现状 JSONL 即此层）
        │  任务结束 → LLM 压缩（memory compaction）
task（任务记忆）      : session_summary.md + 经验包（入 domain_experiences）
        │  精华筛选（LLM 判定"可复用性"≥阈值）
global（全局知识）    : 入 L0 全局向量库（来源=studio_memory）
```

建议扩展 `MemoryEntry.kind` 枚举为 `finding / decision / plan / summary / lesson`，`search()` 升级为"关键词 + 向量"双通道（复用 bge embedding）。

### 5.2 知识生命周期管理

| 环节 | 机制 |
|------|------|
| 入库 | 所有写入统一走 `build_vector_store`（已有 (content,url) 去重）；图片/文档/Obsidian 三类来源打 `source` 标记 |
| 去重 | 向量近似去重：新切片与库内 top-1 相似度 >0.95 丢弃（全局库启用，任务库已有文本去重） |
| 版本 | 上传同名文件：新切片追加 + 旧切片标记 superseded（metadata.version），检索优先新版 |
| 失效 | `knowledge_assets.ttl`/`stale_at`；Obsidian 删除的笔记同步删除对应切片（按 `obsidian://` url 前缀清理） |
| 删除 | 删除项目时已级联清理 DB 与磁盘（delete_project），需同步清理 `chroma_db/{project_id}`、`bm25_db/{project_id}`、`kb_images/` 目录（当前缺口） |

### 5.3 全局检索 API 与前端面板升级

```
GET /api/v1/knowledge/search?q=...&scope=global|domain|task&project_id=...&k=10
  → 三层融合结果（每项含 scope、source、url、snippet、score）

KnowledgePage 升级为三 Tab：
  文档库（现有列表，补全文搜索框）
  图片知识（本地图分析状态 + DDG 图库）
  领域与全局（领域标签管理、相似任务列表、Obsidian 同步状态）
```

### 5.4 权限与多租户（G6）

- `knowledge_assets` 增加 `owner_id`、`visibility`（private/shared/org）、`scope`。
- 检索时按当前用户过滤；`global` 库默认仅本人可见，`org` 级需管理端开启。
- 现有 `ProjectImage`/`Document` 均已有 `project_id`，沿 `projects.owner_id` 继承即可。

### 5.5 Embedding 与向量库选型结论

- **保持现状**：`BAAI/bge-small-zh-v1.5`（本地 SentenceTransformer，中文场景够用、零 API 成本）+ Chroma + BM25 混合。**不需要**为三层知识引入新向量库。
- 可选优化（Phase 3）：全局库换 `bge-m3`（多语言+长文本）或 `text-embedding-3`（若已有 API）；图片语义检索加 CLIP 类模型。
- 风险提示：本地 embedding 首次加载需从 HF 下载模型（项目已配 `HF_ENDPOINT=hf-mirror.com` 镜像），服务器需可访问。

### 5.6 顺手修复的一致性问题（G5）

| 问题 | 修复 |
|------|------|
| 前端 `DOC_EXT` 含 doc/docx/markdown，后端 `ALLOWED_UPLOAD_EXTS` 默认 `pdf,txt,md` → docx 上传 415 | 后端白名单改为 `pdf,md,markdown,txt,doc,docx`（本地解析需支持 docx，可加 `python-docx` 或先收紧前端去掉 doc/docx） |
| 上传文档不写 Document 表，知识页列表看不到 | upload 成功后写一条 `Document(section_title=文件名, section_order=0, source_urls=local://…)` 或新增 `knowledge_assets` 记录 |
| 删除项目不清理向量库目录 | delete_project 中删除 `chroma_db/{pid}`、`bm25_db/{pid}`、`kb_images/{pid}` |
| editor/chat 的 `project_id` 可能为空时检索报错 | 空则跳过 L2 仅用 L1/L0 |

### 5.7 实施路线图

| Phase | 内容 | 预计工作量 | 价值 |
|-------|------|-----------|------|
| **P1（快速见效）** | 图片入库管道 + MiniMax VL 分析（4.2 全链路）；一致性修复（5.6）；`/knowledge/search` 全局检索（先复用文档表全文 + 现有向量库） | 2~3 人日 | 图片成为知识；全局可检索 |
| **P2（核心架构）** | scope_id 泛化（global/domain/task 三库）；任务相似度 + 相似任务面板；经验包抽取与注入；知识资产表与生命周期 | 4~6 人日 | 三层知识体系成型，跨任务借力 |
| **P3（增强）** | Obsidian Vault 同步（3.2）；记忆分层与 compaction（5.1）；MCP 工具暴露知识检索；CLIP 图文检索；权限粒度 | 3~5 人日 | 外部知识源接入、记忆自沉淀 |

**P1 即可先落地，P2 是架构主干，P3 为可选项。**

---

## 6. 参考来源

**Obsidian 集成：**
- [obsidian-local-rest-api（插件，含 MCP server，官方端点文档）](https://github.com/coddingtonbear/obsidian-local-rest-api)
- [mcp-obsidian（PyPI，文件级 MCP server）](https://pypi.org/project/mcp-obsidian/)
- [obsidian-mcp-rest（基于 local REST API 的 MCP 实现）](https://github.com/PublikPrinciple/obsidian-mcp-rest)

**MiniMax 视觉：**
- [minimax-vision-mcp（MiniMax VL 接入参考实现：chatcompletion_v2 端点 + image_url base64 格式）](https://github.com/wenjiaqi8255/minimax-vision-mcp)
- [MiniMax-AI/skills —— vision-analysis（官方五种分析模式：describe/ocr/ui-review/chart-data/object-detect）](https://github.com/MiniMax-AI/skills/blob/main/skills/vision-analysis/SKILL.md)
- [MiniMax 开放平台文档（OpenAI 兼容 chat 接口）](https://platform.minimaxi.com/docs/api-reference/text-chat-openai.md)
- [MiniMax VL-01 模型页（HuggingFace）](https://huggingface.co/MiniMaxAI/MiniMax-VL-01)
- [MiniMax Provider 说明（OpenClaw docs，模型与端点汇总）](https://docs.openclaw.ai/zh-TW/providers/minimax)

**RAG/记忆架构参考：**
- [企业级 RAG 系统全阶段实践指南](https://cloud.baidu.com/article/5317643)
- [LongRAG、Self-RAG 与 GraphRAG 选型分析](https://cloud.tencent.cn/developer/article/2593967)

---

## 7. 实施记录（P1-P3 全量落地，2026-08）

> 以下变更已按本文档设计全部实现并通过验证：
> 后端 57 项既有 pytest 全绿 + 知识系统端到端冒烟测试通过 + 前端 `tsc -b` 编译通过 + `vite build` 构建通过。

### 7.1 已交付功能清单

| 阶段 | 功能 | 落地位置 |
|------|------|----------|
| P1 | 图片知识库入库 API（多图上传→私有落盘→异步 VL 分析） | `projects.py::upload_kb_images` + `knowledge_tasks.py::analyze_image` |
| P1 | MiniMax VL 客户端（base64/URL 入参、结构化 JSON 输出、端点兼容） | `app/llm/vision.py`（新） |
| P1 | 图片分析字段（source/status/analysis_text/tags/file_path）+ 状态机 | `models/project_image.py` + `repositories::create_kb_image/update_image_analysis` |
| P1 | 三层融合检索 API（任务/领域/全局 + documents 文本兜底） | `knowledge.py::search_knowledge` + `retriever.retrieve_scoped` |
| P1 | 一致性修复：白名单对齐（含 docx，需 python-docx）、上传回写 Document 表、删除项目清理向量库/图片目录、editor chat 空 project_id | `config.py`、`projects.py`、`editor.py` |
| P2 | 向量库 scope 泛化（global / domain:{tag} / {project_id} 三库共用基础设施） | `vector_store.py`、`retriever.py` |
| P2 | 任务画像（topic 向量 512 维 + LLM 领域标签）与相似度服务 | `task_similarity.py`（新） |
| P2 | 相似任务 API（含可借用经验文本） | `projects.py::get_similar_projects` |
| P2 | 经验包抽取（LLM 压缩→DB+领域向量库，完成时自动触发） | `knowledge_tasks.py::summarize_experience` + `report_workflow.py` 钩子 |
| P2 | 知识资产登记表 + 领域经验表 + Alembic 0006 迁移 | `models/knowledge_asset.py`、`models/domain_experience.py`（新） |
| P3 | Obsidian Vault 增量同步（frontmatter 解析、mtime 增量、Celery Beat 周期） | `knowledge_tasks.py::sync_obsidian_vault` + `celery_app.py` beat |
| P3 | 记忆分层：kind 枚举（episodic/task/summary）、compact() 压缩、promotable()、分层检索加权 | `agent-platform/.../memory_store.py` |
| P3 | 前端三层 Tab 知识页（检索/图片知识/领域与全局）、图片上传入库组件、相似任务与经验面板 | `KnowledgePage.tsx`、`FileUploader.tsx`（imageKb 模式）、`api.ts`/`types/api.ts` |

### 7.2 配置项（.env 可覆盖）

```dotenv
# P1 图片视觉分析（复用现有 MINIMAX_API_KEY）
MINIMAX_VISION_MODEL=minimax-vl-01
MINIMAX_VISION_ENDPOINT=https://api.minimax.chat/v1/text/chatcompletion_v2
KB_IMAGE_MAX_MB=20
KB_IMAGE_MAX_PER_BATCH=6

# P2 三层检索与相似度
SIMILARITY_BORROW_THRESHOLD=0.55
SIMILARITY_TOP_K=5
RETRIEVE_TASK_K=5
RETRIEVE_DOMAIN_K=3
RETRIEVE_GLOBAL_K=2
RETRIEVE_SCOPE_WEIGHTS={"task":1.0,"domain":0.8,"global":0.6}
EXPERIENCE_MAX_CHARS=800

# P3 Obsidian（留空=关闭）
OBSIDIAN_VAULT_PATH=
OBSIDIAN_SYNC_INTERVAL_MIN=30
OBSIDIAN_REST_API=
OBSIDIAN_REST_API_KEY=
```

### 7.3 上线前注意

1. 执行 `alembic upgrade head`（或重启应用由 create_all 建新表，再跑迁移补列）。
2. `pip install python-docx`（可选：仅 docx 上传需要；未安装时上传返回明确错误）。
3. 图片 VL 分析依赖网络可达 `api.minimax.chat` 且 `MINIMAX_API_KEY` 有效；失败自动重试 2 次后置 failed，不阻塞主流程。
4. 本地 embedding 模型（bge-small-zh-v1.5）首次相似度计算会加载 ~100MB 模型（已在冒烟测试中验证可用）。
