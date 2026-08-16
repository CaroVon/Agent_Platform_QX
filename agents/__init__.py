"""
============================================================
专业 Agent 层 —— Research / Product / Design / Presentation
============================================================

四个专业 Agent（对齐目标架构）:
  - research-agent     市场研究 + 竞品分析
  - product-agent      产品定位 / 画像 / 功能 / 路线图 / PRD
  - design-agent       用户旅程 / 信息架构 / UI 结构
  - presentation-agent 报告与幻灯片结构（Slide JSON Schema）

每个 Agent 都是薄实现：继承平台层 BaseAgent，
声明 System Prompt 与输出 Schema，实现 execute() 任务分派。

目录名按规范使用连字符（research-agent 等），Python 无法直接
import 连字符目录 —— 此处用包注册器把连字符目录注册为
可导入的合法包名（agents.research_agent / ...）。
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

_PKG_ROOT = Path(__file__).parent

# 连字符目录名 → 合法 Python 包名
_FOLDERS = {
    "agents.research_agent": "research-agent",
    "agents.product_agent": "product-agent",
    "agents.design_agent": "design-agent",
    "agents.presentation_agent": "presentation-agent",
    "agents.critic_agent": "critic-agent",
    "agents.ppt_design_agent": "ppt-design-agent",
}


def _register(pkg_name: str, folder: str) -> types.ModuleType:
    """把连字符目录注册为可导入的包。"""
    if pkg_name in sys.modules:
        return sys.modules[pkg_name]
    module = types.ModuleType(pkg_name)
    module.__package__ = pkg_name
    module.__path__ = [str(_PKG_ROOT / folder)]  # type: ignore[attr-defined]
    sys.modules[pkg_name] = module
    return module


for _pkg, _folder in _FOLDERS.items():
    _register(_pkg, _folder)

from agents.research_agent.agent import ResearchAgent  # noqa: E402
from agents.product_agent.agent import ProductAgent  # noqa: E402
from agents.design_agent.agent import DesignAgent  # noqa: E402
from agents.presentation_agent.agent import PresentationAgent  # noqa: E402
from agents.critic_agent.agent import CriticAgent  # noqa: E402
from agents.ppt_design_agent.agent import PptDesignAgent  # noqa: E402

__all__ = [
    "ResearchAgent",
    "ProductAgent",
    "DesignAgent",
    "PresentationAgent",
    "CriticAgent",
    "PptDesignAgent",
]
