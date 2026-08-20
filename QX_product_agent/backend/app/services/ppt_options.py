"""PPT 模板选项服务 —— 设计主题（THEME_PRESETS 镜像）+ 风格方法论（ppt-master）。

API 进程无 agent-platform 路径，主题表在此维护镜像（与
agent_platform/schemas/presentation.py THEME_PRESETS 同步）；
风格方法论从 ppt-master templates/styles/styles_index.json 读取。
预览图为前端静态资产 /theme-previews/{id}.png（scripts/gen_theme_previews.py 生成）。
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# 与 agent_platform/schemas/presentation.py THEME_PRESETS 保持同步的镜像
PPT_THEMES: dict[str, dict] = {
    "default": {"name": "咨询蓝", "summary": "现代咨询蓝，科技产品通用",
                "palette": {"bg": "#f8fafc", "surface": "#ffffff", "primary": "#4f46e5",
                            "accent": "#6366f1", "text": "#0f172a", "muted": "#64748b"}},
    "cyber-crimson": {"name": "经典深红咨询", "summary": "经典红咨询风，决策汇报",
                      "palette": {"bg": "#F3F4EF", "surface": "#FFFFFF", "primary": "#8B1E1E",
                                  "accent": "#B54B4B", "text": "#111111", "muted": "#555555"}},
    "cyber-burgundy": {"name": "冷灰+勃艮第红", "summary": "冷灰底勃艮第强调，稳重调研",
                       "palette": {"bg": "#F5F5F2", "surface": "#FFFFFF", "primary": "#7A1F2B",
                                   "accent": "#A04A55", "text": "#000000", "muted": "#6B6B6B"}},
    "cyber-ivory-wine": {"name": "暖象牙白+暗酒红", "summary": "暖象牙底酒红，品牌调性强",
                         "palette": {"bg": "#F4F1EA", "surface": "#FFFFFF", "primary": "#8A1538",
                                     "accent": "#B04A67", "text": "#121212", "muted": "#77736C"}},
    "cyber-ivory-navy": {"name": "象牙白+深蓝", "summary": "象牙底深蓝，经典商务咨询",
                         "palette": {"bg": "#F7F6F0", "surface": "#FFFFFF", "primary": "#12355B",
                                     "accent": "#3D6491", "text": "#101820", "muted": "#6F7275"}},
    "cyber-grey-green": {"name": "浅灰白+墨绿", "summary": "浅灰底墨绿，可持续/制造",
                         "palette": {"bg": "#F2F3EF", "surface": "#FFFFFF", "primary": "#1F5B4D",
                                     "accent": "#4E8577", "text": "#111111", "muted": "#666666"}},
    "cyber-paper-copper": {"name": "纸张米色+铜棕", "summary": "纸感底铜棕，匠心/手作",
                           "palette": {"bg": "#F4F0E8", "surface": "#FFFFFF", "primary": "#9A5A2E",
                                       "accent": "#C08A5C", "text": "#161616", "muted": "#76716A"}},
    "cyber-black-gold": {"name": "纯净浅灰+黑金", "summary": "浅灰底黑金，高端发布会",
                         "palette": {"bg": "#F6F6F4", "surface": "#FFFFFF", "primary": "#2B2A26",
                                     "accent": "#A87932", "text": "#000000", "muted": "#707070"}},
    "cyber-deep-purple": {"name": "冷白灰+深紫", "summary": "冷白底深紫，学术/前沿",
                          "palette": {"bg": "#F4F5F6", "surface": "#FFFFFF", "primary": "#4B2E83",
                                      "accent": "#7A5FA8", "text": "#111111", "muted": "#6D7175"}},
}

_FALLBACK_STYLES: dict[str, dict] = {
    "consulting-decision": {"summary": "结论先行、证据驱动的决策文档方法", "keywords": ["consulting", "decision"]},
    "investor-pitch": {"summary": "投资人路演：问题-方案-市场-增长", "keywords": ["investor", "pitch"]},
    "product-launch": {"summary": "产品发布：亮点-场景-节奏", "keywords": ["product", "launch"]},
}


def _styles_index() -> dict:
    """ppt-master styles_index.json（工作区布局推断 + 内置兜底）。"""
    backend_dir = Path(__file__).resolve().parents[3]
    for root in (backend_dir.parents[1], backend_dir.parent):
        cand = (root / "agents" / "ppt-design-agent" / "vendor" / "ppt-master"
                / "templates" / "styles" / "styles_index.json")
        if cand.is_file():
            try:
                return json.loads(cand.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                break
    return _FALLBACK_STYLES


def ppt_options() -> dict:
    """前端模板选择器数据源。"""
    themes = [
        {
            "id": tid,
            "name": t["name"],
            "summary": t.get("summary", ""),
            "palette": t.get("palette", {}),
            "preview": f"/theme-previews/{tid}.png",
        }
        for tid, t in PPT_THEMES.items()
    ]
    styles = [
        {"id": sid, "summary": s.get("summary", ""),
         "keywords": (s.get("keywords") or [])[:6]}
        for sid, s in _styles_index().items()
    ]
    return {"themes": themes, "styles": styles}
