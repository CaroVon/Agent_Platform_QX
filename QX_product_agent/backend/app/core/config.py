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

    # ─── 外部 API Key（优先从 .env 读取） ────────────────────────
    TAVILY_API_KEY: str = Field(default="")
    FIRECRAWL_API_KEY: str = Field(default="")
    DEEPSEEK_API_KEY: str = Field(default="")
    DEEPSEEK_BASE_URL: str = Field(default="https://api.deepseek.com/v1")
    DEEPSEEK_MODEL: str = Field(default="deepseek-chat")

    # ─── 多租户（向量库隔离） ────────────────────────────────────
    # 未来：当引入多租户时，每个 tenant 拥有独立的 Chroma 持久化路径
    # CHROMA_PERSIST_DIR_TEMPLATE: str = "/app/chroma_db/{tenant_id}"
    # BM25_PERSIST_DIR_TEMPLATE: str = "/app/bm25_db/{tenant_id}"
    CHROMA_PERSIST_DIR: str = Field(default="./chroma_db")
    BM25_PERSIST_DIR: str = Field(default="./bm25_db")

    # ─── 硅基流动 (SiliconFlow) 图像生成 ─────────────────────────
    SILICONFLOW_API_KEY: str = Field(default="")
    SILICONFLOW_IMAGE_MODEL: str = Field(default="Tongyi-MAI/Z-Image-Turbo")
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

