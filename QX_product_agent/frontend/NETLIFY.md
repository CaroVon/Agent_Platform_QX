# Netlify 部署指南（前端 + 本机后端）

架构：**前端部署在 Netlify（公网），后端继续在本机运行（FastAPI:8000）**。
前端所有 `/api/*` 请求由 Netlify Edge Function（`netlify/edge-functions/api-proxy.ts`）
转发到环境变量 `BACKEND_URL` 指向的地址 —— 因此后端需要暴露一个**公网可达地址**。

```
浏览器（Netlify 静态站点）
   │  /api/v1/*（相对路径）
   ▼
Netlify Edge Function: api-proxy ──→ BACKEND_URL（公网地址）
                                        │
                                        ▼
                                本机 FastAPI :8000（隧道）
```

---

## 一、后端公网暴露（二选一）

后端在本机运行，需要一个公网可访问的地址：

### 方式 A：Cloudflare Tunnel（推荐，免费、稳定、无需账号穿透工具常驻）

```bash
# 1. 安装 cloudflared（WSL）
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O /usr/local/bin/cloudflared
chmod +x /usr/local/bin/cloudflared

# 2. 创建隧道并暴露本机 8000
cloudflared tunnel --url http://localhost:8000
# 输出：https://xxxxx.trycloudflare.com  ← 这就是 BACKEND_URL
```

### 方式 B：ngrok

```bash
# 安装并登录后
ngrok http 8000
# 输出：https://xxxx.ngrok-free.app ← BACKEND_URL
```

> 注意：本机后端 `backend/.env` 已配置真实 API Key；隧道地址仅暴露本机服务，
> 密钥不会上公网。部署期间建议保持后端运行（`bash start_all.sh` 或分步启动）。

---

## 二、Netlify 站点配置

### 2.1 连接仓库

Netlify Dashboard → Add new site → Import an existing project → GitHub：
- 仓库：`CaroVon/Agent_Platform_QX`

### 2.2 构建设置

`Site configuration → Build & deploy → Build settings`：

| 配置项 | 值 |
|--------|-----|
| Base directory | `QX_product_agent/frontend` |
| Build command | `npx vite build` |
| Publish directory | `dist` |

（`netlify.toml` 已内置命令与发布目录；Base directory 需在 UI 设置，或直接用下面的 CLI。）

### 2.3 环境变量

`Site configuration → Environment variables` 添加：

| 变量 | 值 | 说明 |
|------|-----|------|
| `BACKEND_URL` | `https://xxxx.trycloudflare.com` | 必填：本机后端的公网地址 |
| `AUTH_USERNAME` | 自定义 | 可选：Basic Auth 保护站点 |
| `AUTH_PASSWORD` | 自定义 | 可选：Basic Auth 保护站点 |

保存后 Netlify 自动触发部署（或手动 `Trigger deploy`）。

---

## 三、使用 Netlify CLI（可选，本地预览/联调）

```bash
# 安装 CLI
npm install -g netlify-cli

# 本地模拟 Netlify（Edge Functions 在本机运行，可直接代理到 localhost:8000）
cd QX_product_agent/frontend

# Edge Function 的环境变量需经 .env 注入（shell 环境变量不会透传），
# 在 frontend/ 目录创建 .env（已被 gitignore 排除，不会提交）：
echo "BACKEND_URL=http://localhost:8000" > .env

# 启动（自动读取 .env 注入 Edge Function）
npx netlify-cli dev
# 打开 http://localhost:8888 —— 前端走 Netlify 模拟层，API 代理到本机后端
```

这是"后端在本机 + 前端走 Netlify 形态"的本地开发最佳体验：
- 无需隧道、无需公网
- Edge Function（auth + api-proxy）与生产完全一致
- 已实测：经 netlify dev 代理，产品列表 / 知识库文档均正常返回

---

## 四、已验证的前端兼容点

- 前端 API 全部使用相对路径 `/api/v1/*`（统一 `API_BASE`，`VITE_API_BASE` 可覆盖直连）
- SPA 路由（/workspace、/research、/presentation 等）由 `[[redirects]]` 回退 index.html
- 导出文件（PDF/PPTX/HTML）URL `/api/v1/files/...` 同样走代理 → 本机后端静态文件 ✓
- SSE（`/api/v1/projects/{id}/stream-draft`）经 Edge Function 转发可用（Netlify 支持流式代理）
- 可选 `VITE_API_BASE=https://你的后端` 直连模式（绕过代理，需后端 CORS `allow_origins=["*"]`，已开启）

---

## 五、常见问题

| 问题 | 处理 |
|------|------|
| 打开站点显示 `BACKEND_URL not set` | 检查 Netlify 环境变量并重新 Trigger deploy |
| 登录弹窗反复出现 | 未设置 `AUTH_USERNAME/AUTH_PASSWORD` 时 auth 自动跳过；设置了就输对密码 |
| API 502 `edgefn-error` | 隧道服务未运行 / BACKEND_URL 填错；确认本机 `curl https://xxxx/api/v1/product` 可达 |
| 刷新 404 | SPA 回退未生效：确认 `[[redirects]]` 在 netlify.toml 中且已部署 |
| 中文乱码 | 确认 `index.html` 有 `<meta charset="utf-8">`（已有） |

## 快速上手（本机后端，一次实测记录）

```bash
# 1. 启动后端（已有）并跑隧道
bash scripts/start_tunnel.sh
# → https://xxxx.trycloudflare.com（临时地址，重启会变）

# 2. Netlify 环境变量设置
#    BACKEND_URL = https://xxxx.trycloudflare.com
#    （可选 AUTH_USERNAME / AUTH_PASSWORD 站点密码保护）

# 3. Trigger deploy 重新部署（env 修改必须重新部署才注入 Edge Function）
```

实测（2026-08）：快速隧道建立后，浏览器 UA 访问
`https://xxxx.trycloudflare.com/health` 与 `/api/v1/product` 均正常返回
（curl 默认 UA 会被 Cloudflare 简单质询拦截，浏览器无影响）。

---

## 五、隧道失效后的恢复步骤（quick tunnel 重启/过期）

quick tunnel 进程停止或机器重启后 URL 会变（域名解析失败 → Edge Function
报 `502 edgefn-error ... dns error`）。恢复步骤：

```bash
# 1. 重新拉起隧道（前台或 nohup 后台），记录输出中的 trycloudflare 地址
cloudflared tunnel --url http://localhost:8000
#    或 bash scripts/start_tunnel.sh

# 2. 更新 Netlify 环境变量（需要本机 ~/.config/netlify 已登录）
cd QX_product_agent/frontend
netlify env:set BACKEND_URL https://新的.trycloudflare.com \
  --site 4d320b10-0cc2-4528-930b-c9ba73601c08   # qxagentv2

# 3. 重新部署（env 变更需 redeploy 生效；--site 指定站点避免误部署到新站）
netlify deploy --prod --build --site 4d320b10-0cc2-4528-930b-c9ba73601c08

# 4. 验证线上代理
curl https://qxagentv2.netlify.app/api/v1/product?skip=0\&limit=1
```

> 注意：`netlify deploy` 不带 `--site` 时，若当前目录未关联站点会**新建一个站点**，
> 务必显式传 `--site <id>`。
