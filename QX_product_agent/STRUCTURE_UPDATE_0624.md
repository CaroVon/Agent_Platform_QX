# Day 2–3 架构重构报告 — 2026-06-24

> **版本变更**: v0.2 → v0.3 → v0.4
> **重构范围**: 底层渲染引擎两次替换 + 页面架构重组 + 状态管理迁移
> **核心目标**: 废弃 Tiptap/WeasyPrint → Fabric.js/jsPDF → React-Konva/Zustand/jsPDF，根治序列化死循环，实现商用闭源合规

---

## 一、变更概览

```
                    v0.2 (Before)              →        v0.3 (Day 2)              →        v0.4 (Day 3)
┌──────────────────────────────────┐        ┌──────────────────────────────────┐        ┌──────────────────────────────────┐
│ 排版引擎    Tiptap (DOM-based)    │   →    │ 排版引擎    Fabric.js (Canvas)    │   →    │ 排版引擎    React-Konva (Canvas)   │
│ PDF 渲染    WeasyPrint (后端)     │   →    │ PDF 导出    jsPDF (前端)          │   →    │ PDF 导出    jsPDF + 原生 Konva      │
│ 编辑器      BlockEditor (流式长文) │   →    │ 编辑器      CanvasSlideEditor      │   →    │ 编辑器      CanvasSlideEditor (重写) │
│ 页面结构    单页面 WorkspacePage   │   →    │ 页面结构    Workspace + Editor    │   →    │ 页面结构    不变                     │
│ 封面        不存在（丢失）         │   →    │ 封面        dataTransform 强制生成 │   →    │ 封面        不变（CanvasElement 化） │
│ 状态管理    组件内 useState       │   →    │ 状态管理    slidesInternal 传递    │   →    │ 状态管理    Zustand 原子化 Store     │
│ 所见即所得  ❌ CSS→PDF 不一致     │   →    │ 所见即所得  ✅ Canvas→PNG→PDF 精确  │   →    │ 所见即所得  ✅ 声明式渲染 + 离屏导出  │
│ 序列化      —                     │   →    │ 序列化      ⚠️ 全量 fc.toJSON()     │   →    │ 序列化      ✅ 原子 updateElement     │
│ 闭源合规    —                     │   →    │ 闭源合规    ⚠️ Fabric.js GPL/MIT     │   →    │ 闭源合规    ✅ Konva MIT / Zustand MIT │
└──────────────────────────────────┘        └──────────────────────────────────┘        └──────────────────────────────────┘
```

---

## 二、v0.4 文件变更清单（Day 3: Fabric.js → React-Konva + Zustand）

### 新增文件

| 文件 | 行数 | 作用 |
|------|------|------|
| `frontend/src/store/useCanvasStore.ts` | 101 | Zustand 原子化 Canvas 状态管理，消除序列化死循环 |

### 重写文件

| 文件 | 行数 | 变更量 | 说明 |
|------|------|--------|------|
| `frontend/src/lib/dataTransform.ts` | 288 | +68 (原 ~220) | FabricSlide → KonvaSlide，新增 stripMarkdown，CanvasElement 数组替代 fabricJson |
| `frontend/src/components/editor/CanvasSlideEditor.tsx` | 815 | +195 (原 ~620) | Fabric.js 命令式 API → React-Konva 声明式 + 原生 Konva 离屏导出 |
| `frontend/src/pages/EditorPage.tsx` | 486 | +116 (原 ~370) | loadFromJSON 导出 → capturePage(Promise)，AI 面板直连 Zustand |

### 修改文件

| 文件 | 变更 |
|------|------|
| `frontend/package.json` | 移除 `fabric@^6.0.0`；新增 `konva@^9.3.18`、`react-konva@^18.2.10`、`use-image@^1.1.0`；保留 `zustand@^5.0.14`（已存在） |

### 未修改（保留）文件

| 文件 | 状态 |
|------|------|
| `frontend/src/components/editor/BlockEditor.tsx` | ⚠️ 已废弃（不再被引用） |
| `frontend/src/components/editor/InlineAIBubble.tsx` | ⚠️ 已废弃（Tiptap BubbleMenu） |
| `frontend/src/hooks/useDraftStream.ts` | ⚠️ 不再使用 |
| `backend/app/tasks/report_workflow.py` | 不变 |
| `backend/app/tasks/writing_tasks.py` | 不变 |

---

## 三、架构决策记录 (ADR) — v0.4 新增

### ADR-006: Fabric.js → React-Konva + Zustand（序列化死循环根治）

**问题 (v0.3 遗留)**:
Fabric.js 与 React 状态绑定导致严重的"序列化死循环"：
1. 每次 `object:modified`（如拖拽 1px）→ `fc.toJSON()` 全量序列化整个画布 → 推入 React state → 触发 re-render → 覆盖 canvas JSON → 再次触发序列化
2. 拖拽时极度卡顿，编辑体验不可用

