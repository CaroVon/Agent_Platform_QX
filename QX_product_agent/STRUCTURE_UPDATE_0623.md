# QX Product Agent — 结构变更记录 (STRUCTURE_UPDATE_0623)

> **日期**: 2026-06-23 | **基准版本**: v0.2 (commit `e5ab74a`)
>
> 本文档记录当前工作树相对于 v0.2 发布版本的**全部代码结构变更**，
> 含新增模块、删除模块、功能重构及 Bug 修复的完整实现过程。

---

## 目录

1. [变更总览](#1-变更总览)
2. [🆕 多态模板系统：product / design 双模式](#2--多态模板系统product--design-双模式)
3. [🆕 幻灯片编辑器重构：单实例 → 16:9 多实例](#3--幻灯片编辑器重构单实例--169-多实例)
4. [🆕 幻灯片图片暂存 API](#4--幻灯片图片暂存-api)
5. [🆕 手动导出 PDF 真实渲染 (告别 Mock)](#5--手动导出-pdf-真实渲染-告别-mock)
6. [♻️ 工作流重构：切断自动 PDF 生成](#6-️-工作流重构切断自动-pdf-生成)
7. [🐛 Bug 修复：BM25 检索降级](#7--bug-修复bm25-检索降级)
8. [🐛 Bug 修复：PDF 导出目录缺失 + HTML 注入风险](#8--bug-修复pdf-导出目录缺失--html-注入风险)
9. [🔧 搜索召回量调整](#9--搜索召回量调整)
10. [📋 完整变更文件索引](#10--完整变更文件索引)

---

## 1. 变更总览

```
新增文件:  2 个
  + app/llm/prompts.py                          # Prompt 工厂（多态模板中枢）
  + backend/alembic/versions/24f2c9f525d7_...    # Alembic 迁移：projects 表 +template_type

删除文件:  0 个

修改文件: 16 个
  Python 后端: 10 个
  TypeScript 前端:  4 个
  配置/文档:       2 个
```

---

## 2. 🆕 多态模板系统：product / design 双模式

### 功能概述

用户创建项目时可选择报告模板类型，系统根据模板类别切换完全不同的 System Prompt 体系，生成风格迥异的分析报告。

- **product（产品预研，默认）**: 聚焦产品定位、功能、CMF、竞品、定价 —— 商业分析师视角
- **design（工业设计推演）**: 聚焦设计语言、人机工程、CMF、结构堆叠 —— 工业设计师视角

### 数据流

```
CreateProjectModal (前端选择模板)
  → POST /api/v1/projects {topic, template_type}
    → Project 表写入 template_type 字段
      → Phase 2: generate_outline_workflow → repo.get_project_template()
        → generate_outline_task(project_id, template_type)
          → PromptFactory.get_outline_prompt("product"|"design")
            → LLM 生成大纲
      → Phase 3: run_draft_sections_workflow → repo.get_project_template()
        → write_single_section(project_id, title, idx, template_type)
          → PromptFactory.get_section_prompt("product"|"design")
            → LLM 撰写章节
```

### 涉及脚本（6 个）

| 文件 | 角色 | 变更类型 |
|------|------|----------|
| `app/llm/prompts.py` | **新增** — Prompt 工厂，集中管理 4 套 System Prompt（product 大纲/章节 + design 大纲/章节） | new |
| `app/planner/outline_generator.py` | 重构 — 原先硬编码 Product System Prompt，现委托给 `PromptFactory.get_outline_prompt(template_type)` | modified |
| `app/report/section_writer.py` | 重构 — 原先硬编码 `PRODUCT_RESEARCHER_SYSTEM_PROMPT`，现委托给 `PromptFactory.get_section_prompt(template_type)` | modified |
| `backend/app/tasks/report_workflow.py` | 扩展 — Phase 2/3 新增 `template_type` 透传链：`repo.get_project_template()` → LLM 调用 | modified |
| `backend/app/tasks/writing_tasks.py` | 扩展 — `generate_outline_task` / `write_single_section` 签名新增 `template_type` 参数，向 LLM 层透传 | modified |
| `backend/app/repositories/project_repo.py` | 扩展 — 新增 `get_project_template()` 方法，从 DB 读取项目的 `template_type` 字段 | modified |

### 数据模型变更

| 位置 | 变更 |
|------|------|
| `backend/app/models/project.py:60` | 新增列 `template_type: Mapped[str]` (String(50), server_default='product') |
| `backend/alembic/versions/24f2c9f525d7_...` | 新增 Alembic 迁移：`ALTER TABLE projects ADD COLUMN template_type` |
| `backend/app/schemas/__init__.py` | `ProjectCreateRequest` 新增 `template_type` 可选字段；`ProjectResponse` / `ProjectStatusResponse` 新增 `template_type` 字段 |

### 前端适配

| 文件 | 变更 |
|------|------|
| `frontend/src/components/projects/CreateProjectModal.tsx` | 新增模板选择 UI（两个卡片按钮：📊 产品预研 / 🎨 工业设计推演），提交时附带 `template_type` |
| `frontend/src/pages/WorkspacePage.tsx` | 模板选择器选项从 3 个旧选项精简为 2 个（product / design），新增 `useEffect` 从后端 `statusData.template_type` 初始化选中值 |
| `frontend/src/types/api.ts` | `ProjectCreateRequest` / `ProjectResponse` / `ProjectStatusResponse` 新增 `template_type` 字段 |

### 核心实现代码

`app/llm/prompts.py` — 4 套 System Prompt 的 PromptFactory:

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
        """获取大纲生成 System Prompt。"""
        if template_type == "design":
            return DESIGN_OUTLINE_SYSTEM   # 工业设计师 Persona
        return PRODUCT_OUTLINE_SYSTEM      # 产品战略总监 Persona

    @staticmethod
    def get_section_prompt(template_type: str = "product") -> str:
        """获取章节撰写 System Prompt。"""
        if template_type == "design":
            return DESIGN_SECTION_SYSTEM   # 工业设计评论家 Persona
        return PRODUCT_SECTION_SYSTEM      # 商业咨询顾问 Persona
```

---

## 3. 🆕 幻灯片编辑器重构：单实例 → 16:9 多实例

### 功能概述

将 `BlockEditor` 从"单 Tiptap 实例 + prose 长文本排版"重构为"每个 DocumentBlock → 独立 SlidePage 画布"的幻灯片编辑器架构。

### 架构对比

| 维度 | 旧架构 | 新架构 |
|------|--------|--------|
| 编辑器实例数 | 1 个 Tiptap | N 个独立 Tiptap（每 block 一个） |
| 视觉效果 | prose 长文本流 | 16:9 幻灯片卡片 (800×450px) |
| 图片处理 | 不支持插入图片 | `@tiptap/extension-image` 支持 |
| 工具栏 | 全局多按钮工具栏 | 移除（简化交互） |
| AI 气泡 | `InlineAIBubble` 悬浮菜单 | 移除（降低复杂度） |
| 内容同步 | `onUpdate` → 检测光标所在章节 | `onBlockChange(id, html)` → 逐页同步 |
| 导出 PDF | 简单拼接 `<p>` 段落 | `.manual-pdf-page` 包裹精确分页 |

### 涉及脚本

| 文件 | 变更类型 | 行数变动 |
|------|----------|----------|
| `frontend/src/components/editor/BlockEditor.tsx` | 重构 | -240 → +107 (净减 ~133 行) |
| `frontend/src/pages/WorkspacePage.tsx` | 适配 | ~46 行变更 |
| `frontend/package.json` | 新增依赖 | `@tiptap/extension-image` |

### 核心实现

**SlidePage 组件** — 每个 DocumentBlock 对应一个独立画布:

```tsx
function SlidePage({ blockId, initialContent, sectionTitle, onBlockChange, readOnly }) {
  const editor = useEditor({
    extensions: [
      StarterKit,
      Underline,
      Placeholder,
      Image.configure({ inline: false, HTMLAttributes: { class: 'manual-slide-img' } }),
      CitationMark,
    ],
    content: initialContent,
    editable: !readOnly,
    onUpdate: ({ editor: ed }) => {
      onBlockChange(blockId, ed.getHTML())  // 实时同步到父组件
    },
  })

  return (
    <div className="w-[800px] h-[450px] bg-white shadow-2xl ...">
      <EditorContent editor={editor} />
    </div>
  )
}
```

**BlockEditor 容器** — 遍历 blocks 渲染 N 个 SlidePage:

```tsx
export function BlockEditor({ blocks, onSync, ... }) {
  return (
    <div className="w-full bg-gray-50 overflow-y-auto h-full py-4">
      {blocks
        .sort((a, b) => a.order_index - b.order_index)
        .map((block) => (
          <SlidePage
            key={block.id}
            blockId={block.id}
            sectionTitle={block.section_title}
            initialContent={block.content}
            onBlockChange={onSync}
          />
        ))}
    </div>
  )
}
```

**导出 PDF 的分页逻辑** — 用 `.manual-pdf-page` 包裹每一页:

```tsx
// WorkspacePage.tsx — handleExportPdf()
const fullHtmlContent = blocks
  .sort((a, b) => a.order_index - b.order_index)
  .map((b) => `<div class="manual-pdf-page">
      ${b.section_title ? `<h2>${b.section_title}</h2>` : ''}
      ${b.content}
    </div>`)
  .join('\n')

const result = await projectsApi.exportPdf(projectId, { html_content: fullHtmlContent })
```

> **关键 CSS 联动**: 前端每个 slide 被 `<div class="manual-pdf-page">` 包裹，后端 `render_custom_html_to_pdf` 中的 `.manual-pdf-page { page-break-after: always; }` 确保前端每一页对应 PDF 的精确物理分页。

---

## 4. 🆕 幻灯片图片暂存 API

### 功能概述

用户在 16:9 幻灯片编辑器中插入本地图片时，前端通过此 API 上传图片文件，后端保存至 `outputs/assets/{project_id}/` 目录，返回公开 URL 供 Tiptap 编辑器直接引用。

### 涉及脚本

| 文件 | 变更 |
|------|------|
| `backend/app/api/v1/endpoints/projects.py` | 新增 `POST /{project_id}/assets` 端点（~35 行） |

### 核心实现

```python
@router.post("/{project_id}/assets")
async def upload_slide_asset(project_id: uuid.UUID, file: UploadFile = File(...)):
    settings = get_settings()
    asset_dir = os.path.join(settings.OUTPUT_DIR, "assets", str(project_id))
    os.makedirs(asset_dir, exist_ok=True)

    file_ext = os.path.splitext(file.filename or "image.png")[1] or ".png"
    safe_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(asset_dir, safe_filename)

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    public_url = f"/outputs/assets/{project_id}/{safe_filename}"
    return {"url": public_url}
```

> 图片通过 `StaticFiles` 挂载（`main.py: app.mount("/outputs", ...)`）直接暴露，`/outputs/assets/{project_id}/{filename}` 即可公开访问。

---

## 5. 🆕 手动导出 PDF 真实渲染 (告别 Mock)

### 功能概述

`POST /{project_id}/export-pdf` 端点从 Mock 升级为真正的 WeasyPrint 渲染管线。用户在前端自由编辑幻灯片完成后点击"导出"，后端接收完整 HTML 并渲染为 PDF 返回下载链接。

### 变更对比

| 维度 | 旧实现 (Mock) | 新实现 (WeasyPrint 真实渲染) |
|------|---------------|------------------------------|
| 渲染引擎 | `return DownloadResponse(mock_url="/mock_report.pdf")` | `render_custom_html_to_pdf(html, topic, pdf_path)` |
| 文件命名 | 写死 `custom_report.pdf` | 时间戳命名 `manual_report_{project_id}_{timestamp}.pdf` |
| file_size | 写死 `1024` | 真实 `os.path.getsize(pdf_full_path)` |
| 目录创建 | 无 | `os.makedirs(out_dir, exist_ok=True)` (本次 Bug 修复) |
| topic 安全处理 | 无 | HTML 转义 | `&` `<` `>` → `&amp;` `&lt;` `&gt;` (本次 Bug 修复) |

### 涉及脚本

| 文件 | 变更 |
|------|------|
| `backend/app/api/v1/endpoints/projects.py` | `export_manual_pdf` 端点从 Mock 替换为真实 WeasyPrint 调用（~35 行重写） |
| `app/report/pdf_generator.py` | `render_custom_html_to_pdf` 新增目录自动创建 + topic HTML 转义 |

### 核心实现

```python
@router.post("/{project_id}/export-pdf", response_model=DownloadResponse)
async def export_manual_pdf(project_id, body: ExportPdfRequest, db):
    # 验证项目存在
    project = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")

    settings = get_settings()
    pdf_filename = f"manual_report_{project_id}_{int(time.time())}.pdf"
    pdf_full_path = os.path.join(settings.OUTPUT_DIR, pdf_filename)

    # 调用 WeasyPrint 核心排版引擎
    from app.report.pdf_generator import render_custom_html_to_pdf
    render_custom_html_to_pdf(
        raw_html=body.html_content,
        topic=project.topic,
        output_pdf_path=pdf_full_path,
    )

    # 更新数据库指向最新手动导出 PDF
    project.pdf_path = pdf_filename
    await db.commit()

    return DownloadResponse(
        project_id=project_id,
        topic=project.topic,
        download_url=f"{settings.PDF_DOWNLOAD_BASE_URL}/{pdf_filename}",
        filename=f"{project.topic}_终版报告.pdf",
        file_size_bytes=os.path.getsize(pdf_full_path),
        report_ready=True,
    )
```

---

## 6. ♻️ 工作流重构：切断自动 PDF 生成

### 变更动因

v0.2 的 `run_draft_sections_workflow` 在撰写完成后会自动组装 Markdown 报告并渲染 PDF。但这导致用户没有机会编辑 AI 生成的草稿。新流程改为：

```
旧流程: 撰写章节 → 组装 Markdown → 渲染 PDF → COMPLETED
新流程: 撰写章节 → COMPLETED（草稿就绪）→ 用户自由编辑 → 手动导出 PDF
```

### 涉及脚本

| 文件 | 变更 |
|------|------|
| `backend/app/tasks/report_workflow.py` | Phase 3 移除步骤 4（`build_report_markdown`）和步骤 5（`generate_pdf_report`），直接推进到 COMPLETED |

### 核心变更

```python
# ─── 【核心重构：切断自动流】 ──────────────────────
# 原步骤 4（组装 Markdown 报告）和步骤 5（生成 PDF）已移除。
# 现在的 COMPLETED 终态代表"AI 初始草稿生成完成"，
# 等待用户在各页面中自由编辑与排版后，由前端手动触发 PDF 导出。

# 直接将项目状态推进到 COMPLETED（草稿已就绪，等待用户编辑）
repo.update_project_status(project_id, ProjectStatus.COMPLETED, pdf_path=None, md_path=None)

repo.append_project_log(project_id, "drafting_complete",
    "🎉 AI 草稿分页生成完毕！已导入工作台，请在各页面中自由编辑与排版。",
    LogLevel.MILESTONE, "🎉")
```

> **注意**: `render_tasks.py` 中的 `build_report_markdown` 和 `generate_pdf_report` 两个 Celery Task 仍保留在代码中，可被旧版 `run_full_report_workflow` 或 CLI 模式（`app/orchestrator/workflow.py`）调用，只是不再被主流程触发。

---

## 7. 🐛 Bug 修复：BM25 检索降级

### 问题现象

Celery 日志持续出现:
```
[WARNING] BM25 语料加载失败 (Could not import rank_bm25, please install with `pip install rank_bm25`.)
降级为纯向量检索
```

### 根因分析

`rank_bm25` 是 `langchain_community.retrievers.BM25Retriever` 的必需依赖，但未包含在 `requirements.txt` 中，导致 WSL venv 中缺失该包。

**完整错误链**:

```
app/rag/retriever.py:15
  → from langchain_community.retrievers import BM25Retriever
    ↓ (import 成功，但 BM25Retriever 内部对 rank_bm25 是惰性导入)
retriever.py:225
  → BM25Retriever.from_documents(docs, preprocess_func=jieba_tokenizer)
    ↓
langchain_community 内部惰性导入
  → import rank_bm25 → ModuleNotFoundError
    ↓
retriever.py:231
  → except Exception as e:
      logger.warning("BM25 语料加载失败 (%s)，降级为纯向量检索", e)
```

### 影响范围

- **RRF 融合退化为单引擎**: 只有 Chroma 向量检索结果，缺少 BM25 关键词精确匹配
- **中文专有名词/产品型号**等关键词检索场景召回质量显著下降
- **搜索 + 本地上传的全部文档切片**都无法被 BM25 检索，BM25 持久化目录（`bm25_db/`）形同虚设

### 修复方案

| 文件 | 变更 | 状态 |
|------|------|------|
| `requirements.txt` | 新增 `rank-bm25==0.2.2`（位于 Embedding & Retrieval 依赖区） | ✅ 已提交 |
| WSL venv | 执行 `pip install rank-bm25==0.2.2` | ✅ 已安装 |

**验证结果**:
- `rank_bm25` 导入成功 ✅
- `BM25Okapi` 基础功能正常 ✅
- `BM25Retriever.from_documents()` → `invoke()` 全链路正常 ✅

---

## 8. 🐛 Bug 修复：PDF 导出目录缺失 + HTML 注入风险

### 问题 1：输出目录缺失导致写入失败

**现象**: 用户首次导出 PDF 时抛异常 `FileNotFoundError`（若 `OUTPUT_DIR` 未被其他流程预创建）

**根因**: `render_custom_html_to_pdf()` 中:
```python
temp_path = output_pdf_path.replace(".pdf", "_manual_build.html")
with open(temp_path, "w", encoding="utf-8") as f:  # ← 目录不存在则 FileNotFoundError
    f.write(premium_html)
```
WeasyPrint 的 `HTML().write_pdf()` 也不会自动创建父目录。

### 问题 2：topic 注入破坏 HTML 结构

**现象**: 若用户输入 topic 为 `"A & B <Product> 分析"`，f-string 拼接后 HTML 变为:
```html
<title>A & B <Product> 分析 — 产品深度研究报告</title>
```
`&` 被解析为 HTML 实体起始符，`<Product>` 被解析为未知标签，导致 WeasyPrint 渲染异常或崩溃。

### 修复方案

| 文件 | 函数 | 变更 |
|------|------|------|
| `app/report/pdf_generator.py` | `render_custom_html_to_pdf()` | 函数开头新增 `os.makedirs(out_dir, exist_ok=True)`；新增 `safe_topic` 三字符转义 |
| `app/report/pdf_generator.py` | `markdown_to_pdf()` | `HTML(filename=...).write_pdf()` 前新增 `os.makedirs(pdf_dir, exist_ok=True)` |

**核心代码**:

```python
def render_custom_html_to_pdf(raw_html: str, topic: str, output_pdf_path: str):
    # 确保输出目录存在（WeasyPrint 不会自动创建父目录）
    out_dir = os.path.dirname(output_pdf_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    # 安全化 topic 中的 HTML 特殊字符（防止 f-string 注入破坏 HTML 结构）
    safe_topic = topic.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    premium_html = f"""...
    <title>{safe_topic} — 产品深度研究报告</title>
    ..."""
    temp_path = output_pdf_path.replace(".pdf", "_manual_build.html")
    with open(temp_path, "w", encoding="utf-8") as f:
        f.write(premium_html)
    HTML(filename=temp_path).write_pdf(output_pdf_path)
```

---

## 9. 🔧 搜索召回量调整

| 文件 | 变更 | 原因 |
|------|------|------|
| `app/search/tavily_search.py` | `max_results` 默认值从 `15` 调整为 `5` | 15 条结果中大量为低质量重复内容，5 条 + Firecrawl 深度抓取已能覆盖核心信息需求 |

---

## 10. 📋 完整变更文件索引

### 新增文件 (2)

```
+ app/llm/prompts.py
    → PromptFactory 多态模板中枢（4 套 System Prompt）

+ backend/alembic/versions/
    24f2c9f525d7_add_template_type_to_projects.py
    → DB 迁移：projects 表新增 template_type 列 (VARCHAR(50), default='product')
```

### 修改文件 (16)

```
Python 后端 (10):
  M  backend/app/api/v1/endpoints/projects.py
       → export_manual_pdf: Mock → 真实 WeasyPrint 渲染
       → +POST /{project_id}/assets: 幻灯片图片暂存
       → create_project: 写入 template_type 到 DB

  M  backend/app/tasks/report_workflow.py
       → Phase 2/3: template_type 透传到 LLM 层
       → Phase 3: 移除自动 Markdown 组装 + PDF 生成
       → Phase 3: COMPLETED 状态下 pdf_path=None, md_path=None

  M  backend/app/tasks/writing_tasks.py
       → generate_outline_task: 签名新增 template_type 参数
       → write_single_section: 签名新增 template_type 参数

  M  backend/app/repositories/project_repo.py
       → +get_project_template(project_id) 方法

  M  backend/app/schemas/__init__.py
       → ProjectCreateRequest / ProjectResponse / ProjectStatusResponse
         新增 template_type 字段

  M  backend/app/models/project.py
       → Project 模型新增 template_type 列

  M  app/planner/outline_generator.py
       → generate_outline(topic, template_type): 委托 PromptFactory

  M  app/report/section_writer.py
       → write_section / _write_text_section: 委托 PromptFactory

  M  app/report/pdf_generator.py
       → render_custom_html_to_pdf: +目录自动创建 +topic HTML 转义
       → markdown_to_pdf: +目录自动创建

  M  app/search/tavily_search.py
       → max_results: 15 → 5

TypeScript 前端 (4):
  M  frontend/src/components/editor/BlockEditor.tsx
       → 单 Tiptap 实例 → 多 SlidePage 16:9 幻灯片架构
       → -InlineAIBubble -EditorToolbar +Image extension

  M  frontend/src/pages/WorkspacePage.tsx
       → 适配新 BlockEditor (移除 activeSectionTitle/onEditorReady)
       → 模板选择器: 3 旧选项 → product / design 双选项
       → 导出 PDF: .manual-pdf-page 包裹精确分页

  M  frontend/src/components/projects/CreateProjectModal.tsx
       → +TEMPLATE_OPTIONS 模板卡片选择 UI
       → handleSubmit 附带 template_type

  M  frontend/src/types/api.ts
       → ProjectCreateRequest / ProjectResponse / ProjectStatusResponse
         新增 template_type 字段

配置/文档 (2):
  M  requirements.txt
       → +rank-bm25==0.2.2（BM25 检索修复）

  M  command.txt
       → +手动启动命令备忘（三终端分别启动 uvicorn / celery / vite）
```

### 保留但间接受影响的模块

| 模块 | 关系说明 |
|------|----------|
| `backend/app/tasks/render_tasks.py` | `build_report_markdown` / `generate_pdf_report` 不再被主流程调用（保留用于 CLI 模式 `run_full_report_workflow`） |
| `app/orchestrator/workflow.py` | CLI 全自动流程仍调用旧版 `markdown_to_pdf`，不受影响 |
| `frontend/src/components/editor/InlineAIBubble.tsx` | 幻灯片编辑器重构后不再集成（代码保留，可独立复用） |
| `frontend/src/components/editor/DiffViewNode.tsx` | 同上 |
| `frontend/src/hooks/useEditorSync.ts` | 适配新 `onSync` 回调签名（id, html）→ void |

---

> 完整结构化文档参见: `PROJECT_STRUCTURE.md`
