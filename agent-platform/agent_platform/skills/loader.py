"""
============================================================
Skills 机制 —— 可组合的视觉规范（P3）
============================================================

借鉴 DeepAgents/Claude Code 的 skill 模式：Agent 获得专门的行为规则，
而不是把所有要求塞进一个巨型 prompt。

SkillLoader 把 skill 目录下的 markdown 规范文件拼接为
可注入 System Prompt 的规范文本；模型可换，规范不漂移。
"""

from __future__ import annotations

from pathlib import Path

_SKILLS_DIR = Path(__file__).resolve().parent


class SkillLoader:
    """加载 skills/ 目录下的视觉规范 skill。"""

    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or _SKILLS_DIR

    def load(self, name: str) -> str:
        """加载 skill：SKILL.md 优先，其余 md 按文件名排序拼接。"""
        skill_dir = self.base_dir / name
        if not skill_dir.is_dir():
            return ""

        parts: list[str] = []
        files = sorted(skill_dir.glob("*.md"))
        for f in files:
            header = "核心原则" if f.stem.upper() == "SKILL" else f.stem
            parts.append(f"【{header}】\n{f.read_text(encoding='utf-8').strip()}")
        return "\n\n".join(parts)

    def render_into(self, name: str, prompt: str, marker: str = "【视觉规范 Skill】") -> str:
        """把 skill 文本渲染进 prompt（无该 skill 时原样返回）。"""
        skill_text = self.load(name)
        if not skill_text:
            return prompt
        return f"{prompt}\n\n{marker}\n{skill_text}"
