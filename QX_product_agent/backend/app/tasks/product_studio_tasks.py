"""
============================================================
Product Studio 流水线任务
—— 桥接 QX 后端与 agent-platform（LangGraph 多 Agent 工作流）
============================================================

职责（对应迁移策略 Phase 1/2）:
  1. 把 QX Settings 的模型配置桥接为平台层环境变量（AGENT_PLATFORM_*）
  2. 把 agent-platform / agents 目录加入 sys.path（平台层独立于业务代码）
  3. 构建四个专业 Agent + LangGraph 工作流并执行
  4. 资产包（结构化 JSON）持久化到 studio_products 表
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from celery import Task
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import update

from app.core.celery_app import celery_app
from app.core.celery_db import get_sync_engine
from app.core.config import get_settings
from app.models.studio_product import StudioProduct, StudioProductStatus

logger = logging.getLogger(__name__)

# 项目根: backend/app/tasks/xxx.py → parents[3] = QX_product_agent
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_WORKSPACE_ROOT = _PROJECT_ROOT.parent  # ~/dev/agents


class ProductStudioTask(Task):
    """惰性加载 Settings 单例（与 WritingTask 同一模式）。"""

    _settings = None

    @property
    def settings(self):
        if self._settings is None:
            self._settings = get_settings()
        return self._settings


def _bridge_env_file_keys(keys: tuple[str, ...]) -> None:
    """从 backend/.env 补读未导出的键到 os.environ（setdefault 不覆盖现有）。"""
    from pathlib import Path as _Path

    env_file = _Path(__file__).resolve().parents[2] / ".env"
    if not env_file.is_file():
        return
    wanted = set(keys)
    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            if k in wanted and v.strip():
                os.environ.setdefault(k, v.strip())
    except OSError:
        pass


def _bridge_env(settings) -> None:
    """把 QX 配置桥接为平台层环境变量（平台层只读自己的环境变量）。"""
    os.environ.setdefault("AGENT_PLATFORM_LLM_API_KEY", settings.DEEPSEEK_API_KEY)
    os.environ.setdefault("AGENT_PLATFORM_LLM_BASE_URL", settings.DEEPSEEK_BASE_URL)
    os.environ.setdefault("AGENT_PLATFORM_LLM_MODEL", settings.DEEPSEEK_MODEL)
    # MOD（amazon_matrix_mod.llm_interpret）直读 DEEPSEEK_* 环境变量
    if settings.DEEPSEEK_API_KEY:
        os.environ.setdefault("DEEPSEEK_API_KEY", settings.DEEPSEEK_API_KEY)
        os.environ.setdefault("DEEPSEEK_BASE_URL", settings.DEEPSEEK_BASE_URL)
        os.environ.setdefault("DEEPSEEK_MODEL", settings.DEEPSEEK_MODEL)
    # MOD 的 M3/生图读 AGENT_PLATFORM_PRESENTATION_*（QX .env 未导出为环境变量，
    # pydantic Settings 也不声明这些键 → 从 .env 文件补读注入）
    _bridge_env_file_keys(("AGENT_PLATFORM_PRESENTATION_LLM_API_KEY",
                           "AGENT_PLATFORM_PRESENTATION_LLM_BASE_URL",
                           "AGENT_PLATFORM_PRESENTATION_LLM_MODEL",
                           "AGENT_PLATFORM_PRESENTATION_LLM_EXTRA_JSON"))
    if settings.TAVILY_API_KEY:
        os.environ.setdefault("AGENT_PLATFORM_TAVILY_API_KEY", settings.TAVILY_API_KEY)
    # 记忆目录放在业务输出目录下，随项目输出一起管理
    os.environ.setdefault(
        "AGENT_PLATFORM_MEMORY_DIR",
        str(Path(settings.OUTPUT_DIR) / "private" / "studio_memory"),
    )
    # MOD（amazon_matrix_mod）产物统一落 QX OUTPUT_DIR（按任务 ID 组织），
    # 避免落到工作区根 outputs/ 造成产出目录分裂
    os.environ.setdefault("QX_OUTPUT_DIR", str(Path(settings.OUTPUT_DIR).resolve()))
    # Rainforest key 若 worker 环境存在则透传（.env 中未配置时由部署环境提供）
    if settings.RAINFOREST_API_KEY:
        os.environ.setdefault("RAINFOREST_API_KEY", settings.RAINFOREST_API_KEY)


def _ensure_paths(settings) -> None:
    """把 agent-platform 与 agents 目录加入 sys.path（可配置覆盖）。

    注意：`import agents` 需要 agents/ 的父目录在 sys.path 上，
    而 `import agent_platform` 需要 agent-platform/ 目录本身。
    """
    platform_dir = Path(
        settings.AGENT_PLATFORM_PATH or (_WORKSPACE_ROOT / "agent-platform")
    ).resolve()
    # AGENTS_PATH 语义：包含 agents 包的父目录（默认工作区根）
    agents_parent = Path(
        settings.AGENTS_PATH or str(_WORKSPACE_ROOT)
    ).resolve()
    for _d in (str(platform_dir), str(agents_parent)):
        if _d not in sys.path:
            sys.path.insert(0, _d)
    logger.info(
        "[Product Studio] platform=%s agents_parent=%s", platform_dir, agents_parent
    )


def _parse_product_id(product_id: str) -> "uuid.UUID":
    """Celery 参数为字符串，SQLAlchemy Uuid 类型要求 uuid.UUID。"""
    import uuid

    return uuid.UUID(str(product_id))


_PROGRESS_SNAPSHOT: dict = {}


def _persist_progress(product_id: str, event: dict) -> None:
    """节点进度事件 → 合并快照 → 写库（幂等，供前端实时展示）。

    状态优先级（防止重试窗口内的瞬时 failed 覆盖较新的运行中/完成态）：
        completed > running > queued > failed
    同一节点只有更高优先级的后续事件才允许覆盖写库；
    failed 只作为「最低优先级的占位」，一旦节点随后 running/completed 即被替换。

    渐进式交付（P4）：事件携带 artifact_key/artifact 时，即时渲染该节点
    文本资产到 studio_assets/{id}/（前端资产面板节点完成即可预览/下载）；
    artifact 本体不写入 progress_log（保持日志轻量）。
    """
    node = event.get("node", "")
    status = event.get("status", "")
    if not node or not status:
        return
    artifact_key = event.get("artifact_key")
    if artifact_key and event.get("artifact") is not None:
        try:
            from app.services.project_assets import ensure_text_assets

            ensure_text_assets(str(product_id), {str(artifact_key): event["artifact"]})
        except Exception as exc:  # noqa: BLE001 —— 渐进交付失败不影响主流程（完成态会补齐）
            logger.warning("[Product Studio] 渐进资产产出失败 %s.%s: %s",
                           product_id, artifact_key, exc)
    # P0.2/P0.3：心跳刷新 + 事件广播（SSE 通道）；失败静默不阻塞主流程
    try:
        from app.services.task_health import heartbeat, publish_event

        heartbeat(str(product_id))
        publish_event(str(product_id), {
            "ts": datetime.now(timezone.utc).isoformat(),
            "node": node, "status": status,
            "detail": str(event.get("detail") or event.get("error") or "")[:160],
        })
    except Exception:  # noqa: BLE001
        pass
    _RANK = {"completed": 3, "running": 2, "queued": 1, "failed": 0}
    prev = _PROGRESS_SNAPSHOT.get(product_id, {}).get(node)
    if prev is not None and _RANK.get(status, 0) < _RANK.get(prev, 0):
        return  # 不允许低优先级覆盖高优先级
    snapshot = dict(_PROGRESS_SNAPSHOT.get(product_id, {}))
    snapshot[node] = status
    _PROGRESS_SNAPSHOT[product_id] = snapshot

    # 事件明细追加到 progress_log（JSON Lines，供前端真实进度展示）
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "node": node,
        "status": status,
        "detail": event.get("detail") or event.get("error") or "",
    }
    try:
        from sqlalchemy.orm import Session

        engine = get_sync_engine()
        with Session(engine) as session:
            product = session.get(StudioProduct, _parse_product_id(product_id))
            if product is not None:
                log = (product.progress_log or "").strip()
                lines = log.splitlines() if log else []
                lines.append(json.dumps(entry, ensure_ascii=False))
                product.progress_log = "\n".join(lines[-500:])  # 上限 500 条防膨胀
                product.node_status = json.dumps(snapshot, ensure_ascii=False)
                product.updated_at = datetime.now(timezone.utc)
                session.commit()
    except Exception as exc:  # noqa: BLE001 —— 进度写库失败不影响主流程
        logger.warning("[Product Studio] 进度写库失败 %s: %s", product_id, exc)


def _update_product(product_id: str, **fields) -> None:
    """同步更新 studio_products 记录（Celery Worker 同步上下文）。"""
    from sqlalchemy.orm import Session

    engine = get_sync_engine()
    with Session(engine) as session:
        product = session.get(StudioProduct, _parse_product_id(product_id))
        if product is None:
            raise RuntimeError(f"产品不存在: {product_id}")
        for key, value in fields.items():
            setattr(product, key, value)
        session.commit()


def _get_product_status(product_id: str) -> StudioProductStatus | None:
    """读取最新状态，避免用户暂停/结束后旧 Worker 覆盖终态。"""
    from sqlalchemy.orm import Session

    with Session(get_sync_engine()) as session:
        product = session.get(StudioProduct, _parse_product_id(product_id))
        return product.status if product is not None else None


def _json_safe(value):
    """递归转换资产包中的非 JSON 类型，保持集合内容而非转成不可读字符串。"""
    if isinstance(value, (set, frozenset)):
        return sorted((_json_safe(item) for item in value), key=lambda item: repr(item))
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _claim_product_run(product_id: str, *, allow_retry: bool) -> tuple[str, str | None]:
    """原子领取一次流水线执行，阻止 Celery 重投递并发跑同一产品。

    只有 queued 能被首次任务领取；failed 仅允许 Celery 已安排的重试领取。
    running/completed 的重复消息直接返回，不再调用任何 Agent 或外部模型。
    """
    from sqlalchemy.orm import Session

    product_uuid = _parse_product_id(product_id)
    with Session(get_sync_engine()) as session:
        product = session.get(StudioProduct, product_uuid)
        if product is None:
            raise RuntimeError(f"产品不存在: {product_id}")
        if product.status == StudioProductStatus.COMPLETED:
            return "completed", None
        if product.status == StudioProductStatus.RUNNING:
            return "running", None
        if product.status == StudioProductStatus.PAUSED:
            return "paused", None

        allowed = [StudioProductStatus.QUEUED, StudioProductStatus.WAITING_APPROVAL]
        if allow_retry:
            allowed.append(StudioProductStatus.FAILED)
        claimed = session.execute(
            update(StudioProduct)
            .where(
                StudioProduct.id == product_uuid,
                StudioProduct.status.in_(allowed),
            )
            .values(status=StudioProductStatus.RUNNING, error_message=None)
        ).rowcount
        if claimed:
            session.commit()
            _PROGRESS_SNAPSHOT.pop(product_id, None)
            return "claimed", product.idea
        session.rollback()
        return "running", None


@celery_app.task(
    bind=True,
    base=ProductStudioTask,
    max_retries=1,
    acks_late=True,
    # 覆盖全局 30/45min 超时：Product Studio 全链路（含 ppt_design 逐页 SVG，
    # 每页可能重试多次）实测可达 60min+。软超时用于记录慢任务，硬超时兜底。
    soft_time_limit=60 * 50,
    time_limit=60 * 70,
)
def run_product_studio_pipeline(self: ProductStudioTask, product_id: str):
    """
    执行 Product Studio 流水线：

    Requirement Parser → Research → Competitor Analysis
      → Product Strategy → UX Design → Presentation → Asset Package

    结果（ProductAssetPackage 结构化 JSON）写入 studio_products.asset_package；
    失败时状态置为 failed 并记录错误（工作流内部节点级失败不阻断整体）。
    """
    retries = getattr(getattr(self, "request", None), "retries", 0)
    action, idea = _claim_product_run(product_id, allow_retry=retries > 0)
    if action == "completed":
        logger.info("[Product Studio] product=%s 已完成，忽略重复投递", product_id)
        return {"product_id": product_id, "status": "completed", "duplicate": True}
    if action == "running":
        logger.info("[Product Studio] product=%s 已在执行，忽略重复投递", product_id)
        return {"product_id": product_id, "status": "running", "duplicate": True}
    if action == "paused":
        logger.info("[Product Studio] product=%s 已暂停，忽略重复投递", product_id)
        return {"product_id": product_id, "status": "paused", "duplicate": True}

    # 运行锁（DB 状态机之外的第二道防线）：同产品重复投递在状态窗口漏防时，
    # 仅持锁任务执行（TTL 900s，心跳续期；终态显式释放）
    from app.services.task_health import acquire_run_lock

    if not acquire_run_lock(str(product_id)):
        logger.warning("[Product Studio] product=%s 运行锁被占用，忽略本次投递", product_id)
        return {"product_id": product_id, "status": "running", "duplicate": True,
                "run_lock": "busy"}

    settings = self.settings
    _bridge_env(settings)
    _ensure_paths(settings)

    try:
        # ── 构建平台层组件（此时才 import，避免模块级副作用） ──────
        from agent_platform.harness.agent_loop import AgentLoop
        from agent_platform.llm.client import LLMClient
        from agent_platform.memory.memory_store import FileMemoryStore
        from agent_platform.workflows.product_research_graph import GatePause, ProductResearchGraph

        from agents.critic_agent.agent import CriticAgent
        from agents.design_agent.agent import DesignAgent
        from agents.ppt_design_agent.agent import PptDesignAgent
        from agents.presentation_agent.agent import PresentationAgent
        from agents.product_agent.agent import ProductAgent
        from agents.research_agent.agent import ResearchAgent

        memory = FileMemoryStore(base_dir=settings.AGENT_PLATFORM_MEMORY_DIR
                                 if settings.AGENT_PLATFORM_MEMORY_DIR
                                 else str(Path(settings.OUTPUT_DIR) / "private" / "studio_memory"))
        loop = AgentLoop(memory=memory)

        # ── C5 Model Router：按节点路由模型（NODE_MODEL_MAP JSON） ──
        # 格式: {"research": "deepseek", "presentation": "minimax", ...}
        # 值可为提供商名（deepseek/minimax/siliconflow）或完整 LLMClient 配置 dict
        def _build_routed_loop(node: str) -> AgentLoop:
            try:
                import json as _json
                mapping = _json.loads(settings.NODE_MODEL_MAP or "{}")
            except Exception:  # noqa: BLE001
                mapping = {}
            spec = mapping.get(node)
            if not spec:
                return loop  # 未配置 → 默认主 LLM
            if isinstance(spec, str):
                provider = spec.lower()
                if provider == "minimax" and settings.MINIMAX_API_KEY:
                    return AgentLoop(
                        memory=memory,
                        llm=LLMClient(
                            api_key=settings.MINIMAX_API_KEY,
                            base_url=settings.MINIMAX_BASE_URL or "https://api.minimax.chat/v1",
                            model=settings.MINIMAX_MODEL or "MiniMax-M3",
                        ),
                    )
                if provider == "siliconflow" and settings.SILICONFLOW_API_KEY:
                    return AgentLoop(
                        memory=memory,
                        llm=LLMClient(
                            api_key=settings.SILICONFLOW_API_KEY,
                            base_url=settings.SILICONFLOW_BASE_URL or "https://api.siliconflow.cn/v1",
                            model=settings.SILICONFLOW_MODEL or settings.SILICONFLOW_IMAGE_MODEL,
                        ),
                    )
                # deepseek / 默认
                return AgentLoop(
                    memory=memory,
                    llm=LLMClient(
                        api_key=settings.DEEPSEEK_API_KEY,
                        base_url=settings.DEEPSEEK_BASE_URL,
                        model=settings.DEEPSEEK_MODEL,
                    ),
                )
            if isinstance(spec, dict):
                return AgentLoop(
                    memory=memory,
                    llm=LLMClient(
                        api_key=spec.get("api_key") or settings.DEEPSEEK_API_KEY,
                        base_url=spec.get("base_url") or settings.DEEPSEEK_BASE_URL,
                        model=spec.get("model") or settings.DEEPSEEK_MODEL,
                    ),
                )
            return loop

        loops = {
            "research": _build_routed_loop("research"),
            "strategy": _build_routed_loop("strategy"),
            "design": _build_routed_loop("design"),
            "presentation": _build_routed_loop("presentation"),
            "critic": _build_routed_loop("critic"),
        }
        node_models = {
            "requirement_parser": loop.llm.model,
            "research": loops["research"].llm.model,
            "competitor_matrix": loops["research"].llm.model,
            "competitor_analysis": loops["research"].llm.model,
            "strategy": loops["strategy"].llm.model,
            "design": loops["design"].llm.model,
            "presentation": loops["presentation"].llm.model,
            "critic": loops["critic"].llm.model,
            "ppt_design": getattr(loops["presentation"].llm, "model", "deterministic"),
        }

        graph = ProductResearchGraph(
            research_agent=ResearchAgent(loop=loops["research"]),
            product_agent=ProductAgent(loop=loops["strategy"]),
            design_agent=DesignAgent(loop=loops["design"]),
            presentation_agent=PresentationAgent(loop=loops["presentation"], memory=memory),
            critic_agent=CriticAgent(llm=loops["critic"].llm),
            ppt_design_agent=PptDesignAgent(
                progress_callback=lambda event: _persist_progress(product_id, event)),
            llm=loop.llm,
            memory=memory,
            node_models=node_models,
            max_retries=settings.AGENT_PLATFORM_MAX_RETRIES
            if settings.AGENT_PLATFORM_MAX_RETRIES >= 0
            else 2,
            score_threshold=settings.PRESENTATION_SCORE_THRESHOLD
            if settings.PRESENTATION_SCORE_THRESHOLD > 0
            else 80,
            max_revisions=settings.PRESENTATION_MAX_REVISIONS
            if settings.PRESENTATION_MAX_REVISIONS > 0
            else 2,
            progress_callback=lambda event: _persist_progress(product_id, event),
        )

        # ── 初始状态：断点恢复（Plan/Act 门批准后续跑）或全新启动 ──
        gate_nodes = [n.strip() for n in (settings.GATE_NODES or "").split(",") if n.strip()]
        # 资料审核：source_gathering 节点默认门控（用户审核资料后再继续）
        if settings.SOURCE_REVIEW and "source_gathering" not in gate_nodes:
            gate_nodes.insert(0, "source_gathering")
        # P0.4 大纲确认门：presentation 页清单批准后再进入 critic+逐页创作
        if settings.OUTLINE_REVIEW and "presentation" not in gate_nodes:
            gate_nodes.append("presentation")
        extra_initial: dict = {"product_id": str(product_id), "_gate_nodes": gate_nodes}
        # MOD 数据源/抓取量覆盖（MOD_SOURCE=mock 供 0-credit 预演/测试；缺省 rainforest）。
        # 仅 QX_ENV=e2e 时生效：E2E worker 与生产任务共用队列时，防止 mock 夹具
        # 污染真实交付（mock 夹具为固定 wireless mouse 数据，与任务品类无关）。
        _e2e = os.environ.get("QX_ENV", "").strip().lower() == "e2e"
        if _e2e:
            if os.environ.get("MOD_SOURCE"):
                extra_initial["source"] = os.environ["MOD_SOURCE"]
            # MOD 抓取量覆盖（缺省 20：search 1 + product 20 ≈ 21 credits）
            if os.environ.get("MOD_TOP_N"):
                try:
                    extra_initial["top_n"] = int(os.environ["MOD_TOP_N"])
                except ValueError:
                    pass
        elif os.environ.get("MOD_SOURCE"):
            logger.warning(
                "[Product Studio] 忽略 MOD_SOURCE=%s（仅 QX_ENV=e2e 时生效，"
                "防止 mock 数据污染生产任务）", os.environ["MOD_SOURCE"])
        # 读取产品记录判断是否从等待批准状态恢复
        from app.core.celery_db import get_sync_engine
        from sqlalchemy.orm import Session
        from app.models.studio_product import StudioProduct as SP
        with Session(get_sync_engine()) as _session:
            _p = _session.get(SP, _parse_product_id(product_id))
            # 模板选择权（前端指定设计主题/风格方法论 → presentation/MOD 消费）
            if getattr(_p, "theme_id", None):
                extra_initial["ppt_theme"] = _p.theme_id
            if getattr(_p, "style_id", None):
                extra_initial["ppt_style"] = _p.style_id
            _saved = json.loads(_p.asset_package or "{}") if _p and _p.asset_package else {}
            if _saved.get("_resume"):
                for key in ("requirement", "research", "competitor_matrix", "competitor_analysis", "strategy",
                            "design", "presentation", "node_status", "_completed_nodes",
                            "_gate_passed", "critic_score", "revision_count",
                            "_sources_review", "source_gathering_meta",
                            "amazon_collection", "mod_keyword"):
                    if key in _saved:
                        extra_initial[key] = _saved[key]
                extra_initial["idea"] = _saved.get("idea") or idea
                idea = extra_initial["idea"]
                logger.info("[Product Studio] product=%s 从断点恢复 | 已完成=%s",
                            product_id, _saved.get("_completed_nodes"))

        package = graph.invoke(idea, memory_namespace=product_id,
                               extra_initial=extra_initial)
    except GatePause as gp:
        # Plan/Act 门：持久化部分产物并暂停，等待用户批准
        snapshot = gp.state_snapshot
        partial = {
            "idea": snapshot.get("idea"),
            "requirement": snapshot.get("requirement"),
            "research": snapshot.get("research"),
            "competitor_analysis": snapshot.get("competitor_analysis"),
            "strategy": snapshot.get("strategy"),
            "design": snapshot.get("design"),
            "presentation": snapshot.get("presentation"),
            "node_status": snapshot.get("node_status"),
            "_completed_nodes": snapshot.get("_completed_nodes", []),
            "_gate_passed": snapshot.get("_gate_passed", []),
            "_paused_node": gp.node,
            "_resume": True,
            # 资料审核：待审核/已审核资料必须持久化（供前端审核界面 + 续跑使用）
            "_sources_review": snapshot.get("_sources_review", []),
            "source_gathering_meta": snapshot.get("source_gathering_meta", {}),
            # 统一采集层：亚马逊数据摘要必须持久化（gate 展示 + 矩阵节点 0-credit 回放）
            "amazon_collection": snapshot.get("amazon_collection"),
            "mod_keyword": snapshot.get("mod_keyword", ""),
        }
        _update_product(
            product_id,
            status=StudioProductStatus.WAITING_APPROVAL,
            asset_package=json.dumps(partial, ensure_ascii=False),
            error_message=f"等待人工确认节点: {gp.node}",
        )
        try:
            from app.services.task_health import clear_heartbeat, release_run_lock

            clear_heartbeat(str(product_id))
            release_run_lock(str(product_id))
        except Exception:  # noqa: BLE001
            pass
        logger.info("[Product Studio] product=%s 已暂停于节点 %s（等待人工批准）", product_id, gp.node)
        return {"product_id": product_id, "status": "waiting_approval", "node": gp.node}
    except SoftTimeLimitExceeded:
        # 软超时：任务仍在执行（如长 LLM 调用/逐页 SVG），不重投递。
        # 保持 running，等待硬超时兜底；避免软超时触发整条流水线重跑。
        logger.warning("[Product Studio] product=%s 软超时（仍执行中，等待硬超时兜底）", product_id)
        return {"product_id": product_id, "status": "running", "note": "soft_timeout"}
    except Exception as exc:  # noqa: BLE001 —— 记录失败，允许 Celery 重试
        current_status = _get_product_status(product_id)
        if current_status in (StudioProductStatus.PAUSED, StudioProductStatus.FAILED):
            logger.info("[Product Studio] product=%s 已被用户终止，忽略旧任务异常", product_id)
            return {"product_id": product_id, "status": current_status.value}
        logger.exception("[Product Studio] product=%s 流水线失败", product_id)
        _update_product(
            product_id,
            status=StudioProductStatus.FAILED,
            error_message=str(exc)[:2000],
        )
        try:
            from app.services.task_health import clear_heartbeat, release_run_lock

            clear_heartbeat(str(product_id))
            release_run_lock(str(product_id))
        except Exception:  # noqa: BLE001
            pass
        raise self.retry(exc=exc, countdown=30)

    # ── C5: 收集各节点模型 token 用量（成本可观测） ──
    usage = {
        "models": {},
        "total_tokens": 0,
    }
    for node, l in loops.items():
        try:
            u = l.llm.usage_summary
            usage["models"][node] = u
            usage["total_tokens"] += int(u.get("total_tokens") or 0)
        except Exception:  # noqa: BLE001
            continue

    package_dict = _json_safe(package.model_dump())
    package_dict["usage"] = usage
    current_status = _get_product_status(product_id)
    if current_status in (StudioProductStatus.PAUSED, StudioProductStatus.FAILED):
        logger.info("[Product Studio] product=%s 已被用户终止，不覆盖产品状态", product_id)
        return {"product_id": product_id, "status": current_status.value}

    _update_product(
        product_id,
        status=StudioProductStatus.COMPLETED,
        # default=str 兜底：防御个别非 JSON 原生类型（如 set）导致整体失败
        asset_package=json.dumps(package_dict, ensure_ascii=False, default=str),
        error_message=None,
    )
    try:
        from app.services.task_health import clear_heartbeat, release_run_lock

        clear_heartbeat(str(product_id))
        release_run_lock(str(product_id))
    except Exception:  # noqa: BLE001
        pass
    # ── 完成态后处理（耗时优化：五段互不依赖，并行执行） ──
    # keywords 结果回写主线程赋值；其余四段只读 package_dict，各自降级语义保持
    from concurrent.futures import ThreadPoolExecutor

    def _post_keywords():
        from app.services.product_keywords import generate_and_save_keywords

        return generate_and_save_keywords(product_id, package_dict, llm=loop.llm)

    def _post_knowledge():
        from app.rag.studio_knowledge import sync_studio_knowledge

        sync_studio_knowledge(product_id, package_dict, idea=idea)

    def _post_memory():
        from app.rag.studio_memory import extract_memory_from_studio_product

        extract_memory_from_studio_product(product_id, package_dict, llm=loop.llm)

    def _post_design_studio():
        from app.services.design_studio import import_from_product_package

        import_from_product_package(product_id, package_dict)

    def _post_text_assets():
        from app.services.project_assets import ensure_text_assets

        ensure_text_assets(str(product_id), package_dict)

    with ThreadPoolExecutor(max_workers=5, thread_name_prefix="post") as _post_ex:
        _futures = {
            "keywords": _post_ex.submit(_post_keywords),
            "knowledge": _post_ex.submit(_post_knowledge),
            "memory": _post_ex.submit(_post_memory),
            "design_studio": _post_ex.submit(_post_design_studio),
            "text_assets": _post_ex.submit(_post_text_assets),
        }
        for _name, _fut in _futures.items():
            try:
                if _name == "keywords":
                    package_dict["keywords"] = _fut.result()
            except Exception as exc:  # noqa: BLE001 —— 各段失败不阻断完成
                logger.warning("[Post/%s] 失败 | product=%s | %s", _name, product_id, exc)
    failed_nodes = package.meta.errors
    logger.info(
        "[Product Studio] product=%s 完成 | 失败节点=%s",
        product_id, list(failed_nodes) if failed_nodes else "无",
    )
    return {"product_id": product_id, "status": "completed",
            "failed_nodes": failed_nodes}
