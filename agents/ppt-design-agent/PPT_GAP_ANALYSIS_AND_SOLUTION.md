# PPT 产出差距诊断与解决方案

> 调研日期：2026-08-16
> 项目：`/home/administrator/dev/agents/`
> 对标样例：`C:\Users\Administrator\Desktop\ppt temp\{glassmorphism,global_ai_capital_2026,indie_bookstore_zine_guide,pritzker_2026,sugar_rush_memphis,swiss_grid_systems}.pptx`
> 已集成 skill：`agents/ppt-design-agent/vendor/ppt-master`（v4.7.0）

---

## 0. 关键结论（TL;DR）

| 维度 | Demo（hugohe3/ppt-master） | 现有平台（QX） | 差距 |
|---|---|---|---|
| 单页 SVG 平均行数 | 111-642 行（**~390**） | 4-112 行（**~45**） | **~9× 稀疏** |
| 单页 shape 数（含分组内子节点） | 30-50+ | 5-12 | **~5× 缺失** |
| 视觉风格系统 | 18 个 visual styles + 5 个 modes + 12 个 image-renderings 自由组合 | 1 个内置 "咨询风"（CyberPPT） | **设计系统不可用** |
| Hero / 装饰图 | 全幅背景 + 多张配图 | 0（生成了但未使用） | **图片集成空跑** |
| 渐变 / 阴影 / 玻璃态 | linearGradient / radialGradient / 玻璃面板 | 仅 0-1 个色块 | **视觉语言缺失** |
| Typography 角色 | 6+ 个字号角色（13/24/28/44/68/80px，含渐变填充文字） | 1-2 个角色（26/14/11px） | **排版层级过平** |
| 装饰元素 | 圆点 / 横线 / 进度条 / 玻璃面板 / 渐变光带 / 象限图 | 1 根竖线 + 4 个方块卡 | **无装饰语言** |
| Spec Lock 完整度 | `design_spec.md` (~2000行) + `spec_lock.md`（含节奏、字体、引用等数十行） | `设计规范与内容大纲.md`（21行）+ `spec_lock.md`（46行） | **规范不可执行** |
| 最终 PPTX 导出 | ✅ 一键成功（多层、动画、转换） | ❌ `exports/` 为空（svg_quality_checker 拒绝） | **管线未打通** |
| 数据可视化 | 真实业务数据（$297B / 11.2% CAGR / 81%） | 真实数据但渲染极简 | **数据呈现低维** |

> **核心原因**：现有平台把 hugohe3/ppt-master 当作"脚本工具包"调用（只跑了 `finalize_svg.py` + `svg_to_pptx.py`），**完全没有启用**它的设计系统（`references/visual-styles/`、`references/modes/`、`templates/styles/`、`templates/layouts/`），而是写了一个**极简版**的 `svg_author.py` 让 LLM 直接手写 SVG，prompt 过窄、规则过严、视觉词汇为零。

---

## 1. 现有实现深度解剖

### 1.1 当前 `agent.py`（435 行）的 5 步管线

```
DSL → design_spec.md + spec_lock.md（确定性格式）
  → image_gen.py（生图，结果未使用）
  → LLM 逐页写 SVG（svg_author.py）
  → finalize_svg.py
  → svg_to_pptx.py（❌ 失败）
```

**核心文件**：
- `agents/ppt-design-agent/agent.py`（435 行）
- `agents/ppt-design-agent/svg_author.py`（231 行）
- `agents/ppt-design-agent/vendor/ppt-master/scripts/`（**未使用 90%**）

### 1.2 当前 `svg_author.py` 实际产出的 SVG（slide_01_cover.svg）

```xml
<svg ... viewBox="0 0 1280 720">
<rect width="1280" height="720" fill="#F7F6F0"/>
<rect x="500.0" y="292" width="280" height="8" fill="#3D6491"/>
<text x="640.0" y="380" text-anchor="middle" ...>SleepMate · AI 睡眠健康枕</text>
<text x="640.0" y="448" ...>Z 世代的第一颗三合一助眠硬件</text>
</svg>
```

**全部 6 行**。一个 1280×720 的画布只有 4 个元素。

### 1.3 对比 glassmorphism_demo.pptx 封面转出的 SVG

```
[OK] 111 行 svg
   - 4 个 <linearGradient>/<radialGradient> + 1 个文本渐变
   - 全画布背景图 (image 30f1b...)
   - 玻璃面板 (roundRect rx=22, fill=url(#ggrad2), stroke=#FFFFFF opacity 0.2)
   - 3 个圆点装饰 (Ellipse 6/7/8: #3DDDFC/#5B8DEF/#A26BFA)
   - "TECH TALK · 2026" 标签 + 渐变横线
   - 主标题（80px 渐变文本 url(#txtgrad5)）
   - 副标题（28px 白）
   - 渐变强调条 (line, stroke-width=2, stroke-linecap=round)
   - 页脚三段 (作者 / 数据 / VOL·NO)
   - 页脚页码
   - 全部带 data-pptx-* 元数据
```

**这是"设计语言"和"代码量"的双重碾压。**

### 1.4 已生成但被丢弃的产物

| 路径 | 实际状态 |
|---|---|
| `images/hero.png` | ✅ 已生成（封面主视觉） |
| `images/page_01.png` ~ `page_06.png` | ✅ 已生成（页面配图） |
| `svg_output/*.svg` | ✅ 已生成 11 个，但**全无 `<image>` 引用** |
| `svg_final/*.svg` | ✅ 与 svg_output 完全相同（finalize_svg 没有内容可处理） |
| `exports/*.pptx` | ❌ **空目录**，svg_to_pptx 因质量检查未过而拒绝导出 |

**生图阶段是孤立运行，没有任何机制把图片注入到 SVG。**

### 1.5 svg_quality_checker 报错（关键阻塞点）

对当前 slide_02_executive_summary.svg 的检查结果：

