# 专业 Agent 层（AI Product Studio）

四个专业 Agent，全部继承自 `agent-platform` 的 `BaseAgent`（Agent Harness Layer）。

| Agent | 任务 | 输出 Schema | 前端渲染组件 |
|-------|------|-------------|--------------|
| `research-agent` | 市场研究 / 竞品分析 | `MarketResearch` / `CompetitorAnalysis` | MarketCard / CompetitorMatrix |
| `product-agent` | 定位 / 画像 / 功能 / 路线图 / PRD | `ProductStrategy` | PersonaCard / FeatureMatrix / RoadmapTimeline / PRDViewer |
| `design-agent` | 用户旅程 / 信息架构 / UI 结构 | `UXDesign` | — |
| `presentation-agent` | 报告与幻灯片结构 | `SlideDeck`（Slide JSON Schema） | SlideRenderer |

## 约定

- Agent 只生成 **结构化 JSON**（由平台层 `StructuredRunner` 做 Pydantic 校验 + 自愈重试）
- Agent **禁止** 生成 HTML/CSS —— 视觉实现完全由前端渲染组件控制
- 每个 Agent 通过 `execute(task, state, memory)` 被 LangGraph 工作流调用

## 运行

```bash
# PYTHONPATH 需包含 agent-platform/ 目录与 agents/ 的父目录（工作区根）
cd ~/dev/agents
PYTHONPATH=agent-platform:. python -c "from agents import ResearchAgent; print(ResearchAgent.name)"
```
