# PPT 质量改进调研与规划（2026-08）

针对 5 个问题逐项取证分析，给出分阶段方案（证据来自实测产物）。

## 问题 1：内容超出页面范围

**实测证据**（8e796465 产品，10 页 SVG 渲染最大 Y vs 720 画布）：
| 页 | 类型 | 组件数 | 最大 Y | 结论 |
|---|---|---|---|---|
| P03 | market_overview | 8 | **864** | ⚠️ 超界（渲染器 break 静默截断 → **丢内容**） |
| P04 | competitor_matrix | 4 | **764** | ⚠️ 超界 |
| P06 | user_journey | 2 | **722** | ⚠️ 超界 |
| P07 | feature_priority | 3 | **728** | ⚠️ 超界 |

PPTX 层交叉验证：CyberPPT QA `SHAPE_OUTSIDE_SLIDE ×28`（svg_to_pptx 忠实转换了越界形状）。

**根因**：
1. 无页面级高度预算规划（组件先到先得；宽组件全宽叠放拉高两列）
2. 文本换行估算偏乐观（CJK 按 0.62 字号计宽，实际全角≈1.0 字号宽）
3. 确定性注入（enrich/_inject_modular_content）不看页容量，P03 被塞到 8-11 组件
4. 渲染器 `break` 静默截断——数据丢失无告警

**方案（阶段 A）**：
- 页面预算器：先估算全部组件高度 → 超预算按阶梯降级（缩字号 10%×2 → 换列/合并 → 折叠溢出组件为"更多见下页"提示 → 最后截断并记 QA 告警）
- 换行校准：CJK 全角按 1.0em、ASCII 0.55em；文本超长加省略号
- 注入层容量感知：enrich/模块注入按剩余高度配额分配
- 自检门禁：渲染后断言 maxY ≤ 700；与 validate_pptx `SHAPE_OUTSIDE_SLIDE` 联动为 error（当前 28 个 → 目标 0）

## 问题 2：组件样式单调、图表呈现少

**实测证据**：32 组件中 card 16（50%）、metric 5、chart+matrix 仅 **2（6%）**；SVG 图表仅 bar/line/pie/quadrant 四种基础样式。

**根因**：生成侧未强制"数据页必有图"（趋势→line、对比→bar、占比→pie、定位→quadrant）；enrich 注入只产 card/text；渲染侧无雷达/堆叠/环形/双系列/标签美化。

**方案（阶段 A+B）**：
- 生成侧：cyberppt skill 加【图表入页规则】（每个含 ≥3 数据的页必须有 chart/matrix）；enrich_coverage 增加确定性图表注入（趋势→bar、痛点→计数 bar、竞品→quadrant）
- 渲染侧：扩展图表库（radar/stacked bar/donut/双系列+图例+数据标签+网格）；card 加序号/图标点缀；页码/页脚/章节标签
- 原生图表：dsl_to_svg 输出 `data-pptx-role` 标记（svg_to_pptx 已支持语义标记 → 导出为**真 PowerPoint 图表**，QA charts 从 0 变 n）

## 问题 3：ppt-master 使用完整度与 demo 差距

**使用审计**：
| 能力 | 状态 |
|---|---|
| 项目脚手架 / spec_lock / finalize_svg / svg_to_pptx（DrawingML 转换） | ✅ 已用 |
| 设计系统 templates（layouts/brands/charts scaffolds） | ❌ 未用（自绘扁平网格） |
| **图标库**（templates/icons 49MB 三套 + icon_sync + embed-icons） | ❌ 未用 |
| **原生图表/表格 markers**（data-pptx-role → 真图表） | ❌ 未用 |
| **生图后端**（image_gen.py + backend_minimax 等 14 家） | ❌ 未用 |
| 动画/转场/旁白/公式 | ❌ 未用（远期可选） |
| strategist/executor 流程与用户门 | 适配为确定性流程（有意取舍） |

**差距根因**：demo 的 SVG 由 Claude 手写（构图/图标/图片/原生图表/留白节奏）；我们 = 确定性扁平网格 + 无图标/图片/原生图表 + 溢出截断。

**方案（阶段 B）**：图标系统接入（icon_sync 同步 → 组件语义出 `<use>` 图标 → embed-icons）→ 原生 chart markers → 3-5 套 layouts 脚手架（封面/目录/数据页/对比页）→ 生图（阶段 C）→ 动画/旁白远期。

## 问题 4：为什么关闭 MiniMax think / 是否影响质量

**原因（实测）**：M3 默认开启推理 → 单调用 40-90s + `<think>` 泄漏破坏 JSON（曾致连续解析失败、单节点 10+ 分钟）；DSL 生成是**强结构任务**（JSON Schema + 覆盖清单 + 确定性兜底层），推理收益低、时延与失败成本高。官方参数 `thinking:{"type":"disabled"}` 直出 JSON（已实测）。

**质量影响评估**：
- 结构化 DSL 生成：关闭无实质损失——覆盖/密度/专名由 prompt 清单 + enforce/enrich/critic 门保证（评分不依赖模型推理）
- **创意/评审任务有推理价值**：设计简报、critic 评审

**方案（阶段 D，角色化 thinking）**：DSL 生成默认关闭；设计简报 + critic 走第二个客户端（`extra_body={"thinking":{"type":"enabled"}}`），创意质量不牺牲。

## 问题 5：MiniMax 生图 + 插入 + DesignStudio 资产库

**重大利好**：ppt-master 已内置 `image_backends/backend_minimax.py`（MiniMax-Image-01）与 `image_gen.py --manifest`（按 `images/image_prompts.json` 批量生成到 `project/images/`）+ `finalize_svg embed-images`（SVG 内嵌）——**生图管线零自研**。

**方案（阶段 C）**：
1. 配置（backend/.env）：`IMAGE_BACKEND=minimax`、`MINIMAX_API_KEY`、`MINIMAX_MODEL=MiniMax-Image-01`
2. PptDesignAgent 新增图片阶段：由逐页 title+insight 确定性生成 `image_prompts.json`（封面 Hero 1 张 + 每数据页 1 张主题图）→ 调 image_gen.py 批量生成
3. 插入规则：封面 Hero 背景、标题右侧配图、market/architecture 装饰带；SVG `<image>` 引用 → embed-images 内嵌 → 导出为图片对象
4. **DesignStudio 资产库**：生成图片同步落盘 `OUTPUT_DIR/assets/{product_id}/`（与编辑器上传共用目录）；新增 `GET /product/{id}/assets`（列目录）；DesignStudioPage 增加「图片资产库」网格（可复用编辑器 insertImage 插入画布）
5. 降级：生图失败（无 key/超时）→ 跳过图片，页面完整

## 阶段规划（建议顺序）

| 阶段 | 内容 | 验证目标 |
|---|---|---|
| A | 页面预算器 + 换行校准 + 图表入页规则 + 图表库扩展 + 溢出门禁 | SHAPE_OUTSIDE_SLIDE 28→0；图表占比 6%→≥25% |
| B | 图标库 + 原生 chart markers + layouts 脚手架 | PPTX 含图标/真图表（QA charts>0） |
| C | MiniMax 生图管线 + 插入规则 + assets 端点 + DesignStudio 资产库 | 每任务 ≥3 张图嵌入；资产库可见 |
| D | 角色化 thinking（简报/critic 启用推理） | 简报质量对比 |

每阶段配套：Playwright/QA 实测 + 回归测试 + MIGRATION 记录。
