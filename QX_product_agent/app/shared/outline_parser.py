"""
============================================================
大纲解析器 —— 统一的 ## 章节标题提取逻辑
============================================================

CLI、API 路由、Celery 任务均调用此模块的唯一实现，
彻底消除三处重复代码各异导致的解析结果不一致问题。

边界情况覆盖：
  - "## " 空格分隔（标准 Markdown）
  - "##\t" Tab 分隔（某些编辑器产物）
  - "###" 三级标题不会被错误捕获
  - 标题内含 "#" 字符（如 "## 1. 产品 #1 分析"）
"""

import re

# 编译一次，重复使用
_SECTION_PATTERN = re.compile(r"^##[\t ]+(.+)$", re.MULTILINE)


def extract_sections(outline: str) -> list[str]:
    """
    从大纲 Markdown 中提取所有 ## 二级标题作为章节列表。

    Args:
        outline: Markdown 格式的大纲文本。

    Returns:
        章节标题字符串列表（不含 "## " 前缀）。

    Examples:
        >>> extract_sections("# Title\\n## 1. 概述\\n## 2. 市场分析")
        ['1. 概述', '2. 市场分析']

        >>> extract_sections("## 1. Tab\\t标题")
        ['1. Tab\\t标题']

        >>> extract_sections("### 三级标题不应被捕获")
        []
    """
    matches = _SECTION_PATTERN.findall(outline)
    # 去除首尾空白（处理 ##\t 情况残留的空格）
    return [m.strip() for m in matches if m.strip()]
