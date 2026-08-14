"""
记忆存储 —— 文件版 JSONL 实现（零外部依赖）
============================================================

FileMemoryStore 按 namespace（如 product_id）隔离记忆文件，
每个条目一行 JSON，支持追加、最近 N 条召回与关键词搜索。
"""

from __future__ import annotations

import json
import re
import time
from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel, Field


class MemoryEntry(BaseModel):
    """单条记忆。"""

    ts: str = Field(description="ISO 时间戳")
    kind: str = Field(description="记忆类型（finding / decision / plan ...）")
    content: str = Field(description="记忆内容")
    metadata: dict = Field(default_factory=dict, description="附加元信息")


class MemoryStore(ABC):
    """记忆存储抽象接口。"""

    @abstractmethod
    def add(self, namespace: str, kind: str, content: str, metadata: dict | None = None) -> None:
        """追加一条记忆。"""

    @abstractmethod
    def recent(self, namespace: str, limit: int = 10) -> list[MemoryEntry]:
        """召回最近 N 条记忆（时间倒序）。"""

    @abstractmethod
    def search(self, namespace: str, query: str, limit: int = 10) -> list[MemoryEntry]:
        """按关键词召回记忆。"""


class FileMemoryStore(MemoryStore):
    """文件版记忆存储：{dir}/{namespace}.jsonl。"""

    def __init__(self, base_dir: str = "./agent_platform_memory"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, namespace: str) -> Path:
        safe = re.sub(r"[^0-9a-zA-Z_.\-]", "_", namespace)
        return self.base_dir / f"{safe}.jsonl"

    def add(self, namespace: str, kind: str, content: str, metadata: dict | None = None) -> None:
        entry = MemoryEntry(
            ts=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            kind=kind,
            content=content,
            metadata=metadata or {},
        )
        with self._path(namespace).open("a", encoding="utf-8") as f:
            f.write(entry.model_dump_json() + "\n")

    def _load(self, namespace: str) -> list[MemoryEntry]:
        path = self._path(namespace)
        if not path.is_file():
            return []
        entries: list[MemoryEntry] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                entries.append(MemoryEntry.model_validate_json(line))
            except Exception:  # noqa: BLE001 —— 跳过损坏行
                continue
        return entries

    def recent(self, namespace: str, limit: int = 10) -> list[MemoryEntry]:
        return self._load(namespace)[-limit:][::-1]

    def search(self, namespace: str, query: str, limit: int = 10) -> list[MemoryEntry]:
        keywords = [kw for kw in re.split(r"[\s,，。;；]+", query) if kw]
        scored: list[tuple[int, int, MemoryEntry]] = []
        for idx, entry in enumerate(self._load(namespace)):
            score = sum(1 for kw in keywords if kw.lower() in entry.content.lower())
            if score > 0:
                scored.append((score, idx, entry))
        scored.sort(key=lambda item: (-item[0], -item[1]))
        return [entry for _, _, entry in scored[:limit]]
