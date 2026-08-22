#!/usr/bin/env bash
# start_worker.sh —— Celery worker 启动（E2E 专用，环境变量内嵌）
# 用法: ./start_worker.sh [mock|rainforest]   （默认 rainforest）
set -u
cd "$(dirname "$(dirname "$0")")"
export QX_ENV=e2e
export MOD_SOURCE="${1:-rainforest}"
exec ../venv/bin/python -m celery -A app.core.celery_app.celery_app worker \
    --loglevel=info --concurrency=4 --pool=threads
