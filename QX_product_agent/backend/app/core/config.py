"""
============================================================
企业级应用核心配置 —— 基于 Pydantic V2 Settings
支持环境变量覆盖，便于 Docker 部署

.env 文件搜索顺序：
  1. ./backend/.env（从项目根目录运行时）
  2. ./.env（从 backend/ 目录运行时）
============================================================
"""

from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic import Field, PostgresDsn, RedisDsn, model_validator

# ─── 查找 .env 文件路径 ──────────────────────────────────────
def _find_env_file() -> str:
    """按优先级查找 .env 文件，返回第一个存在的路径。"""
    candidates = [
        Path(__file__).parent.parent.parent / ".env",       # backend/.env（从项目根运行）
        Path(__file__).parent.parent.parent.parent / "backend" / ".env",  # 额外兜底
        Path(".env"),                                         # 当前工作目录
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return ".env"  # 默认，pydantic-settings 会静默忽略不存在的文件


class Settings(BaseSettings):
    # ─── 应用基础 ────────────────────────────────────────────────
    APP_NAME: str = "Product Analysis Agent API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=False)

    # ─── 数据库 ──────────────────────────────────────────────────
    # 优先级：DATABASE_URL（环境变量）> 自动拼接 PostgreSQL
    # 本地开发推荐设置 DATABASE_URL=sqlite+aiosqlite:///./local_dev.db
    DATABASE_URL: str | None = Field(default=None)

    # PostgreSQL 参数（仅在 DATABASE_URL 未设置时生效）
    POSTGRES_USER: str = Field(default="postgres")
    POSTGRES_PASSWORD: str = Field(default="postgres")
    POSTGRES_HOST: str = Field(default="postgres")
    POSTGRES_PORT: int = Field(default=5432)
    POSTGRES_DB: str = Field(default="research_agent")

    @property
    def DATABASE_URL_ASYNC(self) -> str:
        """异步 SQLAlchemy 连接串（用于 FastAPI）"""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def DATABASE_URL_SYNC(self) -> str:
        """同步 SQLAlchemy 连接串（用于 Alembic 迁移）"""
        if self.DATABASE_URL:
            # 将异步驱动名替换为同步驱动名
            return self.DATABASE_URL.replace("+aiosqlite", "").replace("+asyncpg", "")
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ─── Redis ──────────────────────────────────────────────────
    REDIS_HOST: str = Field(default="redis")
    REDIS_PORT: int = Field(default=6379)
    REDIS_DB: int = Field(default=0)

    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # ─── Celery ─────────────────────────────────────────────────
    # 本地开发未设置时将使用 memory:// 传输（无需 Redis）
    # 配置这些值以连接 Redis（Docker 部署时请设置）
    CELERY_BROKER_URL: str = Field(default="")
    CELERY_RESULT_BACKEND: str = Field(default="")

    # ─── 文件存储 ────────────────────────────────────────────────
    # 报告输出目录（本地开发用 ./outputs）
    OUTPUT_DIR: str = Field(default="./outputs")
    # PDF 文件对外提供下载的 Base URL
    PDF_DOWNLOAD_BASE_URL: str = Field(default="/api/v1/files")
    # 上传限制（安全加固）：单文件大小上限(MB) + 扩展名白名单
    MAX_UPLOAD_MB: int = Field(default=20)
    # 默认允许 pdf/md/markdown/txt（本地解析），doc/docx 需 python-docx
    ALLOWED_UPLOAD_EXTS: str = Field(default="pdf,md,markdown,txt,doc,docx")

    # ─── 认证（轻量 HMAC token） ────────────────────────────────
    # AUTH_ENABLED=false 时所有端点匿名放行（仅限本地开发）
    AUTH_ENABLED: bool = Field(default=True)
    # 生产环境务必通过环境变量覆盖为强随机值
    AUTH_SECRET: str = Field(default="dev-secret-change-me")
    AUTH_ADMIN_USERNAME: str = Field(default="admin")
    AUTH_ADMIN_PASSWORD: str = Field(default="admin")
    # 本地开发便利：允许 POST /auth/bootstrap 免密签发 token；生产置 false
    AUTH_BOOTSTRAP: bool = Field(default=True)
    AUTH_TOKEN_TTL_HOURS: int = Field(default=24)

    # ─── 节点级 Plan/Act 门（可配置，逗号分隔节点名，如 "research,strategy"） ──
    # 节点完成后暂停等待人工批准；留空 = 全自动（默认）
    GATE_NODES: str = Field(default="")
    # 资料审核（默认开启）：source_gathering 节点搜索后暂停，用户审核资料权重后再继续
    SOURCE_REVIEW: bool = Field(default=True)

    # ─── 看门狗（卡死任务回收） ────────────────────────────────
    # 超过该时长未更新的 running/queued 任务将被置为 failed
    WATCHDOG_STALE_HOURS: int = Field(default=3)
    # 周期性检查间隔（分钟）
    WATCHDOG_INTERVAL_MINUTES: int = Field(default=15)


    # ─── 外部 API Key（优先从 .env 读取） ────────────────────────
    TAVILY_API_KEY: str = Field(default="")
    FIRECRAWL_API_KEY: str = Field(default="")
    # Rainforest（竞品矩阵 MOD 数据源；未配置时 MOD 节点走 mock/复用存档）
    RAINFOREST_API_KEY: str = Field(default="")
    DEEPSEEK_API_KEY: str = Field(default="")
    DEEPSEEK_BASE_URL: str = Field(default="https://api.deepseek.com/v1")
    DEEPSEEK_MODEL: str = Field(default="deepseek-chat")

    # ─── 上传限制（安全加固）扩展白名单：与前端 DOC_EXT 对齐 ─────
    # 默认允许 pdf/md/markdown/txt（本地解析），doc/docx 需 python-docx
    # （未安装时解析会返回明确错误提示，不静默失败）
    # ─── MiniMax 视觉分析（图片知识库入库） ──────────────────────
    # 模型: minimax-vl-01；端点二选一：
    #   OpenAI 兼容: https://api.minimax.chat/v1/chat/completions
    #   官方 V2:     https://api.minimax.chat/v1/text/chatcompletion_v2
    MINIMAX_VISION_MODEL: str = Field(default="minimax-vl-01")
    MINIMAX_VISION_ENDPOINT: str = Field(
        default="https://api.minimax.chat/v1/text/chatcompletion_v2",
    )
    KB_IMAGE_MAX_MB: int = Field(default=20, description="知识库图片单张大小上限(MB)")
    KB_IMAGE_MAX_PER_BATCH: int = Field(default=6, description="单次 VL 请求最多图片数")

    # ─── 三层知识库：全局 / 领域 / 任务 ─────────────────────────
    # 领域库与全局库在 CHROMA_PERSIST_DIR / BM25_PERSIST_DIR 下以
    # 保留字目录隔离：global（全局）、domain_{tag}（领域）。
    # 任务相似度阈值：≥ SIMILARITY_BORROW_THRESHOLD 视为"可借用经验"
    SIMILARITY_BORROW_THRESHOLD: float = Field(default=0.55)
    SIMILARITY_TOP_K: int = Field(default=5)
    # 三层检索每层召回数（任务/领域/全局）
    RETRIEVE_TASK_K: int = Field(default=5)
    RETRIEVE_DOMAIN_K: int = Field(default=3)
    RETRIEVE_GLOBAL_K: int = Field(default=2)
    # 三层融合权重（任务 1.0 / 领域 0.8 / 全局 0.6）
    RETRIEVE_SCOPE_WEIGHTS: str = Field(
        default='{"task": 1.0, "domain": 0.8, "global": 0.6}',
        description="JSON: 各层 RRF 融合权重",
    )
    # 经验包抽取最大长度（字符）
    EXPERIENCE_MAX_CHARS: int = Field(default=800)

    # ─── Obsidian Vault 集成（P3） ───────────────────────────────
    # Vault 目录留空 = 功能关闭。Vault 笔记以 obsidian://{rel_path} 为
    # source URL 进入全局知识库（复用现有来源权重体系）。
    OBSIDIAN_VAULT_PATH: str = Field(default="")
    OBSIDIAN_SYNC_INTERVAL_MIN: int = Field(default=30)
    # 可选增强：obsidian-local-rest-api 插件地址与 API Key（留空禁用）
    OBSIDIAN_REST_API: str = Field(default="")
    OBSIDIAN_REST_API_KEY: str = Field(default="")

    # ─── 多租户（向量库隔离） ────────────────────────────────────
    # 未来：当引入多租户时，每个 tenant 拥有独立的 Chroma 持久化路径
    # CHROMA_PERSIST_DIR_TEMPLATE: str = "/app/chroma_db/{tenant_id}"
    # BM25_PERSIST_DIR_TEMPLATE: str = "/app/bm25_db/{tenant_id}"
    CHROMA_PERSIST_DIR: str = Field(default="./chroma_db")
    BM25_PERSIST_DIR: str = Field(default="./bm25_db")

    # ─── 硅基流动 (SiliconFlow) 图像生成 ─────────────────────────
    SILICONFLOW_API_KEY: str = Field(default="")
    SILICONFLOW_IMAGE_MODEL: str = Field(default="Tongyi-MAI/Z-Image-Turbo")

    # ─── Model Router 多提供商（节点级模型路由） ──────────────────
    MINIMAX_API_KEY: str = Field(default="")
    MINIMAX_BASE_URL: str = Field(default="https://api.minimax.chat/v1")
    MINIMAX_MODEL: str = Field(default="MiniMax-M3")
    SILICONFLOW_BASE_URL: str = Field(default="https://api.siliconflow.cn/v1")
    SILICONFLOW_MODEL: str = Field(default="deepseek-ai/DeepSeek-V3")
    # 节点 → 模型路由（JSON：{"research": "deepseek", "presentation": "minimax"}）
    NODE_MODEL_MAP: str = Field(default="")
    CONCEPT_IMAGE_WIDTH: str = Field(default="1024")
    CONCEPT_IMAGE_HEIGHT: str = Field(default="576")

    # ─── 工业设计推演：概念图批量生成配置 ─────────────────────────
    DESIGN_MAX_CONCEPTS_PER_CHAPTER: int = Field(default=3)
    DESIGN_IMAGE_INTER_CALL_DELAY: float = Field(default=3.0)

    # ─── AI Product Studio（agent-platform 集成） ─────────────────
    # 平台层与专业 Agent 目录（默认: 工作区根下的 agent-platform/ 与 agents/）
    AGENT_PLATFORM_PATH: str = Field(default="")
    AGENTS_PATH: str = Field(default="")
    # 平台层记忆目录（默认: {OUTPUT_DIR}/studio_memory）
    AGENT_PLATFORM_MEMORY_DIR: str = Field(default="")
    # 工作流节点重试次数
    AGENT_PLATFORM_MAX_RETRIES: int = Field(default=2)

    # ─── P5: Critic 质量门 ─────────────────────────────────────
    # 演示评分阈值（< 阈值触发修订循环）与最大修订次数
    PRESENTATION_SCORE_THRESHOLD: int = Field(default=80)
    PRESENTATION_MAX_REVISIONS: int = Field(default=2)

    # ─── P4: Playwright/PptxGenJS 导出 ──────────────────────────
    EXPORT_BASE_URL: str = Field(default="http://127.0.0.1:8000")
    EXPORT_TIMEOUT: int = Field(default=300)

    # ─── HuggingFace / Embedding ─────────────────────────────────
    HF_ENDPOINT: str = Field(default="https://hf-mirror.com")
    EMBEDDING_MODEL_PATH: str = Field(default="BAAI/bge-small-zh-v1.5")

    # ─── 启动时关键配置校验（fail-fast：不要在深度执行时才报错） ───
    @model_validator(mode="after")
    def validate_critical_config(self):
        """
        启动时即校验关键 API Key，失败直接报错抛出明确指引，
        避免用户等待数分钟后在「大纲生成」步骤才看到 401 错误。

        SILICONFLOW_API_KEY 可选——未配置时封面图使用 CSS 渐变兜底。
        """
        missing: list[str] = []
        if not self.DEEPSEEK_API_KEY:
            missing.append("DEEPSEEK_API_KEY（LLM 文本引擎）")
        if not self.TAVILY_API_KEY:
            missing.append("TAVILY_API_KEY（全网搜索）")
        if not self.FIRECRAWL_API_KEY:
            missing.append("FIRECRAWL_API_KEY（网页内容抓取）")

        if missing:
            bullet = "\n  • ".join(missing)
            raise ValueError(
                f"❌ 关键 API Key 未配置，应用无法启动：\n"
                f"  • {bullet}\n\n"
                f"请在项目根目录的 .env 文件中设置这些环境变量：\n"
                f"  DEEPSEEK_API_KEY=sk-xxxx...\n"
                f"  TAVILY_API_KEY=tvly-xxxx...\n"
                f"  FIRECRAWL_API_KEY=fc-xxxx...\n\n"
                f"可参考 backend/.env.example 中的模板。"
            )
        return self

    model_config = {"env_file": _find_env_file(), "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    """全局单例获取配置"""
    return Settings()

settings = Settings()

# ─── 将关键配置桥接到 os.environ ───────────────────────────────
# SentenceTransformer / huggingface_hub 底层直接读取 os.environ，
# 而非 pydantic Settings 对象。此处确保 .env 中的值在模块导入时
# 即写入进程环境变量，避免模型下载时走不通的默认 HuggingFace 地址。
if settings.HF_ENDPOINT:
    os.environ.setdefault("HF_ENDPOINT", settings.HF_ENDPOINT)
if settings.EMBEDDING_MODEL_PATH:
    os.environ.setdefault("EMBEDDING_MODEL_PATH", settings.EMBEDDING_MODEL_PATH)

