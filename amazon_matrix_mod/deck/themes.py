"""MOD deck 主题 —— 与主管线 THEME_PRESETS 单一视觉源对齐。

优先 import agent_platform.schemas.presentation.THEME_PRESETS（worker 内
sys.path 已含 agent-platform）；独立 CLI 场景回退到本地镜像（与平台定义
保持同步：agent_platform/schemas/presentation.py THEME_PRESETS）。
"""
from __future__ import annotations

# 本地镜像（与 agent_platform/schemas/presentation.py 完全一致）
_MIRROR: dict[str, dict] = {
    "default": {"name": "咨询蓝", "palette": {
        "bg": "#f8fafc", "surface": "#ffffff", "primary": "#4f46e5",
        "accent": "#6366f1", "text": "#0f172a", "muted": "#64748b"}},
    "cyber-crimson": {"name": "经典深红咨询", "palette": {
        "bg": "#F3F4EF", "surface": "#FFFFFF", "primary": "#8B1E1E",
        "accent": "#B54B4B", "text": "#111111", "muted": "#555555"}},
    "cyber-burgundy": {"name": "冷灰+勃艮第红", "palette": {
        "bg": "#F5F5F2", "surface": "#FFFFFF", "primary": "#7A1F2B",
        "accent": "#A04A55", "text": "#000000", "muted": "#6B6B6B"}},
    "cyber-ivory-wine": {"name": "暖象牙白+暗酒红", "palette": {
        "bg": "#F4F1EA", "surface": "#FFFFFF", "primary": "#8A1538",
        "accent": "#B04A67", "text": "#121212", "muted": "#77736C"}},
    "cyber-ivory-navy": {"name": "象牙白+深蓝", "palette": {
        "bg": "#F7F6F0", "surface": "#FFFFFF", "primary": "#12355B",
        "accent": "#3D6491", "text": "#101820", "muted": "#6F7275"}},
    "cyber-grey-green": {"name": "浅灰白+墨绿", "palette": {
        "bg": "#F2F3EF", "surface": "#FFFFFF", "primary": "#1F5B4D",
        "accent": "#4E8577", "text": "#111111", "muted": "#666666"}},
    "cyber-paper-copper": {"name": "纸张米色+铜棕", "palette": {
        "bg": "#F4F0E8", "surface": "#FFFFFF", "primary": "#9A5A2E",
        "accent": "#C08A5C", "text": "#161616", "muted": "#76716A"}},
    "cyber-black-gold": {"name": "纯净浅灰+黑金", "palette": {
        "bg": "#F6F6F4", "surface": "#FFFFFF", "primary": "#2B2A26",
        "accent": "#A87932", "text": "#000000", "muted": "#707070"}},
    "cyber-deep-purple": {"name": "冷白灰+深紫", "palette": {
        "bg": "#F4F5F6", "surface": "#FFFFFF", "primary": "#4B2E83",
        "accent": "#7A5FA8", "text": "#111111", "muted": "#6D7175"}},
}

DEFAULT_THEME = "cyber-ivory-navy"


def _presets() -> dict[str, dict]:
    try:
        from agent_platform.schemas.presentation import THEME_PRESETS
        return dict(THEME_PRESETS)
    except Exception:  # noqa: BLE001 —— 独立 CLI 场景（无 agent-platform）
        return _MIRROR


def available_themes() -> list[dict]:
    """[{id, name, palette}] —— 供 ppt-options API / 预览生成使用。"""
    return [{"id": tid, "name": t.get("name", tid), "palette": t.get("palette", {})}
            for tid, t in _presets().items()]


class Theme:
    """主题 tokens（palette 六色 + 常用别名，页面构建器消费）。"""

    def __init__(self, theme_id: str):
        presets = _presets()
        data = presets.get(theme_id) or presets.get(DEFAULT_THEME) \
            or _MIRROR[DEFAULT_THEME]
        p = dict(data.get("palette", {}))
        self.id = theme_id if theme_id in presets else DEFAULT_THEME
        self.name = data.get("name", self.id)
        self.bg = p.get("bg", "#F7F6F0")
        self.surface = p.get("surface", "#FFFFFF")
        self.primary = p.get("primary", "#12355B")
        self.accent = p.get("accent", "#3D6491")
        self.text = p.get("text", "#101820")
        self.muted = p.get("muted", "#6F7275")

    @property
    def visual_style(self) -> str:
        """spec_lock visual_style 命名（与主管线一致：consulting-{theme.id}）。"""
        return f"consulting-{self.id}"
