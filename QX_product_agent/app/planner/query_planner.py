import re
from app.llm.client import get_llm

def plan_section_queries(topic: str, section_title: str, num_queries: int = 3) -> list:
    """
    将宽泛的章节标题拆解为多个具体的检索问句 (Query Planning)
    """
    llm = get_llm()

    prompt = f"""
你是一名资深的产品分析专家和高级搜索策略师。
为了撰写一份专业的产品分析报告，你需要将特定的【报告章节】拆解为 {num_queries} 个具体的【底层检索词（Query）】。

报告主题：{topic}
当前撰写章节：{section_title}

【严格遵守以下核心法则】：
1. 拒绝长句，拥抱实体：不要输出“...的分析/研究/比较”，而是直接输出该章节可能涉及的核心技术名词、数据指标或专有名词。
2. 绝对聚焦：检索词必须100%限定在【{section_title}】的语义范围内！如果该章节是讲技术，绝对不允许生成关于“市场/销量/融资”的词汇。
3. 增加关键词密度：每一个 Query 应该像 Google 高级搜索词组，词与词之间用空格隔开。

【示例参考】
输入主题: "新能源汽车" | 章节: "电池技术发展"
输出:
- 固态电池 磷酸铁锂 三元锂 能量密度 寿命
- 电池热管理系统 液冷 直冷 技术演进
- 半固态电池 量产进度 成本分析

输入主题: "AI眼镜行业" | 章节: "核心玩家与竞争格局"
输出:
- Meta Ray-Ban 华为 Xreal 销量 市场份额
- AI眼镜 传统眼镜厂商 科技巨头 合作模式
- AI智能眼镜 核心初创企业 融资 估值

请基于以上法则，为当前主题和章节输出 {num_queries} 个检索词：
"""

    response = llm.invoke(prompt)
    content = response.content.strip()

    # 解析模型输出，提取查询词
    queries = []
    for line in content.split("\n"):
        line = line.strip()
        # 匹配以 "-" 或 "1." 开头的列表项
        if line.startswith("-") or re.match(r"^\d+\.", line):
            # 移除前缀的 "- " 或 "1. " 等符号
            query = re.sub(r"^(-|\d+\.)\s*", "", line).strip()
            if query:
                queries.append(query)

    # 兜底逻辑：如果模型没有按格式输出（比如遇到模型抽风），把原始 topic + section 作为默认 query
    if not queries:
        queries = [f"{topic} {section_title}"]

    return queries[:num_queries]


if __name__ == "__main__":
    topic = "AI眼镜行业"
    section = "市场分析"
    
    print(f"\n[规划检索策略] {topic} - {section}\n")
    queries = plan_section_queries(topic, section)
    
    for idx, q in enumerate(queries, start=1):
        print(f"Query {idx}: {q}")