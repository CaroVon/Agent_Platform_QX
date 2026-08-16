# PPT 模型分工与 skill 接入（MiniMax + DeepSeek）

## 分工架构

```
主流水线（DeepSeek, AGENT_PLATFORM_LLM_*）
  requirement → research → competitor → strategy → design
                              ↓ document
Presentation 节点（专用模型, AGENT_PLATFORM_PRESENTATION_LLM_*）
  Presentation DSL + 证据包（evidence_pack） + CyberPPT skill
                              ↓ DSL
导出管线（无模型）：Web / HTML / PDF / PPTX（PptxGenJS + ECharts PNG）
```

- **DeepSeek**：research / strategy / design / critic（主 LLM）
- **MiniMax（或 Kimi）**：Presentation 节点——承接 PPT 相关 skill
  （presentation-cyberppt 等）与 DSL 制作

## 启用 MiniMax（OpenAI 兼容，零代码改动）

```bash
# 国内区
export AGENT_PLATFORM_PRESENTATION_LLM_BASE_URL=https://api.minimax.chat/v1
export AGENT_PLATFORM_PRESENTATION_LLM_MODEL=MiniMax-Text-01   # 或 MiniMax-M2 / abab6.5s-chat
export AGENT_PLATFORM_PRESENTATION_LLM_API_KEY=<MiniMax key>
# 国际区：BASE_URL=https://api.minimaxi.com/v1
```

未配置时 Presentation 节点自动回退主 LLM（DeepSeek）。JSON 输出不稳定时
由 harness 自愈重试兜底。官方 OpenAI 兼容文档：
https://platform.minimax.io/docs/api-reference/text-chat-openai.md

## 验证分工生效

1. 设置 env 后重启 Celery worker
2. 创建新产品跑流水线
3. `GET /api/v1/product/{id}` → presentation 节点日志应显示 MiniMax
   客户端（agent-platform 日志中 LLM 请求 base_url）

## ppt-master-skill 嵌入结论（2026-08 调研）

| 组件 | 许可证 | 结论 |
|---|---|---|
| macrochen/ppt-master-skill（skill 包装层） | **无 LICENSE** | ❌ 不可复制/嵌入（默认保留所有权利）；仅可参考方法论 |
| macrochen/ppt-master（上游工具，SVG→PPTX 管线） | **MIT** | ✅ 工具可收编，但 71MB + 重依赖（svg/playwright 类），建议作独立实验分支评估，不接入主流水线 |
| 技术路线 | — | ppt-master = 逐页 SVG 设计 → svg_to_pptx（Office 可"转换为形状"编辑）；与我们的 DSL→PptxGenJS 路线不同，视觉保真更高、文本可编辑性弱 |

**建议**：继续以自有 skill（presentation-cyberppt）+ MiniMax 分工为主路径；
若追求 ppt-master 式视觉保真，后续可评估把「SVG 逐页渲染 → PPTX」作为
export-pptx 的可选实验模式（P3+ 预留，manifest 已记录逐页构图）。
