"""AI Product Studio 任务的知识库持久化。

Studio 产品使用 ``studio_products``，与旧报告项目 ``projects`` 是两套任务模型。
这个模块负责把 Studio 资产写入独立任务向量库，并在登记表中保留明确的任务链接。
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)


def sync_studio_knowledge(
    product_id: str,
    package: dict | None,
    *,
    idea: str = "",
) -> dict[str, int | str]:
    """幂等写入任务知识库和知识资产登记表。"""
    from app.rag.chunker import chunk_text
    from app.rag.vector_store import build_vector_store
    from app.repositories import ProjectRepo
    from app.services.product_keywords import _extract_package_text

    package = package or {}
    product_id = str(product_id)
    corpus = _extract_package_text(package)
    chunks = chunk_text(corpus)
    chunk_rows = [
        {
            "content": chunk,
            "url": f"studio://product/{product_id}",
        }
        for chunk in chunks
        if chunk.strip()
    ]
    if chunk_rows:
        build_vector_store(chunk_rows, project_id=product_id)

    keywords = package.get("keywords") or {}
    tags = [
        str(word)
        for values in keywords.values()
        if isinstance(values, list)
        for word in values[:4]
    ]
    title = idea or package.get("idea") or f"Product Studio 任务 {product_id[:8]}"
    ProjectRepo().save_knowledge_asset(
        scope=f"studio:{product_id}",
        source="studio",
        title=title,
        source_url=f"studio://product/{product_id}",
        tags=tags[:20],
        chunk_count=len(chunk_rows),
        studio_product_id=product_id,
        extra={"product_id": product_id, "asset_keys": list(package.keys())},
    )
    logger.info(
        "[Studio Knowledge] 任务知识已同步 | product=%s | chunks=%d",
        product_id,
        len(chunk_rows),
    )
    return {
        "product_id": product_id,
        "chunks": len(chunk_rows),
        "assets": 1,
    }
