#!/bin/bash
# 黄金集夜跑（P2 评测 CI）：对最近完成的 deck 自动评测，非 PASS 退出 1
set -euo pipefail
BACKEND="$(cd "$(dirname "$0")/../.." && pwd)"
PY="$BACKEND/../venv/bin/python"
OUT="${OUTPUT_DIR:-/mnt/d/DEV/agents_outputs}"
LATEST=$("$PY" - <<PYEOF
import sqlite3
con = sqlite3.connect("$BACKEND/runtime/local_dev.db", timeout=10)
row = con.execute("SELECT id FROM studio_products WHERE status='completed' ORDER BY updated_at DESC LIMIT 1").fetchone()
print(row[0] if row else "")
PYEOF
)
[ -z "$LATEST" ] && { echo "无 completed 产品"; exit 1; }
echo "评测产品: $LATEST"
"$PY" "$BACKEND/scripts/eval/evaluate_deck.py" "$LATEST" --output-root "$OUT" --out "$OUT/eval_report_latest.json"
