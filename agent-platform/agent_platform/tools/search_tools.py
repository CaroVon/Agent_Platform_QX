"""
搜索工具 —— Tavily 全网搜索封装
============================================================

平台层自包含实现（httpx 直连 Tavily REST API），不依赖业务侧封装。
无 API Key 时优雅降级为空结果，不阻塞工作流。
"""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel, Field

from agent_platform.config.settings import get_settings

logger = logging.getLogger(__name__)

TAVILY_SEARCH_URL = "https://api.tavily.com/search"


class SearchResult(BaseModel):
    """单条搜索结果。"""

    title: str
    url: str
    content: str = Field(default="", description="摘要片段")
    score: float | None = Field(default=None, description="相关度分数")


class WebSearchTool:
    """Tavily 全网搜索工具。"""

    name = "web_search"
    description = "搜索互联网获取与产品想法相关的市场信息、竞品资料与行业趋势"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or get_settings().TAVILY_API_KEY

    def run(self, query: str, max_results: int = 5) -> list[SearchResult]:
        """执行搜索，返回结构化结果列表；失败/未配置时返回空列表。"""
        if not self.api_key:
            logger.warning("TAVILY_API_KEY 未配置，web_search 降级为空结果")
            return []

        try:
            resp = httpx.post(
                TAVILY_SEARCH_URL,
                json={
                    "api_key": self.api_key,
                    "query": query,
                    "max_results": max(1, min(int(max_results), 20)),
                    "search_depth": "basic",
                },
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("web_search 调用失败，降级为空结果: %s", exc)
            return []

        results: list[SearchResult] = []
        for item in data.get("results", []):
            try:
                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        content=item.get("content", ""),
                        score=item.get("score"),
                    )
                )
            except Exception:  # noqa: BLE001 —— 单条脏数据不阻塞整体
                continue
        return results
