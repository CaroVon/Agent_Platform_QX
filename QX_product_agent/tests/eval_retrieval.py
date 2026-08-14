import os
import time
import pickle
import jieba

from langchain_chroma import Chroma
from langchain_community.retrievers import BM25Retriever
from sentence_transformers import SentenceTransformer

# 1. 本地模型与分词器
class LocalEmbeddingModel:
    def __init__(self):
        self.model = SentenceTransformer(
            "/root/autodl-tmp/models/embedding/bge-small-zh-v1.5"
        )
    def embed_documents(self, texts):
        return self.model.encode(texts).tolist()
    def embed_query(self, text):
        return self.model.encode(text).tolist()

def jieba_tokenizer(text):
    return list(jieba.cut(text))

# 2. 自定义 RRF 融合算法
def reciprocal_rank_fusion(vector_results, bm25_results, k=60):
    fused_scores = {}
    doc_map = {}

    for rank, doc in enumerate(vector_results, start=1):
        doc_key = doc.page_content
        doc_map[doc_key] = doc
        fused_scores[doc_key] = fused_scores.get(doc_key, 0.0) + 1 / (rank + k)

    for rank, doc in enumerate(bm25_results, start=1):
        doc_key = doc.page_content
        doc_map[doc_key] = doc
        fused_scores[doc_key] = fused_scores.get(doc_key, 0.0) + 1 / (rank + k)

    reranked_results = [
        doc_map[doc_key] 
        for doc_key, score in sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)
    ]
    return reranked_results

# 3. 对比执行逻辑
def run_retrieval_comparison(query: str, k: int = 3):
    print(f"\n[系统] 正在评测检索词: '{query}'...")

    print("[系统] 加载模型与向量库中...")
    embedding_model = LocalEmbeddingModel()
    
    if not os.path.exists("./chroma_db"):
        print("❌ 错误：未找到 ./chroma_db。请先运行知识库构建脚本！")
        return
    vector_db = Chroma(persist_directory="./chroma_db", embedding_function=embedding_model)
    vector_retriever = vector_db.as_retriever(search_kwargs={"k": k * 2})

    if not os.path.exists("./bm25_db/docs.pkl"):
        print("❌ 错误：未找到 ./bm25_db/docs.pkl。请确认你已重新构建了知识库！")
        return
    with open("./bm25_db/docs.pkl", "rb") as f:
        docs = pickle.load(f)
    bm25_retriever = BM25Retriever.from_documents(docs, preprocess_func=jieba_tokenizer)
    bm25_retriever.k = k * 2

    # --- 开始执行检索 ---
    print("[系统] 执行纯向量检索 (Path A)...")
    start_time = time.time()
    vec_results = vector_db.similarity_search(query, k=k)
    vec_time = time.time() - start_time

    print("[系统] 执行混合融合检索 (Path B)...")
    start_time = time.time()
    v_res = vector_retriever.invoke(query)
    b_res = bm25_retriever.invoke(query)
    hyb_results = reciprocal_rank_fusion(v_res, b_res)[:k]
    hyb_time = time.time() - start_time

    # --- 构建 Markdown 报告 ---
    print("[系统] 正在生成完整对比报告...")
    report = []
    report.append(f"# 检索策略对比报告")
    report.append(f"> **评测检索词**: `{query}`\n")
    
    report.append("## 📊 路径 A: 纯向量检索 (Dense Only)")
    report.append(f"- **耗时**: {vec_time:.2f}s\n")
    for idx, doc in enumerate(vec_results, 1):
        # 移除多余换行，保留段落结构，方便阅读
        content = doc.page_content.replace('\n', ' ').strip()
        report.append(f"### [Chunk {idx}]\n{content}\n")

    report.append("---\n")
    report.append("## 🚀 路径 B: 混合检索 (Vector + BM25)")
    report.append(f"- **耗时**: {hyb_time:.2f}s\n")
    for idx, doc in enumerate(hyb_results, 1):
        content = doc.page_content.replace('\n', ' ').strip()
        report.append(f"### [Chunk {idx}]\n{content}\n")

    report_content = "\n".join(report)

    # --- 写入文件 ---
    current_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(current_dir, "retrieval_comparison_result.md")
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_content)
        
    print("="*60)
    print(f"✅ 评测完成！结果已完整导出。")
    print(f"📄 文件路径: {output_path}")
    print("="*60)

if __name__ == "__main__":
    # 测试硬核实体词
    test_query = "Micro-OLED 显示技术"
    run_retrieval_comparison(test_query, k=3)