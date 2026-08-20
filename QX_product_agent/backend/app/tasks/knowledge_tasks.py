"""
============================================================
知识库构建任务
—— 封装原有的 app/rag/vector_store.py 和 chunker 逻辑
   新增（P1-P3）：
     knowledge.analyze_image          图片 VL 分析入库
     knowledge.summarize_experience   任务完成经验包抽取
     knowledge.sync_obsidian_vault    Obsidian 笔记同步入库
   新增（P4）：
     knowledge.build_memory_graph     任务完成记忆图沉淀（实体/关系/洞察）
     knowledge.decay_memories         记忆置信度衰减（周期任务）
============================================================
"""

from __future__ import annotations

import os
import json
import logging
from typing import Any

from celery import Task

from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.core.celery_db import get_crawled_data_path

logger = logging.getLogger(__name__)


class KnowledgeTask(Task):
    _settings = None

    @property
    def settings(self):
        if self._settings is None:
            self._settings = get_settings()
        return self._settings


@celery_app.task(
    bind=True,
    base=KnowledgeTask,
    name="knowledge.build_knowledge_base",
    max_retries=2,
    default_retry_delay=15,
    acks_late=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def build_knowledge_base(self: KnowledgeTask, project_id: str) -> dict[str, Any]:
    """
    第2步：知识库构建
    —— 将爬取的文本切片后存入 Chroma 向量库和 BM25 持久化文件

    未来多租户扩展：
    当引入多租户时，此处需要根据 project 的 tenant_id
    切换不同的 CHROMA_PERSIST_DIR / BM25_PERSIST_DIR
    例如: /app/chroma_db/{tenant_id}/{project_id}
    """
    logger.info("[TASK] 开始构建知识库 | project_id=%s", project_id)

    settings = self.settings

    # ─── 1. 从数据库获取爬取数据快照 ──────────────────────────
    # 目前方案：search_and_crawl 任务的返回值通过链式调用传递
    # 注意：Celery 链式调用任务之间通过返回值和参数传递数据
    # 这里我们直接从 storage 获取，或者通过任务签名传递
    # 简化方案：重新调用搜索任务（或从文件读取）
    #
    # TODO: 生产环境建议将 crawled_data 存入 Redis 或 Task 结果中
    # 这里演示标准流程，实际部署时由 workflow 编排传入数据

    # ─── 2. 文本切片 ──────────────────────────────────────────
    from app.rag.chunker import chunk_text
    from app.rag.vector_store import build_vector_store

    # 由于 Celery 链式调用中无法直接传递大量数据（受 Broker 限制），
    # 我们采用"先存后读"策略：search_and_crawl 将结果保存到文件/Redis，
    # 此处再读取。
    temp_data_path = get_crawled_data_path(project_id)

    if os.path.exists(temp_data_path):
        with open(temp_data_path, "r", encoding="utf-8") as f:
            crawled_data = json.load(f)
    else:
        # 如果找不到临时文件，说明 search_and_crawl 可能未执行
        logger.warning("[TASK] 未找到临时数据文件，尝试从上游任务结果获取")
        raise FileNotFoundError(f"临时数据文件不存在: {temp_data_path}")

    # ─── 3. 执行切片 ──────────────────────────────────────────
    all_chunks_with_meta = []
    for item in crawled_data:
        content = item.get("content", "")
        url = item.get("url", "unknown")

        if not content:
            continue

        chunks = chunk_text(content)
        for chunk in chunks:
            all_chunks_with_meta.append({
                "content": chunk,
                "url": url,
            })

        logger.info("[TASK] 切片完成: %s -> %d chunks", url, len(chunks))

    logger.info("[TASK] 共 %d 个切片，开始构建向量库", len(all_chunks_with_meta))

    # ─── 4. 构建向量库 + BM25 ─────────────────────────────────
    # 未来多租户：此处根据 tenant_id 切换目录
    # chroma_dir = settings.CHROMA_PERSIST_DIR_TEMPLATE.format(tenant_id=tenant_id)
    # bm25_dir = settings.BM25_PERSIST_DIR_TEMPLATE.format(tenant_id=tenant_id)

    # 使用配置中的持久化目录 + per-project 子目录（根治多项目覆盖）
    os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
    os.makedirs(settings.BM25_PERSIST_DIR, exist_ok=True)
    build_vector_store(all_chunks_with_meta, project_id=project_id)

    # ─── 5. 清理临时文件 ──────────────────────────────────────
    try:
        os.remove(temp_data_path)
    except OSError:
        pass

    logger.info("[TASK] 知识库构建完成 | project=%s | total_chunks=%d",
                project_id, len(all_chunks_with_meta))

    return {
        "project_id": project_id,
        "total_chunks": len(all_chunks_with_meta),
        "status": "completed",
    }


# ══════════════════════════════════════════════════════════════
# P1: 图片 VL 分析入库（MiniMax minimax-vl-01）
# ══════════════════════════════════════════════════════════════

@celery_app.task(
    bind=True,
    base=KnowledgeTask,
    name="knowledge.analyze_image",
    max_retries=2,
    default_retry_delay=15,
    acks_late=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def analyze_image(self: KnowledgeTask, image_id: str) -> dict[str, Any]:
    """
    对一张知识库图片执行 MiniMax VL 分析：
      VL 结构化输出（概述/OCR/标签/主体/场景/图表数据）
      → 文本化切片写入任务向量库（image:// 来源）
      → 更新 project_images 表（status/analysis_text/tags）
    """
    logger.info("[TASK] 图片分析开始 | image_id=%s", image_id)

    from app.repositories import ProjectRepo
    repo = ProjectRepo()

    img = repo.get_image(image_id)
    if img is None:
        raise FileNotFoundError(f"图片记录不存在: {image_id}")

    if not img.file_path or not os.path.isfile(img.file_path):
        raise FileNotFoundError(f"图片文件不存在: {getattr(img, 'file_path', None)}")

    # 防止重复分析（幂等：ready 状态直接返回）
    if img.status == "ready" and img.analysis_text:
        logger.info("[TASK] 图片已分析过，跳过 | image_id=%s", image_id)
        return {"image_id": image_id, "status": "ready", "cached": True}

    repo.update_image_analysis(image_id, status="analyzing")

    try:
        from app.llm.vision import analyze_image_structured
        result = analyze_image_structured(image_path=img.file_path)
    except Exception as e:
        logger.error("[TASK] VL 分析失败 | image_id=%s | error=%s", image_id, str(e))
        repo.update_image_analysis(image_id, status="failed")
        raise

    # ── 文本化切片 → 任务向量库 ──────────────────────────────
    text_parts = [
        result.get("summary", ""),
        result.get("ocr_text", ""),
        result.get("chart_data", ""),
    ]
    text = "\n".join(p for p in text_parts if p).strip()
    if not text:
        logger.warning("[TASK] VL 分析无有效文本，仅保存元数据 | image_id=%s", image_id)
        repo.update_image_analysis(
            image_id, status="ready",
            analysis_text=json.dumps(result, ensure_ascii=False),
            tags=result.get("tags", []),
        )
        return {"image_id": image_id, "status": "ready", "chunks": 0}

    from app.rag.chunker import chunk_text
    from app.rag.vector_store import build_vector_store
    filename = os.path.basename(img.file_path)
    chunks = [
        {"content": c, "url": f"image://{img.project_id}/{filename}"}
        for c in chunk_text(text)
    ]
    try:
        build_vector_store(chunks, project_id=str(img.project_id))
    except Exception as e:
        logger.error("[TASK] 图片切片入库失败 | image_id=%s | error=%s", image_id, str(e))
        repo.update_image_analysis(image_id, status="failed")
        raise

    repo.update_image_analysis(
        image_id,
        status="ready",
        analysis_text=json.dumps(result, ensure_ascii=False),
        tags=result.get("tags", []),
    )

    logger.info("[TASK] 图片分析完成 | image_id=%s | chunks=%d | tags=%s",
                image_id, len(chunks), result.get("tags", []))
    return {"image_id": image_id, "status": "ready", "chunks": len(chunks)}


# ══════════════════════════════════════════════════════════════
# P2: 任务完成 → 领域经验包抽取
# ══════════════════════════════════════════════════════════════

@celery_app.task(
    bind=True,
    base=KnowledgeTask,
    name="knowledge.summarize_experience",
    max_retries=1,
    default_retry_delay=30,
    acks_late=True,
)
def summarize_experience(self: KnowledgeTask, project_id: str) -> dict[str, Any]:
    """
    项目完成后的领域经验沉淀：
      LLM 压缩章节成果 → domain_experiences 表 + 领域向量库
    失败不阻断主流程（增强型任务）。
    """
    logger.info("[TASK] 经验包抽取开始 | project_id=%s", project_id)
    from app.rag.task_similarity import summarize_task_experience
    result = summarize_task_experience(project_id)
    if result is None:
        logger.info("[TASK] 经验包抽取跳过（项目未完成或无内容） | project_id=%s", project_id)
        return {"project_id": project_id, "status": "skipped"}
    logger.info("[TASK] 经验包抽取完成 | project_id=%s | exp_id=%s",
                project_id, result.get("experience_id"))
    return {"project_id": project_id, "status": "completed", **result}


# ══════════════════════════════════════════════════════════════
# P3: Obsidian Vault 同步（全局知识库）
# ══════════════════════════════════════════════════════════════

@celery_app.task(
    bind=True,
    base=KnowledgeTask,
    name="knowledge.sync_obsidian_vault",
    max_retries=1,
    default_retry_delay=60,
    acks_late=True,
)
def sync_obsidian_vault(self: KnowledgeTask) -> dict[str, Any]:
    """
    增量同步 Obsidian Vault 笔记到全局知识库（L0）。

    - 扫描 vault/**/*.md（跳过 .obsidian 与 .trash）
    - 按 mtime 增量处理
    - frontmatter tags/type 解析 → knowledge_assets 登记 + 全局向量库
    - 已删除笔记清理对应切片（按 obsidian:// url 前缀）
    """
    settings = self.settings
    vault_path = settings.OBSIDIAN_VAULT_PATH.strip()
    if not vault_path:
        logger.info("[TASK] OBSIDIAN_VAULT_PATH 未配置，跳过同步")
        return {"status": "disabled"}

    vault = os.path.abspath(os.path.expanduser(vault_path))
    if not os.path.isdir(vault):
        logger.warning("[TASK] Vault 目录不存在: %s", vault)
        return {"status": "error", "detail": f"vault 目录不存在: {vault}"}

    from app.repositories import ProjectRepo
    from app.rag.chunker import chunk_text
    from app.rag.vector_store import build_vector_store
    repo = ProjectRepo()

    # 上次同步记录（存 vault 同级 .obsidian_sync_state.json，避免侵入用户目录 → 存 outputs 私有目录）
    sync_state_path = os.path.join(
        settings.OUTPUT_DIR, "private", "obsidian_sync_state.json",
    )
    state: dict[str, float] = {}
    if os.path.isfile(sync_state_path):
        try:
            with open(sync_state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception:  # noqa: BLE001
            state = {}

    last_sync = state.get("last_sync", 0.0)
    added = skipped = failed = 0

    for root, dirs, files in os.walk(vault):
        dirs[:] = [d for d in dirs if d not in (".obsidian", ".trash", ".git", "node_modules")]
        for name in files:
            if not name.endswith(".md"):
                continue
            full = os.path.join(root, name)
            rel = os.path.relpath(full, vault).replace("\\", "/")
            try:
                mtime = os.path.getmtime(full)
            except OSError:
                continue

            if mtime <= last_sync:
                skipped += 1
                continue

            try:
                content, tags, title = _parse_vault_note(full, rel)
                if not content.strip():
                    skipped += 1
                    continue

                source_url = f"obsidian://{rel}"
                chunks = [
                    {"content": c, "url": source_url, "tags": tags}
                    for c in chunk_text(content)
                ]
                if chunks:
                    build_vector_store(chunks, scope="global")
                repo.save_knowledge_asset(
                    scope="global",
                    title=title,
                    source="obsidian",
                    source_url=source_url,
                    tags=tags,
                    chunk_count=len(chunks),
                )
                added += 1
            except Exception as e:  # noqa: BLE001
                failed += 1
                logger.warning("[TASK] Vault 笔记处理失败 | %s | %s", rel, e)

    state["last_sync"] = os.path.getmtime(vault) if os.path.isdir(vault) else last_sync
    os.makedirs(os.path.dirname(sync_state_path), exist_ok=True)
    with open(sync_state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)

    logger.info("[TASK] Vault 同步完成 | added=%d | skipped=%d | failed=%d",
                added, skipped, failed)
    return {"status": "completed", "added": added, "skipped": skipped, "failed": failed}


def _parse_vault_note(full_path: str, rel_path: str) -> tuple[str, list[str], str]:
    """解析 Obsidian 笔记：frontmatter(tags/type/title) + 正文。"""
    with open(full_path, "r", encoding="utf-8", errors="replace") as f:
        raw = f.read()

    tags: list[str] = []
    title = os.path.splitext(os.path.basename(full_path))[0]

    # YAML frontmatter 解析（极简版：--- 包裹的首块）
    if raw.startswith("---"):
        end = raw.find("\n---", 3)
        if end != -1:
            fm = raw[3:end]
            body = raw[end + 4:]
            in_tags = False
            for line in fm.splitlines():
                line = line.strip()
                if line.startswith("tags:"):
                    in_tags = True
                    rest = line[len("tags:"):].strip()
                    if rest.startswith("["):
                        tags = [t.strip().strip("'\"") for t in rest.strip("[]").split(",") if t.strip()]
                        in_tags = False
                    elif rest:
                        tags = [rest.strip().strip("'\"")]
                elif in_tags and line.startswith("- "):
                    tags.append(line[2:].strip().strip("'\" "))
                elif not line.startswith("- "):
                    in_tags = False
                if line.lower().startswith("title:"):
                    t = line[len("title:"):].strip().strip("'\"")
                    if t:
                        title = t
            raw = body

    return raw, tags[:20], title


# ══════════════════════════════════════════════════════════════
# P4: 任务完成 → 记忆图沉淀（实体/关系/洞察 + 全局提升）
# ══════════════════════════════════════════════════════════════

@celery_app.task(
    bind=True,
    base=KnowledgeTask,
    name="knowledge.build_memory_graph",
    max_retries=1,
    default_retry_delay=30,
    acks_late=True,
)
def build_memory_graph(self: KnowledgeTask, project_id: str) -> dict[str, Any]:
    """
    任务完成后的记忆图沉淀（P4a）：
      LLM 抽取实体/关系/洞察 → 归一化合并 → 项目记忆入库
      → 记忆向量化 → 跨项目全局提升
    失败不阻断主流程（增强型任务）。
    """
    logger.info("[TASK] 记忆图沉淀开始 | project_id=%s", project_id)
    from app.rag.memory_extraction import extract_memory_from_project
    result = extract_memory_from_project(project_id)
    if result is None:
        logger.info("[TASK] 记忆图沉淀跳过（项目未完成或无语料） | project_id=%s", project_id)
        return {"project_id": project_id, "status": "skipped"}
    logger.info("[TASK] 记忆图沉淀完成 | project_id=%s | %s", project_id, result)
    return {"project_id": project_id, "status": "completed", **result}


@celery_app.task(
    bind=True,
    base=KnowledgeTask,
    name="knowledge.build_studio_memory_graph",
    max_retries=1,
    default_retry_delay=30,
    acks_late=True,
)
def build_studio_memory_graph(self: KnowledgeTask, product_id: str) -> dict[str, Any]:
    """手动重建 Product Studio 任务的记忆图。"""
    from sqlalchemy.orm import Session
    from app.core.celery_db import get_sync_engine
    from app.models.studio_product import StudioProduct
    from app.tasks.product_studio_tasks import _ensure_paths

    settings = self.settings
    _ensure_paths(settings)
    with Session(get_sync_engine()) as session:
        product = session.get(StudioProduct, product_id)
        if product is None:
            return {"product_id": product_id, "status": "missing"}
        package = json.loads(product.asset_package or "{}")

    from agent_platform.llm.client import LLMClient
    from app.rag.studio_memory import extract_memory_from_studio_product

    llm = LLMClient(
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL,
        model=settings.DEEPSEEK_MODEL,
    )
    result = extract_memory_from_studio_product(product_id, package, llm)
    return {"product_id": product_id, "status": "completed", **(result or {})}


# ══════════════════════════════════════════════════════════════
# P4c: 记忆置信度衰减（周期任务）
# ══════════════════════════════════════════════════════════════

@celery_app.task(
    bind=True,
    base=KnowledgeTask,
    name="knowledge.decay_memories",
    max_retries=1,
    default_retry_delay=60,
    acks_late=True,
)
def decay_memories(self: KnowledgeTask) -> dict[str, Any]:
    """长期未引用的记忆实体置信度衰减（记忆遗忘机制）。"""
    from app.rag.memory_extraction import decay_memories as _decay
    count = _decay()
    return {"status": "completed", "decayed": count}
