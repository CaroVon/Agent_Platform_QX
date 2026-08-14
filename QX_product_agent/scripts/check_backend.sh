#!/bin/bash
# ============================================================
# 检测 QX Product Research Agent 后台服务运行状态
# ============================================================
# 检测项:
#   1. Redis 容器 (redis-qx)
#   2. FastAPI 后端 (端口 8000)
#   3. Celery Worker 进程
#   4. Redis 任务队列长度（>0 表示有待处理任务）
#   5. Product Studio 最新任务状态（backend/studio_products 表）
#
# 用法:
#   bash scripts/check_backend.sh
# ============================================================

# 项目根 = 本脚本所在目录的上一级 (scripts/ -> QX_product_agent/)
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
PY="$PROJECT_ROOT/venv/bin/python"

echo "============================================================"
echo "  QX Product Research Agent — 后台运行状态检测"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"

# ─── 1. Redis ──────────────────────────────────────────────
if docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^redis-qx$'; then
    echo "  [OK]   Redis 容器 (redis-qx) 运行中"
else
    echo "  [FAIL] Redis 容器 (redis-qx) 未运行"
fi

# ─── 2. FastAPI (8000) ─────────────────────────────────────
HTTP_CODE=$(curl -s -m 3 -o /dev/null -w '%{http_code}' http://localhost:8000/health 2>/dev/null)
if [ "$HTTP_CODE" = "200" ]; then
    echo "  [OK]   FastAPI 后端 http://localhost:8000/health -> 200"
else
    echo "  [FAIL] FastAPI 后端未响应 (HTTP $HTTP_CODE)"
fi

# ─── 3. Celery Worker 进程 ─────────────────────────────────
WORKER_COUNT=$(ps aux | grep -v grep | grep -c "celery.*worker" 2>/dev/null)
if [ "$WORKER_COUNT" -gt 0 ]; then
    echo "  [OK]   Celery Worker 进程数: $WORKER_COUNT"
else
    echo "  [FAIL] Celery Worker 未运行"
fi

# ─── 4. Redis 任务队列 ─────────────────────────────────────
QUEUE_LEN=$(docker exec redis-qx redis-cli LLEN celery 2>/dev/null | tr -d '\r')
if [ -z "$QUEUE_LEN" ]; then
    echo "  [WARN] 无法查询 Redis 队列长度"
else
    echo "  [INFO] Redis 任务队列长度: $QUEUE_LEN ($([ "$QUEUE_LEN" -gt 0 ] && echo 有待处理任务 || echo 无待处理))"
fi

# ─── 5. Product Studio 最新任务 ────────────────────────────
echo "  [INFO] Product Studio 最新任务:"
cd "$BACKEND_DIR" || exit 1
"$PY" - <<'EOF'
from sqlalchemy.orm import Session
from app.core.celery_db import get_sync_engine
from app.models.studio_product import StudioProduct

with Session(get_sync_engine()) as s:
    rows = s.query(StudioProduct).order_by(StudioProduct.created_at.desc()).limit(5).all()
    if not rows:
        print("    (尚无产品任务)")
    for p in rows:
        status = p.status.value
        icon = {"completed": "✅", "running": "🔄", "queued": "⏳", "failed": "❌"}.get(status, "·")
        print(f"    {icon} {p.idea} | {status} | {p.id}")
        if p.error_message:
            print(f"        错误: {p.error_message[:80]}")
EOF

echo "============================================================"
