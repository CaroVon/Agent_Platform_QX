"""
============================================================
向量存储引擎 (Vector Store + BM25 持久化)
—— 每个项目使用独立子目录，根除多项目并发覆盖
============================================================
"""
import os
import pickle
import logging
import warnings

from langchain_chroma import Chroma
from langchain_core.documents import Document
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class LocalEmbeddingModel:
    """Embedding 模型封装 —— 线程安全单例，模型路径从配置读取。"""

    _instance = None
    _model = None

    # 批量嵌入的每批大小，避免一次性嵌入过多文本导致 OOM 或超时
    EMBED_BATCH_SIZE = 32

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _get_model(self):
        if self._model is None:
            try:
                from app.core.config import get_settings
                settings = get_settings()
                model_path = settings.EMBEDDING_MODEL_PATH
            except ImportError:
                model_path = os.environ.get(
                    "EMBEDDING_MODEL_PATH", "BAAI/bge-small-zh-v1.5",
                )
            logger.info("[Embedding] 正在加载模型: %s", model_path)
            self._model = SentenceTransformer(model_path)
            logger.info("[Embedding] 模型加载完成")
        return self._model

    def embed_documents(self, texts):
        """批量嵌入文档，分批处理避免内存溢出或连接超时。"""
        model = self._get_model()
        all_embeddings = []
        batch_size = self.EMBED_BATCH_SIZE
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_embeddings = model.encode(batch, show_progress_bar=False).tolist()
            all_embeddings.extend(batch_embeddings)
            logger.debug("[Embedding] 嵌入进度: %d/%d", min(i + batch_size, len(texts)), len(texts))
        return all_embeddings

    def embed_query(self, text):
        return self._get_model().encode(text).tolist()


embedding_model = LocalEmbeddingModel()


def _resolve_persist_dirs(project_id: str | None = None):
    """
    解析向量库持久化目录。

    优先使用集中配置中的路径；当 project_id 提供时创建
    per-project 子目录，杜绝多项目并发覆盖。
    """
    try:
        from app.core.config import get_settings
        settings = get_settings()
        chroma_base = settings.CHROMA_PERSIST_DIR
        bm25_base = settings.BM25_PERSIST_DIR
    except ImportError:
        chroma_base = os.environ.get("CHROMA_PERSIST_DIR", "./chroma_db")
        bm25_base = os.environ.get("BM25_PERSIST_DIR", "./bm25_db")

    if project_id:
        chroma_dir = os.path.join(chroma_base, project_id)
        bm25_dir = os.path.join(bm25_base, project_id)
    else:
        warnings.warn(
            "build_vector_store() 未提供 project_id——使用共享向量库目录。"
            "多项目并发时数据会互相覆盖，请尽快传入 project_id。",
            FutureWarning,
            stacklevel=3,
        )
        chroma_dir = chroma_base
        bm25_dir = bm25_base

    return chroma_dir, bm25_dir


def build_vector_store(
    chunk_data_list: list[dict],
    project_id: str | None = None,
):
    """
    接收带有元数据的切片列表，构建 Chroma + BM25 持久化存储。

    Args:
        chunk_data_list: [{"content": "...", "url": "https://..."}, ...]
        project_id:      项目 UUID 字符串（用于 per-project 向量库隔离）。

    Returns:
        Chroma vector_store 实例。
    """
    if not chunk_data_list:
        logger.warning("build_vector_store: chunk_data_list 为空，跳过构建")
        return None

    chroma_dir, bm25_dir = _resolve_persist_dirs(project_id)

    # ── 构建 LangChain Document 列表 ────────────────────
    docs = []
    for item in chunk_data_list:
        doc = Document(
            page_content=item.get("content", ""),
            metadata={"url": item.get("url", "unknown")},
        )
        docs.append(doc)

    # ── 1. 持久化到 Chroma（向量检索） ──────────────────
    os.makedirs(chroma_dir, exist_ok=True)
    vector_store = Chroma.from_documents(
        documents=docs,
        embedding=embedding_model,
        persist_directory=chroma_dir,
    )
    logger.info("Chroma 向量库已构建: %s (%d 个文档)", chroma_dir, len(docs))

    # ── 2. 持久化原始 Chunks 到本地（BM25 检索） ────────
    os.makedirs(bm25_dir, exist_ok=True)
    bm25_path = os.path.join(bm25_dir, "docs.pkl")

    # 追加模式：加载已有语料并合并，防止多批次写入时互相覆盖
    existing_docs: list[Document] = []
    if os.path.exists(bm25_path):
        try:
            with open(bm25_path, "rb") as f:
                existing_docs = pickle.load(f)
            logger.info("BM25 已有 %d 个文档，将追加 %d 个新文档", len(existing_docs), len(docs))
        except Exception as e:
            logger.warning("BM25 已有语料加载失败，将覆盖写入: %s", e)

    # 基于 (content, url) 去重：已存在的切片不再重复写入
    seen = {(d.page_content, d.metadata.get("url", "")) for d in existing_docs}
    new_unique = [d for d in docs if (d.page_content, d.metadata.get("url", "")) not in seen]
    all_docs = existing_docs + new_unique

    with open(bm25_path, "wb") as f:
        pickle.dump(all_docs, f)
    logger.info(
        "BM25 语料已更新: %s (追加 %d，去重后总计 %d 个文档)",
        bm25_path, len(new_unique), len(all_docs),
    )

    logger.info(
        "Vector Store + BM25 构建完毕 (project=%s, chunks=%d)",
        project_id or "(共享)", len(docs),
    )
    return vector_store


if __name__ == "__main__":
    sample_chunks = [
        {"content": "AI glasses market is growing rapidly.", "url": "https://example.com/1"},
        {"content": "Meta and RayBan launched smart glasses.", "url": "https://example.com/2"},
        {"content": "AI wearable devices are becoming popular.", "url": "https://example.com/3"},
    ]
    db = build_vector_store(sample_chunks)
    print("Vector store built successfully.")
