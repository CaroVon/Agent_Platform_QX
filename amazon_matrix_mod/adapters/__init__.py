"""适配器注册表：数据源 → 采集函数。换数据源只改这里（P1 确立的架构）。"""
from __future__ import annotations

from typing import Callable, Optional

from amazon_matrix_mod.adapters import mock, rainforest

FETCHERS: dict[str, Callable[..., list[dict]]] = {
    "rainforest": rainforest.fetch_competitors,
    "mock": mock.fetch_competitors,
}


def get_fetcher(source: str):
    if source not in FETCHERS:
        raise ValueError(f"未知数据源: {source}（可选: {', '.join(FETCHERS)}）")
    return FETCHERS[source]


__all__ = ["FETCHERS", "get_fetcher", "Optional"]
