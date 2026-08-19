# Workspace 对话式输入优化方案

> 目标：将 Product Workspace 的"单次产品输入"升级为**对话式输入 + 提示词建议 chips**，
> 让用户像与产品经理对话一样逐步澄清想法，再由 AI 团队接管生成。
> 日期：2026-08-18

---

## 1. 现状分析

### 1.1 当前交互（ProductWorkspacePage + IdeaInput）

```
┌──────────────────────────────────────────────┐
│   ✦ Describe the product you want to build   │
│   你的 AI 产品团队（研究/产品/设计/演示）…    │
│                                              │
│  [ 单行输入框: "为新中产打造国潮智能床品"  ]  │
│                    [ Generate ]              │
└──────────────────────────────────────────────┘
```

- 单行 `<input>` + Generate 按钮（`src/components/workspace/IdeaInput.tsx`）
- 提交后直接 `POST /product/create` 触发七节点流水线
- **痛点**：
  1. 用户想法模糊时（"我想做个健康产品"）无法获得澄清引导，直接生成质量低
  2. 无示例/提示词引导，冷启动认知成本高
  3. 想法→需求规格（requirement_parser 的 goals/constraints/success_metrics）
     全靠一句 idea 推断，**用户输入的约束与指标从未真正进入下游**（审计已确认此问题）
  4. 无对话记忆：同一想法二次迭代仍需重新输入

### 1.2 后端现有能力（可复用）

| 能力 | 位置 | 说明 |
|---|---|---|
| SSE 流式对话 | `POST /api/v1/editor/chat`（chat/work 双模式） | 已验证可用，逐 token 推送 |
| 需求解析节点 | requirement_parser（LangGraph 首节点） | 把 idea 解析为 RequirementSpec |
| 资料审核门 | source_gathering（上轮实现） | 搜索→加权→用户审核 |

---

## 2. 开源工具调研

### 2.1 候选库对比

