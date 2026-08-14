"""
============================================================
大纲解析器单元测试
============================================================
"""

import pytest
from app.shared.outline_parser import extract_sections


class TestExtractSections:
    """测试大纲 Markdown 中 ## 章节标题的提取"""

    def test_standard_headings(self):
        """标准 Markdown 二级标题"""
        outline = "# 主标题\n## 1. 行业概述\n## 2. 市场分析\n## 3. 竞品研究"
        sections = extract_sections(outline)
        assert sections == ["1. 行业概述", "2. 市场分析", "3. 竞品研究"]

    def test_no_headings(self):
        """没有二级标题"""
        assert extract_sections("只是一段文字") == []
        assert extract_sections("# 只有一级标题") == []

    def test_empty_string(self):
        """空字符串"""
        assert extract_sections("") == []

    def test_tab_separator(self):
        """Tab 分隔的标题（某些编辑器的产物）"""
        outline = "## 1. 概述\n##\t2. 市场分析"
        sections = extract_sections(outline)
        assert "1. 概述" in sections
        assert "2. 市场分析" in sections

    def test_hash_in_title(self):
        """标题内包含 # 字符"""
        outline = "## 1. 产品 #1 分析"
        sections = extract_sections(outline)
        assert sections == ["1. 产品 #1 分析"]

    def test_triple_hash_not_captured(self):
        """### 三级标题不应被捕获"""
        outline = "# 主标题\n## 1. 概述\n### 1.1 子节\n## 2. 分析"
        sections = extract_sections(outline)
        assert sections == ["1. 概述", "2. 分析"]

    def test_multiple_hashes_in_heading(self):
        """## 后多个 # 的情况"""
        outline = "## 1. 这是一个 # 标签 ## 测试"
        sections = extract_sections(outline)
        assert "1. 这是一个 # 标签 ## 测试" in sections

    def test_chinese_headings(self):
        """中文标题"""
        outline = "## 一、行业概述与趋势分析\n## 二、市场规模与增长预测\n## 三、竞争格局深度剖析"
        sections = extract_sections(outline)
        assert len(sections) == 3
        assert "一、行业概述与趋势分析" in sections

    def test_trailing_whitespace(self):
        """标题前后的空白字符"""
        outline = "##   1. 有前导空格   \n## 2. 正常"
        sections = extract_sections(outline)
        assert "1. 有前导空格" in sections
        assert "2. 正常" in sections

    def test_real_world_outline(self):
        """真实的大纲格式"""
        outline = """# 智能坐姿矫正指环产品深度分析

## 1. 产品概述与设计理念

## 2. 市场定位与目标用户

## 3. 竞品对比分析

## 4. 技术特性与创新点

## 5. 用户体验与交互设计

## 6. 商业模式与风险挑战"""
        sections = extract_sections(outline)
        assert len(sections) == 6
        assert sections[0] == "1. 产品概述与设计理念"
        assert sections[-1] == "6. 商业模式与风险挑战"
