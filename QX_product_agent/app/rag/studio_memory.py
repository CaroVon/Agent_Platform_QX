"""AI Product Studio 任务记忆图沉淀。

不复用旧 ``projects.project_id`` 外键，所有节点和洞察通过
``studio_product_id`` 与 Product Studio 任务明确关联。
"""

from __future__ import annotations

import json
import logging

from app.rag.memory_extraction import (
    ENTITY_TYPES,
    _EXTRACT_PROMPT,
    _normalize_name,
    _now,
    _parse_extract_json,
    _upsert_relation,
)

logger = logging.getLogger(__name__)


def _corpus(package: dict | None) -> str:
    package = package or {}
    parts: list[str] = []
    for key in (
        "requirement",
        "research",
        "competitor_analysis",
        "strategy",
        "design",
        "presentation",
    ):
        value = package.get(key)
        if value:
            parts.append(f"## {key}\n{json.dumps(value, ensure_ascii=False, default=str)}")
    return "\n\n".join(parts)[:20000]


def _upsert_entity(repo, product_id: str, name: str, entity_type: str, summary: str):
    existing = repo.find_studio_entity(product_id, name)
    if existing:
        repo.update_entity_merge(
            str(existing.id),
            new_alias=name,
            new_summary=summary or existing.summary,
            confidence_delta=0.1,
            last_seen=_now(),
        )
        return existing.id
    return repo.save_memory_entity(
        scope="project",
        studio_product_id=product_id,
        name=name,
        type=entity_type,
        summary=summary,
        confidence=0.6,
        first_seen=_now(),
        last_seen=_now(),
    ).id


def _vectorize(repo, entity_ids: list[str], product_id: str) -> None:
    try:
        from app.rag.vector_store import build_vector_store

        rows: list[dict] = []
        for entity_id in entity_ids:
            entity = repo.get_entity(entity_id)
            if entity:
                rows.append({
                    "content": f"{entity.name}：{entity.summary or ''}".strip("："),
                    "url": f"memory://entity/{entity_id}",
                })
        for insight in repo.list_insights(
            scope="project", studio_product_id=product_id, limit=20,
        ):
            rows.append({
                "content": insight.content,
                "url": f"memory://insight/{insight.id}",
            })
        if rows:
            build_vector_store(rows, scope="memory")
    except Exception as exc:  # noqa: BLE001
        logger.warning("[Studio Memory] 向量化失败（不影响数据库入库）: %s", exc)


def extract_memory_from_studio_product(
    product_id: str,
    package: dict | None,
    llm,
) -> dict[str, int | str] | None:
    """从 Studio 资产包抽取并幂等保存实体、关系、洞察。"""
    from app.repositories import ProjectRepo

    corpus = _corpus(package)
    if not corpus.strip():
        return None
    repo = ProjectRepo()
    try:
        raw = llm.complete_json(
            [
                {
                    "role": "system",
                    "content": "你是知识沉淀引擎。严格输出 JSON，不要 Markdown。",
                },
                {"role": "user", "content": _EXTRACT_PROMPT.replace("{corpus}", corpus)},
            ],
            temperature=0.1,
            max_tokens=2048,
        )
        data = raw if isinstance(raw, dict) else _parse_extract_json(str(raw))
    except Exception as exc:  # noqa: BLE001
        logger.warning("[Studio Memory] LLM 抽取失败 | product=%s | %s", product_id, exc)
        return None

    entity_ids: dict[str, str] = {}
    saved_entities: list[str] = []
    for item in data.get("entities") or []:
        name = _normalize_name(str(item.get("name") or ""))
        if not name:
            continue
        entity_type = item.get("type") or "other"
        if entity_type not in ENTITY_TYPES:
            entity_type = "other"
        entity_id = _upsert_entity(
            repo, product_id, name, entity_type, str(item.get("summary") or "")[:300],
        )
        entity_ids[name] = str(entity_id)
        saved_entities.append(str(entity_id))

    saved_relations = 0
    for item in data.get("relations") or []:
        source = _normalize_name(str(item.get("source") or ""))
        target = _normalize_name(str(item.get("target") or ""))
        if not source or not target or source == target:
            continue
        for name in (source, target):
            if name not in entity_ids:
                entity_ids[name] = str(_upsert_entity(repo, product_id, name, "other", ""))
        if _upsert_relation(
            repo,
            entity_ids[source],
            entity_ids[target],
            str(item.get("relation") or "相关")[:50],
            product_id,
        ):
            saved_relations += 1

    saved_insights = 0
    existing_insights = {
        insight.content
        for insight in repo.list_insights(
            scope="project", studio_product_id=product_id, limit=100,
        )
    }
    for item in data.get("insights") or []:
        content = str(item).strip()[:500]
        if not content or content in existing_insights:
            continue
        linked = [
            entity_id
            for name, entity_id in entity_ids.items()
            if len(name) >= 2 and name in content
        ][:10]
        repo.save_memory_insight(
            scope="project",
            studio_product_id=product_id,
            content=content,
            entity_ids=linked,
            source="studio_task_summary",
            source_url=f"studio://product/{product_id}",
        )
        saved_insights += 1

    saved_entities = list(dict.fromkeys(saved_entities))
    _vectorize(repo, saved_entities, product_id)
    promoted = promote_global_studio_memories(repo, product_id)
    result = {
        "product_id": product_id,
        "entities": len(saved_entities),
        "relations": saved_relations,
        "insights": saved_insights,
        "promoted": promoted,
    }
    logger.info("[Studio Memory] 任务记忆已同步 | %s", result)
    return result


def promote_global_studio_memories(repo, product_id: str) -> int:
    """将至少出现在两个任务（Studio 或 research 项目合并计数）的实体提升到全局记忆。"""
    promoted = 0
    for entity in repo.list_studio_entities(product_id):
        # 双通道合并计数：同名实体跨 research 项目 + Studio 任务合计 ≥2
        if repo.count_entity_across_all_tasks(
                entity.name, exclude_product=product_id) < 1:
            continue
        global_entity = repo.find_global_entity(entity.name)
        if global_entity:
            global_id = global_entity.id
            repo.update_entity_merge(
                str(global_id),
                new_summary=entity.summary or global_entity.summary,
                confidence_delta=0.05,
                last_seen=_now(),
            )
        else:
            global_id = repo.save_memory_entity(
                scope="global",
                name=entity.name,
                type=entity.type,
                summary=entity.summary,
                confidence=min(0.9, entity.confidence + 0.1),
                first_seen=_now(),
                last_seen=_now(),
            ).id
        promoted += 1
        for relation in repo.list_relations_for_entity(str(entity.id), active_only=True):
            other_id = (
                relation.target_entity_id
                if str(relation.source_entity_id) == str(entity.id)
                else relation.source_entity_id
            )
            source_id, target_id = (
                (global_id, other_id)
                if str(relation.source_entity_id) == str(entity.id)
                else (other_id, global_id)
            )
            if not repo.find_relation(str(source_id), str(target_id), relation.relation_type):
                repo.save_memory_relation(
                    source_id=str(source_id),
                    target_id=str(target_id),
                    relation_type=relation.relation_type,
                    evidence=relation.evidence,
                    weight=relation.weight,
                    valid_from=relation.valid_from,
                )
    return promoted