**决策**: 将底层 Canvas 引擎从 Fabric.js 替换为 React-Konva，引入 Zustand 作为原子化状态管理。

**核心机制**:
- Fabric.js: `fc.toJSON()` 每次全量序列化（所有对象 + 属性 + 样式）
- Zustand: `updateElement(page, id, { x, y })` 只更新单个元素的坐标，不触碰其他元素
- React-Konva: 声明式 `<Stage><Layer>{elements.map(el => <Rect ... />)}</Layer></Stage>`，React 自动 diff 最小化 DOM 更新

**效果**: 拖拽不再触发任何序列化，仅通过 `onDragEnd → updateElement → set({...})` 原子更新坐标，渲染由 React-Konva 声明式完成。

### ADR-007: 原生 Konva 离屏渲染导出（Invalid string length 修复）

**问题**:
v0.3 的导出使用 `canvasRef.current.loadFromJSON()` 遍历页面截图，v0.4 初版使用 React-Konva Stage 的 `toDataURL` 通过 Zustand 切换 activePage。当用户添加图片后，导出报错 `RangeError: Invalid string length`。

**根因分析**:
```
PNG 数据 URL (2560×1440, 含照片: 3–15 MB)
  → jsPDF: atob() → 解码 PNG → RGBA buffer (14.7 MB)
    → String.fromCharCode.apply(null, pixelArray)
      → JavaScript 函数参数上限 ~65k，实际 14.7M → 💥 Invalid string length
```

**决策**: 使用**原生 Konva 离屏 Stage** + **JPEG 格式** + **Blob API** 替换 React-Konva 的 `toDataURL('image/png')`。

**实现细节** (`capturePage` 方法):
1. 预加载所有图片 (`new window.Image()` + `crossOrigin = 'anonymous'`)
2. 创建隐藏 `<div>` 容器（`position:fixed; left:-9999px`）
3. 创建原生 `new Konva.Stage({ container, width: 1280, height: 720 })`（无 CSS 缩放）
4. 逐一添加原生 Konva 图形（`Konva.Rect` / `Konva.Text` / `Konva.Image` / `Konva.Group`）
5. `layer.draw()` 同步渲染
6. `stage.toCanvas({ pixelRatio: 2 })` → `canvas.toBlob(callback, 'image/jpeg', 0.92)` → `FileReader.readAsDataURL(blob)`
7. `stage.destroy()` + 清理容器

**JPEG vs PNG 对比**:
| 格式 | 2560×1440 含照片 | 解码后缓冲区 | jsPDF 兼容性 |
|------|------------------|-------------|-------------|
| PNG | 3–15 MB | RGBA 14.7 MB | ❌ 参数超限 |
| JPEG Q=0.92 | 200–800 KB | RGB 11.0 MB → 正常 | ✅ |

### ADR-008: CanvasElement 统一数据模型

**问题**: v0.3 使用 `FabricSlide { fabricJson: Record<string, unknown> }` — 这是 Fabric.js 专有格式，深度嵌套、不可序列化到其他引擎，且 `objects` 数组中无类型安全的元素定义。

**决策**: 定义 `CanvasElement` 接口作为跨引擎的通用元素模型：

```typescript
interface CanvasElement {
  id: string
  type: 'text' | 'rect' | 'image' | 'table'
  x: number; y: number
  width: number; height: number
  fill?: string     // 颜色
  text?: string     // 文本内容
  src?: string      // 图片 URL / Blob URL
  tableData?: string[][]  // 表格数据
}
```

**优势**:
- 引擎无关：同一份数据可被 React-Konva、原生 Konva、甚至未来的其他引擎消费
- 类型安全：TypeScript 联合类型 `type` 字段驱动 switch 渲染
- 轻量序列化：`JSON.stringify(elements)` 只包含必要字段，无 Fabric.js 的 `version`/`styles`/`charSpacing` 等冗余属性

### ADR-009: stripMarkdown 纯文本转换

**问题**: v0.3 将后端返回的 Markdown 内容直接塞入 Fabric.js Textbox，渲染出 `# 标题`、`**粗体**` 等原始语法字符。

**决策**: 在 `dataTransform.ts` 中实现 `stripMarkdown()` 纯函数，在构建幻灯片元素前去除 Markdown 符号：

| 模式 | 处理 |
|------|------|
| `# 标题` | 去除 `#` |
| `**粗体**` / `*斜体*` | 去除 `*` |
| `[链接](url)` | 保留文本 `[链接]` |
| `` `代码` `` | 去除反引号 |
| `- 列表` | 替换为 `•` |
| `> 引用` | 去除 `>` |

---

## 四、数据流变更

### v0.3 (Fabric.js)
```
GET /blocks → convertBlocksToFabricSlides() → FabricSlide[]
  → CanvasSlideEditor (Fabric.js Canvas)
  → 导出: canvasRef.loadFromJSON() → setTimeout(200ms) → fc.toDataURL() → jsPDF
  → AI 面板: canvasRef.editorApi.addText() → Fabric.js Textbox
```

