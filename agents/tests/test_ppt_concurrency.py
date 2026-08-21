"""
PptDesignAgent 并发加速单元测试 —— _author_pages_v2 batch 自适应并发
====================================================================

覆盖：
  - classify_llm_error 限流分类（HTTP 429 / MiniMax 2056 配额 / 其它）
  - 并发生成正确性：文件齐全、顺序正确、stats 聚合
  - 质量回归：并发输出与顺序版**逐字节一致**
  - 速度提升：同延迟下并发墙钟时间显著低于顺序
  - 瞬时限流 → 重排队；持久限流 → fallback；配额耗尽 → 立即 fallback 不重试
  - 无 LLM → 全 fallback（不报错）

全部零网络：MockLLM 本地返回合法 SVG。
"""

import re
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]  # ~/dev/agents
for _d in (str(_ROOT / "agent-platform"), str(_ROOT)):
    if _d not in sys.path:
        sys.path.insert(0, _d)

import pytest

from agent_platform.config.settings import get_settings
from agent_platform.llm.client import LLMError, classify_llm_error

import agents.ppt_design_agent.agent as agent_mod
from agents.ppt_design_agent import cross_page as cp
from agents.ppt_design_agent.agent import PptDesignAgent


# ─────────────────────────────────────────────────────────────
# 夹具
# ─────────────────────────────────────────────────────────────

