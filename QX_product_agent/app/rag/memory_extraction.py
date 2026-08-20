"""
============================================================
记忆图服务（P4a/P4c）
—— 任务沉淀 → 实体/关系/洞察抽取 → 合并 → 全局提升 → 邻域检索
============================================================

设计借鉴（详见 docs/memory-graph-upgrade-plan.md §2.3）：
  Graphiti      → 实体合并/冲突时间窗（简化版）
  LightRAG      → 双层检索：实体邻域（low-level）+ 洞察（high-level）
  mem0          → scope 分层（global / project）
  nano-graphrag → SQLite 存图（零新增基础设施）

核心函数：
  extract_memory_from_project()  任务完成后沉淀记忆（Celery 调用）
  retrieve_memory_context()      GraphRAG 式邻域检索 → prompt 注入文本
  get_memory_graph()             关系图数据（可视化 API）
  promote_global_memories()      项目记忆 → 全局记忆提升
  decay_memories()               置信度衰减（生命周期）
  delete_project_memories()      项目删除级联清理
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

# 实体类型白名单（与前端图标映射一致）
ENTITY_TYPES = ("company", "product", "technology", "person", "market", "metric", "other")

# 实体合并向量相似度阈值
MERGE_EMBED_THRESHOLD = 0.92
# 全局提升：同名词实体出现在 ≥ 此数量项目时提升
PROMOTE_MIN_PROJECTS = 2
# 记忆向量库 scope 键
MEMORY_VECTOR_SCOPE = "memory"
# 衰减：超过 N 天未引用，confidence -0.05
DECAY_AFTER_DAYS = 30
DECAY_STEP = 0.05
CONFIDENCE_FLOOR = 0.3

_EXTRACT_PROMPT = (
    "你是知识沉淀引擎。请从下面的产品研究项目成果中抽取结构化记忆，严格输出 JSON（不要 Markdown 代码块、不要解释）：\n"
    '{\n'
    '  "entities": [{"name": "实体主名（中文，去除冗余修饰）", '
    '"type": "company|product|technology|person|market|metric|other", '
    '"summary": "≤80字摘要"}],\n'
    '  "relations": [{"source": "实体主名", "relation": "关系（如 竞争/供应商/用于/收购/推出/合作/属于/相关，2-6字）", "target": "实体主名"}],\n'
    '  "insights": ["结论级洞察（≤120字，含数据口径，可跨任务复用）"]\n'
    '}\n'
    "要求：实体 5-15 个，只抽取项目中最重要的事实；关系 5-15 条，必须两端都存在于 entities；"
    "洞察 2-5 条，是有复用价值的结论而非流水账。\n\n项目成果：\n{corpus}"
)


def _get_repo():
    from app.repositories import ProjectRepo
    return ProjectRepo()


def _get_chat_llm(settings):
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL,
        model=settings.DEEPSEEK_MODEL,
        temperature=0.1,
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_name(name: str) -> str:
    """实体名归一化：去首尾空白/全角空格、统一大小写、折叠内部空白。"""
    n = (name or "").strip()
    n = n.replace("\u3000", " ").replace("\xa0", " ")
    n = re.sub(r"\s+", " ", n)
    return n


def _embed_text(text: str) -> list[float] | None:
    try:
        from app.rag.retriever import embedding_model
        return embedding_model.embed_query(text)
    except Exception as e:  # noqa: BLE001
        logger.warning("记忆向量计算失败（降级）: %s", e)
        return None


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
# 1. 主入口：任务完成 → 记忆沉淀
# ══════════════════════════════════════════════════════════════

def extract_memory_from_project(project_id: str) -> dict[str, Any] | None:
    """
    任务完成后沉淀记忆图（项目级），并执行全局提升。

    任一步骤失败都不抛出（记忆沉淀是增强而非阻断），返回 None。
    """
    from app.core.config import get_settings
    settings = get_settings()
    repo = _get_repo()

    is_studio = project_id.startswith("studio:")
    raw_pid = project_id[len("studio:"):] if is_studio else project_id

    if is_studio:
        # ── Studio 产品：语料来自资产包 ─────────────────────
        product = repo.get_studio_product(raw_pid)
        if product is None:
            logger.info("[记忆图] Studio 产品不存在，跳过 | product=%s", raw_pid)
            return None
        status_value = getattr(product, "status", None)
        if status_value is not None and getattr(status_value, "value", str(status_value)) != "completed":
            logger.info("[记忆图] Studio 产品未完成，跳过 | product=%s", raw_pid)
            return None
        corpus = _assemble_studio_corpus(product)
    else:
        try:
            project = repo.get_project(project_id)
        except Exception as e:  # noqa: BLE001
            logger.warning("[记忆图] 项目读取失败: %s", e)
            return None
        status_value = getattr(project, "status", None)
        if status_value is not None and getattr(status_value, "value", str(status_value)) != "completed":
            logger.info("[记忆图] 项目未完成，跳过 | project=%s", project_id)
            return None
        corpus = _assemble_project_corpus(repo, project_id)

    if not corpus.strip():
        logger.info("[记忆图] 无可用语料，跳过 | source=%s", project_id)
        return None

    # ── LLM 结构化抽取 ─────────────────────────────────────
    try:
        llm = _get_chat_llm(settings)
        # Prompt 含有 JSON 示例大括号，不能使用 str.format；只替换语料占位符。
        raw = llm.invoke(_EXTRACT_PROMPT.replace("{corpus}", corpus)).content or ""
        data = _parse_extract_json(raw)
    except Exception as e:  # noqa: BLE001
        logger.warning("[记忆图] LLM 抽取失败: %s", e)
        return None

    entities_in = data.get("entities") or []
    relations_in = data.get("relations") or []
    insights_in = data.get("insights") or []
    if not entities_in:
        logger.info("[记忆图] LLM 未抽取到实体，跳过 | project=%s", project_id)
        return None

    # ── 3. 实体归一化 + 合并入库 ─────────────────────────────
    entity_ids: dict[str, str] = {}  # 归一化名 → entity_id
    saved_entities: list[str] = []
    for item in entities_in:
        name = _normalize_name(item.get("name", ""))
        if not name:
            continue
        etype = item.get("type") or "other"
        if etype not in ENTITY_TYPES:
            etype = "other"
        summary = str(item.get("summary") or "")[:300]
        entity_id = _upsert_entity(repo, raw_pid, name, etype, summary)
        entity_ids[name] = str(entity_id)
        saved_entities.append(str(entity_id))

    # ── 4. 关系入库（带证据 + 时间窗） ───────────────────────
    saved_relations = 0
    for item in relations_in:
        src = _normalize_name(item.get("source", ""))
        tgt = _normalize_name(item.get("target", ""))
        rel = str(item.get("relation") or "相关").strip()[:50]
        if not src or not tgt or src == tgt:
            continue
        # 未在实体列表中的两端：自动补建
        for name in (src, tgt):
            if name not in entity_ids:
                entity_ids[name] = str(_upsert_entity(repo, raw_pid, name, "other", ""))
        if _upsert_relation(repo, entity_ids[src], entity_ids[tgt], rel, raw_pid):
            saved_relations += 1

    # ── 5. 洞察入库 ──────────────────────────────────────────
    saved_insights = 0
    for insight in insights_in:
        text = str(insight).strip()[:500]
        if not text:
            continue
        linked = [
            eid for eid in entity_ids.values()
            if any(kw in text for kw in entity_ids if kw and len(kw) >= 2)
        ][:10]
        repo.save_memory_insight(
            scope="project", project_id=raw_pid, content=text,
            entity_ids=linked, source="task_summary",
            source_url=f"{'studio' if is_studio else 'project'}://{raw_pid}",
        )
        saved_insights += 1

    # ── 6. 记忆向量化（scope=memory 独立向量库） ─────────────
    _vectorize_entities(repo, saved_entities, raw_pid)

    # ── 7. 全局提升 ──────────────────────────────────────────
    promoted = promote_global_memories(raw_pid)

    logger.info(
        "[记忆图] 沉淀完成 | project=%s | entities=%d | relations=%d | insights=%d | promoted=%d",
        project_id, len(saved_entities), saved_relations, saved_insights, promoted,
    )
    return {
        "project_id": project_id,
        "entities": len(saved_entities),
        "relations": saved_relations,
        "insights": saved_insights,
        "promoted": promoted,
    }


def _parse_extract_json(raw: str) -> dict[str, Any]:
    """解析 LLM 抽取输出（容忍围栏/前后缀/推理块）。"""
    text = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        text = text[start:end + 1]
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("抽取结果非对象")
    return data


def _upsert_entity(repo, project_id: str, name: str, etype: str, summary: str) -> uuid.UUID:
    """
    实体合并入库：
      1) 同 scope 同名（归一化）→ 更新 aliases/summary/confidence/last_seen
      2) 同 scope 向量相似 > 0.92 → 合并（aliases 追加）
      3) 否则新建（confidence=0.6）
    """
    now = _now()
    existing = repo.find_project_entity(project_id, name)
    if existing:
        repo.update_entity_merge(
            str(existing.id),
            new_alias=name,
            new_summary=summary or existing.summary,
            confidence_delta=0.1,
            last_seen=now,
        )
        return existing.id

    # 向量相似合并（候选：同 scope 全部实体，量级小直接遍历）
    emb = _embed_text(name)
    if emb:
        for cand in repo.list_project_entities(project_id):
            if not cand.embedding:
                continue
            try:
                cand_emb = json.loads(cand.embedding)
            except (json.JSONDecodeError, TypeError):
                continue
            if _cosine(emb, cand_emb) > MERGE_EMBED_THRESHOLD:
                repo.update_entity_merge(
                    str(cand.id),
                    new_alias=name,
                    new_summary=summary or cand.summary,
                    confidence_delta=0.1,
                    last_seen=now,
                )
                return cand.id

    entity = repo.save_memory_entity(
        scope="project", project_id=project_id, type=etype,
        name=name, summary=summary,
        confidence=0.6, first_seen=now, last_seen=now,
    )
    return entity.id


def _upsert_relation(
    repo,
    source_id: str,
    target_id: str,
    relation_type: str,
    project_id: str,
) -> bool:
    """
    关系入库：
      - 同向同类型存在 → weight += 0.5（上限 3.0），evidence 追加去重
      - 反向同类型存在 → 旧边 valid_to=now（时间窗冲突，Graphiti 思想）
      - 否则新建（weight=1.0, evidence=[{project_id, section}]）
    """
    now = _now()
    existing = repo.find_relation(source_id, target_id, relation_type, active_only=True)
    if existing:
        evidence = json.loads(existing.evidence) if existing.evidence else []
        if project_id not in [e.get("project_id") for e in evidence]:
            evidence.append({"project_id": project_id, "at": now.isoformat()})
        repo.update_relation_weight(
            str(existing.id),
            weight=min(3.0, (existing.weight or 1.0) + 0.5),
            evidence=json.dumps(evidence, ensure_ascii=False),
        )
        return True

    # 反向冲突检测：同类型、方向相反、仍有效 → 旧边过期
    reverse = repo.find_relation(target_id, source_id, relation_type, active_only=True)
    if reverse:
        repo.expire_relation(str(reverse.id), valid_to=now)

    repo.save_memory_relation(
        source_id=source_id, target_id=target_id, relation_type=relation_type,
        evidence=json.dumps([{"project_id": project_id, "at": now.isoformat()}], ensure_ascii=False),
        weight=1.0, valid_from=now,
    )
    return True


def _vectorize_entities(repo, entity_ids: list[str], project_id: str) -> None:
    """实体 name+summary 与洞察写入 scope=memory 向量库（供检索）。"""
    try:
        from app.rag.vector_store import build_vector_store
        chunks: list[dict] = []
        for eid in entity_ids:
            entity = repo.get_entity(eid)
            if not entity:
                continue
            text = f"{entity.name}：{entity.summary or ''}".strip("：")
            if len(text) >= 4:
                chunks.append({"content": text, "url": f"memory://entity/{eid}"})
        for insight in repo.list_insights(scope="project", project_id=project_id, limit=10):
            chunks.append({"content": insight.content, "url": f"memory://insight/{insight.id}"})
        if chunks:
            build_vector_store(chunks, scope=MEMORY_VECTOR_SCOPE)
    except Exception as e:  # noqa: BLE001
        logger.warning("[记忆图] 记忆向量化失败（不影响入库）: %s", e)


# ══════════════════════════════════════════════════════════════
# 2. 全局提升（项目记忆 → 全局记忆）
# ══════════════════════════════════════════════════════════════

def promote_entity_to_global(entity_id: str) -> dict:
    """手动把单个项目实体提升为全局（图谱侧栏「提升到全局记忆」入口）。

    逻辑与 promote_global_memories 的单实体分支一致：创建/合并 global
    实体并复制其关系；幂等（已存在 global 同名实体时合并）。
    """
    repo = _get_repo()
    try:
        entity = repo.get_entity(entity_id)
    except Exception:  # noqa: BLE001
        entity = None
    if entity is None:
        return {"promoted": False, "reason": "实体不存在"}
    if entity.scope == "global":
        return {"promoted": False, "reason": "已是全局实体"}
    now = _now()
    global_entity = repo.find_global_entity(entity.name)
    created_new = global_entity is None
    if global_entity:
        repo.update_entity_merge(
            str(global_entity.id),
            new_alias=entity.name,
            new_summary=entity.summary or global_entity.summary,
            confidence_delta=0.05,
            last_seen=now,
        )
        gid = global_entity.id
    else:
        gid = repo.save_memory_entity(
            scope="global", project_id=None, type=entity.type,
            name=entity.name, summary=entity.summary,
            confidence=min(0.9, entity.confidence + 0.1),
            first_seen=now, last_seen=now,
        ).id
    copied = 0
    for rel in repo.list_relations_for_entity(str(entity.id)):
        other_id = rel.target_entity_id if str(rel.source_entity_id) == str(entity.id) \
            else rel.source_entity_id
        if str(other_id) == str(entity.id):
            continue
        src, tgt = (gid, other_id) if str(rel.source_entity_id) == str(entity.id) \
            else (other_id, gid)
        if not repo.find_relation(str(src), str(tgt), rel.relation_type, active_only=True):
            repo.save_memory_relation(
                source_id=str(src), target_id=str(tgt),
                relation_type=rel.relation_type,
                evidence=rel.evidence, weight=rel.weight,
                valid_from=rel.valid_from,
            )
            copied += 1
    if not created_new and copied == 0:
        # 幂等：全局已存在同名实体且无新增关系 → 非提升
        return {"promoted": False, "reason": "全局已存在同名实体且无新增关系",
                "global_entity_id": str(gid)}
    return {"promoted": True, "global_entity_id": str(gid), "relations_copied": copied}


def promote_global_memories(project_id: str) -> int:
    """
    将跨项目复现的实体/洞察提升为全局记忆：
      - 实体：同名词出现在 ≥ PROMOTE_MIN_PROJECTS 个不同项目 → 创建/更新 global 实体，
        并把该项目的关系复制一份连到 global 实体
      - 洞察：confidence ≥ 0.7 且引用全局实体 → 复制为 global
    返回提升数量。
    """
    repo = _get_repo()
    promoted = 0
    try:
        project_entities = repo.list_project_entities(project_id)
        for entity in project_entities:
            name = entity.name
            # 跨任务复现计数（双通道合并：research 项目 + Studio 任务）
            similar = repo.count_entity_across_all_tasks(
                name, exclude_project=project_id)
            if similar + 1 < PROMOTE_MIN_PROJECTS:
                continue
            global_entity = repo.find_global_entity(name)
            now = _now()
            if global_entity:
                repo.update_entity_merge(
                    str(global_entity.id),
                    new_alias=name,
                    new_summary=entity.summary or global_entity.summary,
                    confidence_delta=0.05,
                    last_seen=now,
                )
                gid = global_entity.id
            else:
                g = repo.save_memory_entity(
                    scope="global", project_id=None, type=entity.type,
                    name=name, summary=entity.summary,
                    confidence=min(0.9, entity.confidence + 0.1),
                    first_seen=now, last_seen=now,
                )
                gid = g.id
            # 复制该项目中与此实体相连的关系到全局实体（evidence 溯源）
            for rel in repo.list_relations_for_entity(str(entity.id)):
                other_id = rel.target_entity_id if str(rel.source_entity_id) == str(entity.id) else rel.source_entity_id
                if str(other_id) == str(entity.id):
                    continue
                src, tgt = (gid, other_id) if str(rel.source_entity_id) == str(entity.id) else (other_id, gid)
                existing = repo.find_relation(str(src), str(tgt), rel.relation_type, active_only=True)
                if not existing:
                    repo.save_memory_relation(
                        source_id=str(src), target_id=str(tgt),
                        relation_type=rel.relation_type,
                        evidence=rel.evidence, weight=rel.weight,
                        valid_from=rel.valid_from,
                    )
            promoted += 1

        # 洞察提升：引用实体中含全局实体的高置信洞察
        global_ids = {str(e.id) for e in repo.list_global_entities()}
        for insight in repo.list_insights(scope="project", project_id=project_id, limit=20):
            linked = json.loads(insight.entity_ids) if insight.entity_ids else []
            if insight.confidence >= 0.7 and any(eid in global_ids for eid in linked):
                exists = repo.find_global_insight_by_content(insight.content)
                if not exists:
                    repo.save_memory_insight(
                        scope="global", project_id=None, content=insight.content,
                        entity_ids=linked, source="task_summary",
                        source_url=insight.source_url, confidence=insight.confidence,
                    )
                    promoted += 1
    except Exception as e:  # noqa: BLE001
        logger.warning("[记忆图] 全局提升失败: %s", e)
    return promoted


# ══════════════════════════════════════════════════════════════
# 3. 邻域检索（GraphRAG low-level + high-level）
# ══════════════════════════════════════════════════════════════

def retrieve_memory_context(query: str, project_id: str | None = None, k: int = 8) -> str:
    """
    GraphRAG 式记忆检索：
      ① 向量命中实体/洞察（scope=memory 向量库）
      ② 实体 1 跳邻域展开（SQL）
      ③ 关联洞察召回
    组装为可注入 prompt 的文本；无命中返回空串。
    """
    repo = _get_repo()
    parts: list[str] = []

    # ── ① 向量命中 ──────────────────────────────────────────
    hit_entity_ids: list[str] = []
    hit_insight_ids: list[str] = []
    try:
        from app.rag.retriever import retrieve
        docs = retrieve(query, k=k, scope=MEMORY_VECTOR_SCOPE)
        for doc in docs:
            url = doc.metadata.get("url", "")
            if url.startswith("memory://entity/"):
                hit_entity_ids.append(url.rsplit("/", 1)[-1])
            elif url.startswith("memory://insight/"):
                hit_insight_ids.append(url.rsplit("/", 1)[-1])
    except Exception as e:  # noqa: BLE001
        logger.debug("记忆向量检索失败: %s", e)

    # 向量未命中时：关键词兜底（项目实体名 LIKE）
    if not hit_entity_ids:
        try:
            for ent in repo.search_entities_by_keyword(query, scope="project", project_id=project_id, limit=3):
                hit_entity_ids.append(str(ent.id))
        except Exception:  # noqa: BLE001
            pass

    # ── ② 邻域展开（1 跳） ──────────────────────────────────
    seen_entities: dict[str, Any] = {}
    for eid in hit_entity_ids[:4]:
        entity = repo.get_entity(eid)
        if not entity:
            continue
        seen_entities[eid] = entity
        for rel in repo.list_relations_for_entity(eid, active_only=True, limit=8):
            other_id = str(rel.target_entity_id) if str(rel.source_entity_id) == eid else str(rel.source_entity_id)
            other = repo.get_entity(other_id)
            if not other:
                continue
            if other_id not in seen_entities:
                seen_entities[other_id] = other
            parts.append(
                f"{entity.name} —[{rel.relation_type}]→ {other.name}"
                f"（证据: {_evidence_snippet(rel.evidence)}）"
            )

    for eid, entity in list(seen_entities.items())[:8]:
        parts.append(f"{entity.name}（{entity.type}，{entity.summary or '无摘要'}）")

    # ── ③ 关联洞察 ──────────────────────────────────────────
    if seen_entities:
        for insight in repo.list_insights_by_entity_ids(list(seen_entities.keys()), limit=5):
            parts.append(f"💡 {insight.content}（来源: {insight.source}）")

    if not parts:
        return ""
    unique = list(dict.fromkeys(parts))
    return "【记忆图（跨任务知识）】\n" + "\n".join(unique[:k + 4])


def _evidence_snippet(evidence_json: str | None) -> str:
    if not evidence_json:
        return "项目证据"
    try:
        evidence = json.loads(evidence_json)
        projects = {e.get("project_id", "")[:8] for e in evidence if e.get("project_id")}
        if projects:
            return f"{len(projects)} 个项目"
        return "项目证据"
    except (json.JSONDecodeError, TypeError):
        return "项目证据"


# ══════════════════════════════════════════════════════════════
# 4. 关系图数据（可视化 API）
# ══════════════════════════════════════════════════════════════

def get_memory_graph(
    scope: str = "global",
    project_id: str | None = None,
    studio_product_id: str | None = None,
    q: str | None = None,
    entity_types: list[str] | None = None,
    limit: int = 300,
    min_confidence: float = 0.0,
) -> dict[str, Any]:
    """
    构建关系图数据（节点 + 边 + 元信息）。

    q 命中时：返回命中实体及其 2 跳邻域（focused 标记），其余节点 muted。
    limit 超限时：按 degree 取 top-N，meta.truncated=true。
    """
    repo = _get_repo()

    if scope == "project" and not project_id and not studio_product_id:
        # 项目视图未指定任务 → 返回空图（不回落 global：
        # 回落会造成项目视图闪现全局旧数据，前端切换体验实测受损）
        return {
            "nodes": [], "edges": [], "query": q,
            "meta": {"entity_count": 0, "relation_count": 0,
                     "projects_covered": 0, "studio_products_covered": 0,
                     "truncated": False},
        }
    entities = repo.list_memory_entities(
        scope=scope, project_id=project_id, studio_product_id=studio_product_id, q=q,
        entity_types=entity_types, min_confidence=min_confidence,
    )

    # 全局图：纳入与全局实体直接相连的项目实体（跨项目聚合可视化）
    extra_entities: list[Any] = []
    if scope == "global" and entities:
        base_ids = {str(e.id) for e in entities}
        related_ids: set[str] = set()
        for eid in base_ids:
            for rel in repo.list_relations_for_entity(eid, active_only=True, limit=50):
                related_ids.add(str(rel.source_entity_id))
                related_ids.add(str(rel.target_entity_id))
        related_ids -= base_ids
        if related_ids:
            extra_entities = repo.get_entities_by_ids(list(related_ids))
    entities = entities + extra_entities

    # 邻域展开（q 模式：2 跳）
    focused_ids: set[str] = set()
    if q and scope == "global":
        query_ids = {str(e.id) for e in entities}
        hop1: set[str] = set()
        for eid in query_ids:
            for rel in repo.list_relations_for_entity(eid, active_only=True, limit=20):
                hop1.add(str(rel.source_entity_id))
                hop1.add(str(rel.target_entity_id))
        focused_ids = query_ids | hop1
        # 2 跳
        hop2: set[str] = set()
        for eid in hop1:
            for rel in repo.list_relations_for_entity(eid, active_only=True, limit=20):
                hop2.add(str(rel.source_entity_id))
                hop2.add(str(rel.target_entity_id))
        focused_ids |= hop2

    # 边（限定在实体集合内）
    entity_ids = {str(e.id) for e in entities}
    all_relations = repo.list_relations_between(entity_ids, active_only=True, limit=3000)
    edge_map: dict[tuple[str, str, str], dict] = {}
    for rel in all_relations:
        key = (str(rel.source_entity_id), str(rel.target_entity_id), rel.relation_type)
        if key in edge_map:
            edge_map[key]["weight"] = min(3.0, edge_map[key]["weight"] + rel.weight)
        else:
            edge_map[key] = {
                "source": str(rel.source_entity_id),
                "target": str(rel.target_entity_id),
                "relation": rel.relation_type,
                "weight": rel.weight,
                "expired": bool(rel.valid_to),
            }

    # 度数统计 + 截断
    degree: dict[str, int] = {}
    for edge in edge_map.values():
        degree[edge["source"]] = degree.get(edge["source"], 0) + 1
        degree[edge["target"]] = degree.get(edge["target"], 0) + 1

    truncated = len(entities) > limit
    ordered = sorted(entities, key=lambda e: degree.get(str(e.id), 0), reverse=True)
    kept = ordered[:limit]
    kept_ids = {str(e.id) for e in kept}
    edges = [e for e in edge_map.values() if e["source"] in kept_ids and e["target"] in kept_ids]

    nodes = [
        {
            "id": str(e.id),
            "name": e.name,
            "type": e.type,
            "summary": e.summary or "",
            "scope": e.scope,
            "project_id": str(e.project_id) if e.project_id else None,
            "studio_product_id": str(e.studio_product_id) if e.studio_product_id else None,
            "confidence": round(e.confidence or 0.6, 2),
            "degree": degree.get(str(e.id), 0),
            "focused": str(e.id) in focused_ids,
            "last_seen_at": e.last_seen_at.isoformat() if e.last_seen_at else None,
            "aliases": json.loads(e.aliases) if e.aliases else [],
        }
        for e in kept
    ]

    return {
        "scope": scope,
        "project_id": project_id,
        "studio_product_id": studio_product_id,
        "query": q or "",
        "nodes": nodes,
        "edges": edges,
        "meta": {
            "entity_count": len(entities),
            "relation_count": len(edges),
            "truncated": truncated,
            "limit": limit,
            "projects_covered": len({e.project_id for e in entities if e.project_id}),
            "studio_products_covered": len({
                e.studio_product_id for e in entities if e.studio_product_id
            }),
        },
    }


# ══════════════════════════════════════════════════════════════
# 5. 生命周期：衰减 / 清理
# ══════════════════════════════════════════════════════════════

def decay_memories(days: int = DECAY_AFTER_DAYS, step: float = DECAY_STEP) -> int:
    """长期未引用的项目实体置信度衰减（下限 CONFIDENCE_FLOOR）。返回衰减数量。"""
    repo = _get_repo()
    cutoff = _now() - timedelta(days=days)
    count = repo.decay_stale_entities(cutoff=cutoff, step=step, floor=CONFIDENCE_FLOOR)
    if count:
        logger.info("[记忆图] 置信度衰减 | %d 个实体", count)
    return count


def delete_project_memories(project_id: str) -> None:
    """
    项目删除级联清理记忆：
      - scope=project 且归属该项目的实体（连带关系/洞察）
      - scope=global 中 source 为该项目的洞察
    全局实体保留（跨项目资产）。
    """
    repo = _get_repo()
    entity_ids = [str(e.id) for e in repo.list_project_entities(project_id)]
    if entity_ids:
        repo.delete_entities_with_relations(entity_ids)
    repo.delete_insights_by_project(project_id, scope="global")
    logger.info("[记忆图] 项目记忆已清理 | project=%s | entities=%d", project_id, len(entity_ids))


def delete_entity_cascade(entity_id: str) -> bool:
    """删除单个实体及其全部关系（用户纠错）。"""
    repo = _get_repo()
    entity = repo.get_entity(entity_id)
    if entity is None:
        return False
    repo.delete_entities_with_relations([entity_id])
    return True


def _assemble_project_corpus(repo, project_id: str) -> str:
    """传统研究报告项目语料：章节 + 经验包 + 图片分析。"""
    blocks = repo.list_document_blocks(project_id, limit=12)
    corpus_parts = [f"## {b.section_title}\n{(b.content or '')[:1500]}" for b in blocks]
    experiences = repo.list_domain_experiences(project_id, limit=2)
    for exp in experiences:
        corpus_parts.append(f"## 经验包\n{exp.summary[:800]}")
    images = repo.list_kb_images(project_id, limit=5)
    for img in images:
        if img.analysis_text:
            try:
                analysis = json.loads(img.analysis_text)
                corpus_parts.append(f"## 图片分析\n{analysis.get('summary', '')}")
            except (json.JSONDecodeError, AttributeError):
                pass
    return "\n\n".join(corpus_parts)[:20000]


def _assemble_studio_corpus(product) -> str:
    """Studio 产品语料：idea + 关键词 + 资产包文本（递归提取字符串值）。"""
    parts = [f"## 产品想法\n{product.idea or ''}"]
    if getattr(product, "keywords", None):
        parts.append(f"## 关键词\n{product.keywords}")
    if getattr(product, "asset_package", None):
        try:
            package = json.loads(product.asset_package)
            text_chunks: list[str] = []

            def walk(node, depth=0):
                if depth > 6:
                    return
                if isinstance(node, dict):
                    for k, v in node.items():
                        if isinstance(v, str) and len(v) > 20:
                            text_chunks.append(f"[{k}] {v[:600]}")
                        elif isinstance(v, (dict, list)):
                            walk(v, depth + 1)
                elif isinstance(node, list):
                    for item in node[:10]:
                        walk(item, depth + 1)

            walk(package)
            parts.append("## 资产包\n" + "\n".join(text_chunks[:60]))
        except (json.JSONDecodeError, TypeError):
            parts.append("## 资产包\n" + str(product.asset_package)[:8000])
    return "\n\n".join(parts)[:20000]
