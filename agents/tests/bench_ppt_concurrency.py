#!/usr/bin/env python3
"""
PPT 逐页 SVG 并发加速 Benchmark（零网络，MockLLM 模拟真实延迟）
================================================================
模拟真实生产特征：
  - 每页延迟 0.5s 基础 + ±30% 抖动（对应真实 M3 单页 ~40-90s 的缩比）
  - 11 页（对标「新国潮床垫」真实规模）与 7 页两种场景
  - 顺序（并发 1） vs 并发 4 对比
  - 真实提速比 = 顺序耗时 / 并发耗时（按比例外推即真实提速比）
  - 输出逐字节一致校验 + 限流模拟（中途 429 → 降级重排队）

用法：
  QX_product_agent/venv/bin/python agents/tests/bench_ppt_concurrency.py
"""

import random
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
for _d in (str(_ROOT / "agent-platform"), str(_ROOT)):
    if _d not in sys.path:
        sys.path.insert(0, _d)

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_ppt_concurrency import MockLLM, _presentation, _svg_for_prompt  # noqa: E402

from agent_platform.config.settings import get_settings  # noqa: E402
from agent_platform.llm.client import LLMError  # noqa: E402

import agents.ppt_design_agent.agent as agent_mod  # noqa: E402
from agents.ppt_design_agent import cross_page as cp  # noqa: E402
from agents.ppt_design_agent.agent import PptDesignAgent  # noqa: E402

LATENCY_BASE = 0.5   # 每页基础延迟（秒）——真实 ~40-90s/页的缩比
JITTER = 0.3         # ±30% 抖动


def _realistic_behavior(mock, prompt):
    delay = LATENCY_BASE * random.uniform(1 - JITTER, 1 + JITTER)
    time.sleep(delay)
    return _svg_for_prompt(prompt)


def _run(agent, pres, project_dir, concurrency: int, behavior) -> tuple:
    s = get_settings()
    s.PPT_DESIGN_CONCURRENCY = concurrency
    s.PPT_DESIGN_CONCURRENCY_MAX = max(concurrency, 6)
    s.PPT_DESIGN_RATE_PAUSE = 0
    agent_mod._PPT_SVG_BATCH_GAP_SEC = 0.0
    mock = MockLLM(behavior=behavior)
    agent_mod.get_presentation_llm_client = lambda: mock
    agent_mod.get_llm_client = lambda: mock
    identity = cp.DeckIdentity(product_name="Bench 产品", product_code="2026.08")
    t0 = time.perf_counter()
    files, stats = agent._author_pages_v2(
        project_dir=project_dir, presentation=pres,
        theme=pres.get("theme") or {}, design_spec="# bench spec",
        images={}, identity=identity, cross_page_module=cp,
    )
    return mock.calls, time.perf_counter() - t0, files, stats


def _bench(n_pages: int) -> dict:
    random.seed(n_pages)  # 两次跑同一随机流，公平对比
    agent = PptDesignAgent()
    pres = _presentation(n_pages)
    root = Path(f"/tmp/ppt_bench_{n_pages}")
    seq_dir, con_dir = root / "seq", root / "con"
    for d in (seq_dir, con_dir):
        d.mkdir(parents=True, exist_ok=True)
        for f in d.glob("*.svg"):
            f.unlink()

    calls1, t_seq, files1, stats1 = _run(agent, pres, seq_dir, 1, _realistic_behavior)
    random.seed(n_pages)
    calls4, t_con, files4, stats4 = _run(agent, pres, con_dir, 4, _realistic_behavior)

    # 逐字节一致校验
    identical = files1 == files4 and all(
        (seq_dir / "svg_output" / n).read_bytes()
        == (con_dir / "svg_output" / n).read_bytes()
        for n in files1
    )
    return {
        "pages": n_pages,
        "calls": (calls1, calls4),
        "t_seq": t_seq, "t_con": t_con,
        "ratio": t_seq / t_con,
        "identical": identical,
        "fallbacks": (stats1["fallbacks"], stats4["fallbacks"]),
        "retries": (stats1["retries"], stats4["retries"]),
        "theoretical_seq": n_pages * LATENCY_BASE,
    }


def _bench_rate_limit(n_pages: int) -> dict:
    """中途注入 3 次 429（模拟瞬时限流）→ 验证重排队 + 降级后仍全部完成。"""
    agent = PptDesignAgent()
    pres = _presentation(n_pages)
    root = Path(f"/tmp/ppt_bench_rl_{n_pages}")
    root.mkdir(parents=True, exist_ok=True)
    state = {"rl_left": 3}

    def behavior(mock, prompt):
        if state["rl_left"] > 0:
            state["rl_left"] -= 1
            raise LLMError("LLM 返回 429: rate limit", status_code=429,
                           error_body="too many requests")
        delay = LATENCY_BASE * random.uniform(0.8, 1.2)
        time.sleep(delay)
        return _svg_for_prompt(prompt)

    calls, elapsed, files, stats = _run(agent, pres, root, 4, behavior)
    return {
        "pages": n_pages, "calls": calls, "elapsed": elapsed,
        "files": len(files), "fallbacks": stats["fallbacks"],
        "retries_429_injected": 3,
    }


def main() -> None:
    print("=" * 74)
    print("PPT 逐页 SVG 生成并发加速 Benchmark（MockLLM 延迟 0.5s/页 ±30% 抖动）")
    print("=" * 74)
    print(f"{'页数':>4} | {'顺序(s)':>9} | {'并发4(s)':>9} | {'提速比':>6} | "
          f"{'调用数(seq/con)':>15} | {'fallback':>8} | {'逐字节一致':>8}")
    print("-" * 74)
    for n in (7, 11):
        r = _bench(n)
        print(f"{r['pages']:>4} | {r['t_seq']:>9.2f} | {r['t_con']:>9.2f} | "
              f"{r['ratio']:>5.2f}× | {r['calls'][0]:>7}/{r['calls'][1]:<7} | "
              f"{r['fallbacks'][0]}/{r['fallbacks'][1]:<6} | {str(r['identical']):>8}")
        # 理论外推（真实 ~50-90s/页 → 11 页真实顺序 ~8-16min）
        real_ratio = r["ratio"]
        print(f"    └─ 理论顺序耗时 {r['theoretical_seq']:.1f}s；外推真实场景："
              f"11 页顺序 ~776-1025s（历史实测）→ 并发 4 预计 "
              f"{776 / real_ratio:.0f}-{1025 / real_ratio:.0f}s")
    print("-" * 74)
    rl = _bench_rate_limit(11)
    print(f"限流模拟（11 页注入 3 次 429）：完成 {rl['files']} 页，调用 {rl['calls']} 次"
          f"（重排队 {rl['calls'] - 11} 次），fallback {rl['fallbacks']}，耗时 {rl['elapsed']:.2f}s")
    print("=" * 74)


if __name__ == "__main__":
    main()
