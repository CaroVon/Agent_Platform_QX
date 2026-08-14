# tests/eval_citation.py
import re
from langchain_core.documents import Document

# （为了测试脚本自包含，直接把工具函数 copy 过来）
def build_context_with_citations(retrieved_docs):
    context_str = ""
    ref_map = {}
    url_to_id = {}
    current_id = 1
    for doc in retrieved_docs:
        url = doc.metadata.get("url", "unknown")
        if url not in url_to_id:
            url_to_id[url] = current_id
            ref_map[current_id] = url
            current_id += 1
        ref_id = url_to_id[url]
        context_str += f"【参考资料 {ref_id}】\n{doc.page_content}\n\n"
    return context_str, ref_map

def resolve_and_append_citations(llm_output, ref_map):
    used_refs = set(re.findall(r'\[\^?(\d+)\]', llm_output))
    if not used_refs:
        return llm_output
    footer = "\n\n---\n### 📚 参考资料\n"
    for ref_id in sorted([int(r) for r in used_refs]):
        if ref_id in ref_map:
            footer += f"[^{ref_id}]: 来源链接: <{ref_map[ref_id]}>\n"
    return llm_output + footer


def run_citation_test():
    print("="*60)
    print("🔍 [测试阶段 1]: 后端传入多个重叠的 Chunk...")
    
    # 模拟检索到了 3 个 Chunk，但前两个其实来自同一篇报告 (URL 相同)
    docs = [
        Document(page_content="全球AI眼镜出货量明年将达500万台。", metadata={"url": "https://report.xyz/hua_chuang.pdf"}),
        Document(page_content="Micro-OLED将成为主流方案。", metadata={"url": "https://report.xyz/hua_chuang.pdf"}), # 相同 URL
        Document(page_content="专家认为竞争格局将向巨头集中。", metadata={"url": "https://sohu.com/news/123"})
    ]
    
    context_str, ref_map = build_context_with_citations(docs)
    print("生成的 Reference Map:", ref_map)
    print("\n喂给 LLM 的 Context:\n" + context_str.strip())
    
    print("\n" + "="*60)
    print("🤖 [测试阶段 2]: 模拟大模型基于 Prompt 严格输出了带有 [^n] 的文本...")
    
    mock_llm_response = (
        "## AI眼镜市场洞察\n"
        "行业测算指出，明年全球 AI 眼镜出货量预计将达到 500 万台，且 Micro-OLED 会成为主流显示方案[^1]。"
        "另一方面，有业内专家强调，未来的竞争格局将不可避免地向科技巨头集中[^2]。"
        "这两大趋势将共同重塑行业生态[^1][^2]。"
    )
    print("\nLLM 原始输出 (仅含角标):\n", mock_llm_response)
    
    print("\n" + "="*60)
    print("🛠️ [测试阶段 3]: Python 正则介入，执行 Reference Resolution...")
    
    final_report = resolve_and_append_citations(mock_llm_response, ref_map)
    
    print("\n✅ 最终交付给用户的严谨报告：")
    print("-" * 40)
    print(final_report)
    print("-" * 40)

if __name__ == "__main__":
    run_citation_test()