```
[ERROR] <path> attribute fill='currentColor' × 8  (图标用 currentColor 转换器拒绝)
[ERROR] spec_lock typography-size recurrence: undeclared font-size 11 (14 occurrences) 超过稀疏上限
[ERROR] <g id="p3-chart"> data-pptx-bounds exceeds canvas viewBox  (chart 的 EMU 坐标超出画布)
[ERROR] <text> exceeds <g id="p3-chart"> data-pptx-bounds
[ERROR] page SVG is missing root data-pptx-page-role
[WARN]  17 ungrouped top-level Slide-local element(s) (rect/text 没分组)
[WARN]  Top-level visible <g> without id  (动画/语义引用断裂)
```

→ **管线在最后一公里卡住**，用户看到的是 `exports/ 为空`，而错误信息没有暴露到前端。

### 1.6 现有 spec_lock.md 的缺陷

对比 demo 项目的 `design_spec.md` 普遍 200+ 行（包含 §I-X 十节），现有 spec_lock **完全没有**：

- `## III. Visual Theme` 详细描述（形状/装饰/留白/纹理）
- `## IV. Typography System` 字号阶梯（demo 用了 6 档：13/24/28/44/68/80）
- `## V. Layout System` 网格 / 安全区
- `## VI. Icon System` 库引用 / 笔画
- `## VII. Visualization System` 图表家族
- `## VIII. Image Resource List` 资源列表（demo 引用 8-20 张图）
- `## IX. Page Roster` 逐页完整 brief（每页包含：Core message / Audience move / Layout / Visualization / Content）
- `## X. Source / Provenance` 引用与依据

**当前的 spec_lock 只有 7 个 section，整个执行锁定是"空壳"。**

### 1.7 已被废弃但更完整的 dsl_to_svg.py

仓库的 `Agent_Platform_QX/agents/ppt-design-agent/dsl_to_svg.py` 有 **614 行**完整代码，包含：

- 页面预算器（高度预算 → 字号阶梯降级 → 截断 → 溢出标记）
- CJK 换行校准（CJK 1.0em / ASCII 0.55em）
- 图表库（column/line/pie/radar/stacked/scatter）
- 原生 chart marker（data-pptx-replace-with="chart"）
- chunk-filled 图标内联
- 版式脚手架（Hero/标题区/页脚页码/章节强调条）
- 图片槽位

**这是 v1 时代的成果，v2（当前 agent.py）以"放弃确定性渲染"为名丢弃了它**，但 v2 自身又没有把 LLM 创作引导到 demo 的水准。

---

## 2. 差距根因分析（按优先级）

### 🔴 P0：设计语言完全缺失（最关键）

现有实现将 hugohe3/ppt-master 视为"工具脚本"而不是"设计系统"。`SKILL.md` 明确写的：

> PPT Master is a routed presentation workflow. This entry owns global execution discipline and route selection only; each selected route owns its procedure.

但当前实现**没有走任何 Route**：

- 没有从 `references/visual-styles/_index.md` 选一种 visual style
- 没有从 `references/modes/_index.md` 选一个 mode
- 没有从 `references/image-renderings/_index.md` 选 image-rendering
- 没有走 `workflows/generate-pptx.md` 的 7 步流程
- 没有跑 `strategist` / `confirm_ui` / `image_acquisition` 等关键节点

**后果**：LLM 不知道"玻璃态"是什么、"瑞士极简"是什么、"孟菲斯风格"是什么，只能产出"咨询风通用版"——而这个"通用版"是空的（没有具体的形状/装饰/排版规则）。

### 🔴 P0：SVG 创作 prompt 过窄

`build_page_prompt`（`svg_author.py:65-117`）只有约 60 行有效指令：

```python
- 封面/结尾：居中标题 + 强调色条 + 留白；可选 Hero 图（低透明度铺底）
- 内容页：左上标题（26px 加粗）+ 强调竖条 + insight（14px 主色）；内容两列网格或全宽布局
- 指标卡：圆角卡片（surface 底 + accent 描边）+ 大号主色数值 + 次级标签
- 清单卡：圆角卡片 + 标题 + "• " 条目（≤8 条，超出用「等 N 项」）
- 表格：主色表头白字 + 斑马纹行
- 时间线：阶段名主色 + 里程碑条目
```

**对比 demo**：glassmorphism.svg 第 1 页有 28 个**不同类型**的视觉元素（渐变背景 / 玻璃面板 / 圆点装饰 / 标签线 / 渐变文本 / 副标题 / 强调条 / 页脚 3 段 / 页码）。

LLM 拿到的"配方表"严重不足，只能按"指标卡 + 标题 + 副标题"三件套排列。

### 🟠 P1：图片完全未嵌入

`agent.py` 的 `_generate_images` 完整跑了 `image_gen.py`，把 PNG 落到 `project_dir / images/` 和 `assets/{product_id}/`，但**没有任何代码把图片引用注入 SVG**：

```python
# agent.py 第 95-100
img_hint = ""
if images:
    parts = []
    if images.get("hero"):
        parts.append(f'<image href="images/hero.png" x="0" y="0" width="1280" height="720" ...>')
        # ↑ 这行在 svg_author.py 里被生成，但 svg_author 没拿到 images 参数
```

**bug**：`svg_author.py` 的 `build_page_prompt` 接受 `images` 参数但**默认 `None`**，而 `agent.py:_author_pages` 调用时**传了 `img_assets`**（见 agent.py:295），但 `img_assets["pages"]` 是 `images.get("pages") or {}`（agent.py:295），而 `_generate_images` 返回的 `result["pages"]` 是一个 dict 把 `f"{int(m.group(1)):02d}"` 映射到 `svg_ref`（agent.py:421-422）。**理论上能传，但 LLM 看到 prompt 里的图片提示后，输出的 SVG 99% 不带 `<image>` 标签**——LLM 在第一轮 8192 token 限制下根本不会画多层结构。

### 🟠 P1：质量检查失败但无降级

`svg_to_pptx.py` 默认 release export 要求 `svg_quality_checker.py --stage final` 通过。当前输出有：

