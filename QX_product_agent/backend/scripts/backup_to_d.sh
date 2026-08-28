#!/bin/bash
# 可选：产物定时备份回 D 盘（供 Windows 资源管理器直读）
# crontab -e: */30 * * * * /home/administrator/dev/agents/QX_product_agent/backend/scripts/backup_to_d.sh
set -euo pipefail
SRC="${OUTPUT_DIR:-/home/administrator/dev/agents_outputs}"
DST="${BACKUP_DST:-/mnt/d/DEV/agents_outputs}"
mkdir -p "$DST"
rsync -a --delete "$SRC/" "$DST/"
