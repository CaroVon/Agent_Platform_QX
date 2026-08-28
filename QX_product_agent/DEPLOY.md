# 部署与运维指南（P0-P2 全量更新版）

## 一键部署

```bash
cd QX_product_agent
cp backend/.env.example backend/.env   # 填 API keys
docker compose up -d --build           # api + worker + redis + postgres + flower
```

## 环境变量速查（本次更新新增）

| 变量 | 默认 | 说明 |
|---|---|---|
| `AGENT_PLATFORM_PPT_DESIGN_CONCURRENCY` | 4 | PPT 逐页创作并发（429 自动降并发兜底；内存紧张调 2） |
| `AGENT_PLATFORM_SVG_KERNEL` | rust | 默认启用 Rust 内核；`python` 回退（等价性测试保障） |
| `AGENT_PLATFORM_CHECKPOINT_POSTGRES_URI` | 空 | 配置后 LangGraph 任意节点断点持久化 |
| `OUTLINE_REVIEW` | true | 大纲确认门（presentation 后暂停审批页清单） |
| `SOURCE_REVIEW` | true | 资料审核门（Tavily+Rainforest 双源） |
| `MOD_SOURCE` | rainforest | `mock` 供 0-credit 预演 |
| `CHART_THEME` | 默认咨询蓝 | `warm` / `cool` 图表主题（svgcharts） |
| `OUTPUT_DIR` | ./outputs | 产出根（建议大盘挂载） |

## P0-P2 变更摘要

- **P0**：PostgreSQL（含数据迁移）、LangGraph Postgres checkpointer（任意节点断点）、
  worker 心跳自愈（Redis TTL + 看门狗，失联 ≥3min 自动 queued 重投）、
  SSE 实时进度（`/product/{id}/events`）、大纲确认门、页级👎返工
  （运行中入队 / 完成态外科单页重做）、前端拆包（首屏 2MB→~1.6MB、编辑器按需）
- **P1**：vendor 转换器进程内调用（-10~15s/deck）、Rust 内核 qx_svg_tools
  （snap/qa，等价对照测试）、版式库 20、叙事模板×3、图表主题×3、图标库×10、
  reveal.js 网页 deck 出口
- **P2**：评测 harness（`scripts/eval/`，夜跑 gate）、docker-compose 一键化

## 安全收口（生产必做）

1. `AUTH_BOOTSTRAP=false`（本地免密引导仅限开发）
2. Cloudflare quick tunnel → named tunnel + Cloudflare Access
3. `/api/v1/files` 静态路由加鉴权（当前公开，PPT 缩略图直链需要 token 化）
4. CORS `allow_origins=["*"]` 收敛到具体域名

## 评测 CI

```bash
bash backend/scripts/eval/nightly.sh   # 最近 completed deck 评测，非 PASS 退出 1
```

报告维度：结构（10-24 页/MOD≥4）、逐页 QA 复检（遮挡/占位 hard，色板 warning）、
产物完整性（双 PPTX/reveal/MOD 数据）、渐进交付资产齐备。