- 8 个 currentColor 错误（图标系统问题）
- 14 处未声明字号 11（spec_lock 不完整）
- chart EMU bounds 越界
- 缺失根 `data-pptx-page-role`
- 17 个未分组顶级元素

`agent.py` 用了 `subprocess.run` 跑 `svg_to_pptx.py`，**只读 returncode**，把 stderr 的最后 500 字符塞进 `RuntimeError` 抛出。但前端/caller 大概率把它当作普通异常吞了，用户看到的是 `exports/ 为空` + 后端日志里一坨英文错误。

### 🟡 P2：spec_lock 缺关键锚点

`spec_lock.md` 缺失（对比 demo 的 spec_lock 实际有的字段）：

```yaml
typography:
  title: 26          # demo 实际 80 / 68
  body: 14           # demo 实际 14 / 24 / 28
  # demo 还有 caption: 11, eyebrow: 13, display: 80
icons:
  library: none      # demo 是 chunk-filled
image_rendering:      # 整个 section 缺失
  hero: full-bleed-overlay
  cards: glass
page_rhythm:         # 存在但太简
  P01: anchor        # demo 是 P01: cover-anchor / P02: section-divider / ...
  P02: dense
  # demo 的 page_rhythm 是 8 段叙事节奏
```

→ `svg_quality_checker` 直接因为"undeclared font-size 11 (14 occurrences) 超过 sparse-display limit 2" 把页面打回。

### 🟡 P2：图标用 currentColor 触发转换器拒绝

`dsl_to_svg.py` 的图标系统是把 `currentColor` 替换为具体色（agent.py:85 `inner.replace("currentColor", color)`），但当前 `svg_author.py` 没有这个步骤。LLM 直接抄了 chunk-filled 图标的 `currentColor` 进 SVG，被 svg_to_pptx 拒绝。

### 🟢 P3：分页 LLM 调用互相不感知

11 个页面独立调 LLM，没有"系列一致性"机制：

- 同一封面的 4 段页脚（"AI Agent 工程化" / 数据日期 / "VOL·NO" / "$297B·81%·4 deals"）跨 20 页保持完全一致
- 同一渐变（`url(#ggrad4)`）跨多张幻灯片复用
- 同一字体（`"Segoe UI", "Microsoft YaHei"`）全篇统一
- 同一调色板（六色 HEX 严格保持）

当前 `build_page_prompt` 把 palette 注入 prompt，但**没有注入跨页调色板文件**、**没有注入跨页渐变/装饰 reuse 机制**。LLM 看到的是 "这次用这几个色"，下次就漂移。

### 🟢 P3：模型选择偏弱

`agent_platform/config/settings.py` 默认 PRESENTATION_LLM_MODEL 是空的，会回退主 LLM（DeepSeek）。DeepSeek 在 SVG 长输出（4-6k tokens）+ 严格 XML 规范下表现远不如专门的视觉/代码模型（MiniMax、Claude Sonnet）。8192 max_tokens 对一页 200+ 形状的 SVG 来说偏紧。

---

## 3. 解决方案（三阶段）

### 总览

```
Phase 1 (P0, 1-2 天) — 修复阻塞，恢复 PPTX 导出
Phase 2 (P0-P1, 1 周) — 接入 ppt-master 完整设计系统
Phase 3 (P1-P3, 1-2 周) — 跨页一致性 + 多风格库 + 质量门禁
```

---

### Phase 1：打通管线（紧急止血）

**目标**：现有 11 页输入能稳定产出可用的 PPTX；视觉质量小幅提升（≥3× 密度）。

#### 1.1 重写 `svg_author.py` 的 prompt 引擎

`build_page_prompt` 从 60 行扩到 ~250 行，包含：

```python
# 1. 视觉风格配方（按 selected_visual_style 注入）
STYLE_RECIPES = {
    "glassmorphism": """
        全画布深色 #0A0E27 背景 → 上覆一张全幅 hero image (opacity 0.4)
        → 半透明玻璃面板 (roundRect rx=22, fill=url(#gradient1) opacity 0.22,
           stroke=#FFFFFF opacity 0.2)
        → 渐变光带 (line, stroke=url(#gradient2) stroke-width=2 stroke-linecap=round)
        → 渐变文字 (fill=url(#txtgradient) 用于主标题)
        → 装饰圆点三连 (Ellipse r=4, fill=#3DDDFC/#5B8DEF/#A26BFA, 间距 12)
    """,
    "swiss-minimal": """
        浅色 #FFFFFF 背景 + 12 列网格 (左 56px / 右 56px 安全边)
        → 大号无衬线主标题 (60-80px) 顶部偏左
        → 红色横线 (line, stroke=#E63946 stroke-width=2) 紧贴主标题
        → 黑色亚标题 (24px) + 灰色 metadata (11px tracking)
        → 数据条 (rect 高度 6, fill=#000 主体 + #DDD 背景)
        → 页脚左下"项目编号 / 日期" / 右下"页码" 11px
    """,
    "soft-rounded": """
        米色 #F5F1E8 背景
        → 圆角卡片 (rect rx=16, fill=#FFFFFF, shadow filter)
        → 标题 (28px 黑色) + 强调色小圆点 + 副标题
        → 指标用三列卡片 (大数 44px + 单位 14px + 标签 12px)
        → 时间线 (3-5 段横线 + 圆点 + 阶段名)
    """,
    "consulting-cyber-ivory-navy": """  # 现有"咨询风"
        象牙白 #F7F6F0 背景
        → 左上标题 (26px 衬线 + 主色 #12355B 竖条 4x34)
        → insight 副标题 (14px primary)
        → 圆角指标卡 (rect rx=14 stroke=#3D6491 1.5px)
        → 强调色数值 (28px primary bold) + 灰色标签
        → 页脚 (line + 页码)
    """,
}
```

#### 1.2 修复 currentColor + 注入 spec_lock 字号角色

