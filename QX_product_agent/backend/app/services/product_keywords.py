"""
====================================================================
Product Keywords —— 产品关键词组服务
====================================================================

职责：
  1. 任务完成后，基于产品资产包（需求/研究/竞品/PRD/设计/演示）的前序
     文本内容，由 LLM 总结「设计 / 功能 / 外观 / 人群 / 场景」五组关键词；
  2. 关键词写入 studio_products.keywords 列，并同步进 asset_package.keywords
     （作为产品资产的组成部分，随详情接口返回）；
  3. 用户可自行编辑关键词组（见 API PUT /api/v1/product/{id}/keywords）；
     一旦存在用户/自动生成的关键词，流水线不会重复覆盖。

存储格式（JSON）：
  {"design": ["极简", ...], "function": [...], "appearance": [...],
   "audience": [...], "scenario": [...]}
====================================================================
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

# 固定分组：key → 中文标签（LLM 提示与前端编辑共用同一契约）
KEYWORD_GROUPS: dict[str, str] = {
    "design": "设计",
    "function": "功能",
    "appearance": "外观",
    "audience": "人群",
    "scenario": "场景",
}

# 参与关键词总结的资产（按重要性排序；缺失时跳过）
_KEY_ASSETS = (
    "requirement",
    "research",
    "competitor_matrix",
    "competitor_analysis",
    "strategy",
    "design",
    "presentation",
)

_MAX_TEXT_CHARS = 8000
_MAX_KEYWORDS_PER_GROUP = 8
_MAX_KEYWORD_LEN = 30

_SYSTEM_PROMPT = """你是一名资深产品经理与品牌策略专家。请阅读下面给出的产品资产内容，\
总结出该产品在不同方面的关键词组，用于资产库索引与后续产品开发复用。

必须输出且只输出一个 JSON 对象，格式如下：
{
  "design": ["设计理念/交互/信息架构关键词", ...],
  "function": ["核心功能关键词", ...],
  "appearance": ["外观/视觉风格/材质关键词", ...],
  "audience": ["目标人群关键词", ...],
  "scenario": ["使用场景关键词", ...]
}

要求：
- 每个方面 3-6 个关键词，不足的方面可以少于 3 个，但不要编造内容中没有的信息；
- 每个关键词 2-12 个字，简洁、具体、可检索，中文为主，允许必要的英文术语；
- 关键词应能代表该产品的差异化特征，避免空泛词（如"好用""创新"）；
- 如果某方面在内容中完全没有信息，该组输出空数组。"""


def _extract_package_text(package: dict | None) -> str:
    """把资产包中参与总结的资产序列化为紧凑文本（截断到上限）。"""
    package = package or {}
    parts: list[str] = []
    for key in _KEY_ASSETS:
        data = package.get(key)
        if not data:
            continue
        try:
            text = json.dumps(data, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            text = str(data)
        parts.append(f"### {key}\n{text}")
    text = "\n\n".join(parts).strip()
    if len(text) > _MAX_TEXT_CHARS:
        text = text[:_MAX_TEXT_CHARS] + "\n…（内容过长已截断）"
    return text or "（资产包无文本内容）"


def _normalize_keywords(raw: object) -> dict[str, list[str]]:
    """把模型输出规范化为固定五组的关键词字典（容错：缺组补空、去重、限长）。"""
    groups: dict[str, list[str]] = {key: [] for key in KEYWORD_GROUPS}
    if not isinstance(raw, dict):
        return groups
    for key, values in raw.items():
        if key not in groups or not isinstance(values, list):
            continue
        seen: set[str] = set()
        cleaned: list[str] = []
        for item in values:
            if not isinstance(item, str):
                continue
            word = item.strip().strip('"\'，。、')
            if not word or word in seen:
                continue
            if len(word) > _MAX_KEYWORD_LEN:
                continue
            seen.add(word)
            cleaned.append(word)
            if len(cleaned) >= _MAX_KEYWORDS_PER_GROUP:
                break
        groups[key] = cleaned
    return groups


def generate_keywords(package: dict | None, llm) -> dict[str, list[str]]:
    """调用 LLM 从资产包文本总结五组关键词（失败时返回全空组，不抛出）。"""
    text = _extract_package_text(package)
    try:
        raw = llm.complete_json(
            [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"产品资产内容：\n{text}"},
            ],
            temperature=0.3,
            max_tokens=1024,
        )
        return _normalize_keywords(raw)
    except Exception as exc:  # noqa: BLE001 —— 关键词生成失败不影响流水线主流程
        logger.warning("[Product Keywords] LLM 总结失败，返回空组: %s", exc)
        return {key: [] for key in KEYWORD_GROUPS}


def _save_keywords(product_id: str, groups: dict[str, list[str]]) -> None:
    """同步写库：keywords 列 + asset_package.keywords（资产组成部分）。"""
    from sqlalchemy.orm import Session

    from app.core.celery_db import get_sync_engine
    from app.models.studio_product import StudioProduct
    from app.tasks.product_studio_tasks import _parse_product_id

    payload = json.dumps(groups, ensure_ascii=False)
    with Session(get_sync_engine()) as session:
        product = session.get(StudioProduct, _parse_product_id(product_id))
        if product is None:
            logger.warning("[Product Keywords] 产品不存在，跳过保存: %s", product_id)
            return
        product.keywords = payload
        if product.asset_package:
            try:
                package = json.loads(product.asset_package)
            except json.JSONDecodeError:
                package = {}
            package["keywords"] = groups
            product.asset_package = json.dumps(package, ensure_ascii=False, default=str)
        session.commit()


def generate_and_save_keywords(
    product_id: str, package: dict | None, llm
) -> dict[str, list[str]]:
    """生成并保存关键词组（流水线完成后调用）。

    幂等保护：若该产品已有关键词（AI 生成或用户编辑），跳过生成，避免覆盖用户修改。
    """
    from sqlalchemy.orm import Session

    from app.core.celery_db import get_sync_engine
    from app.models.studio_product import StudioProduct
    from app.tasks.product_studio_tasks import _parse_product_id

    with Session(get_sync_engine()) as session:
        product = session.get(StudioProduct, _parse_product_id(product_id))
        if product is not None and product.keywords:
            try:
                existing = json.loads(product.keywords)
                if isinstance(existing, dict) and existing:
                    logger.info(
                        "[Product Keywords] 已存在关键词，跳过生成 | product=%s", product_id
                    )
                    return {k: list(v) for k, v in existing.items() if isinstance(v, list)}
            except json.JSONDecodeError:
                pass  # 损坏的旧数据 → 重新生成

    groups = generate_keywords(package, llm)
    _save_keywords(product_id, groups)
    logger.info(
        "[Product Keywords] 生成完成 | product=%s | 组数=%d 关键词数=%d",
        product_id,
        len(groups),
        sum(len(v) for v in groups.values()),
    )
    return groups
