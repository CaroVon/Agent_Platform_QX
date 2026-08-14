"""FileMemoryStore 测试 —— 隔离、召回与搜索。"""

from agent_platform.memory.memory_store import FileMemoryStore


def test_add_and_recent(tmp_path):
    store = FileMemoryStore(base_dir=str(tmp_path))
    store.add("p1", "finding", "市场 A 规模 100 亿")
    store.add("p1", "decision", "主打高端")

    recent = store.recent("p1", limit=10)
    assert [e.content for e in recent] == ["主打高端", "市场 A 规模 100 亿"]


def test_namespace_isolation(tmp_path):
    store = FileMemoryStore(base_dir=str(tmp_path))
    store.add("p1", "finding", "内容甲")
    store.add("p2", "finding", "内容乙")
    assert len(store.recent("p1")) == 1
    assert store.recent("p1")[0].content == "内容甲"


def test_search_by_keyword(tmp_path):
    store = FileMemoryStore(base_dir=str(tmp_path))
    store.add("p1", "finding", "竞品 A 定价 99 元")
    store.add("p1", "finding", "行业趋势：订阅制兴起")
    hits = store.search("p1", "定价", limit=5)
    assert len(hits) == 1
    assert "定价" in hits[0].content


def test_corrupt_lines_skipped(tmp_path):
    store = FileMemoryStore(base_dir=str(tmp_path))
    path = store._path("p1")
    path.write_text("not-json\n", encoding="utf-8")
    store.add("p1", "finding", "合法条目")
    assert len(store.recent("p1")) == 1