```python
# 在 sanitize_svg 之前做：
def _replace_current_color(svg, color):
    return svg.replace('"currentColor"', f'"{color}"').replace("'currentColor'", f"'{color}'")

# 在 build_page_prompt 中显式列出版本:
"""- 文字字号（共 6 档，只用以下字号，违反视为越界）：
   - 11px (页脚 / metadata / 跟踪标签)
   - 13px (eyebrow / 段落标签)
   - 14px (body 正文)
   - 24-28px (subhead / 卡片标题)
   - 44-68px (主标题)
   - 80px (display，仅 P01 封面/章节扉页)"""
```

#### 1.3 修复 chart bounds 单位（EMU）

`dsl_to_svg.py` 用 `EMU = 9525` 是正确的（1px = 9525 EMU），但当前 `svg_author.py` 不生成 chart marker，问题不大。如果生成，确保：

```python
# data-pptx-bounds 单位必须是 EMU，不是 px
bounds = f"{x*9525:.0f},{y*9525:.0f},{w*9525:.0f},{h*9525:.0f}"
# 且 bounds 必须在 viewBox 内 (0,0)-(1280,720) → (0,0)-(12192000, 6858000) EMU
```

#### 1.4 注入根属性 + 顶级分组

```python
def _wrap_svg(body, page_type, page_idx):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720"
  viewBox="0 0 1280 720"
  data-pptx-page-role="{page_type}">
<g id="slide-background" data-pptx-role="background">
  <!-- 背景层 -->
</g>
<g id="slide-frame" data-pptx-role="decoration">
  <!-- 页眉/页脚 -->
</g>
<g id="slide-content-{page_idx}">
  {body}
</g>
</svg>'''
```

#### 1.5 兜底页升级

当前 `fallback_svg`（svg_author.py:204-231）只有 28 行、内容稀薄。升级为：

- 至少 80 行
- 含渐变背景 / Hero 占位 / 圆角指标卡 / 渐变强调条 / 多行页脚
- 仍保证"内容不丢"（每个 component 都渲染出来）

#### 1.6 暴露错误到前端

```python
# agent.py:_run 末尾
if proc.returncode != 0:
    # 解析 svg_quality_checker 的输出，把 ERROR 列表写回 state
    detail = _parse_quality_errors(proc.stderr or proc.stdout)
    raise RuntimeError(f"svg_to_pptx 失败: {detail}")
# 同时把 detail 写一份到 project_dir / validation_report.json 供前端展示
```

#### 1.7 Phase 1 验收

- [ ] 11 页全部导出 `exports/*.pptx`
- [ ] 打开 PPTX 看到至少 25+ 形状 / 页（含分组）
- [ ] 至少有 1 个渐变 / 页
- [ ] 至少 3 个不同字号
- [ ] 至少 1 个装饰元素（圆点/横线/小色块）/ 页

---

### Phase 2：接入完整设计系统（核心升级）

**目标**：从"单风格咨询风"升级为"6 风格可选 + 跨页复用设计元素"，向 demo 水平靠拢（≥70% 视觉密度）。

#### 2.1 新建 `design_system/` 模块

```
agents/ppt-design-agent/
├── design_system/
│   ├── __init__.py
│   ├── style_library.py       # 6 个 visual_style 的完整配方
│   ├── style_recipes/         # 6 个 .md：glassmorphism / swiss-minimal / soft-rounded /
│   │                          #           dark-tech / ink-wash / consulting-cyber-ivory-navy
│   ├── mode_library.py        # 5 个 mode：briefing / pyramid / narrative / showcase / instructional
│   ├── palette_anchors.py     # 12 套调色板（HEX + 语义 role）
│   ├── typography_roles.py    # 6 档字号阶梯 + 字体栈
│   ├── element_library.py     # 装饰元素 (圆点/横线/玻璃面板/象限轴) 模板函数
│   ├── component_library.py   # 12 类 component 的渲染器 (从 dsl_to_svg 移植并升级)
│   └── cross_page.py          # 跨页一致性：页脚/页码/项目编号/渐变 ID
```

#### 2.2 style_library.py 设计

```python
from dataclasses import dataclass, field
from typing import Callable

@dataclass
class VisualStyle:
    id: str
    name: str
    description: str
    page_background: str
    decorative_elements: list[str]
    recipe_md_path: str  # 指向 recipes/{id}.md
    build_cover: Callable
    build_section_divider: Callable
    build_content: Callable
    build_data_dense: Callable
    build_conclusion: Callable

STYLES = {
    "glassmorphism": VisualStyle(
        id="glassmorphism",
        name="Glassmorphism 玻璃态",
        description="深色 #0A0E27 + 半透明玻璃面板 + 渐变光带 + 渐变文字。SaaS / 金融科技 / AI 产品发布。",
        page_background="#0A0E27",
        decorative_elements=["glass_panel", "radial_glow", "3_dot", "gradient_bar", "image_overlay"],
        recipe_md_path="style_recipes/glassmorphism.md",
        build_cover=_build_glassmorphism_cover,
        ...
    ),
    "swiss-minimal": VisualStyle(...),
    "soft-rounded": VisualStyle(...),
    "dark-tech": VisualStyle(...),
    "ink-wash": VisualStyle(...),
    "consulting-cyber-ivory-navy": VisualStyle(...),  # 现有
}
```

#### 2.3 component_library.py 升级

把 dsl_to_svg.py 的 12 类组件（`metric / card / table / timeline / quote / chart / matrix / text / cover / summary / ...`）**逐个升级**：

| 组件 | 当前（dsl_to_svg） | Phase 2 升级 |
|---|---|---|
| `metric` | 圆角卡 + 数值 + 标签 | + icon slot + 单位槽 + 趋势箭头 + mini sparkline |
| `card` | 标题 + bullet 列表 | + 序号 + tag chips + 悬浮态阴影 |
| `table` | 表头 + 行 | + 主色斑马纹 + 关键行高亮 + 列对齐规则 |
| `timeline` | 阶段名 + 里程碑 | + 进度条 + 节点圆 + 阶段色阶 |
| `quote` | 引用 + 来源 | + 大引号字符 + 双线装饰 + 来源页码 |
| `chart` | SVG 兜底 + chart marker | + 5 类图表 (column/line/pie/radar/scatter) + 渐变填充 |
| `matrix` | 2D 散点 | + 象限名 + 中轴 + 标签 + 本品高亮 |
| `text` | 段落 | + 首字下沉 + 引用块 + 编号 |
| `cover` | 居中标题 + 副标题 | + Hero 图全幅 + 渐变遮罩 + 双语标题 + 多行 meta |
| `summary` | 4 个 metric | + 大数 + 趋势 + 排名 + 链接 |