| 库 | 定位 | 核心组件 | 技术栈 | 与项目契合度 | 结论 |
|---|---|---|---|---|---|
| **[prompt-kit](https://github.com/ibelick/prompt-kit)（ibelick）** | AI 应用 UI 组件库 | **PromptInput**（AI 提示输入）、**PromptSuggestion**（提示建议 chips，Normal/Highlight 双模式）、消息气泡、Markdown 渲染 | shadcn/ui + Tailwind + React 19 | 高：同为 Tailwind 生态；PromptSuggestion 正是"对话框下方弹出可选提示词"的现成范式 | **借鉴其交互模式，自研实现**（避免引入 shadcn CLI 依赖链；项目有自有 Design Token，直接复制组件会与纸感风格冲突） |
| **[Vercel AI SDK](https://vercel.com/changelog/introducing-ai-elements)（@ai-sdk/react）** | 对话状态管理 + 流式标准 | useChat / useCompletion / AI Elements | React + 任意后端 | 中：状态管理优秀，但其 SSE 协议（`data: {...}` 标准流）与项目自定义 `event: content` 协议不兼容，需适配层 | 不引入；**自研轻量 hook 复用现有 SSE** |
| **[assistant-ui](https://www.shadcn.io/template/assistant-ui-assistant-ui)** | 完整聊天 UI 框架 | Thread/Composer/Suggestion 全套 | Radix + AI SDK + Tailwind | 低：重依赖、全量组件树，纸感定制成本高 | 不引入 |
| **[CopilotKit](https://champsignal.com/comparisons/copilotkit.ai-vs-assistant-ui.com)** | 应用内 Copilot 框架 | useCoAgent/useChat + 前端 agent 运行时 | React | 低：面向"内嵌 agent 操作应用"，与产品生成工作流重叠但绑定重 | 不引入 |
| **[@chatscope/chat-ui-kit-react](https://socket.dev/npm/package/@chatscope/chat-ui-kit-react)** | 传统聊天 UI 套件 | ChatContainer/MessageList/Input | React + CSS | 低：样式老旧、非 Tailwind | 不引入 |

> 参考：2025-2026 年 AI Chat UI 库横向评估（[codeables.dev](https://codeables.dev/article/assistant-ui-vs-copilotkit-vs-a-shadcn-ui-custom-build-which-handles)、[DEV Community 全库评测](https://dev.to/alexander_lukashov/i-evaluated-every-ai-chat-ui-library-in-2026-heres-what-i-found-and-what-i-built-4p10)）结论一致：**简单对话场景自研成本最低，框架价值在复杂多端场景**。

### 2.2 结论

**不自研基础轮子、不引入重型框架，采用"借鉴范式 + 自研轻量实现"**：
- 借鉴 prompt-kit 的 PromptInput + PromptSuggestion 交互模式（chips 弹出、highlight 高亮）
- 复用项目现有 SSE（editor/chat 同款管道）+ Zustand + 纸感 Design Token
- 唯一新增后端：产品澄清专用 SSE 端点（复用现有 LLM 管道，~80 行）

---

## 3. 交互设计

### 3.1 双模式输入（默认对话模式）

```
┌────────────────────────────────────────────────────────────┐
│  ✦ 与 AI 产品团队对话，描述你的想法                         │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 💬 我：想做一个帮独居老人按时吃药的产品               │  │
│  │ 🤖 AI：好的！为了生成精准的研究与 PRD，想先了解：      │  │
│  │        1) 目标用户：仅老人本人使用，还是家人也参与？    │  │
│  │        2) 核心场景：日常提醒为主，还是需要远程监护？    │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  [ 多行输入区（Enter 发送 / Shift+Enter 换行）        ]    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 💡 提示：                                              │  │
│  │ [面向独居老人的智能药盒] [智能睡眠监测枕]               │  │
│  │ [健身私教镜] [智能空气净化器]  [🎲 换个方向]            │  │
│  └──────────────────────────────────────────────────────┘  │
│                                            [ ✨ 直接生成 ]  │
│                                            [ 生成产品 → ]   │
└────────────────────────────────────────────────────────────┘
```

**关键交互**：
1. **对话澄清**：AI 用引导式提问（每次最多 2-3 个问题）收集 4 个关键维度：
   目标用户 → 使用场景 → 核心功能/差异化 → 约束（技术/成本/合规）
2. **信息足够即提示生成**：收集完 4 维度（或用户点"生成产品"）→ 把对话整理为
   结构化 brief → 提交流水线（requirement_parser 获得完整输入）
3. **Suggestion chips**（对话框下方弹出）：
   - **静态模板**（本地维护，P0）：产品方向示例（行业 × 人群 × 场景组合）
   - **点击填充**：chips 点击把示例 idea 填入输入框，可编辑后发送
   - **动态建议**（P2，可选）：基于已输入内容由 LLM 生成 3 条补全建议
4. **快速通道**：保留"直接生成"（跳过对话，与现状一致），两种模式切换按钮

### 3.2 对话状态

```
idle（欢迎语+chips） → clarifying（多轮问答，SSE 流式） → brief_ready（可生成） → running（流水线）
                                                        ↘ 直接生成（跳过对话）
```

---

## 4. 架构方案

### 4.1 数据流

```
用户输入
  │
  ├─ 对话模式 ──→ POST /api/v1/product/clarify（SSE，专用澄清 prompt，有界 2-4 轮）
  │                ↓ 收集 目标用户/场景/功能/约束 四维度
  │                ↓ 前端对话记录（Zustand + localStorage 持久化，可续聊）
  │                ↓ 用户点「生成产品」
  │                ↓ 对话 → 结构化 brief（前端拼装 或 后端 clarify/summary 端点）
  │                ↓
  └─ 快速模式 ──→ 单行 idea
                   ↓
              POST /product/create（idea=brief 或 原句）
                   ↓
        requirement_parser → 资料审核 → 现有七节点流水线
```

### 4.2 组件结构（全部新增/改造于 frontend/src）

```
components/workspace/
├── ChatInput.tsx          # 对话输入区（多行 Textarea + Enter 发送 + 状态指示）
├── ChatMessageList.tsx    # 消息气泡（用户/AI 两种样式，纸感 token，Markdown 轻渲染）
├── SuggestionChips.tsx    # 提示词 chips（静态模板数据 + 点击填充 + 🎲 随机示例）
└── ClarifyPanel.tsx       # 对话模式总容器（消息列表 + 输入区 + chips + 生成按钮）

hooks/
└── useClarifyChat.ts      # 对话状态：messages[] + SSE 接收（复用 editor/chat 的解析器）
                           # + brief 拼装 + localStorage 恢复

pages/ProductWorkspacePage.tsx  # 改造：双模式切换（对话 / 快速），
                                # 对话就绪后与现有 productApi.create 衔接
```

### 4.3 后端（新增一个端点 + 一个 system prompt）

```
backend/app/api/v1/endpoints/product.py
└── POST /api/v1/product/clarify          # SSE 流式需求澄清
    body: { idea?, messages: [{role, content}...], max_rounds?: 4 }
    行为：
    1. 组装「需求澄清引导」system prompt（见下）
    2. 追加历史对话 → LLM 流式回复（deepseek-chat，temperature 0.5）
    3. 回复末尾由 LLM 给出结构化信号：{dimensions_covered: [...]} 
       （内嵌 JSON，前端解析判断是否可生成）
    4. 幂等/防滥用：max_rounds 上限、消息长度上限

backend/app/llm/prompts.py
└── PRODUCT_CLARIFY_SYSTEM               # 澄清引导 prompt：
    # - 角色：资深产品经理，一次最多问 2-3 个问题
    # - 必须按序收集：目标用户→使用场景→核心功能/差异化→约束
    # - 用户信息足够时输出「✅ 信息已足够，可以生成」并给出 brief 摘要
    # - 禁止编造用户未提供的信息
```

### 4.4 与现有系统的衔接点

| 环节 | 衔接方式 |
|---|---|
| requirement_parser | brief 直接作为 idea 提交（已含 goals/constraints 的对话摘要，解析质量显著提升） |
| 资料审核门 | 不变（对话生成的 brief 同样进入 source_gathering 审核） |
| editor/chat | 复用其 SSE 服务端实现模式（`event: content`），澄清端点独立（不同 prompt/状态） |
| 快速模式 | IdeaInput 保留，双模式 Tab 切换 |

---

## 5. 实施步骤

### P0（核心，约 1-2 天）
1. 后端：`PRODUCT_CLARIFY_SYSTEM` prompt + `POST /product/clarify`（SSE，含维度覆盖信号）
2. 前端：`useClarifyChat` hook（SSE 解析复用现有解析器）+ `ClarifyPanel` + `SuggestionChips`
3. 前端：ProductWorkspacePage 双模式切换；对话→brief→`productApi.create`
4. 测试：clarify 端点单测（FakeLLM）+ 前端 tsc/构建 + UI 冒烟

### P1（增强，约 1 天）
5. 对话持久化（localStorage，刷新可续聊）
6. chips 动态建议（输入停顿 800ms 后 LLM 生成 3 条补全，可开关）
7. 对话记录归档到产品资产（"需求澄清记录"卡片，沉淀决策来源）

### P2（可选探索）
8. 对话式局部迭代："改一下目标用户" → 局部重生成（与 regenerate 端点打通）

---

## 6. 风险与取舍

| 风险 | 对策 |
|---|---|
| 澄清轮数失控（用户嫌烦） | 默认最多 4 轮；每轮只问 2-3 个问题；随时可跳过直接生成 |
| SSE 协议与 AI SDK 不兼容 | 不引入 AI SDK；自研 hook 复用现有 `event: content` 解析 |
| 引入 prompt-kit 的诱惑 | 其组件基于 shadcn CLI + React 19，与项目 React 18 + 自有 token 冲突；只借鉴交互范式 |
| 对话质量依赖 prompt | 澄清 prompt 严格约束"一次最多 2-3 问、禁止编造、信息足够即停" |
| 并发工作流 | 新端点独立文件，不与现有端点冲突；prompt 常量放 prompts.py 追加段 |

---

## 7. 结论

**推荐：自研轻量对话式输入（借鉴 prompt-kit 的 PromptInput/PromptSuggestion 范式），不引入重型框架。**
- 开源调研表明：现成库中 prompt-kit 的 suggestion 组件最贴合需求，但其 shadcn CLI + React 19 依赖与本项目（React 18 + 自有纸感 token）冲突，直接引入成本高于自研
- 项目已有 SSE 对话管道与完整设计系统，新增量仅：1 个后端澄清端点 + 1 个前端对话面板 + 1 个 chips 组件
- 该方案同时解决审计遗留问题："用户输入的约束/指标从未进入下游"（对话 brief 直达 requirement_parser）
