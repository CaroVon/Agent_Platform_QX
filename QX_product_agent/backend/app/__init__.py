"""
============================================================
backend/app 包初始化
—— 通过扩展 __path__ 将 research_agent/app/ 的子模块合并进来
============================================================

问题背景：
  backend/app/ 和 research_agent/app/ 都是 "app" 包。
  Python 在同一命名空间下默认只能使用一个包路径，
  导致 research_agent/app/ 下的子模块（search, crawler, rag 等）
  无法被 Celery Worker 导入。

解决方案：
  在 __path__ 中追加 research_agent/app/ 目录，
  使得 app.search / app.crawler / app.planner / app.report / app.rag
  等子模块可以被正确解析。

  支持两种运行环境：
  1. 本地开发：通过文件路径 ../../app 相对于 __file__ 计算
  2. Docker 容器：通过 /app/engine 挂载卷寻找
"""

import os
import sys

# ─── 计算 research_agent 根目录 ────────────────────────────
# __file__: /root/autodl-tmp/research_agent/backend/app/__init__.py (本地)
# __file__: /app/app/__init__.py (Docker)
_current_dir = os.path.dirname(os.path.abspath(__file__))        # backend/app/
_backend_dir = os.path.dirname(_current_dir)                      # backend/
_research_agent_dir = os.path.dirname(_backend_dir)               # research_agent/

# ─── 将 research_agent 加入 sys.path（确保 import app 时能找到） ─
if _research_agent_dir not in sys.path:
    sys.path.insert(0, _research_agent_dir)

# ─── 策略1（本地开发）：通过相对路径找到 research_agent/app/ ─────
_engine_found = False
_research_agent_app = os.path.join(_research_agent_dir, "app")
if os.path.isdir(_research_agent_app) and _research_agent_app not in __path__:
    _has_engine_submodules = any(
        os.path.isdir(os.path.join(_research_agent_app, d))
        for d in ("planner", "search", "crawler", "report", "rag", "llm")
    )
    if _has_engine_submodules:
        __path__.append(_research_agent_app)
        _engine_found = True

# ─── 策略2（Docker 容器）：通过 /app/engine 挂载卷寻找 ──────────
# docker-compose.yml 中需要将 research_agent/app/ 挂载到 /app/engine
if not _engine_found:
    _docker_engine = "/app/engine"
    if os.path.isdir(_docker_engine) and _docker_engine not in __path__:
        _has_engine_submodules = any(
            os.path.isdir(os.path.join(_docker_engine, d))
            for d in ("planner", "search", "crawler", "report", "rag", "llm")
        )
        if _has_engine_submodules:
            __path__.append(_docker_engine)
            _engine_found = True

if not _engine_found:
    import warnings
    warnings.warn(
        "⚠️ 未找到 app 引擎模块（planner/search/crawler 等）。"
        "请确保 research_agent/app/ 可通过以下路径之一访问：\n"
        f"  - 本地: {_research_agent_app}\n"
        "  - Docker: /app/engine\n"
        "某些任务将无法正常运行。"
    )