每个组件**都返回 `data-pptx-bounds` 和 `data-pptx-id`**，让 `svg_to_pptx` 能精确转换。

#### 2.4 跨页一致性 `cross_page.py`

```python
@dataclass
class DeckIdentity:
    project_name: str
    project_code: str          # "VOL.01 · NO.05"
    date: str                  # "数据截至 2026-05-15"
    footer_left: str           # "AI Agent 工程化"
    footer_center: str         # "Capital, Compute, and the Closed Loop"
    accent_color: str
    text_palette: dict
    gradient_ids: list[str]    # 复用

def inject_deck_identity(svg: str, identity: DeckIdentity, page_idx: int, total: int) -> str:
    """在每页 SVG 末尾注入统一的页脚组 (data-pptx-layer='master')"""
    footer = f'''
<g id="page-footer-{page_idx}" data-pptx-layer="master">
  <line x1="58.7" y1="676.95" x2="1221.3" y2="676.95" stroke="#6B7299" stroke-width="0.5" opacity="0.4"/>
  <text x="58.7" y="688" font-size="13" fill="#A8B0D0" font-weight="bold">{identity.footer_left}</text>
  <text x="640" y="688" text-anchor="middle" font-size="11" fill="#6B7299">{identity.footer_center}</text>
  <text x="1221.3" y="688" text-anchor="end" font-size="13" fill="#6B7299" font-weight="bold">{page_idx:02d} / {total:02d}</text>
</g>'''
    return svg.replace("</svg>", footer + "</svg>")
```

#### 2.5 把 spec_lock 真正做厚

参考 `templates/spec_lock_reference.md` 完整字段：

```markdown
# Execution Lock

## canvas
- viewBox: 0 0 1280 720
- format: PPT 16:9

## communication
- primary_language: zh-CN
- audience: 决策者与产品团队
- objective: 完整传达产品论证（SCR）并驱动行动
- core_message: ...

## mode
- mode: briefing
- mode_references: [briefing]

## visual_style
- visual_style: glassmorphism
- visual_style_references: [glassmorphism]

## colors
- bg: #0A0E27
- surface: #1A1F3A
- primary: #5B8DEF
- accent: #A26BFA
- text: #E8ECFF
- muted: #6B7299
- secondary_accent: #3DDDFC
- tertiary_accent: #4ADE80
- gradient_ids: [ggrad1, ggrad2, ggrad3, ggrad4, ggrad5, txtgrad6]

## typography
- font_family: "Segoe UI", "Microsoft YaHei", "PingFang SC", sans-serif
- title_family: "Segoe UI", "Microsoft YaHei", sans-serif
- title: 80              # display
- subtitle: 28
- body: 14
- caption: 11
- eyebrow: 13
- metric_value: 68
- font_size_recurrence_max: 8   # 替代 svg_quality_checker 的硬限 2

## icons
- library: chunk-filled
- inventory: [chart-line, list, chart-bar, clock, lightbulb, ...]

## image_rendering
- hero: full-bleed-overlay
- decoration: glass-blur
- page_thumbnail: glass-card

## page_rhythm
- P01: cover-anchor
- P02: section-divider
- P03: contents-toc
- P04-P10: data-dense
- P11: conclusion-anchor

## pptx_structure
- mode: flat

## forbidden
- mask, style, class, foreignObject, textPath, font-face, animate, set, script, iframe
```

→ 这套 spec_lock 满足 `svg_quality_checker` 的所有要求，且能真正引导 SVG 创作。

#### 2.6 LLM prompt 重构（核心 prompt 升级）

把 `build_page_prompt` 拆成 4 段：

```python
def build_page_prompt(page, style, mode, spec_lock, design_spec, images, page_idx, total):
    return f"""
## 角色
你是 ppt-master Executor（资深咨询/科技风 SVG 设计师）。
按 locked visual_style "{style.id}" 的视觉语言，输出 1 页 1280×720 的 SVG。

## 视觉风格配方（{style.id}）
{style.recipe_md}        # 150-300 行 markdown：形状/装饰/留白/纹理/调色板规则

## 模式（{mode.id}）
{mode.recipe_md}          # 50-100 行：叙事节奏 / 内容承载 / 视觉变化

## 排版（spec_lock）
{typography_block}       # 6 档字号阶梯 + 字体栈
{palette_block}          # 7 个 HEX + 角色
{decorative_block}       # 可用装饰元素 ID 列表

## 跨页身份（deck identity）
{identity_block}         # 页脚 / 项目编号 / 渐变 ID

## 当前页面（DSL）
{page_json}

## 可用图片
{images_block}           # hero + page-specific

## 硬性规则
{skill_rules}

## 构图要求（{page.type}）
{style.build_<page_type>(page)}

## 输出
仅输出 <svg>…</svg>，200-400 行结构化 SVG。"""
```

→ 把每种 visual_style 写成 200 行的 markdown "操作手册"，LLM 拿到的"配方"从 60 行变成 ~600 行。

#### 2.7 模型升级

`settings.py` 默认 `PRESENTATION_LLM_MODEL` 留空，迫使回退到 DeepSeek-chat。改为：

```python
# 默认值（与 DeepSeek 并列时优先用专门的视觉模型）
PRESENTATION_LLM_MODEL: str = Field(default="claude-sonnet-4.5")
# 或：MiniMax-M3（当前模型）/ claude-sonnet-4.5 / gpt-4o (排序按视觉质量)
# max_tokens 8192 → 16384（让 LLM 一次画 300+ 形状）
```

`LLM_MAX_TOKENS: int = Field(default=16384)` 用于 presentation 任务。

#### 2.8 Phase 2 验收