### v0.4 (React-Konva + Zustand)
```
GET /blocks → convertBlocksToKonvaSlides() → KonvaSlide[] + useCanvasStore.setSlides()
  → CanvasSlideEditor (React-Konva Stage, 声明式渲染)
  → 导出: slides[i].elements → capturePage() → 原生 Konva Stage → JPEG Blob → jsPDF
  → AI 面板: useCanvasStore.getState().addElement() → 自增 id → 原子写入
```

### 状态流（拖拽为例）
```
v0.3: 拖拽1px → object:modified → fc.toJSON() → setState → re-render → loadFromJSON → renderAll (卡顿)
v0.4: 拖拽1px → onDragEnd → updateElement(page, id, {x, y}) → set({...}) → React diff → 仅重绘该元素 (丝滑)
```

---

## 五、依赖变更详情

### package.json diff

```diff
- "fabric": "^6.0.0",
+ "konva": "^9.3.18",
+ "react-konva": "^18.2.10",
+ "use-image": "^1.1.0",
  "jspdf": "^2.5.2",          // 保留
  "zustand": "^5.0.14",       // 保留（之前已存在）
```

### 许可证合规

| 库 | 许可证 | 商用闭源 |
|----|--------|----------|
| `konva` | MIT | ✅ |
| `react-konva` | MIT | ✅ |
| `zustand` | MIT | ✅ |
| `use-image` | MIT | ✅ |
| `jspdf` | MIT | ✅ |
| ~~`fabric`~~ | ~~GPL/MIT~~ | ~~⚠️ 有风险~~ |

---

## 六、已知限制 & 后续计划（更新）

| 限制 | 优先级 | 状态 |
|------|--------|------|
| 拖拽卡顿 / 序列化死循环 | P0 | ✅ 已修复 (Zustand 原子更新) |
| PDF 导出含图片时报 Invalid string length | P0 | ✅ 已修复 (JPEG + Blob + 原生 Konva) |
| Fabric.js 闭源合规风险 | P1 | ✅ 已修复 (MIT 协议全栈) |
| 缩略图为占位符（仅显示页码） | P1 | 待处理 |
| 长文本单页溢出 | P1 | 待处理 |
| 文本不支持双击编辑（Konva 限制） | P2 | 待接入 Konva Transformer |
| 图片搜索需手动粘贴 URL | P2 | 待集成 |
| 无撤销/重做 | P3 | 待接入 Zustand middleware (temporal) |
| Markdown 渲染为纯文本（非富文本） | P2 | 可扩展 CanvasElement.textStyle |

---

## 七、验证清单（更新）

- [x] Canvas 画布初始化成功（v0.3 修复死锁 → v0.4 无初始化概念）
- [x] 缩略图列表渲染 + 点击切换
- [x] 文本添加 / 拖拽（丝滑，无序列化死循环）
- [x] 图片添加（本地文件 + AI 生成 URL + Blob URL）
- [x] jsPDF 导出多页 PDF（含图片，JPEG 格式）
- [x] AI 侧边栏"应用到画布"功能（直连 Zustand）
- [x] WorkspacePage → EditorPage 导航
- [x] 后端状态机 DRAFTING→COMPLETED
- [ ] 真实缩略图渲染
- [ ] 长文本自动分页
- [ ] Konva Transformer 双击编辑

---

## 八、Bug 修复记录

### Bug #1: "Invalid string length" — jsPDF 大 PNG 解码崩溃

- **触发条件**: 在幻灯片中添加本地图片后导出 PDF
- **根因**: `stage.toDataURL({ mimeType: 'image/png' })` 生成的 PNG 在 jsPDF 内部解码时，RGBA buffer（2560×1440×4 ≈ 14.7M entries）作为参数传递给 `String.fromCharCode.apply()`，超出 JS 函数参数上限
- **修复**: 改用 JPEG + Blob API（`canvas.toBlob('image/jpeg', 0.92)` + `FileReader`）
- **修复文件**: `CanvasSlideEditor.tsx:capturePage()`, `EditorPage.tsx:handleExport()`
- **修复日期**: 2026-06-24

### Bug #2: "Failed to fetch dynamically imported module: konva"

- **触发条件**: Vite dev server 热更新后点击导出
- **根因**: `capturePage` 内使用 `const Konva = (await import('konva')).default` 动态导入，Vite 未预构建该 chunk
- **修复**: 改为模块顶层静态导入 `import Konva from 'konva'`
- **修复文件**: `CanvasSlideEditor.tsx` 第 17 行
- **修复日期**: 2026-06-24

---

> **相关文档**: `PROJECT_STRUCTURE.md` (v0.4)
> **原始需求**: `fix/day3/fix_canvas.md`
> **上一版本**: v0.3 (Day 2, Fabric.js 迁移)
