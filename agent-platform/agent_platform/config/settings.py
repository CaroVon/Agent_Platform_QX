"""
============================================================
平台层集中配置 —— 基于 pydantic-settings
============================================================

环境变量约定（前缀 AGENT_PLATFORM_，可直接被平台读取）：

  AGENT_PLATFORM_LLM_API_KEY    模型 API Key（缺省回退 DEEPSEEK_API_KEY）
  AGENT_PLATFORM_LLM_BASE_URL   模型 Base URL（OpenAI 兼容）
  AGENT_PLATFORM_LLM_MODEL      模型名（deepseek-chat / qwen-max / gpt-4o-mini ...）
  AGENT_PLATFORM_TAVILY_API_KEY 搜索工具 API Key（缺省回退 TAVILY_API_KEY）
  AGENT_PLATFORM_MEMORY_DIR     记忆存储目录
  AGENT_PLATFORM_AGENT_MAX_TURNS       单 Agent 最大迭代轮数
  AGENT_PLATFORM_AGENT_MAX_RETRIES     结构化输出重试次数
  AGENT_PLATFORM_CONTEXT_CHAR_BUDGET   上下文字符预算

模型层支持 DeepSeek / Qwen / GPT 等任何 OpenAI 兼容接口，
切换模型只需修改 AGENT_PLATFORM_LLM_* 三个变量。
"""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings


class PlatformSettings(BaseSettings):
    """Agent Platform Runtime 配置单例。"""

    # ─── 模型层 ────────────────────────────────────────────────
    LLM_API_KEY: str = Field(default="")
    LLM_BASE_URL: str = Field(default="https://api.deepseek.com/v1")
    LLM_MODEL: str = Field(default="deepseek-chat")
    LLM_TEMPERATURE: float = Field(default=0.2)
    LLM_MAX_TOKENS: int = Field(default=8192)
    LLM_TIMEOUT: int = Field(default=180)

    # ─── Presentation Agent 专用模型（P3: 可选，如 Kimi） ───────
    # 未配置时回退主 LLM；Kimi 示例:
    #   AGENT_PLATFORM_PRESENTATION_LLM_BASE_URL=https://api.moonshot.cn/v1
    #   AGENT_PLATFORM_PRESENTATION_LLM_MODEL=kimi-k2-turbo-preview
    #   AGENT_PLATFORM_PRESENTATION_LLM_API_KEY=sk-xxx
    PRESENTATION_LLM_API_KEY: str = Field(default="")
    PRESENTATION_LLM_BASE_URL: str = Field(default="")
    PRESENTATION_LLM_MODEL: str = Field(default="")

    # ─── 工具层 ────────────────────────────────────────────────
    TAVILY_API_KEY: str = Field(default="")

    # ─── 记忆 ─────────────────────────────────────────────────
    MEMORY_DIR: str = Field(default="./agent_platform_memory")

    # ─── Agent 循环参数 ───────────────────────────────────────
    AGENT_MAX_TURNS: int = Field(default=3, ge=1, le=10)
    AGENT_MAX_RETRIES: int = Field(default=2, ge=0, le=5)
    CONTEXT_CHAR_BUDGET: int = Field(default=60000)

    @model_validator(mode="after")
    def _apply_env_fallbacks(self) -> "PlatformSettings":
        """兼容业务侧既有环境变量：未显式配置时回退到通用命名。"""
        if not self.LLM_API_KEY:
            self.LLM_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
        if not self.TAVILY_API_KEY:
            self.TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
        return self

    model_config = {
        "env_prefix": "AGENT_PLATFORM_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache()
def get_settings() -> PlatformSettings:
    """全局单例获取配置。"""
    return PlatformSettings()
