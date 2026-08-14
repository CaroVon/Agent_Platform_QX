# DEV_SECTION_LOOP — section_writer → Canvas 单点测试循环

> **用途**: 绕过 Celery/Redis，反复重跑 section_writer → DocumentBlock → Canvas 渲染流程，秒级验证排版修改效果。
>
> **适用场景**: 调试 `app/report/section_writer.py`（LLM 撰写逻辑）和 `frontend/src/lib/dataTransform.ts`（Markdown → Canvas 排版引擎）。

---

## 为什么需要这个工具？

当前修改 section_writer 到画布排版的流程，每次都需要：

```
创建项目 → 等 Phase 1 搜索 → 审核资料 → 等 Phase 2 大纲 → 审批大纲 → 等 Phase 3 撰写 → 打开编辑器
```

全流程耗时 5-10 分钟，其中 Phase 1/2 在排版调试期间**完全不需要变更**。

这个工具将流程压缩为：

```
（一次性）创建项目 → 审批到 WAITING_FOR_OUTLINE
（反复）  python scripts/dev_section_loop.py run  →  刷新浏览器
```

每次迭代只需 30-60 秒（取决于章节数和 LLM 响应速度）。

---

## 核心原理

```
┌─────────────────────────────────────────────────────────────┐
│  检查点（保存一次，反复使用）                                │
│  ├── Project: topic, outline_content, template_type, depth  │
│  ├── chroma_db/{id}/ — 向量库（只读）                       │
│  ├── bm25_db/{id}/ — BM25 索引（只读）                     │
│  └── crawled_data_{id}.json — 搜索结果（只读）              │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  dev_section_loop.py run（每次重放）                         │
│  1. 清空 document_blocks, documents, project_images         │
│  2. 重置 project status → DRAFTING                          │
│  3. 逐章调用 write_section()（直接 import，无 Celery）       │
│  4. 保存 DocumentBlock → 设置 COMPLETED                     │
│  5. 打印耗时/字数报告                                       │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  前端（无需重启）                                            │
│  GET /api/v1/projects/{id}/blocks → convertBlocksToKonvaSlides │
│  → Canvas 渲染 → 刷新浏览器即可看到新内容                    │
└─────────────────────────────────────────────────────────────┘
```

关键设计：
- **绕过 Celery**: `write_section()` 是纯 Python 函数，直接 import 调用
- **不重建知识库**: Chroma + BM25 在 Phase 2 已构建，只读不写
- **不触发图片搜索**: 默认 `--no-images`，节省 API 调用
- **章节级 Block**: 每章节一个 DocumentBlock，与生产环境一致

---

## 快速上手

### 1. 创建检查点项目（只做一次）

通过前端或 API 创建一个项目，跑到 **WAITING_FOR_OUTLINE** 状态：

```
前端操作:
  Dashboard → 新建项目 → 输入主题 → 等待搜索完成
  → 审核资料（全选或按需） → 等待大纲生成
  → 审批大纲 → 停留在 WAITING_FOR_OUTLINE（不要点"开始撰写"！）
```

此时项目处于"大纲已就绪，尚未撰写"的完美检查点状态。

### 2. 首次运行

```bash
cd /home/administrator/dev/agents/QX_product_agent
source venv/bin/activate

# 指定项目 ID 运行（自动保存为检查点）
python scripts/dev_section_loop.py run --project <你的项目UUID>
```

输出示例：
```
═══ Section Writer Dev Loop ═══
Project:  445c499f-b2ed-47da-b005-462f12fbdf59
Mode:     LIVE (已写入数据库)
Results:  7 success, 0 failed, 45.2s total

  ✅ 1. 市场概况与趋势分析
     2,847 chars | 6.3s
  ✅ 2. 核心技术解析
     3,215 chars | 7.1s
  ✅ 3. 竞品分析
     4,102 chars | 8.2s
  ...

Total: 24,156 chars across 7 sections
Canvas: http://localhost:8000/projects/445c499f-.../editor
═══ ═══ ═══ ═══ ═══ ═══ ═══ ═══
```

### 3. 迭代循环

```bash
# 修改 section_writer.py 中的 Prompt...
vim app/report/section_writer.py

# 重跑（自动使用已保存的检查点项目）
python scripts/dev_section_loop.py run

# 修改 dataTransform.ts 中的排版逻辑...
vim frontend/src/lib/dataTransform.ts

# 重跑（前端无需重启，只需刷新浏览器）
python scripts/dev_section_loop.py run

# 浏览器中刷新编辑器页面查看效果
```

---

## 命令参考

### `run` — 重跑章节撰写

```bash
# 使用已保存的检查点项目（最常用）
python scripts/dev_section_loop.py run

# 指定项目（首次使用 / 切换项目）
python scripts/dev_section_loop.py run --project <uuid>

# 只重跑单个章节（模糊匹配标题）
python scripts/dev_section_loop.py run --section "竞品分析"

# 预览模式——输出内容但不写入数据库
python scripts/dev_section_loop.py run --dry-run

# 允许图片搜索（默认关闭以加速）
python scripts/dev_section_loop.py run --no-images
```

