#!/bin/bash
# ============================================================
# QX Product Research Agent — WSL 全模块一键启动脚本
# 适配环境：WSL2 Ubuntu + Docker Redis + WSL Python venv
# 前端构建为静态文件，由 FastAPI 统一托管在 8000 端口
# 运行时路径：WSL 原生文件系统 (/home)，禁止使用 /mnt/*
# ============================================================
set -e

# ─── 颜色输出 ──────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[ OK ]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fatal() { echo -e "${RED}[FATAL]${NC} $*"; exit 1; }

PROJECT_ROOT="/home/administrator/dev/agents/QX_product_agent"
RUNTIME_DIR="$PROJECT_ROOT/backend/runtime"

cd "$PROJECT_ROOT" || fatal "项目目录不存在: $PROJECT_ROOT"

# 确保运行时目录存在（日志/数据库隔离）
mkdir -p "$RUNTIME_DIR"

echo "============================================================"
echo "  QX Product Research Agent — 全模块启动"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"
echo ""

# ─── 1. Redis (Docker) ─────────────────────────────────────
info "检测 Redis 容器 (redis-qx)..."
if docker ps --format '{{.Names}}' | grep -q '^redis-qx$'; then
    ok "Redis 容器已运行 (redis-qx:6379)"
else
    if docker ps -a --format '{{.Names}}' | grep -q '^redis-qx$'; then
        warn "Redis 容器已停止，正在重启..."
        docker start redis-qx > /dev/null 2>&1
        ok "Redis 容器已重启"
    else
        warn "Redis 容器不存在，正在创建..."
        docker run -d --name redis-qx -p 6379:6379 --restart unless-stopped redis:7-alpine > /dev/null 2>&1
        ok "Redis 容器已创建并运行"
    fi
fi
echo ""

# ─── 2. Python 虚拟环境 ────────────────────────────────────
info "检测 Python 虚拟环境..."
if [ ! -f "$PROJECT_ROOT/venv/bin/activate" ]; then
    fatal "venv 不存在，请先运行: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
fi
source "$PROJECT_ROOT/venv/bin/activate"
ok "Python venv 已激活 ($(python3 --version))"
echo ""

# ─── 3. 前端构建 ───────────────────────────────────────────
info "检测前端构建产物..."
FRONTEND_DIST="$PROJECT_ROOT/frontend/dist"
NEED_BUILD=false
if [ ! -f "$FRONTEND_DIST/index.html" ]; then
    NEED_BUILD=true
fi

if $NEED_BUILD; then
    if ! command -v node &> /dev/null; then
        warn "Node.js 未找到，跳过前端构建（API 仍可正常使用）"
    else
        ok "Node.js $(node --version)"
        info "正在构建前端 (Vite build)..."
        cd "$PROJECT_ROOT/frontend"
        node_modules/.bin/vite build > "$RUNTIME_DIR/vite_build.log" 2>&1
        if [ -f "$FRONTEND_DIST/index.html" ]; then
            ok "前端构建完成"
        else
            warn "前端构建失败，请查看 backend/runtime/vite_build.log"
        fi
    fi
else
    ok "前端构建产物已存在，跳过 build"
fi
echo ""

# ─── 4. 停止旧进程（避免端口冲突） ────────────────────────
info "清理旧进程..."
OLD_PID=$(ss -tlnp 2>/dev/null | grep ':8000' | grep -oP 'pid=\K[0-9]+' | head -1)
if [ -n "$OLD_PID" ]; then
    warn "端口 8000 被 PID $OLD_PID 占用，正在终止..."
    kill "$OLD_PID" 2>/dev/null || true
    sleep 1
    ok "旧进程已停止"
else
    ok "端口 8000 空闲"
fi
echo ""

# ─── 5. FastAPI 后端 (端口 8000，稳定模式 / 无 reload) ────
info "启动 FastAPI 后端 (端口 8000, 稳定模式)..."
cd "$PROJECT_ROOT/backend"
# ⚠️ 必须用 python -m 启动：venv/bin/uvicorn 的 shebang 指向 /mnt/d 旧路径
# （Windows 侧项目副本，9P 挂载极慢），直接执行会导致进程卡死 (D 状态)
nohup "$PROJECT_ROOT/venv/bin/python" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 \
    > "$RUNTIME_DIR/api.log" 2>&1 &
FASTAPI_PID=$!
ok "FastAPI 已启动 (PID: $FASTAPI_PID, 端口: 8000)"
echo "   日志: backend/runtime/api.log"
echo ""

# ─── 6. Celery Worker (prefork 池，独立进程) ────────────────
# prefork 使 task_time_limit 硬超时真正生效（threads 池无法强杀线程）
info "启动 Celery Worker..."
cd "$PROJECT_ROOT/backend"
nohup "$PROJECT_ROOT/venv/bin/python" -m celery -A app.core.celery_app.celery_app worker \
    --loglevel=info --concurrency=4 --pool=prefork \
    > "$RUNTIME_DIR/celery.log" 2>&1 &
CELERY_PID=$!
ok "Celery Worker 已启动 (PID: $CELERY_PID, pool: prefork)"
echo "   日志: backend/runtime/celery.log"
echo ""

# ─── 7. 等待服务预热 ──────────────────────────────────────
info "等待后端服务就绪..."
for i in $(seq 1 60); do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        ok "后端服务已就绪 (${i}s)"
        break
    fi
    if [ "$i" -eq 60 ]; then
        warn "后端服务可能仍在加载中，请稍后访问 http://localhost:8000"
    fi
    sleep 1
done

# ─── 8. 最终报告 ──────────────────────────────────────────
echo ""
echo "============================================================"
echo "  全部模块启动完毕！"
echo "============================================================"
echo ""
echo "  PID 汇总:"
echo "    FastAPI:  $FASTAPI_PID"
echo "    Celery:   $CELERY_PID"
echo ""
echo "  访问地址 (统一端口 8000):"
echo "    前端界面:   http://localhost:8000"
echo "    API 文档:   http://localhost:8000/docs"
echo "    健康检查:   http://localhost:8000/health"
echo ""
echo "  停止服务:  bash $PROJECT_ROOT/stop_all.sh"
echo "============================================================"
