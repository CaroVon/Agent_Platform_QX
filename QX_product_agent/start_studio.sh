#!/bin/bash
# ============================================================
# Agent Platform QX —— 本机一键启动（开发模式）
# ============================================================
# 启动：Redis 容器 → FastAPI(8000) → Celery Worker → Vite Dev(5173)
# 可选：--tunnel 同时启动 Cloudflare 隧道（供 Netlify 联调）
#
# 用法:
#   bash start_studio.sh            # 全部启动
#   bash start_studio.sh --tunnel   # 全部启动 + 公网隧道
#   bash start_studio.sh stop       # 停止全部
#
# 访问:
#   开发前端  http://localhost:5173  （Vite HMR）
#   API 文档  http://localhost:8000/docs
#   健康检查  http://localhost:8000/health
# ============================================================

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
PY="$PROJECT_ROOT/venv/bin/python"
RUNTIME_DIR="$BACKEND_DIR/runtime"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()  { echo -e "${GREEN}[ OK ]${NC} $*"; }
warn(){ echo -e "${YELLOW}[WARN]${NC} $*"; }
fail(){ echo -e "${RED}[FAIL]${NC} $*"; exit 1; }

# ══════════════════════════════════════════════════════════
# 停止全部
# ══════════════════════════════════════════════════════════
if [ "$1" = "stop" ]; then
  echo "停止全部服务..."
  pkill -f "uvicorn app.main" 2>/dev/null
  pkill -f "celery -A app.core.celery_app" 2>/dev/null
  pkill -f "npm run dev" 2>/dev/null
  pkill -f "cloudflared tunnel" 2>/dev/null
  sleep 2
  ok "已停止（Redis 容器保留运行）"
  exit 0
fi

mkdir -p "$RUNTIME_DIR"

# ══════════════════════════════════════════════════════════
# 1. Redis（Docker 容器）
# ══════════════════════════════════════════════════════════
echo "── 1/5 Redis ──────────────────────────────"
if docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^redis-qx$'; then
  ok "Redis 容器运行中 (redis-qx:6379)"
elif docker ps -a --format '{{.Names}}' 2>/dev/null | grep -q '^redis-qx$'; then
  docker start redis-qx >/dev/null 2>&1 && ok "Redis 容器已重启"
else
  docker run -d --name redis-qx -p 6379:6379 --restart unless-stopped redis:7-alpine >/dev/null 2>&1 \
    && ok "Redis 容器已创建" || fail "Redis 启动失败（Docker 是否在运行？）"
fi

# ══════════════════════════════════════════════════════════
# 2. FastAPI 后端（⚠️ 必须 python -m，避免 /mnt/d shebang 卡死）
# ══════════════════════════════════════════════════════════
echo "── 2/5 FastAPI ─────────────────────────────"
if curl -s -m 2 -o /dev/null http://localhost:8000/health 2>/dev/null; then
  ok "FastAPI 已在运行 (8000)"
else
  cd "$BACKEND_DIR"
  nohup "$PY" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 \
    > "$RUNTIME_DIR/api.log" 2>&1 &
  ok "FastAPI 启动中 (PID $!，日志 $RUNTIME_DIR/api.log)"
  cd "$PROJECT_ROOT"
fi

# ══════════════════════════════════════════════════════════
# 3. Celery Worker（⚠️ 同上，python -m）
# ══════════════════════════════════════════════════════════
echo "── 3/5 Celery Worker ───────────────────────"
if ps aux | grep -v grep | grep -q "celery -A app.core.celery_app"; then
  ok "Celery Worker 已在运行"
else
  cd "$BACKEND_DIR"
  # PPT 逐页创作并发（默认 4；共享开发机内存紧张时可降 2）
  export AGENT_PLATFORM_PPT_DESIGN_CONCURRENCY="${AGENT_PLATFORM_PPT_DESIGN_CONCURRENCY:-4}"
  # prefork（与 start_all 一致）：硬超时可强杀；threads 池在内存高压下有
  # GIL/锁滞留风险（详见稳定性加固记录）
  nohup "$PY" -m celery -A app.core.celery_app.celery_app worker \
    --loglevel=info --concurrency=4 --pool=prefork \
    > "$RUNTIME_DIR/celery.log" 2>&1 &
  ok "Celery 启动中 (PID $!，PPT并发=$AGENT_PLATFORM_PPT_DESIGN_CONCURRENCY，日志 $RUNTIME_DIR/celery.log)"
  cd "$PROJECT_ROOT"
fi

# ══════════════════════════════════════════════════════════
# 4. Vite Dev Server（HMR 开发模式）
# ══════════════════════════════════════════════════════════
echo "── 4/5 Vite Dev ────────────────────────────"
if curl -s -m 2 -o /dev/null http://localhost:5173/ 2>/dev/null; then
  ok "Vite Dev 已在运行 (5173)"
else
  cd "$FRONTEND_DIR"
  nohup npm run dev > "$RUNTIME_DIR/vite.log" 2>&1 &
  ok "Vite Dev 启动中 (PID $!，日志 $RUNTIME_DIR/vite.log)"
  cd "$PROJECT_ROOT"
fi

# ══════════════════════════════════════════════════════════
# 5. 等待就绪 + 隧道（可选）
# ══════════════════════════════════════════════════════════
echo "── 5/5 就绪检查 ────────────────────────────"
for i in $(seq 1 40); do
  API_OK=$(curl -s -m 2 -o /dev/null -w '%{http_code}' http://localhost:8000/health 2>/dev/null)
  VITE_OK=$(curl -s -m 2 -o /dev/null -w '%{http_code}' http://localhost:5173/ 2>/dev/null)
  [ "$API_OK" = "200" ] && [ "$VITE_OK" = "200" ] && break
  sleep 2
done
[ "$API_OK" = "200" ] && ok "FastAPI 就绪 (8000)" || warn "FastAPI 未就绪，查看 $RUNTIME_DIR/api.log"
[ "$VITE_OK" = "200" ] && ok "Vite Dev 就绪 (5173)" || warn "Vite 未就绪，查看 $RUNTIME_DIR/vite.log"

if [ "$1" = "--tunnel" ]; then
  echo "── 附加：Cloudflare 隧道 ─────────────────────"
  CLOUDFLARED="$HOME/.local/bin/cloudflared"
  if [ ! -x "$CLOUDFLARED" ]; then
    mkdir -p "$(dirname "$CLOUDFLARED")"
    wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O "$CLOUDFLARED"
    chmod +x "$CLOUDFLARED"
  fi
  nohup "$CLOUDFLARED" tunnel --url http://localhost:8000 > "$RUNTIME_DIR/tunnel.log" 2>&1 &
  ok "隧道启动中，公网地址见 $RUNTIME_DIR/tunnel.log（搜 trycloudflare.com）"
fi

# ══════════════════════════════════════════════════════════
echo ""
echo "============================================================"
echo "  Agent Platform QX —— 已就绪"
echo "============================================================"
echo "  开发前端    http://localhost:5173   (Product Studio)"
echo "  API 文档    http://localhost:8000/docs"
echo "  健康检查    http://localhost:8000/health"
echo "  停止服务    bash start_studio.sh stop"
echo "============================================================"
