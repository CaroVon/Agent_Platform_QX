# Layout Rules —— 布局选择与必覆盖内容清单

布局只能从以下 10 个 Layout Library 枚举中选择：

| 页型 | 布局 | 使用场景 |
|------|------|----------|
| cover | cover | 标题 + 副标题 + 底部来源 |
| executive_summary | summary | 核心结论 + 关键指标卡 + 痛点/趋势摘要 |
| market_overview | market | 市场规模全指标 + 趋势 + 痛点 |
| competitor_matrix | matrix | 象限定位（全部竞品）+ 洞察 + 差异化机会 |
| user_persona | persona | 全部画像并列卡片 |
| user_journey | journey | 步骤式旅程 + 触点 + 情绪 |
| feature_priority | features | P0/P1/P2 全部功能分组 |
| product_architecture | architecture | 分层架构卡片栈 |
| roadmap | roadmap | 全部阶段时间线 + 里程碑 |
| conclusion | closing | 金句 + 行动号召 |

## 必覆盖内容清单（完整叙事，逐项核对后输出）

| 上游字段 | 要求 |
|----------|------|
| market_size.tam / sam / som / cagr | market 页必须全部呈现（metric 或 table），附 summary 结论与来源 |
| customer_pain_points | 全部（≥4 条）必须出现在 market 页或 executive_summary 页 |
| industry_trends | 全部（≥3 条）必须出现在 market 页 |
| competitors | 全部（≥4 个）必须进入 competitor_matrix 页的 quadrant 数据点 |
| differentiation_opportunities | competitor_matrix 页 insight 或 card 呈现 |
| personas | 全部画像（2-4 个）进入 user_persona 页卡片 |
| features | 全部功能（不遗漏）按 P0/P1/P2 分组进 feature_priority 页 table |
| roadmap | 全部阶段（名称+周期+全部里程碑）进入 roadmap 页 timeline |
| prd_sections 核心结论 | 至少 1 页承载（executive_summary 的 insight 或 architecture 页），如「产品概述/成功指标」要点 |
| design.user_flow | journey 页呈现完整旅程步骤（若有该资产） |

**专有名词必须原文引用**：功能名、竞品名、画像名、路线图阶段名、
指标数值与上游文档完全一致，禁止改写/简写 —— 质量门逐项核对原文。

## 叙事顺序

8-14 页，顺序固定：cover → executive_summary → market_overview →
competitor_matrix → user_persona → (user_journey) → feature_priority →
product_architecture → roadmap → conclusion。
