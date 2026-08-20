# Amazon 价格×竞品矩阵 MOD — P1 数据源验证脚手架

> 目标站点：**美亚 (amazon.com, domain=1)** ｜ 预算：**~$20–40/月** ｜ 规模：**50 ASIN 日更**
> 本目录 = P1（数据源验证）：注册 API → 按关键词发现 ASIN → 拉取全字段 → 输出字段完整性报告。

## 数据源选择（三选一即可跑通 P1）

| 数据源 | 注册/支付 | 免费/试用 | 覆盖 | 价格 | 脚本 |
|---|---|---|---|---|---|
| **卖家精灵 MCP** 🇨🇳（推荐-国内支付） | 中文界面，开放平台注册，**支付宝** | 接口可申请试用 | 45 个工具：ASIN 详情/竞品/销量预测/**市场/价格分布**/评论/流量 | 接口按量计（如 ASIN 详情 ¥988/月起，以官网为准） | `fetch_sellersprite_mcp.py` |
| **Rainforest API** | 邮箱注册，国际卡 | 含试用额度 | 实时快照：产品/搜索/评论/卖家/BSR 榜单 | $18/月 500 次 | `fetch_rainforest.py` |
| **Keepa API** | 邮箱注册，国际卡 | 免费 100 请求/10 分钟 | **价格历史**/BSR/评论历史（行业标准） | 付费约 €20–30/月 | `fetch_keepa.py` |

> 三个脚本输出**同构的 raw 存档**，`merge_report.py` 自动汇总全部存档生成统一验收报告；后续切换数据源只需换一个 fetch 脚本。

## 一、注册指引

### 1. 卖家精灵（推荐：中文 + 支付宝，注册最简单）
1. 访问 <https://open.sellersprite.com> 注册（手机号/邮箱，中文界面）；
2. **购买 MCP 套餐**：<https://open.sellersprite.com/pricing/mcp>（Basic 限时 ¥99/月 = 1000 次/月；年付 ¥990 = 4000 次/月更划算）；
3. 购买后在 **MCP 控制台 →【我的密钥】** 创建 MCP 专用密钥；
4. 官方 MCP 端点：`https://mcp.sellersprite.com/mcp`，**认证方式为请求头 `secret-key: <密钥>`**（非 Bearer）；
5. 也可先零代码体验：把 MCP 配到 Chatbox / Claude / CherryStudio / Coze 等客户端，自然语言直接查数据。

### 2. Rainforest（国际卡，邮箱注册）
1. 访问 <https://www.rainforestapi.com> 注册（含试用额度）；
2. 拿到 api_key 后设置环境变量 `RAINFOREST_API_KEY`；
3. 文档：<https://docs.trajectdata.com/rainforestapi>。

### 3. Keepa（国际卡，价格历史最强）— 默认方案
1. 访问 <https://www.keepa.com> 注册 → Subscription 页购买 **API access**（或先用免费层）；
2. 账户页获取 **Access Key** → 环境变量 `KEEPA_API_KEY`。

## 二、运行步骤（P1 验收）

```bash
cd amazon_matrix_mod
pip install -r requirements.txt

# ── 数据源任选其一（或都跑，merge 会自动汇总）──

# 方式 A：卖家精灵 MCP（推荐-支付宝）
export SELLERSPRITE_API_KEY="你的key"
python fetch_sellersprite_mcp.py --list-tools                 # 查看 45 个工具与参数
python fetch_sellersprite_mcp.py --tool asin_detail --asins B0XXXXXXXX,B0YYYYYYYY
python fetch_sellersprite_mcp.py --tool competitor_lookup --asins B0XXXXXXXX

# 方式 B：Rainforest
export RAINFOREST_API_KEY="你的key"
python fetch_rainforest.py --keyword "yoga mat" --limit 10    # 关键词自动发现竞品
python fetch_rainforest.py --asins B0XXXXXXXX,B0YYYYYYYY      # 或直接指定 ASIN

# 方式 C：Keepa
export KEEPA_API_KEY="你的key"
python fetch_keepa.py --keyword "yoga mat" --limit 10

# ── 生成验收报告（汇总 raw 目录下全部数据源）──
python merge_report.py
```

输出：
- `outputs/raw/*.json` — 各数据源原始响应存档（字段核对用）；
- `outputs/matrix_report.md` — **P1 验收报告**：ASIN ｜ 现价 ｜ 90 天低/高 ｜ 评分 ｜ 评论数 ｜ BSR ｜ 主图 URL ｜ FBA/FBM ｜ 字段完整性。

## 三、P1 验收标准

1. ✅ 10 个 ASIN 的：当前价格、评分、评论数、BSR、主图 URL 全部拿到（Keepa/Rainforest 另含 90 天价格统计）；
2. ✅ 记录实测请求消耗（各服务商控制台/文档口径），据此推算 50 ASIN 日更的月成本；
3. ✅ 主图 URL 能正常下载显示（下一步 P3 矩阵图要用）；
4. ✅ 输出一份 `matrix_report.md` 给评审。

## 五、P2/P3：竞品矩阵 MOD 管道（run_mod.py）

```bash
# 完整管道：关键词 → Rainforest 采集 → 4 区规则 → LLM 解读 → PNG/HTML/CSV/MD
export RAINFOREST_API_KEY="你的key"
export DEEPSEEK_API_KEY="..."        # 复用 QX backend/.env 亦可

python run_mod.py --keyword "wireless mouse" --top-n 50 --our-asin B0XXXXXX
python run_mod.py --keyword "wireless mouse" --top-n 8     # 测试建议 ≤8（9 credits）
python run_mod.py --source mock --top-n 12 --skip-llm      # 离线开发（0 credits）
python run_mod.py --reuse outputs/raw/rainforest_*.json    # 复用存档
```

产物（`outputs/mod_<kw>_<ts>/` 或 `studio_assets/{product_id}/competitor_matrix/`）：
`mod_report.png`（1920×1080 静态图）｜ `mod_report.html`（ECharts 交互）｜ `data.csv` ｜ `competitor_matrix.md` ｜ `zoning.json`

### Studio 调度（七节点流水线 → 八节点）

`competitor_matrix` 节点插在 `research` 之后、`competitor_analysis` 之前：
- 后端：`agent-platform/.../product_research_graph.py` NODE_ORDER + `agents/research-agent/agent.py` execute 分支
- 资产：`project_assets.py` TEXT_ASSETS 已注册「竞品矩阵」
- 前端：`AgentTimeline.tsx` 节点说明已同步

## 六、注意事项

- **限流**：Keepa 免费层 100 请求/10 分钟；P1 量小无所谓，P2 起统一做队列 + 批处理；
- **字段容错**：脚本对各服务商响应做防御性解析（字段名以实际返回为准），原始 JSON 一律存档；如与预期不符，改对应 fetch 脚本中的解析段即可；
- **销量估算**：`merge_report.py` 中的 BSR→月销量估算为**粗估系数**，P2 阶段用类目基准校准；报告会标注"估算值"；
- **合规**：三家均为第三方合规数据服务商，不直接爬亚马逊；PA-API/SP-API 限制与本次路线无关。