### `status` — 查看检查点状态

```bash
python scripts/dev_section_loop.py status
```

输出：
```
═══ Dev Section Loop Status ═══

📌 已保存检查点:
   Project ID:  445c499f-b2ed-47da-b005-462f12fbdf59
   Topic:       智能眼镜
   Saved at:    2026-07-01T10:30:00+00:00

📋 项目当前状态:
   Topic:       智能眼镜
   Status:      completed
   Template:    product
   Depth:       10
   Sections:    7
     - 1. 市场概况与趋势分析
     - 2. 核心技术解析
     ...
   Blocks:      7

═══ ═══ ═══ ═══ ═══ ═══ ═══ ═══
```

---

## 典型工作流

### 场景 1：调试 section_writer Prompt

```bash
# 1. 修改 Prompt
vim app/report/section_writer.py  # 修改 _write_text_section 中的 prompt 模板

# 2. 预览效果（不写库，快速迭代）
python scripts/dev_section_loop.py run --dry-run

# 3. 满意后正式运行
python scripts/dev_section_loop.py run

# 4. 浏览器查看 Canvas 排版效果
```

### 场景 2：调试 dataTransform 排版

```bash
# 1. 修改排版逻辑
vim frontend/src/lib/dataTransform.ts

# 2. 重跑章节（保留同样的 LLM 输出，验证排版变化）
python scripts/dev_section_loop.py run

# 3. 刷新浏览器
# 无需重启 Vite，HMR 自动生效
```

### 场景 3：调试单个章节

```bash
# 只重跑"竞品分析"章节，其他章节保持不变
python scripts/dev_section_loop.py run --section "竞品分析"
```

### 场景 4：对比不同 search_depth 的效果

```bash
# 修改数据库中的 search_depth
# 然后重跑对比
python scripts/dev_section_loop.py run
```

---

## 前置条件

| 条件 | 说明 |
|------|------|
| Python venv 已激活 | `source venv/bin/activate` |
| `.env` 配置正确 | DEEPSEEK_API_KEY 等已设置 |
| 项目已到 WAITING_FOR_OUTLINE | 大纲已生成、知识库已构建 |
| 后端在运行（可选） | 仅查看 Canvas 时需要（`start_all.sh`） |

**不需要**：
- ❌ Celery Worker 运行
- ❌ Redis 运行
- ❌ Phase 1/2 重新执行

---

## 文件说明

| 文件 | 说明 |
|------|------|
| `scripts/dev_section_loop.py` | 主脚本 |
| `scripts/.dev_checkpoint.json` | 检查点记录（gitignore） |
| `DEV_SECTION_LOOP.md` | 本文档 |

---

## 常见问题

### Q: "未指定 project_id，且无已保存的检查点"

**A**: 首次使用需要 `--project` 参数指定项目 UUID：
```bash
python scripts/dev_section_loop.py run --project <你的项目UUID>
```
之后会自动保存检查点，直接 `python scripts/dev_section_loop.py run` 即可。

### Q: "项目大纲为空"

**A**: 项目尚未完成 Phase 2（大纲生成）。需要先通过前端审批大纲，确保项目到达 `WAITING_FOR_OUTLINE` 状态。

### Q: 某些章节撰写失败

**A**: 脚本会跳过失败的章节继续执行。查看错误信息判断是 API Key 问题还是网络问题。已成功的章节不受影响。

### Q: 如何切换项目？

**A**: 使用 `--project` 参数指定新的项目 UUID，会自动更新检查点：
```bash
python scripts/dev_section_loop.py run --project <新项目UUID>
```

### Q: run 之后前端看不到新内容？

**A**: 确认：
1. 后端正在运行（`start_all.sh`）
2. 浏览器刷新了编辑器页面（Ctrl+R）
3. 项目状态是 COMPLETED（`python scripts/dev_section_loop.py status` 确认）

---

## 实现细节

### 清理策略

每次 `run` 会清除以下表中的该项目的所有记录：
- `document_blocks` — Canvas 渲染的数据源
- `documents` — 章节快照（非必须，但保持清洁）
- `project_images` — 图片搜索缓存（避免新旧图片混淆）

不清除：
- `projects` 表（保留 topic、outline、template 等）
- `chroma_db/` 和 `bm25_db/`（知识库，重建成本高）
- `crawled_data_*.json`（搜索结果）

### 与 Celery 工作流的对比

| 维度 | Celery (生产) | dev_section_loop (开发) |
|------|---------------|------------------------|
| 启动耗时 | 10-30s（Worker 初始化） | <1s（直接 import） |
| 依赖 | Redis + Celery Worker | 无 |
| 图片搜索 | 每章自动搜索 | 默认跳过 |
| Document 快照 | 写入 | 跳过 |
| 重试机制 | 指数退避 auto-retry | 无（失败即跳过） |
| 适用场景 | 生产环境 | 本地排版调试 |
