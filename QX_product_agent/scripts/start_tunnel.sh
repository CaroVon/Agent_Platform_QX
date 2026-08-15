#!/bin/bash
# ============================================================
# 启动 Cloudflare 快速隧道，暴露本机后端 (localhost:8000)
# 用于 Netlify 前端 + 本机后端的公网联调
#
# 用法:
#   bash scripts/start_tunnel.sh
#
# 输出: 形如 https://xxxx.trycloudflare.com 的公网地址
#   → 填入 Netlify 环境变量 BACKEND_URL → Trigger deploy
#
# 注意: 快速隧道为临时地址，进程重启后 URL 会变，需重新更新 Netlify env。
# 生产长期使用建议注册 Cloudflare 账号创建固定命名隧道。
# ============================================================

set -e

CLOUDFLARED="${CLOUDFLARED:-$HOME/.local/bin/cloudflared}"
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"

# ─── 确保后端在运行 ─────────────────────────────────────────
if ! curl -s -m 3 -o /dev/null "$BACKEND_URL/health"; then
  echo "[FATAL] 本机后端未运行: $BACKEND_URL/health 不可达（先执行 bash start_all.sh）"
  exit 1
fi
echo "[OK] 本机后端可达: $BACKEND_URL"

# ─── 安装 cloudflared（首次） ───────────────────────────────
if [ ! -x "$CLOUDFLARED" ]; then
  echo "[INFO] 安装 cloudflared..."
  mkdir -p "$(dirname "$CLOUDFLARED")"
  wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 \
    -O "$CLOUDFLARED"
  chmod +x "$CLOUDFLARED"
fi
echo "[OK] cloudflared: $("$CLOUDFLARED" --version | head -1)"

# ─── 启动隧道（前台；Ctrl+C 停止） ──────────────────────────
echo "[INFO] 启动隧道 → $BACKEND_URL"
echo "[INFO] 从输出中复制 trycloudflare.com 地址填入 Netlify BACKEND_URL"
exec "$CLOUDFLARED" tunnel --url "$BACKEND_URL"