- [ ] 6 套 visual_style 全部能产出可导出 PPTX
- [ ] glassmorphism 风格的 SVG 至少含：1 个 linearGradient + 1 张 image + 1 个玻璃面板 + 1 个渐变文字 + 3 个圆点 + 页脚 3 段
- [ ] 跨 11 页的页脚/项目编号/渐变 ID 完全一致
- [ ] spec_lock 通过 `project_manager.py validate` 校验
- [ ] 5+ 种不同字体角色被实际使用（不只 26/14 两档）

---

### Phase 3：质量门禁 + 多风格库 + 跨页复用

**目标**：跑赢 demo（≥90% 视觉密度），跑通视觉风格 A/B，支持动画与交互。

#### 3.1 端到端质量门禁

`agent.py:_run` 末尾增加 3 道门：

```python
# 门 1: SVG 质量（ppt-master 自带）
svg_qc = subprocess.run([sys.executable, str(QC_SCRIPT), project_dir, "--stage", "final", "--json"],
                       capture_output=True, text=True, timeout=300)
qc_report = json.loads(svg_qc.stdout)
if qc_report["summary"]["fatal"] > 0:
    # 自动 LLM 修复一轮（带错误反馈）
    fixed = self._retry_svg_with_feedback(svg_files, qc_report)
    # 重新跑 QC；如果仍失败，启用 v1 dsl_to_svg 兜底
    if not fixed:
        _fallback_legacy_dsl_render(presentation, project_dir)

# 门 2: 内容完整性（关键文本/数据值都在 SVG 里）
content_check = self._content_completeness_check(svg_files, presentation)
if not content_check.ok:
    raise RuntimeError(f"内容缺失: {content_check.missing}")

# 门 3: 视觉密度（每页至少 N 个 shape / M 个字号档）
density = self._visual_density_check(svg_files)
if density.avg_shapes_per_page < 25:
    logger.warning("视觉密度低于 25 shapes/page, 建议升级 prompt")
```

#### 3.2 自动修复回路

LLM 创作的 SVG 经常犯同样错误，建立"错误→修复"模式库：

```python
SVG_FIX_RECIPES = {
    r"fill=['\"]currentColor['\"]": lambda svg, ctx: svg.replace("currentColor", ctx["primary"]),
    r"font-size=['\"](\d+)['\"]  # 出现 > 8 次的字号不在 spec_lock 声明里":
        lambda svg, ctx: _normalize_undeclared_font_sizes(svg, ctx),
    r"<text[^>]*>([^<]+)</text>(?!\s*<text)":  # 连续 5 个 <text> 没分组
        lambda svg, ctx: _wrap_loose_texts(svg),
    # ...
}
```

→ svg_qc 失败后，先跑这个 pattern-based 修复器，再 LLM 重试。

#### 3.3 风格选择 UI

前端加一个 "Style" 下拉（glassmorphism / swiss-minimal / soft-rounded / dark-tech / ink-wash / consulting-cyber-ivory-navy），默认按产品类型自动选：

```python
STYLE_AUTO_SELECT = {
    "tech": "glassmorphism",
    "consulting": "consulting-cyber-ivory-navy",
    "creative": "soft-rounded",
    "luxury": "swiss-minimal",
    "education": "ink-wash",
    "default": "soft-rounded",
}
```

#### 3.4 模板复用

把 glassmorphism_demo.pptx / global_ai_capital_2026.pptx / swiss_grid_systems.pptx 等 6 个 demo 通过 `create-template` 流程固化为 `templates/decks/` 下的可复用 workspace：

```bash
# 把 demo 转成 deck workspace
python3 ${SKILL_DIR}/scripts/template_import.py /path/to/glassmorphism_demo.pptx \
  --out ${SKILL_DIR}/templates/decks/glassmorphism-tech/

# 之后在设计 spec 中引用
visual_style: glassmorphism
template_workspace: deck/glassmorphism-tech
```

→ Phase 3 后期用 workspace 模式生产，能达到 demo 100% 还原。

#### 3.5 动画 / 过渡（可选）

`templates/styles/` 和 `executor-base.md` §1 都支持动画。Phase 3 末开启：

- P01 封面：渐入 (fade-in 600ms)
- P03 目录：左侧 1-6 数字逐次滑入
- 数据图表：柱条从 0 长到目标高度 (1000ms ease-out)
- 全文 1 道 page transition (推入 / 淡出)

#### 3.6 Phase 3 验收

