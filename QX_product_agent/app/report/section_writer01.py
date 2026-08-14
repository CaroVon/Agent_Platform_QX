from app.llm.client import get_llm
from app.rag.retriever import retrieve  # 注意：这里改为直接引入底层的 retrieve，获取 raw documents
from app.planner.query_planner import plan_section_queries
from app.rag.citation_utils import build_context_with_citations, resolve_and_append_citations

def write_section(topic: str, section_title: str):
    llm = get_llm()

    # 1. 查询规划 (Query Planning)
    print(f"\n[1/3] 正在为【{section_title}】规划检索策略...")
    queries = plan_section_queries(topic, section_title, num_queries=3)

    # 2. 多路检索与 Document 聚合 (Multi-Query Retrieval)
    print(f"[2/3] 正在执行多路检索与 Document 聚合...")
    all_retrieved_docs = []
    
    for i, query in enumerate(queries, start=1):
        print(f"      -> 检索子维度 {i}: {query}")
        # 直接调用底层的 retrieve 函数，返回的是 Document 对象列表
        docs = retrieve(query, k=2)
        all_retrieved_docs.extend(docs)

    # 3. 经过 Citation 引擎处理，生成带编号的 Context 和映射表
    context_str, ref_map = build_context_with_citations(all_retrieved_docs)

    # 4. 撰写章节 (注入极其严苛的引用规则 Prompt)
    print(f"[3/3] 正在撰写带有溯源角标的章节内容...")
    prompt = f"""
你是一名专业行业研究员。请基于提供的【参考资料】，撰写行业研究报告章节。

【严厉的引用规范】（必须绝对遵守）：
1. 客观严谨：所有数据、专有名词、核心结论【必须】来源于参考资料。禁止瞎编数据。
2. 强制溯源角标：当你的句子使用了某参考资料的信息时，必须在该句末尾（句号前）添加对应的 Markdown 脚注编号。例如：“预计销量达500万台[^1]。”
3. 多重引用：如果一句话综合了资料 1 和资料 2，请写作：“...呈现稳步增长[^1][^2]。”
4. 格式限制：正文中【绝对不允许】直接输出包含 http 的超链接，只允许输出类似 [^n] 的纯编号！

【输出要求】：
1. 使用专业行业分析语言
2. 使用 Markdown 格式，输出结构化内容
3. 明确给出关键趋势、数据支撑和结论
4. **只需输出正文**，不要你在文末列出参考链接，系统会在外部自动处理。

研究主题：
{topic}

当前撰写章节：
{section_title}

【参考资料】
{context_str}

请开始撰写：
"""

    response = llm.invoke(prompt)
    raw_content = response.content

    # 5. 后处理阶段：解析文中生成的 [^n]，并组装底部参考链接栏
    print(f"[INFO] 正在解析引用角标并生成底部参考书目...")
    final_content = resolve_and_append_citations(raw_content, ref_map)

    return final_content


if __name__ == "__main__":
    content = write_section(
        "AI眼镜行业",
        "市场分析与竞争格局"
    )
    
    print("\n========== GENERATED SECTION ==========\n")
    print(content)