"""
============================================================
agent-platform 测试配置
============================================================
"""

import sys
from pathlib import Path

# 确保 agent_platform 包可导入（pytest 从任意 CWD 运行均可）
_PKG_ROOT = Path(__file__).resolve().parent.parent
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))
