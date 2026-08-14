#!/bin/bash
# ============================================================
# QX Product Research Agent — 全模块停止脚本
# ============================================================

GREEN='\033[0;32m'
NC='\033[0m'

echo "正在停止 QX Product Research Agent 所有服务..."

# 停止 uvicorn (FastAPI, 端口 8000)
PID=$(ss -tlnp 2>/dev/null | grep ':8000' | grep -oP 'pid=\K[0-9]+' | head -1)
if [ -n "$PID" ]; then
    kill "$PID" 2>/dev/null && echo -e "${GREEN}[OK]${NC} FastAPI (PID $PID) 已停止"
else
    echo -e "${GREEN}[OK]${NC} FastAPI 未运行"
fi

# 停止 celery worker
pkill -f "celery.*worker" 2>/dev/null && echo -e "${GREEN}[OK]${NC} Celery Worker 已停止" || echo -e "${GREEN}[OK]${NC} Celery Worker 未运行"

echo "所有服务已停止。"
echo "注意: Redis 容器 (redis-qx) 仍在运行，如需停止请运行: docker stop redis-qx"
