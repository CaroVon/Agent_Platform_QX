# Agent Platform QX

> AI Product Studio —— 基于 LangGraph + Agent Harness 的多 Agent 产品平台。
> monorepo：平台层（可复用） + 专业 Agent（可复用） + QX 业务应用（演示/生产接线）。

## 仓库结构

```
Agent_Platform_QX/
├── agent-platform/        # Agent Platform Runtime（独立 Python 包 agent_platform）
│   ├── agent_platform/
│   │   ├── harness/       #   Agent 循环：规划 → 执行 → 评估 → 反思
│   │   ├── workflows/     #   LangGraph 七节点产品研究工作流
│   │   ├── schemas/       #   Pydantic 结构化契约（Agent 通信协议）
│   │   ├── tools/         #   搜索 / 文档解析 / 工具注册表
│   │   ├── memory/        #   项目级持久记忆
│   │   ├── config/        #   AGENT_PLATFORM_* 集中配置
│   │   └── llm/           #   OpenAI 兼容模型层（DeepSeek/Qwen/GPT）
│   └── tests/             #   平台层测试（FakeLLM，零网络）
│
├── agents/                # 四个专业 Agent（继承平台层 BaseAgent）
│   ├── research-agent/    #   市场研究 + 竞品分析
│   ├── product-agent/     #   定位 / 画像 / 功能 / 路线图 / PRD
│   ├── design-agent/      #   用户旅程 / 信息架构 / UI 结构
│   ├── presentation-agent/#   Slide JSON（报告与幻灯片结构）
│   └── tests/             #   全链路集成测试
│
└── QX_product_agent/      # QX 业务应用（FastAPI + Celery + React）
    ├── app/               #   研究引擎（RAG / 搜索 / 报告）
    ├── backend/           #   FastAPI + Celery + SQLAlchemy + /api/v1/product/*
    ├── frontend/          #   React + Vite 前端（含 /studio Product Studio）
    ├── scripts/           #   冒烟测试 / 状态检测脚本
    ├── MIGRATION.md       #   AI Product Studio 迁移文档
    └── README.md          #   业务应用文档
```

## 架构

```
Product Studio UI (/studio)  ── 既有工作台 (/projects/*)
        │ REST + SSE
QX Application Layer（FastAPI + Celery）── 只做桥接，不内嵌框架
        │ Python import（单向）
Agent Platform Runtime（agent-platform/）
        │ 构造注入（依赖倒置）
四个专业 Agent（agents/）
        │
Model Layer：DeepSeek / Qwen / GPT（OpenAI 兼容）
```

依赖方向：**QX → agents → agent-platform**（单向）；平台层零业务依赖，可独立复用/发版。

## 快速开始（业务应用）

```bash
cd QX_product_agent
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install && cd ..

# Redis（Docker）→ FastAPI(8000) → Celery → 前端
bash start_all.sh
# 访问 http://localhost:8000/studio 或 http://localhost:5173/studio
```

## 文档

- 迁移说明/架构决策/测试结果/风险：`QX_product_agent/MIGRATION.md`
- 平台层文档：`agent-platform/README.md`
- 专业 Agent 说明：`agents/README.md`

## 测试

```bash
cd agent-platform && python -m pytest tests/ -q      # 26 passed（零网络）
cd agents && python -m pytest tests/ -q              # 2 passed
cd QX_product_agent/backend && ../venv/bin/python -m pytest tests/ -q   # 44 passed
```
