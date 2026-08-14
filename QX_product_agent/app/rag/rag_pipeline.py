"""
============================================================
RAG Pipeline —— 知识库构建 + 上下文检索
============================================================
"""
import logging

from app.search.tavily_search import tavily_search
from app.crawler.firecrawl_crawler import crawl_url
from app.rag.chunker import chunk_text
from app.rag.vector_store import build_vector_store
from app.rag.retriever import retrieve

logger = logging.getLogger(__name__)


def build_knowledge_base(query: str, project_id: str | None = None):
    """
    搜索 + 爬取 + 切片 + 向量化，构建项目知识库。

    Args:
        query:      搜索主题
        project_id: 项目 UUID（用于 per-project 向量库隔离）
    """
    search_results = tavily_search(query)
    results = search_results.get("results", [])

    all_chunks_with_meta: list[dict] = []

    for item in results[:3]:
        url = item.get("url")
        if not url:
            continue

        logger.info("爬取: %s", url)
        try:
            crawl_result = crawl_url(url)
            markdown = getattr(crawl_result, "markdown", "")

            if markdown:
                chunks = chunk_text(markdown)
                for chunk in chunks:
                    all_chunks_with_meta.append({
                        "content": chunk,
                        "url": url,
                    })
                logger.info("  ✓ %d chunks from %s", len(chunks), url)

        except Exception as e:
            logger.error("爬取失败 %s: %s", url, e)

    build_vector_store(all_chunks_with_meta, project_id=project_id)
    logger.info("知识库构建完成: %d 个切片 (project=%s)",
                len(all_chunks_with_meta), project_id or "(共享)")


def retrieve_context(query: str, k: int = 5, project_id: str | None = None) -> str:
    """
    检索并格式化为 LLM 可消费的上下文块。

    Args:
        query:      检索查询字符串
        k:          返回文档数量
        project_id: 项目 UUID（用于 per-project 向量库隔离）

    Returns:
        格式化的上下文字符串（含来源 URL）。
    """
    results = retrieve(query, k=k, project_id=project_id)
    context_parts: list[str] = []

    for idx, r in enumerate(results, start=1):
        source_url = r.metadata.get("url", "unknown")
        context_parts.append(
            f"[Chunk {idx} | 来源: {source_url}]\n\n{r.page_content}\n"
        )

    return "\n".join(context_parts)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        topic = sys.argv[1]
        pid = sys.argv[2] if len(sys.argv) > 2 else None
    else:
        topic = "AI眼镜行业"
        pid = None

    print("========== 1. 构建知识库 ==========")
    build_knowledge_base(topic, project_id=pid)

    print("\n========== 2. 混合检索测试 ==========")
    ctx = retrieve_context("AI眼镜市场规模与竞争格局", k=3, project_id=pid)
    print(ctx)
