"""
============================================================
任务相似度与领域经验服务 (L1 领域知识层)
—— 判别哪些任务相似度高可互相借用，并抽取/注入领域经验包
============================================================

职责：
  1. ensure_project_profile(project_id)  —— 计算 topic 向量 + 领域标签（惰性）
  2. find_similar_projects(project_id)    —— 余弦相似度 + 标签重合 + 模板一致
  3. summarize_task_experience(project_id)—— 任务完成时 LLM 抽取经验包并入库
  4. retrieve_experiences(project_id)     —— 召回相似任务经验包（供 prompt 注入）
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)

# 相似度权重：主题向量 0.6 / 标签重合 0.3 / 模板一致 0.1
EMBED_WEIGHT = 0.6
TAG_WEIGHT = 0.3
TEMPLATE_WEIGHT = 0.1

_DOMAIN_TAG_PROMPT = (
    "请从以下产品分析主题中抽取领域标签，严格输出 JSON 数组，最多 5 个，"
    "每个标签格式为 '维度:值'（如 'industry:消费电子'、'category:智能穿戴'、"
    "'scene:运动健康'）。不要输出解释。\n主题："
)


def _embed_text(text: str) -> list[float] | None:
    """使用 bge-small-zh-v1.5 计算文本向量；失败返回 None（不阻断流程）。"""
    try:
        from app.rag.retriever import embedding_model
        return embedding_model.embed_query(text)
    except Exception as e:  # noqa: BLE001
        logger.warning("Embedding 计算失败（相似度服务降级）: %s", e)
        return None


def _get_repo():
    from app.repositories import ProjectRepo
    return ProjectRepo()


# ══════════════════════════════════════════════════════════════
# 任务画像（topic 向量 + 领域标签），惰性计算并持久化
# ══════════════════════════════════════════════════════════════

def ensure_project_profile(project_id: str) -> dict[str, Any]:
    """
    确保项目已有 topic_embedding 与 domain_tags；缺失则计算并落库。

    Returns:
        {"topic_embedding": [...], "domain_tags": [...]}
    """
    repo = _get_repo()
    project = repo.get_project(project_id)

    profile: dict[str, Any] = {}
    if getattr(project, "topic_embedding", None):
        try:
            profile["topic_embedding"] = json.loads(project.topic_embedding)
        except (json.JSONDecodeError, TypeError):
            profile["topic_embedding"] = None
    else:
        profile["topic_embedding"] = None

    if getattr(project, "domain_tags", None):
        try:
            profile["domain_tags"] = json.loads(project.domain_tags)
        except (json.JSONDecodeError, TypeError):
            profile["domain_tags"] = None
    else:
        profile["domain_tags"] = None

    changed = False

    if not profile["topic_embedding"]:
        emb = _embed_text(project.topic)
        if emb:
            profile["topic_embedding"] = emb
            changed = True

    if not profile["domain_tags"]:
        tags = _infer_domain_tags(project.topic)
        if tags:
            profile["domain_tags"] = tags
            changed = True

    if changed:
        repo.update_project_profile(
            project_id,
            topic_embedding=profile["topic_embedding"],
            domain_tags=profile["domain_tags"],
        )
        logger.info("[相似度] 项目画像已生成 | project=%s | tags=%s",
                    project_id, profile["domain_tags"])

    return profile


def _infer_domain_tags(topic: str) -> list[str]:
    """用 LLM 从主题抽取领域标签；失败时降级为空（不阻断）。"""
    try:
        from app.core.config import get_settings
        settings = get_settings()
        llm = _get_chat_llm(settings)
        raw = llm.invoke(_DOMAIN_TAG_PROMPT + topic).content or ""
        start, end = raw.find("["), raw.rfind("]")
        if start == -1 or end <= start:
            return []
        tags = json.loads(raw[start:end + 1])
        return [str(t).strip() for t in tags if str(t).strip()][:5]
    except Exception as e:  # noqa: BLE001
        logger.warning("领域标签推断失败（降级为空）: %s", e)
        return []


def _get_chat_llm(settings):
    """构造 ChatOpenAI（与 backend editor.py 一致的模型路由）。"""
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL,
        model=settings.DEEPSEEK_MODEL,
        temperature=0.2,
    )


# ══════════════════════════════════════════════════════════════
# 相似任务检索
# ══════════════════════════════════════════════════════════════

def find_similar_projects(
    project_id: str,
    top_k: int = 5,
    min_similarity: float = 0.0,
) -> list[dict[str, Any]]:
    """
    计算与给定项目最相似的历史任务。

    sim = 0.6·cos(topic_emb) + 0.3·标签重合率 + 0.1·模板一致

    Returns:
        [{"project_id", "topic", "template_type", "similarity", "status",
          "domain_tags", "experience_summary"}, ...]（按相似度降序）
    """
    repo = _get_repo()
    profile = ensure_project_profile(project_id)
    base_emb = profile.get("topic_embedding")
    base_tags = set(profile.get("domain_tags") or [])
    base_template = repo.get_project_template(project_id)

    all_projects = repo.list_projects_for_similarity()
    results: list[dict[str, Any]] = []

    for p in all_projects:
        if str(p.id) == str(project_id):
            continue
        if p.status and p.status.value in ("failed", "preparing_data"):
            continue  # 失败/未开始的任务不参与借用

        sim = 0.0
        if base_emb:
            try:
                other_emb = json.loads(p.topic_embedding) if p.topic_embedding else None
                if other_emb:
                    sim += EMBED_WEIGHT * _cosine(base_emb, other_emb)
            except (json.JSONDecodeError, TypeError):
                pass

        if base_tags:
            try:
                other_tags = set(json.loads(p.domain_tags) if p.domain_tags else [])
            except (json.JSONDecodeError, TypeError):
                other_tags = set()
            if other_tags:
                sim += TAG_WEIGHT * len(base_tags & other_tags) / max(len(base_tags | other_tags), 1)

        if (p.template_type or "product") == base_template:
            sim += TEMPLATE_WEIGHT

        if sim < min_similarity:
            continue

        results.append({
            "project_id": str(p.id),
            "topic": p.topic,
            "template_type": p.template_type or "product",
            "similarity": round(sim, 4),
            "status": p.status.value if p.status else "unknown",
            "domain_tags": json.loads(p.domain_tags) if p.domain_tags else [],
        })

    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:top_k]


def _cosine(a: list[float], b: list[float]) -> float:
    import math
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# ══════════════════════════════════════════════════════════════
# 经验包：抽取 / 入库 / 召回
# ══════════════════════════════════════════════════════════════

_EXPERIENCE_PROMPT = (
    "你是行业研究知识沉淀助手。请把以下产品分析项目的成果压缩为一份"
    "{max_chars}字以内的【领域经验包】，供未来相似主题任务直接借用。"
    "经验包必须包含：1) 3-5 条关键结论（含数据口径与出处）；"
    "2) 本任务验证有效的方法/结构（如何组织大纲、哪些指标最关键）；"
    "3) 避坑记录（数据缺失、口径陷阱、无效来源类型）。"
    "输出纯文本，不要 Markdown 标题。\n\n"
    "项目主题：{topic}\n\n章节内容：\n{sections}"
)


def summarize_task_experience(project_id: str) -> dict[str, Any] | None:
    """
    任务完成时：抽取经验包 → 写入 domain_experiences 表 + 领域向量库。

    任何一步失败都不抛出（经验沉淀是增强而非阻断），返回 None。
    """
    from app.core.config import get_settings
    settings = get_settings()
    repo = _get_repo()
    try:
        project = repo.get_project(project_id)
    except Exception as e:  # noqa: BLE001
        logger.warning("[经验包] 项目读取失败: %s", e)
        return None

    # 只对已完成的正式项目抽取
    status_value = getattr(project, "status", None)
    if status_value is not None and getattr(status_value, "value", str(status_value)) != "completed":
        logger.info("[经验包] 项目未完成，跳过抽取 | project=%s", project_id)
        return None

    profile = ensure_project_profile(project_id)
    tags = profile.get("domain_tags") or []

    # 1. 组装章节内容（从 DocumentBlock 读取）
    blocks = repo.list_document_blocks(project_id)
    sections_text = "\n\n".join(
        f"## {b.section_title}\n{b.content[:1500]}" for b in blocks[:8]
    )[:12000]
    if not sections_text.strip():
        logger.info("[经验包] 无章节内容，跳过 | project=%s", project_id)
        return None

    # 2. LLM 压缩
    try:
        llm = _get_chat_llm(settings)
        prompt = _EXPERIENCE_PROMPT.format(
            max_chars=settings.EXPERIENCE_MAX_CHARS,
            topic=project.topic,
            sections=sections_text,
        )
        summary = (llm.invoke(prompt) or "").strip()
        if len(summary) > settings.EXPERIENCE_MAX_CHARS * 2:
            summary = summary[: settings.EXPERIENCE_MAX_CHARS * 2]
        if not summary:
            logger.warning("[经验包] LLM 返回空摘要 | project=%s", project_id)
            return None
    except Exception as e:  # noqa: BLE001
        logger.warning("[经验包] LLM 抽取失败: %s", e)
        return None

    # 3. 入库：DB 表
    exp_id = repo.save_domain_experience(
        project_id=project_id,
        domain_tags=tags,
        topic=project.topic,
        summary=summary,
    )

    # 4. 入库：领域向量库（每个标签一个 scope，供 L1 检索）
    try:
        from app.rag.chunker import chunk_text
        from app.rag.vector_store import build_vector_store
        chunks = [
            {"content": c, "url": f"experience://{project_id}"}
            for c in chunk_text(summary)
        ]
        for tag in (tags or ["general"]):
            build_vector_store(chunks, scope=f"domain:{tag}")
        logger.info("[经验包] 已写入领域库 | project=%s | tags=%s | exp_id=%s",
                    project_id, tags, exp_id)
    except Exception as e:  # noqa: BLE001
        logger.warning("[经验包] 领域向量库写入失败（DB 已保存）: %s", e)

    return {"experience_id": str(exp_id), "summary": summary, "tags": tags}


def retrieve_experiences(project_id: str, k: int = 3) -> str:
    """
    召回相似任务的领域经验包，格式化为可注入 prompt 的文本。

    Returns:
        空字符串（无可用经验）或 "【相似任务经验】..." 文本块。
    """
    try:
        from app.core.config import get_settings
        settings = get_settings()
        similar = find_similar_projects(
            project_id,
            top_k=settings.SIMILARITY_TOP_K,
            min_similarity=settings.SIMILARITY_BORROW_THRESHOLD,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("相似任务检索失败: %s", e)
        return ""

    if not similar:
        return ""

    repo = _get_repo()
    parts: list[str] = []
    for item in similar[:k]:
        experiences = repo.list_domain_experiences(item["project_id"])
        for exp in experiences[:1]:  # 每个相似任务最多取 1 条最新经验
            parts.append(
                f"- [来自任务「{exp.topic}」sim={item['similarity']:.2f}] {exp.summary[:400]}"
            )

    if not parts:
        return ""
    return "【相似任务经验（可参考的领域经验包）】\n" + "\n".join(parts)


# ══════════════════════════════════════════════════════════════
# 领域库检索（L1 corpus，不含经验包表）
# ══════════════════════════════════════════════════════════════

def domain_scope_keys(domain_tags: list[str] | None) -> list[str]:
    """把领域标签映射为向量库 scope 键列表。"""
    tags = domain_tags or []
    return [f"domain:{t}" for t in tags] or ["domain:general"]