def _svg_for_prompt(prompt: str) -> str:
    """从 prompt 中提取页面 title/insight，构造能通过全部校验（含 QA 门禁）的合法 SVG。"""
    m_title = re.search(r'"title":\s*"([^"]*)"', prompt)
    m_ins = re.search(r'"insight":\s*"([^"]*)"', prompt)
    title = m_title.group(1) if m_title else "产品核心价值"
    insight = m_ins.group(1) if m_ins else "市场规模持续增长"
    # QA 门禁要求：≥8 text、≥4 rect、有 defs/渐变、色板内颜色、mod 页带溯源标记
    rows = "\n".join(
        f'  <text x="60" y="{y}" font-size="14" fill="#111111">数据行 {i} · [A{i}] B0TEST{i:02d}</text>'
        for i, y in enumerate(range(200, 560, 40))
    )
    cards = "\n".join(
        f'  <rect x="{x}" y="580" width="120" height="60" fill="#FFFFFF" stroke="#3D6491"/>'
        for x in range(60, 900, 150)
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <defs><linearGradient id="g"><stop offset="0" stop-color="#3D6491"/><stop offset="1" stop-color="#F7F6F0"/></linearGradient></defs>
  <rect x="0" y="0" width="1280" height="720" fill="#F7F6F0"/>
  <rect x="60" y="80" width="4" height="80" fill="#3D6491"/>
  <text x="60" y="100" font-size="44" fill="#111111">{title}</text>
  <text x="60" y="160" font-size="18" fill="#3D6491">{insight}</text>
{rows}
{cards}
  <text x="60" y="700" font-size="10" fill="#6F7275">*Rainforest data · B0TEST</text>
</svg>'''


class MockLLM:
    """可配置延迟/行为/计数的假 LLM（api_key 非空 → 走 LLM 路径）。"""

    api_key = "test-key"
    model = "mock-model"

    def __init__(self, latency: float = 0.0, behavior=None):
        self.latency = latency
        self.behavior = behavior  # callable(mock, prompt) -> str（或 raise）
        self.calls = 0
        self.prompts: list[str] = []

    def complete(self, messages, temperature=None, max_tokens=None):
        self.calls += 1
        prompt = messages[-1]["content"]
        self.prompts.append(prompt)
        if self.latency:
            time.sleep(self.latency)
        if self.behavior is not None:
            return self.behavior(self, prompt)
        return _svg_for_prompt(prompt)


def _page(no: int, ptype: str) -> dict:
    return {
        "id": f"p{no}",
        "type": ptype,
        "title": f"第 {no} 页核心卖点与市场机会",
        "insight": f"结论：第 {no} 页数据显示增长明确",
        "components": [
            {"type": "metric", "data": {"value": f"{no}00亿", "label": "市场规模"}},
        ],
    }


_PAGE_TYPES = [
    "cover", "executive_summary", "market_overview", "competitor_matrix",
    "user_persona", "feature_priority", "product_architecture",
    "user_journey", "roadmap", "conclusion", "content",
]


def _presentation(n: int) -> dict:
    return {
        "theme": {
            "name": "咨询风",
            "palette": {"accent": "#3D6491", "muted": "#6F7275",
                        "text": "#111111", "bg": "#F7F6F0"},
        },
        "pages": [_page(i + 1, _PAGE_TYPES[i % len(_PAGE_TYPES)]) for i in range(n)],
    }


@pytest.fixture
def agent() -> PptDesignAgent:
    return PptDesignAgent()


def _set_concurrency(monkeypatch, concurrency: int) -> None:
    s = get_settings()
    monkeypatch.setattr(s, "PPT_DESIGN_CONCURRENCY", concurrency)
    monkeypatch.setattr(s, "PPT_DESIGN_CONCURRENCY_MAX", max(concurrency, 6))
    monkeypatch.setattr(s, "PPT_DESIGN_RATE_PAUSE", 0)  # 测试不真睡
    monkeypatch.setattr(agent_mod, "_PPT_SVG_BATCH_GAP_SEC", 0.0)


def _run_author(agent, presentation, project_dir, monkeypatch,
                concurrency: int, latency: float = 0.0, behavior=None):
    _set_concurrency(monkeypatch, concurrency)
    mock = MockLLM(latency=latency, behavior=behavior)
    monkeypatch.setattr(agent_mod, "get_presentation_llm_client", lambda: mock)
    monkeypatch.setattr(agent_mod, "get_llm_client", lambda: mock)
    theme = presentation.get("theme") or {}
    identity = cp.DeckIdentity(
        product_name="测试产品", product_code="2026.08",
        theme_color="#3D6491", muted_color="#6F7275",
        text_color="#111111", bg_color="#F7F6F0",
    )
    files, stats = agent._author_pages_v2(
        project_dir=project_dir,
        presentation=presentation,
        theme=theme,
        design_spec="# 测试设计规范\n- 咨询风\n",
        images={},
        identity=identity,
        cross_page_module=cp,
    )
    return mock, files, stats


# ─────────────────────────────────────────────────────────────
# 1. 限流分类
# ─────────────────────────────────────────────────────────────

def test_classify_http_429_transient():
    exc = LLMError("LLM 返回 429: rate limit", status_code=429,
                   error_body='{"error": {"message": "Too many requests"}}')
    assert classify_llm_error(exc) == "rate_limit_transient"


def test_classify_minimax_2056_quota():
    # MiniMax 实测形态：HTTP 200 + base_resp.status_code 2056（Token Plan 用量上限）
    exc = LLMError(
        "LLM 业务错误 2056: 已达到 Token Plan 用量上限",
        status_code=2056,
        error_body='{"base_resp": {"status_code": 2056, "status_msg": '
                   '"已达到 Token Plan 用量上限：请升级 Token Plan 套餐或购买积分补充用量。"}}',
    )
    assert classify_llm_error(exc) == "rate_limit_quota"


def test_classify_quota_keyword_in_message():
    exc = LLMError("LLM 返回 429: 配额不足", status_code=429)
    assert classify_llm_error(exc) == "rate_limit_quota"


def test_classify_other_error():
    exc = LLMError("LLM 请求失败: Connection refused", status_code=None)
    assert classify_llm_error(exc) == "other"
    assert classify_llm_error(ValueError("boom")) == "other"


# ─────────────────────────────────────────────────────────────
# 2. 并发正确性
# ─────────────────────────────────────────────────────────────

def test_concurrent_7_pages_all_written_and_ordered(agent, tmp_path, monkeypatch):
    pres = _presentation(7)
    mock, files, stats = _run_author(agent, pres, tmp_path, monkeypatch, concurrency=4)

    assert mock.calls == 7, f"每页恰好 1 次调用，实际 {mock.calls}"
    expected = [f"slide_{i + 1:02d}_{_PAGE_TYPES[i % len(_PAGE_TYPES)]}.svg"
                for i in range(7)]
    assert files == expected, "返回列表必须按页码排序"
    written = sorted(p.name for p in (tmp_path / "svg_output").glob("*.svg"))
    assert written == files, "磁盘产物齐全且与返回列表一致"
    assert stats["fallbacks"] == 0
    assert stats["retries"] == 0
    assert len(stats["per_page"]) == 7
    assert all(v["status"] == "llm" for v in stats["per_page"].values())
    # 跨页注入仍然生效
    assert stats["root_metadata_injected"] == 7
    assert stats["footers_injected"] == 6  # cover 不放 footer
    # footer / 根属性确实写进了文件
    first = (tmp_path / "svg_output" / files[0]).read_text(encoding="utf-8")
    assert "data-pptx-page-role" in first and "data-pptx-page-total" in first
    assert 'id="page-footer-02"' in (tmp_path / "svg_output" / files[1]).read_text(encoding="utf-8")


def test_output_byte_identical_to_sequential(agent, tmp_path, monkeypatch):
    """质量回归：并发产物与顺序版逐字节一致。"""
    pres = _presentation(7)
    d1 = tmp_path / "seq"
    d2 = tmp_path / "con"
    d1.mkdir()
    d2.mkdir()
    mock1, files1, stats1 = _run_author(agent, pres, d1, monkeypatch, concurrency=1)
    mock2, files2, stats2 = _run_author(agent, pres, d2, monkeypatch, concurrency=4)

    assert files1 == files2
    for name in files1:
        b1 = (d1 / "svg_output" / name).read_bytes()
        b2 = (d2 / "svg_output" / name).read_bytes()
        assert b1 == b2, f"{name} 并发版与顺序版不一致（质量回归失败）"
    assert stats1 == stats2


def test_no_llm_all_fallback(agent, tmp_path, monkeypatch):
    _set_concurrency(monkeypatch, 4)
    monkeypatch.setattr(agent_mod, "get_presentation_llm_client", lambda: None)
    monkeypatch.setattr(agent_mod, "get_llm_client", lambda: None)
    pres = _presentation(3)
    files, stats = agent._author_pages_v2(
        project_dir=tmp_path, presentation=pres, theme=pres.get("theme") or {},
        design_spec="spec", images={}, identity=cp.DeckIdentity(),
        cross_page_module=cp,
    )
    assert len(files) == 3
    assert stats["fallbacks"] == 3
    assert all(v["status"] == "fallback" for v in stats["per_page"].values())


# ─────────────────────────────────────────────────────────────
# 3. 速度提升
# ─────────────────────────────────────────────────────────────

def test_speedup_sequential_vs_concurrent(agent, tmp_path, monkeypatch):
    """11 页、每页 0.12s 延迟：并发 4 必须显著快于顺序。"""
    pres = _presentation(11)
    latency = 0.12
    (tmp_path / "seq").mkdir()
    (tmp_path / "con").mkdir()
    t0 = time.perf_counter()
    _run_author(agent, pres, tmp_path / "seq", monkeypatch, concurrency=1, latency=latency)
    t_seq = time.perf_counter() - t0

    t0 = time.perf_counter()
    _run_author(agent, pres, tmp_path / "con", monkeypatch, concurrency=4, latency=latency)
    t_con = time.perf_counter() - t0

    # 理论值：顺序 ≈ 11×0.12 = 1.32s；并发 4 ≈ 3 波 ×0.12 = 0.36s + 线程开销
    assert t_seq >= 1.1, f"顺序基线异常偏快（{t_seq:.2f}s），测试无效"
    assert t_con < t_seq / 2.0, (
        f"并发未显著提速：seq={t_seq:.2f}s con={t_con:.2f}s"
    )
    # 同时验证提速幅度接近理论（≥2.2×，留足 CI 抖动余量）
    ratio = t_seq / t_con
    assert ratio >= 2.2, f"提速比 {ratio:.2f}× < 2.2×（seq={t_seq:.2f}s con={t_con:.2f}s）"


# ─────────────────────────────────────────────────────────────
# 4. 限流降级
# ─────────────────────────────────────────────────────────────

def _raise_429(_mock, _prompt=None):
    raise LLMError("LLM 返回 429: rate limit", status_code=429,
                   error_body="too many requests")


def test_transient_rate_limit_requeue_then_success(agent, tmp_path, monkeypatch):
    """全局仅 1 次 429 → 该页重排队后成功，无 fallback。"""
    state = {"failed": 0}

    def behavior(mock, prompt):
        if state["failed"] < 1:
            state["failed"] += 1
            _raise_429(mock)
        return _svg_for_prompt(prompt)

    pres = _presentation(7)
    mock, files, stats = _run_author(agent, pres, tmp_path, monkeypatch,
                                     concurrency=4, behavior=behavior)
    assert mock.calls == 8, f"7 页 + 1 次重试 = 8 次调用，实际 {mock.calls}"
    assert stats["fallbacks"] == 0, "瞬时限流重排队后不应 fallback"
    assert len(files) == 7


def test_persistent_rate_limit_falls_back(agent, tmp_path, monkeypatch):
    """持续 429（模拟配额/RPM 一直被限）→ 预算耗尽后全部 fallback，deck 仍完整。"""
    pres = _presentation(7)
    mock, files, stats = _run_author(agent, pres, tmp_path, monkeypatch,
                                     concurrency=4, behavior=_raise_429)
    assert len(files) == 7, "限流下页面仍必须齐全（fallback 占位）"
    assert stats["fallbacks"] == 7
    assert all(v["status"] == "fallback" for v in stats["per_page"].values())
    assert mock.calls <= 7 * agent_mod._PPT_SVG_MAX_RATE_LIMIT_ATTEMPTS + 7, (
        f"限流重试必须有界，实际 {mock.calls} 次"
    )


def test_quota_exhaustion_immediate_fallback_no_retry(agent, tmp_path, monkeypatch):
    """配额型限流（MiniMax 2056）→ 每页 1 次调用即 fallback，绝不重试浪费请求。"""
    def behavior(_mock, _prompt=None):
        raise LLMError(
            "LLM 业务错误 2056: 已达到 Token Plan 用量上限",
            status_code=2056,
            error_body='{"base_resp": {"status_code": 2056, "status_msg": '
                       '"已达到 Token Plan 用量上限：请升级 Token Plan 套餐或购买积分补充用量。"}}',
        )

    pres = _presentation(7)
    mock, files, stats = _run_author(agent, pres, tmp_path, monkeypatch,
                                     concurrency=4, behavior=behavior)
    assert mock.calls == 7, f"配额耗尽必须立即 fallback（每页 1 次调用），实际 {mock.calls}"
    assert stats["fallbacks"] == 7
    assert len(files) == 7
