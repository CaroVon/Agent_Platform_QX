# Agent Platform Runtime

> AI Product Studio 的现代 Agent Runtime 层 —— 基于 **LangGraph + Agent Harness**，
> 独立于业务应用（QX_product_agent），不反向依赖任何业务代码。

## 架构

```
Product Studio UI (React + Tailwind)
      │  REST + SSE
QX Application Layer (FastAPI + Celery)      ← 业务应用，只做桥接
      │  Python import
Agent Platform Runtime (本仓库)              ← 平台层
      │
harness  │  workflows  │  schemas  │  tools  │  memory  │  config  │  llm
      │
Model Layer: DeepSeek / Qwen / GPT（OpenAI 兼容接口）
```

| 模块 | 职责 |
|------|------|
| `harness/` | Agent 执行循环（规划 → 执行 → 评估 → 反思）、Prompt 管理、工具调用、上下文管理、结构化输出（自愈重试） |
| `workflows/` | LangGraph 工作流、状态管理、多 Agent 编排、节点重试与失败降级 |
| `schemas/` | Pydantic 结构化契约（Agent 通信协议），LLM 输出强制过 Schema |
| `tools/` | 搜索（Tavily）、文档解析、外部 API，声明式注册 |
| `memory/` | 项目级持久记忆（JSONL 文件实现，可替换） |
| `config/` | 集中配置（`AGENT_PLATFORM_*` 环境变量） |
| `llm/` | 模型客户端（OpenAI 兼容：DeepSeek / Qwen / GPT） |

## 核心设计

### 1. LangGraph 工作流（`workflows/product_research_graph.py`）

```
Requirement Parser → Research → Competitor Analysis
  → Product Strategy → UX Design → Presentation → Asset Package
```

- 每个节点：接收结构化 state、产出 Schema 校验通过的结构化输出
- 每个节点：`_with_retry` 包装器（失败重试 → 结构化记录错误 → 降级继续）
- 节点失败不阻断整体：最终资产包（`ProductAssetPackage`）保留
  `meta.node_status` / `meta.errors` 供前端呈现部分成功
- Agent 实现通过构造参数注入（依赖倒置），平台层不 import 具体业务 Agent

### 2. Agent Harness（`harness/`）

```
AgentLoop:  Planning → Execution → Evaluation → Reflection → Memory
```

- **Planning** `planner.py` — LLM 目标分解（失败回退单步）
- **Execution** `runner.py` — LLM JSON → Pydantic 校验；失败把错误回传 LLM 自愈重试
- **Evaluation** `agent_loop.py` — 默认评估器 + 可注入自定义评估器
- **Reflection** — 评估未通过时生成修正要求进入下一轮（`AGENT_MAX_TURNS` 轮）
- **Memory** — 每轮产物写入 `MemoryStore`，跨 Agent 传承上下文

### 3. 结构化契约（`schemas/`）

| Schema | 关键字段（对齐产品需求） |
|--------|--------------------------|
| `MarketResearch` | `market_size` / `competitors[]` / `customer_pain_points[]` / `industry_trends[]` |
| `CompetitorAnalysis` | `competitors[]` / `matrix` / `competitive_landscape` / `differentiation_opportunities[]` |
| `ProductStrategy` | `personas[]` / `features[]` / `roadmap[]` / `prd_sections[]` |
| `UXDesign` | `user_flow[]` / `pages[]` / `components[]` |
| `SlideDeck`（Slide JSON Schema） | `slides[]` / `sections[]`；每页含 `layout_type` + `visual_metadata` |

**Markdown-first → JSON Schema + Renderer**：LLM 只生成结构化 JSON，
禁止生成 HTML/CSS；排版（字体/间距/样式）由前端渲染组件统一控制。

## 配置

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `AGENT_PLATFORM_LLM_API_KEY` | 回退 `DEEPSEEK_API_KEY` | 模型 API Key |
| `AGENT_PLATFORM_LLM_BASE_URL` | `https://api.deepseek.com/v1` | OpenAI 兼容 Base URL |
| `AGENT_PLATFORM_LLM_MODEL` | `deepseek-chat` | 模型名（可切 qwen-max / gpt-4o-mini） |
| `AGENT_PLATFORM_TAVILY_API_KEY` | 回退 `TAVILY_API_KEY` | 搜索工具 Key（缺省优雅降级） |
| `AGENT_PLATFORM_MEMORY_DIR` | `./agent_platform_memory` | 记忆目录 |
| `AGENT_PLATFORM_AGENT_MAX_TURNS` | `3` | Agent 循环最大轮数 |
| `AGENT_PLATFORM_AGENT_MAX_RETRIES` | `2` | 结构化输出重试次数 |

## 安装与测试

```bash
pip install -r requirements.txt

# 测试（FakeLLM，零网络）
python -m pytest tests/ -q
```

## 在业务应用中使用

```python
# 前置：PYTHONPATH 需包含本目录（agent-platform/）与 agents/ 的父目录
#   export PYTHONPATH=$PWD:$PWD/../:$PYTHONPATH

from agent_platform.harness.agent_loop import AgentLoop
from agent_platform.memory.memory_store import FileMemoryStore
from agent_platform.workflows.product_research_graph import ProductResearchGraph

from agents.research_agent.agent import ResearchAgent     # 业务 Agent（agents/）
from agents.product_agent.agent import ProductAgent
from agents.design_agent.agent import DesignAgent
from agents.presentation_agent.agent import PresentationAgent

loop = AgentLoop(memory=FileMemoryStore())
graph = ProductResearchGraph(
    research_agent=ResearchAgent(loop=loop),
    product_agent=ProductAgent(loop=loop),
    design_agent=DesignAgent(loop=loop),
    presentation_agent=PresentationAgent(loop=loop),
    llm=loop.llm,
)
package = graph.invoke("Build an AI fitness application")
print(package.model_dump_json())
```
