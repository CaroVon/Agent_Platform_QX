"""
app.shared — 跨模块共享工具库
提供大纲解析、时间戳工厂等基础设施。
"""
from app.shared.outline_parser import extract_sections
from app.shared.time_utils import utcnow

__all__ = ["extract_sections", "utcnow"]
