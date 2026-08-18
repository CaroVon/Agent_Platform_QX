"""
记忆存储 —— 文件版 JSONL 实现（零外部依赖）
============================================================

FileMemoryStore 按 namespace（如 product_id）隔离记忆文件，
每个条目一行 JSON，支持追加、最近 N 条召回与关键词搜索。

记忆分层（P3 升级）：
  - episodic（运行中流水）: kind ∈ finding / decision / plan / note
  - task（任务级记忆）    : kind = summary —— compact() 将流水压缩为任务摘要
  - semantic（全局知识）  : 由上层将 summary/lesson 提升进入全局知识库
"""

from __future__ import annotations

import json
import re
import time
from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel, Field

# 记忆类型（episodic 层）
EPISODIC_KINDS = ("finding", "decision", "plan", "note")
# 记忆类型（task 层，由 compact 产出）
SUMMARY_KIND = "summary"
# 可提升为全局知识的记忆类型
PROMOTABLE_KINDS = ("summary", "lesson", "finding")


class MemoryEntry(BaseModel):
    """单条记忆。"""

    ts: str = Field(description="ISO 时间戳")
    kind: str = Field(description="记忆类型（finding / decision / plan / note / summary / lesson）")
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

    # 每个 namespace 最多保留的条目数（防无限增长）
    MAX_ENTRIES = 200

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
        path = self._path(namespace)
        with path.open("a", encoding="utf-8") as f:
            f.write(entry.model_dump_json() + "\n")
        # 容量上限：超出后裁剪为最近 MAX_ENTRIES 条（原子替换）
        if path.stat().st_size > 0 and len(self._load(namespace)) > self.MAX_ENTRIES:
            keep = self._load(namespace)[-self.MAX_ENTRIES:]
            path.write_text(
                "".join(e.model_dump_json() + "\n" for e in keep),
                encoding="utf-8",
            )

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
                # 分层加权：summary/lesson 命中权重更高（更可信）
                if entry.kind in ("summary", "lesson"):
                    score += 2
                elif entry.kind in ("decision", "finding"):
                    score += 1
                scored.append((score, idx, entry))
        scored.sort(key=lambda item: (-item[0], -item[1]))
        return [entry for _, _, entry in scored[:limit]]

    # ══════════════════════════════════════════════════════════
    # 记忆分层（P3）：episodic → task 压缩
    # ══════════════════════════════════════════════════════════

    def compact(self, namespace: str, keep_recent: int = 12) -> MemoryEntry | None:
        """
        将最近的流水记忆（finding/decision/plan/note）压缩为一条 summary 记忆
        （task 层）。规则化压缩（零外部依赖）：
          - 决策/结论优先保留原文，流水类合并去重。
        返回新生成的 summary 条目；无内容时返回 None。
        """
        entries = self._load(namespace)
        recent = [e for e in entries if e.kind in EPISODIC_KINDS][-keep_recent:]
        if not recent:
            return None

        # 1. 决策与结论原文保留
        core = [e.content for e in recent if e.kind in ("decision", "finding")][:6]
        # 2. 流水类（plan/note）只保留要点（首行）
        flow = [e.content.splitlines()[0][:120] for e in recent if e.kind in ("plan", "note")][:6]
        parts = core + flow
        if not parts:
            return None

        summary_text = "\n".join(f"- {p}" for p in parts)
        entry = MemoryEntry(
            ts=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            kind=SUMMARY_KIND,
            content=f"任务阶段总结（压缩自 {len(recent)} 条流水记忆）：\n{summary_text}",
            metadata={
                "source_kinds": sorted({e.kind for e in recent}),
                "compacted_count": len(recent),
            },
        )
        self.add(namespace, SUMMARY_KIND, entry.content, entry.metadata)
        return entry

    def promotable(self, namespace: str, limit: int = 10) -> list[MemoryEntry]:
        """召回可提升为全局知识的记忆（summary/lesson/finding）。"""
        return [
            e for e in self._load(namespace)
            if e.kind in PROMOTABLE_KINDS
        ][-limit:][::-1]