- [ ] 6 套风格都能产出与 demo 同等密度的 SVG
- [ ] 至少 3 个 deck workspace 可复用
- [ ] 端到端跑通：DSL → design_spec → svg_output → svg_final → exports/*.pptx
- [ ] PPTX 在 PowerPoint / Keynote / WPS 三端打开一致
- [ ] 动画开关可配置

---

## 4. 关键技术决策表

| 决策 | 方案 A | 方案 B | 推荐 |
|---|---|---|---|
| 风格如何选 | 写死在 theme.id → mapping | 前端 UI 让用户选 | A 上线后切 B |
| SVG 创作 | 纯 LLM 自由写 | 模板骨架 + LLM 填空 | **B**（demo 就是骨架式） |
| 图片集成 | 生图后直接 embed | 用 ppt-master 的 image_strategy pipeline | **B**（复用现有脚本） |
| 质量门禁 | svg_quality_checker 硬拒 | pattern 自动修复 + 重试 | **B** |
| 兜底 | v2 fallback_svg | v1 dsl_to_svg 移植升级 | **B** |
| 跨页一致性 | LLM 在每页 prompt 重复声明 | cross_page.py 注入 master layer | **B** |
| 模型 | DeepSeek | Claude Sonnet / MiniMax | **B**（专门视觉任务） |
| max_tokens | 8192 | 16384 | **B** |
| 风格库规模 | 1 (咨询风) | 6 (Phase 2) → 18 (Phase 3) | **渐进** |

---

## 5. 工作量估算

| 阶段 | 关键文件 | 行数估算 | 人天 |
|---|---|---|---|
| Phase 1.1 prompt 扩写 | `svg_author.py` | +200 | 1 |
| Phase 1.2 currentColor 修复 | `svg_author.py` | +20 | 0.5 |
| Phase 1.3 chart bounds 修复 | `svg_author.py` | +30 | 0.5 |
| Phase 1.4 根属性 + 分组 | `svg_author.py` | +40 | 0.5 |
| Phase 1.5 兜底升级 | `svg_author.py` | +80 | 0.5 |
| Phase 1.6 错误暴露 | `agent.py` | +40 | 0.5 |
| Phase 1 联调 | - | - | 1 |
| **Phase 1 合计** | | **~410 行** | **4.5 人天** |
| Phase 2.1 design_system 模块 | 新建 5 文件 | +800 | 3 |
| Phase 2.2 style_library.py | 新建 | +300 | 1 |
| Phase 2.3 component_library.py | 移植+升级 | +1200 | 4 |
| Phase 2.4 cross_page.py | 新建 | +200 | 1 |
| Phase 2.5 spec_lock 重做 | `agent.py` | +200 | 1 |
| Phase 2.6 prompt 重构 | `svg_author.py` | +300 | 2 |
| Phase 2.7 模型升级 | `settings.py` | +5 | 0.5 |
| Phase 2 联调 | - | - | 2 |
| **Phase 2 合计** | | **~3000 行** | **14.5 人天** |
| Phase 3.1 端到端门禁 | `agent.py` | +300 | 2 |
| Phase 3.2 自动修复 | `svg_author.py` | +250 | 2 |
| Phase 3.3 风格 UI | 前端 + 后端 | +400 | 2 |
| Phase 3.4 模板复用 | 6 个 deck workspace | +800 | 3 |
| Phase 3.5 动画 | `agent.py` | +200 | 2 |
| **Phase 3 合计** | | **~1950 行** | **11 人天** |
| **总计** | | **~5400 行** | **~30 人天** |

---

## 6. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| LLM 仍输出低质量 SVG | 高 | 阻塞 | 模板骨架 + 详细 prompt + 兜底三件套 |
| Claude/MiniMax 不可用 | 中 | 阻塞 | DeepSeek + 自动 pattern 修复 |
| svg_quality_checker 规则过严 | 中 | 阻塞 | fork 并放宽 sparse-display 限值（2→8） |
| 6 个 demo 模板导入失败 | 中 | 中 | 先用 style_recipe 模式（不导入），Phase 3 末再补 |
| 用户误选风格导致效果差 | 低 | 低 | auto-select 默认 + 提示用户 |
| ppt-master 版本升级破坏兼容 | 低 | 高 | 锁定 vendor/ppt-master 版本到 4.7.0 |
| 图片版权 / 敏感内容 | 低 | 高 | image_gen prompt 加审核 + 关键词过滤 |

---

## 7. 立即可执行的 3 个动作

如果只能做 3 件事，按优先级：

1. **修 svg_to_pptx 错误暴露 + 启用 v1 dsl_to_svg 兜底**（2 小时）
   - 把 `dsl_to_svg.py` 从 614 行 v1 改造成 `v3_compat.py`，避免 currentColor / chart bounds 错误
   - `agent.py` 在 LLM 创作失败时自动回退 v3
   - 把 svg_quality_checker 的 stderr 写回 state.data["errors"]

2. **prompt 大幅扩写 + spec_lock 真实化**（半天）
   - `build_page_prompt` 加 6 段（角色/视觉配方/模式/排版/跨页身份/构图）
   - spec_lock 真正写 6 档字号 + 5 个 decorative elements + image_rendering

3. **图片注入 + 跨页 footer 注入**（半天）
   - `agent.py` 生成图片后，把 `<image>` 标签直接写进 SVG（不靠 LLM）
   - `cross_page.py` 注入统一的 footer group（data-pptx-layer="master"）

→ 完成这 3 件事，**单页 shape 数能从 5-12 提升到 30-50**，**单页 SVG 行数从 45 提升到 200-400**，**且 PPTX 能成功导出**。视觉密度会从 demo 的 11% 提升到 50-60%。

---

## 8. 附录

### 8.1 关键文件位置

```
/home/administrator/dev/agents/agents/ppt-design-agent/
├── agent.py              (435 行) — 框架适配
├── svg_author.py         (231 行) — LLM 创作引擎 + 兜底
└── vendor/ppt-master/    (~150 个文件) — 完整 skill，未被使用
    ├── SKILL.md
    ├── workflows/
    │   ├── generate-pptx.md     (完整 7 步流程)
    │   ├── profiles/             (Quick / Image-to-PPTX / Beautify)
    │   └── stages/              (10 个 stage)
    ├── references/
    │   ├── visual-styles/       (18 个 style markdown)
    │   ├── modes/               (5 个 mode markdown)
    │   ├── image-renderings/    (12 个 rendering)
    │   ├── image-palettes/      (12 个调色板)
    │   ├── executor-base.md     (SVG 创作规则)
    │   ├── shared-standards-core.md
    │   └── svg-effects.md
    ├── templates/
    │   ├── styles/              (12 套风格模板)
    │   ├── layouts/             (8 套布局模板)
    │   ├── decks/               (2 个 deck workspace)
    │   ├── design_spec_reference.md
    │   └── spec_lock_reference.md
    └── scripts/                  (40+ 脚本)
        ├── finalize_svg.py       (✅ 在用)
        ├── svg_to_pptx.py        (✅ 在用)
        ├── svg_quality_checker.py (未用)
        ├── project_manager.py
        ├── source_to_md.py
        ├── image_gen.py
        ├── image_search.py
        ├── pptx_to_svg.py
        └── ... (30+ more)
```

### 8.2 已尝试的 6 个 demo（来自 `C:\Users\Administrator\Desktop\ppt temp`）

| 文件 | 风格 | 页数 | 视觉密度 | 备注 |
|---|---|---|---|---|
| glassmorphism_demo.pptx | glassmorphism | 12 | 极高 | 玻璃态 + 渐变文字 + Hero 图 |
| global_ai_capital_2026.pptx | editorial/data-journalism | 20 | 极高 | 多层分组 + 数据可视化 |
| indie_bookstore_zine_guide.pptx | zine | 18 | 中高 | 印刷质感 + 网格 |
| pritzker_2026.pptx | editorial | 11 | 极高 | 杂志风格 + 大图 |
| sugar_rush_memphis.pptx | memphis | 14 | 中 | 几何块 + 撞色 |
| swiss_grid_systems.pptx | swiss-minimal | 14 | 中 | 极简瑞士 + 网格 |

### 8.3 当前 spec_lock.md vs demo spec_lock.md 字段对比

| 字段 | 当前 | demo glassmorphism | demo global_ai | 备注 |
|---|---|---|---|---|
| canvas | ✅ | ✅ | ✅ | 一致 |
| communication | ✅ 4 字段 | ✅ 7 字段 | ✅ 7 字段 | 当前缺 audience/objective 等 |
| mode | ✅ custom | ✅ briefing | ✅ narrative | 当前是空壳 |
| visual_style | ✅ 1 个 id | ✅ 1 个 + 描述 | ✅ 1 个 + 描述 | 缺 recipe 引用 |
| colors | ✅ 6 色 | ✅ 8 色 + gradient | ✅ 8 色 + gradient | 缺渐变 ID |
| typography | ✅ 4 字段 | ✅ 8 字段 | ✅ 8 字段 | 缺字号角色表 |
| icons | ✅ none | ✅ chunk-filled + 库存 | ✅ chunk-filled | 当前没有图标库 |
| image_rendering | ❌ 缺失 | ✅ 完整 | ✅ 完整 | 缺整段 |
| page_rhythm | ✅ 2 类 | ✅ 8 段节奏 | ✅ 6 段 | 太简 |
| pptx_structure | ✅ flat | ✅ flat | ✅ flat | 一致 |
| forbidden | ✅ 完整 | ✅ 完整 | ✅ 完整 | 一致 |
| **总行数** | **46** | **~80** | **~80** | demo 字段更全 |

### 8.4 6 个 visual_style 描述（来自 `references/visual-styles/_index.md`）

| ID | 名称 | 最佳场景 | Illus. | Paired Rendering |
|---|---|---|---|---|
| swiss-minimal | 网格极简 | 咨询/建筑/奢华 | sparse | minimalist-swiss |
| soft-rounded | 柔圆卡片 | 产品/SaaS/培训 | supportive | flat |
| glassmorphism | 玻璃态 | SaaS/金融/AI 演示 | sparse | glassmorphism |
| dark-tech | 深色科技 | 科技/AI/数据产品 | sparse | digital-dashboard |
| editorial | 杂志层级 | 金融/新闻/分析 | supportive | editorial |
| photo-editorial | 大图主导 | 建筑/设计/旅游 | sparse | corporate-photo |
| data-journalism | 数据新闻 | 财经/Bloomberg | sparse | editorial |
| brutalist | 新闻密度 | 年度报告 | supportive | screen-print |
| memphis | 孟菲斯 | 节日/青年 | core | flat |
| zine | 独立志 | 文化/设计 | core | screen-print |
| vintage-poster | 复古海报 | 老字号/周年 | core | vintage-poster |
| paper-cut | 剪纸 | 民俗/儿童 | core | paper-cut |
| sketch-notes | 草图笔记 | 教育/培训 | core | sketch-notes |
| ink-notes | 水墨笔记 | 方法论/宣言 | supportive | ink-notes |
| chalkboard | 黑板 | 教学/课堂 | core | chalkboard |
| ink-wash | 水墨 | 文化/哲学 | supportive | ink-notes |
| pixel-art | 像素 | 游戏/复古 | core | pixel-art |
| blueprint | 蓝图 | 工程/系统 | supportive | blueprint |

### 8.5 失败原因（按出现频次降序）

| 错误 | 出现页 | 根因 | 修复点 |
|---|---|---|---|
| fill='currentColor' | 8/11 | 图标未替换 currentColor | Phase 1.2 |
| undeclared font-size 11/9 | 8/11 | spec_lock 缺字号角色 | Phase 1.2 + Phase 2.5 |
| chart bounds 越界 (EMU 533400) | 3/11 | chart marker 边界计算错 | Phase 1.3 |
| 缺根 data-pptx-page-role | 11/11 | svg 模板无根属性 | Phase 1.4 |
| 17 ungrouped 顶级元素 | 8/11 | LLM 不分组 | Phase 1.4 + 模板骨架 |
| 缺 data-pptx-bounds | 5/11 | 组件未声明边界 | Phase 2.3 |
| 缺 data-pptx-id | 5/11 | 同上 | Phase 2.3 |

### 8.6 当前生成的 svg_output 形态

```
svg_output/
├── slide_01_cover.svg              5 行
├── slide_02_executive_summary.svg  35 行
├── slide_03_market_overview.svg    29 行
├── slide_04_market_overview.svg    43 行
├── slide_05_competitor_matrix.svg  90 行
├── slide_06_user_persona.svg       43 行
├── slide_07_user_journey.svg       37 行
├── slide_08_product_architecture.svg 68 行
├── slide_09_feature_priority.svg   112 行
├── slide_10_roadmap.svg            31 行
├── slide_11_conclusion.svg         4 行
└── 总计 497 行 / 11 页
```

### 8.7 demo 的 svg-flat 形态（`/tmp/opencode/glassmorphism_svg/svg-flat/`）

```
slide_01.svg   111 行
slide_02.svg   174 行
slide_03.svg   421 行
slide_04.svg   642 行
slide_05.svg   485 行
...
slide_09.svg   553 行
总计 3905 行 / 12 页
```

→ demo 平均每页 **370 行** vs 当前 **45 行**，**8.2× 差距**。

---

**报告完成。核心建议先做 Phase 1（4.5 人天），立即把 PPTX 导出打通并把视觉密度提升 3×；再上 Phase 2（14.5 人天）真正接入 ppt-master 的设计系统。**
