import os
from langchain_core.documents import Document
from app.rag.retriever import get_source_weight, reciprocal_rank_fusion

# 1. 对照组：原始的无权重 RRF 算法 (Baseline)
def baseline_rrf(vector_results, bm25_results, k=60):
    fused_scores = {}
    doc_map = {}
    
    for rank, doc in enumerate(vector_results, start=1):
        url = doc.metadata.get("url", "unknown")
        doc_key = doc.page_content + "|" + url
        doc_map[doc_key] = doc
        fused_scores[doc_key] = fused_scores.get(doc_key, 0.0) + 1 / (rank + k)

    for rank, doc in enumerate(bm25_results, start=1):
        url = doc.metadata.get("url", "unknown")
        doc_key = doc.page_content + "|" + url
        doc_map[doc_key] = doc
        fused_scores[doc_key] = fused_scores.get(doc_key, 0.0) + 1 / (rank + k)

    # 返回带分数的排序列表，方便观察
    return sorted(fused_scores.items(), key=lambda x: x[1], reverse=True), doc_map

# 2. 实验组：调用你业务代码里带 Source Ranking 的 RRF 算法
def weighted_rrf(vector_results, bm25_results, k=60):
    fused_scores = {}
    doc_map = {}
    
    for rank, doc in enumerate(vector_results, start=1):
        url = doc.metadata.get("url", "unknown")
        doc_key = doc.page_content + "|" + url
        doc_map[doc_key] = doc
        weight = get_source_weight(url)
        fused_scores[doc_key] = fused_scores.get(doc_key, 0.0) + (1 / (rank + k)) * weight

    for rank, doc in enumerate(bm25_results, start=1):
        url = doc.metadata.get("url", "unknown")
        doc_key = doc.page_content + "|" + url
        doc_map[doc_key] = doc
        weight = get_source_weight(url)
        fused_scores[doc_key] = fused_scores.get(doc_key, 0.0) + (1 / (rank + k)) * weight

    return sorted(fused_scores.items(), key=lambda x: x[1], reverse=True), doc_map


def run_ranking_test():
    print("[系统] 正在初始化受控测试数据 (Mock Data)...")
    
    # 模拟场景：检索 "AI眼镜出货量预测"
    # 文档 A：知乎大V的回答（语义极度匹配，向量和关键词都排第1，但来源是 UGC）
    doc_zhihu = Document(
        page_content="[知乎大V爆料] 我觉得AI眼镜出货量明年肯定能翻倍，大家赶紧买爆！",
        metadata={"url": "https://www.zhihu.com/question/123456"}
    )
    
    # 文档 B：普通新闻网报道（语义匹配一般，排第2，来源普通）
    doc_news = Document(
        page_content="[搜狐新闻] 专家指出，AI眼镜出货量预期将保持稳定增长态势。",
        metadata={"url": "https://www.sohu.com/a/123"}
    )
    
    # 文档 C：券商研报PDF（语义比较干涩，排第3，但来源极度权威）
    doc_pdf = Document(
        page_content="[华创证券] 图表12：2024-2025年全球AI眼镜出货量测算模型（单位：万台）。",
        metadata={"url": "https://report.xyz/hua_chuang_ai_glasses.pdf"}
    )

    # 模拟检索返回的顺序
    mock_vector_results = [doc_zhihu, doc_news, doc_pdf] # 排名：1知乎, 2新闻, 3PDF
    mock_bm25_results = [doc_zhihu, doc_news, doc_pdf]   # 排名同上
    
    print("[系统] 执行 Baseline (无权重) RRF 排序...")
    base_scores, base_map = baseline_rrf(mock_vector_results, mock_bm25_results)
    
    print("[系统] 执行 Advanced (带权重) RRF 排序...")
    weight_scores, weight_map = weighted_rrf(mock_vector_results, mock_bm25_results)

    # --- 生成 Markdown 对比报告 ---
    print("[系统] 正在生成 Markdown 分析报告...")
    report = []
    report.append("# ⚖️ Source Ranking (信息源权重) 算法验证报告\n")
    report.append("> **测试场景**: 模拟检索“AI眼镜出货量”，库中同时存在极度匹配的知乎水文，和匹配度略低的券商PDF。\n")
    
    report.append("## 📊 路径 A: 原始 RRF 排序 (无权重干预)")
    report.append("纯按数学排名融合，**不管出处，只管匹配度**。\n")
    for i, (doc_key, score) in enumerate(base_scores, 1):
        doc = base_map[doc_key]
        url = doc.metadata.get("url")
        report.append(f"### Rank {i} (最终得分: {score:.5f})")
        report.append(f"- **来源**: `{url}`")
        report.append(f"- **内容**: {doc.page_content}\n")

    report.append("---\n")
    
    report.append("## 🚀 路径 B: 业务线 Source Ranking 排序 (乘数干预)")
    report.append("引入 `get_source_weight` 引擎，**让良币驱逐劣币**。\n")
    for i, (doc_key, score) in enumerate(weight_scores, 1):
        doc = weight_map[doc_key]
        url = doc.metadata.get("url")
        weight = get_source_weight(url)
        report.append(f"### Rank {i} (最终得分: {score:.5f}) [权重倍率: x{weight}]")
        report.append(f"- **来源**: `{url}`")
        report.append(f"- **内容**: {doc.page_content}\n")

    report_content = "\n".join(report)
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(current_dir, "source_ranking_result.md")
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_content)
        
    print("="*60)
    print(f"✅ 评测完成！结果已完整导出。")
    print(f"📄 文件路径: {output_path}")
    print("="*60)

if __name__ == "__main__":
    run_ranking_test()