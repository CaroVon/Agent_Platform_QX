# 记忆与知识图 · 视觉美化完整方案

> 版本：v1.0 ｜ 日期：2026-08 ｜ 配套：`docs/memory-graph-upgrade-plan.md`（记忆图架构）＋ `docs/knowledge-system-analysis.md`（P1-P3）
>
> 本文档回答：知识关系图"**好看且有用**"的全部细节——主题、配色、节点/边/标签规范、布局、动效、交互、组件架构、性能与无障碍。
> 原则：**零新增可视化依赖起步**（复用 `echarts@6.1`），设计令牌（Design Token）完全对接项目现有 HSL 主题系统，亮/暗双主题自动适配。

---

## 1. 设计目标与原则

参考 [yfiles 知识图谱可视化指南](https://www.yfiles.com/resources/how-to/guide-to-visualizing-knowledge-graphs.html) 与 Obsidian Graph View 的设计讨论（[Obsidian Forum](https://forum.obsidian.md/t/design-talk-about-the-graph-view/22594/71)），确立四条原则：

| 原则 | 含义 | 落地 |
|------|------|------|
| **P1 一图读懂** | 3 秒内看懂"这是什么图、谁是大节点、分了哪些簇" | 类型配色 + 尺寸 ∝ 关联度 + 社区着色 |
| **P2 Focus+Context** | 关注一个实体时，邻域清晰、背景安静 | 点击聚焦 → 邻域高亮、其余降饱和降透明度 |
| **P3 数据即美** | 不画装饰性图形，所有视觉变量都有数据含义 | 颜色=类型、大小=度数、描边=置信度、透明度=新鲜度、虚线=过期 |
| **P4 融入而非突兀** | 与现有 Vintage Linear 设计语言一致，不另起炉灶 | 全部颜色取自项目 HSL tokens 的调和派生 |

---

## 2. 主题融入（双主题 Token 桥接）

项目现有主题（`frontend/src/styles/globals.css`）为 shadcn 风格 HSL 变量：

| Token | 亮色（当前值） | 暗色（当前值） |
|-------|---------------|---------------|
| `--background` | `42 30% 97%`（暖白） | `220 18% 10%`（深蓝黑） |
| `--card` | `40 26% 95.5%` | `220 15% 13%` |
| `--primary` | `212 46% 26%`（深蓝） | `205 40% 60%`（浅蓝） |
| `--sidebar` | `208 28% 16%` | `220 20% 9%` |

**方案**：新增 `--graph-*` 一组图专用 token（挂 `:root` 与 `.dark`），值由 primary 色相（212°/205°）调和派生，保证与品牌一致：

```css
:root {
  /* 图背景：比 background 更纯净的"画布"，与卡片区分 */
  --graph-bg: 40 30% 98%;
  /* 实体类型色板（亮色：降饱和 + 提亮；暗色：提饱和 + 提亮） */
  --graph-type-company:    212 55% 45%;
  --graph-type-product:    160 45% 40%;
  --graph-type-technology: 265 45% 52%;
  --graph-type-person:     25  70% 48%;
  --graph-type-market:     340 55% 48%;
  --graph-type-metric:     190 55% 42%;
  --graph-type-other:      220 8%  48%;
  /* 语义色 */
  --graph-focus:     212 46% 30%;
  --graph-focus-ring:212 70% 55%;
  --graph-muted:     220 10% 60%;
  --graph-edge:      220 12% 55%;
  --graph-edge-focus:212 50% 45%;
}
.dark { /* 同结构，换暗色取值 */ }
```

> 为什么不直接用固定色值？—— 双主题下同一色相需要不同亮度/饱和度才能同时满足对比度（WCAG AA：节点标签与画布对比 ≥ 4.5:1），token 化后由 `GraphCanvas` 统一读取。

---

## 3. 配色系统

### 3.1 实体类型色板（Categorical，7+1 色）

- 依据 [ColorBrewer 类定性色板](https://colorbrewer2.org/) 的**色相差值原则**：相邻色相间隔 ≥40°，保证色盲可辨（模拟 deuteranopia 后仍可区分）
- 类型映射（与后端 `memory_entities.type` 对齐）：

| 类型 | 亮色示例 | 暗色示例 | lucide 图标 |
|------|----------|----------|-------------|
| company 公司 | `hsl(212 55% 45%)` 蓝 | `hsl(205 60% 62%)` | `Building2` |
| product 产品 | `hsl(160 45% 40%)` 绿 | `hsl(158 55% 58%)` | `Package` |
| technology 技术 | `hsl(265 45% 52%)` 紫 | `hsl(262 60% 66%)` | `Cpu` |
| person 人物 | `hsl(25 70% 48%)` 橙 | `hsl(28 75% 62%)` | `User` |
| market 市场 | `hsl(340 55% 48%)` 玫红 | `hsl(338 60% 62%)` | `TrendingUp` |
| metric 指标/数据 | `hsl(190 55% 42%)` 青 | `hsl(190 60% 58%)` | `Gauge` |
| other 其他 | `hsl(220 8% 48%)` 灰蓝 | `hsl(220 12% 60%)` | `CircleDot` |
| project 项目（聚合节点） | 主色 `primary` | 主色 | `FolderKanban` |

### 3.2 高亮体系（Focus + Context 三级）

```
聚焦态（focus）    : 节点 = 类型色 100% 填充 + --graph-focus-ring 描边 2.5px + 辉光
邻域态（context）  : 一跳邻居 = 类型色 85% 填充 + 半透明描边；二跳邻居 = 60%
背景态（muted）    : 其余全部降为 --graph-muted（饱和度 12%），透明度 0.25
```
- 交互一致性：任何 hover/点击/搜索命中都进入同一套三级状态，用户一次学会全局操作。

### 3.3 数据维度视觉编码（P3 数据即美）

| 数据 | 编码通道 | 规则 |
|------|----------|------|
| 实体类型 | 色相 + 图标 | 见 3.1 |
| 关联度（degree） | 节点面积 | `size = 24 + 10·√degree`（平方根压缩，防 hub 淹没） |
| 置信度 | 节点描边宽度 | `0.75 + 1.75·confidence`，低置信加虚线描边 |
| 新鲜度（last_seen） | 填充透明度 | 30 天内 1.0 → 每 30 天 -0.15，下限 0.45 |
| 关系权重 | 边宽 | `1 + 2·weight`（1~3px） |
| 关系时效 | 线型 | 过期边（valid_to < now）虚线 + 降透明 0.4 |
| 关系方向 | 箭头 | 有向边 `arrow` 样式；无向关系（"相关"）无箭头 |
| 全局/项目 | 徽标 | 全局实体右下角小圆点徽标（hover 显示 project_count） |

---

## 4. 节点规范

```
┌─────────────────────────────┐
│  ○  实体节点（圆形，主形态）  │
│  ●  类型图标内嵌（lucide）   │
│  ◐  渐变填充（类型色→浅 12%） │
│  ▁  描边：置信度编码          │
│  ▾  底部投影（柔和，非硬边）  │
│  •  右下徽标：全局实体/项目数  │
└─────────────────────────────┘
```

- **形状**：主形态圆形（ECharts `symbol: 'circle'`）；`project` 聚合节点用圆角方形（`roundRect`）区分层级
- **图标**：lucide 图标渲染为 SVG 注册到 ECharts 自定义 symbol（`symbol: 'image://data:image/svg+xml;base64,...'` 缓存），16px 内嵌
- **渐变**：`itemStyle.color` 用 `new echarts.graphic.LinearGradient(0,0,0,1, [typeColor, typeColor@12%透明度])`，营造轻微立体感而非扁平色块
- **尺寸分级**：≤8 种离散档位（24/32/40/50/62/76/92/110px），避免连续映射导致视觉噪声
- **动画**：节点入场弹性缩放（`scale: [0→1], easing: 'elasticOut'`）

---

## 5. 边规范

```
├─ 曲率：quadratic（curveness 0.15~0.3），平行边（同一对实体多条关系）
│        按索引递增曲率并左右镜像，避免完全重叠
├─ 方向：有向箭头（arrow + arrowSize 6/8/10），无向"相关"边不画箭头
├─ 宽度：1 + 2·weight（1~3px），聚焦时邻域边 2.5px、其余 0.5px
├─ 颜色：hsl(var(--graph-edge))，聚焦时沿源节点类型色（40% 透明）
├─ 标签：仅 hover / 聚焦时显示关系类型（`edgeLabel`），常态隐藏防视觉噪声
└─ 状态：过期虚线（4,4 dash）+ 0.4 透明度；被隐藏实体相连的边一并隐藏
```

---

## 6. 标签与信息层级（LOD 分级）

| 缩放档位（zoom） | 显示内容 |
|------------------|----------|
| < 0.35 | 无标签，仅节点色块（纯鸟瞰） |
| 0.35 ~ 0.7 | 仅 hub 节点（degree ≥ 阈值）标签 |
| 0.7 ~ 1.4 | 全部节点名称标签 + 聚合节点项目数 |
| > 1.4 | 名称 + 类型副标签（小字）+ 置信度百分比 |

- **防遮挡**：标签碰撞检测——ECharts 无内置碰撞布局，用**近似方案**：标签绘制前按节点坐标做简单 grid 冲突检测，冲突者沿径向偏移或降级隐藏（实现 < 60 行）
- **标签样式**：`color: hsl(var(--foreground))`，`backgroundColor: hsl(var(--card) / 0.82)` 圆角 4px 遮罩（保证任意底图可读），字号 11/12/13px 分级
- **主名/别名**：hover 实体时 tooltip 展示 aliases（"又名：xxx / yyy"）

---

## 7. 布局系统

### 7.1 力导向（默认，ECharts force 布局调参）

```ts
series: [{
  type: 'graph', layout: 'force',
  force: {
    repulsion: 220,          // 全局排斥力（节点越大排斥越强：edgeLength 建议关闭，
                             // 用 repulsion 调疏密；hub 自动外扩）
    gravity: 0.08,           // 轻微向心，避免整体漂移
    friction: 0.6,           // 阻尼，快速收敛
    layoutAnimation: false,  // 首帧布局完成后再开交互动画（避免布局期卡顿）
  },
  roam: true,                // 缩放/拖拽
  scaleLimit: { min: 0.2, max: 4 },
}]
```
- **固定机制**：用户拖拽后的节点 `fixed: true` 并持久化（localStorage key=`qx-graph-pin-{scope}`），刷新不丢失
- **布局重排**：数据更新时保留已固定节点，其余重新布局（diff 更新而非全量重建）

### 7.2 社区着色（可选增强，P4d）

- 后端返回 Louvain/标签传播社区 id（Python `networkx` 已有依赖可算，或图 API 内联实现标签传播 ~40 行）
- 前端"按社区着色"开关：节点颜色切换为社区色板（复用 §3.1 色板按社区循环），**类型色则迁移到图标颜色**——同一套视觉变量不冲突

### 7.3 聚合/降采样（大图模式）

- 后端：degree < 2 的叶子节点在 `limit` 超限时聚合为"其他 N 项"占位节点（点击展开）
- 前端：仅渲染 top-N（按 degree），底部提示"已显示 200/1,234 节点 —— 搜索或放大聚焦"

---

## 8. 动效系统

| 场景 | 动效 | 参数 |
|------|------|------|
| 进场（首载） | 节点弹性缩放 + 边淡入（stagger 60ms） | `elasticOut`, 500ms |
| hover 节点 | 涟漪扩散一圈（`graphic` 元素动画） | 400ms, 1 次 |
| hover 边 | 边加亮 + 两端节点轻微放大 1.08 | 150ms ease |
| 点击/搜索聚焦 | 相机缩放至焦点邻域（`dispatchAction zoom`）+ 三级高亮 | 450ms cubicOut |
| 聚焦解除 | 状态回退 + 相机回到整体视图 | 350ms |
| 类型过滤 | 被滤节点收缩消失（scale→0 + opacity→0），保留布局锚点 | 300ms |
| **时间轴重放**（P4c 增强） | 底部时间滑块：按 `first_seen/valid_from` 播放记忆形成过程，节点/边按时间点亮（Graphiti 时序思想的可视化） | 播放速率 1x/2x/4x |
| 数据刷新 | 新增节点从 0 缩放入场，消失节点淡出 | 300ms |

> 动效克制原则：所有动效 ≤500ms，不用无限循环动画（除 loading 态），尊重 `prefers-reduced-motion`（媒体查询降级为 0ms 直切）。

---

## 9. 交互细节

| 交互 | 实现 |
|------|------|
| 搜索实体 | 顶部搜索框：输入即过滤（后端 `/memory/graph?q=` 实体名模糊 + 向量双通道），命中首个实体自动聚焦 |
| 类型筛选 | 图例 chips 多选（company/product/…），非选中类型淡出 |
| scope 切换 | 顶部 Segmented：全局记忆 / 项目记忆（联动项目下拉） |
| 右键菜单 | 自定义 context menu：查看详情 / 固定位置 / 隐藏该实体 / 删除（管理员，走 DELETE API） |
| 悬浮详情 | tooltip：名称、类型、置信度、first/last seen、关联洞察数、证据来源（可点击跳转项目） |
| 详情侧栏 | 点击实体：右滑面板（实体摘要 / 关联关系表 / 洞察列表 / 来源时间线） |
| 键盘 | `Esc` 取消聚焦；`↑↓←→` 在聚焦邻域间移动；`/` 聚焦搜索框；`+/-` 缩放 |
| 导出 | 工具栏：导出 PNG（ECharts `getDataURL`）——可直接用于报告配图 |
| 空/加载态 | 骨架屏 + 引导文案；空图显示插画与"完成第一个任务后自动生成"CTA |

---

## 10. 组件架构（前端落地）

```
frontend/src/components/graph/
├── GraphCanvas.tsx          // 核心画布：ECharts 实例管理、resize 观察、主题桥接
├── graphTheme.ts            // 读取 CSS 变量 → 生成 echarts theme 对象（亮/暗）
├── graphOptions.ts          // data → ECharts option 工厂（节点/边/标签/力导/动效）
├── graphIcons.ts            // 类型 → lucide SVG data-URL 注册表（缓存）
├── useGraphData.ts          // /memory/graph 拉取 + 本地采样/过滤/固定持久化
└── GraphSidebar.tsx         // 实体详情侧栏 + 洞察面板
frontend/src/pages/MemoryPage.tsx  // 页面组装：搜索/筛选/scope/画布/侧栏/时间轴
```

- **主题桥接**：`graphTheme.ts` 用 `getComputedStyle(document.documentElement)` 读取 `--graph-*` 与 `--primary` 等 token；监听 `classList` 变化（亮/暗切换）→ `chart.dispose()` + 重建（或 `setOption(theme)` 热切换）
- **数据转换**：后端 `{nodes, edges}` → 前端补全 `symbol/size/itemStyle/emphasis/edgeLabel` 派生字段，保持后端 API 纯净
- **状态管理**：本地 `useState` + zustand（项目已有）存"聚焦实体/筛选/固定点"，不污染全局 store

---

## 11. 性能与降级

| 规模 | 策略 |
|------|------|
| < 800 节点 | 全量渲染，SVG renderer（清晰、可选中文字） |
| 800 ~ 3,000 | `renderer: 'canvas'`（默认），关闭 `layoutAnimation`，标签按 LOD |
| > 3,000 | 后端聚合（§7.3）+ 前端仅渲染 top-N；建议 P4d 评估 [AntV G6 v5](https://github.com/antvis/G6)（WebGL + 自定义布局 + 大数据量） |
| 3D 炫酷模式（可选 P4d） | [3d-force-graph](https://github.com/vasturiano/3d-force-graph) 独立页（致敬 Obsidian 3D Graph 插件生态，如 [obsidian-3d-graph](https://github.com/Apoo711/obsidian-3d-graph)）——仅作"演示模式"，不作为主交互 |

---

## 12. 无障碍与国际化

- 色盲安全：类型色板经 deuteranopia/protanopia 模拟校验（开发期用 [Color Oracle](https://colororacle.org/) 或浏览器插件验证）
- 对比度：节点标签/图标与画布对比 ≥ 4.5:1（暗色主题尤其注意青色/绿色系）
- 键盘可达：全部交互有键盘路径（§9）
- 动效降级：`@media (prefers-reduced-motion: reduce)` 关闭弹性/涟漪
- 文案中文化：与现有界面一致；实体名、关系类型由后端返回中文（LLM 抽取时要求中文输出）

---

## 13. 实施清单（并入 P4 路线图）

| 工作项 | 内容 | 工作量 |
|--------|------|--------|
| M1 | `--graph-*` token（亮/暗）+ graphTheme 桥接 | 0.5 人日 |
| M2 | GraphCanvas + graphOptions（节点/边/标签/力导/高亮/动效/LOD） | 1 人日 |
| M3 | useGraphData + 搜索/类型筛选/scope 切换/固定持久化/右键菜单 | 0.5 人日 |
| M4 | MemoryPage 组装 + GraphSidebar + 空/载/错状态 + PNG 导出 | 0.5 人日 |
| M5 | 后端补字段：社区 id（可选）、聚合/降采样参数、`q=` 搜索 | 0.5 人日 |
| M6 | 时间轴重放（P4c）+ 3D 演示模式（P4d 可选） | 各 0.5 人日 |

**验证标准**：
1. 亮/暗主题切换后关系图配色自动适配，对比度达标
2. 100 节点图：点击任意实体 → 三级高亮 + 邻域缩放动画流畅（≥55fps）
3. 平行边不重叠；标签在任意缩放档不互相遮挡（抽查 3 个密度区域）
4. 全部交互键盘可达；`prefers-reduced-motion` 下无动画
5. 截图对比：与 Sidebar/KnowledgePage 视觉语言一致（同色系、同圆角/阴影语言）

---

## 14. 参考来源

- [yfiles: Guide to Creating Knowledge Graph Visualizations（节点/边/布局/视觉编码四要素）](https://www.yfiles.com/resources/how-to/guide-to-visualizing-knowledge-graphs.html)
- [Obsidian Forum: Design talk about the Graph View（官方设计讨论）](https://forum.obsidian.md/t/design-talk-about-the-graph-view/22594/71)
- [ECharts Graph 系列文档（力导/邻域高亮/自定义 symbol）](https://echarts.apache.org/zh/option.html#series-graph)
- [AntV G6 v5（P4d 升级候选）](https://github.com/antvis/G6)
- [Sigma.js: Style the graph（样式系统参考）](https://v4.sigmajs.org/get-started/style-the-graph/)
- [3d-force-graph（3D 演示模式）](https://github.com/vasturiano/3d-force-graph)
- [obsidian-3d-graph（Obsidian 3D 图插件）](https://github.com/Apoo711/obsidian-3d-graph)
- [ColorBrewer 2.0（定性色板设计）](https://colorbrewer2.org/)
- [Color Oracle（色盲模拟校验）](https://colororacle.org/)

---

## 15. 实施记录（2026-08）

本文档 M1-M4 已随 P4 一并落地（`pages/MemoryPage.tsx` + `components/graph/` 六件套）：

- M1 ✅ `--graph-*` 令牌（亮/暗双主题，色相派生自 primary）＋ `graphTheme.ts` 主题桥接（MutationObserver 热切换）
- M2 ✅ `GraphCanvas.tsx`（实例/resize/主题重建/LOD/点击回调）+ `graphOptions.ts`（力导 220/0.08/0.6、类型色+图标、度数√离散尺寸、置信度描边、新鲜度透明度、平行边曲率 ±0.15 交替、有向箭头、过期虚线、三级高亮 adjacency）
- M3 ✅ `useGraphData.ts`（scope/项目/搜索/类型筛选/重建）+ `graphIcons.tsx`（lucide SVG data-URL 缓存）
- M4 ✅ `MemoryPage.tsx` 组装（工具栏/统计条/画布/图例/洞察面板/PNG 导出）+ `GraphSidebar.tsx`（详情/邻域/洞察/证据/纠错删除）+ Sidebar 入口 + 懒加载路由
- M5 ⏳ 社区着色与后端聚合（>3000 节点场景）留待 P4d（当前 limit=400 截断提示已实现）
- M6 ⏳ 时间轴重放与 3D 演示模式留待 P4d（可选）

---

## 16. 显示问题修复记录（2026-08）

### 问题现象
Memory Graph 页面无法显示关系图（画布空白 / 项目视图报错 / 各视图均为空状态）。

### 根因链（调研结论）

| # | 根因 | 修复 |
|---|------|------|
| 1 | **GraphCanvas 渲染时序 bug**：loading 分支不渲染容器 div，`containerRef` 为 null，初始化 effect 只在挂载时执行一次 → 图表实例从未创建 | 容器 div 常驻，loading/error/empty 改为覆盖层；主题切换 dispose 后重建并重放 option；点击回调改经 ref 读取最新数据（`GraphCanvas.tsx` 重写） |
| 2 | **前端/后端 studio 契约不一致**：前端传 `project_id=studio:{uuid}`，后端按 `projects.id` 解析 → `uuid.UUID('studio:…')` 抛错 → HTTP 500 | 后端 `/memory/graph` 与 `/memory/insights` 兼容剥离 `studio:` 前缀（`memory.py`）；外部已实现的 `studio_product_id` 独立参数路径保持不变 |
| 3 | **记忆抽取未覆盖 Product Studio 产品**：记忆钩子只挂在传统研究报告流程，studio 产品（用户实际主要工作流）无记忆数据 | `extract_memory_from_project` 支持 `studio:{id}` 源（语料来自 `studio_products.asset_package`/`keywords` 递归提取文本）；`build_studio_memory_graph` 任务与 `/memory/rebuild-studio` 端点（外部已实现）配套 |
| 4 | **空状态无引导**：全局视图无全局记忆时只显示"空的"，用户不知道去哪看 | 空状态引导条：全局空 → "查看项目记忆"CTA；项目空 → "立即抽取"CTA（触发 rebuild） |

### 验证（Playwright headless chromium 实测）
- ✅ 全局视图：空状态 + 引导条显示
- ✅ 项目视图（studio 产品）：canvas 渲染（752×558，非背景像素 >0）、无 JS 错误
- ✅ 点击画布 → 实体详情侧栏弹出
- ✅ `tsc -b` 零错误、`vite build` 通过、后端 75 项 pytest 全绿

### 环境备注
- 本机 headless 截图依赖 `LD_LIBRARY_PATH=/tmp/alsa-stub`（系统缺 libasound.so.2，stub 以 ALSA_0.9/ALSA_0.9.0rc4 版本节点导出 125 个符号）；验证脚本见 `/tmp/final-verify.js`
- 演示种子数据：admin 用户传统项目"智能手表竞品分析"（7 实体/8 关系/2 洞察）+ studio 产品"青年财务 App"（5 实体/5 关系/2 洞察），可在 Memory Page 直接查看
- **后端需重启**（uvicorn 热加载不生效）以加载 `memory_extraction.py` 的 studio 抽取分支
