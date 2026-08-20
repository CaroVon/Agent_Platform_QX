#!/usr/bin/env python3
"""
真实 LLM（MiniMax-M3）冒烟测试 —— 顺序 vs 并发 4 速度对比 + 全链路验证
====================================================================
- 6 页真实咨询风演示内容（对标真实产品结构）
- 顺序（并发 1）与并发 4 各跑一遍，测墙钟时间
- 并发产物继续走 finalize_svg.py + svg_to_pptx.py 全链路，验证 PPTX 可产出
- 必须从 backend 目录运行（读取 backend/.env 的 MiniMax 配置）

用法：
  cd QX_product_agent/backend && python /path/to/smoke_real_ppt_concurrency.py
"""

import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]  # ~/dev/agents
BACKEND = _ROOT / "QX_product_agent" / "backend"
os.chdir(BACKEND)

for _d in (str(_ROOT / "agent-platform"), str(_ROOT)):
    if _d not in sys.path:
        sys.path.insert(0, _d)

from agent_platform.config.settings import get_settings  # noqa: E402

get_settings.cache_clear()
_settings = get_settings()
assert _settings.PRESENTATION_LLM_API_KEY, "未找到 PRESENTATION LLM key（需从 backend 目录运行）"
print(f"[CONFIG] model={_settings.PRESENTATION_LLM_MODEL} base={_settings.PRESENTATION_LLM_BASE_URL}")

from agents.ppt_design_agent import cross_page as cp  # noqa: E402
from agents.ppt_design_agent.agent import PptDesignAgent  # noqa: E402

THEME = {
    "name": "咨询风",
    "palette": {"accent": "#3D6491", "muted": "#6F7275",
                "text": "#111111", "bg": "#F7F6F0"},
}
DESIGN_SPEC = """# 设计规范与内容大纲
## 产品：新国潮智能床垫
- 主题：咨询风（黑灰白基底 + 单强调色）
- 页数：6 页 · 画布：1280×720
## 视觉方向
- 信息密度高、结论先行；卡片语言统一圆角卡片
- 图表风格：原生 bar chart 标记，数据必须来自页面数据
- 每页左上标题 + 强调竖条 + insight 主色行
## 逐页大纲
- P01 cover：居中标题 + 强调色条 + 留白
- P02 executive_summary：指标卡 TAM/CAGR + 差异化卡片
- P03 market_overview：柱状图 + 驱动因素卡片
- P04 feature_priority：P0/P1 功能优先级卡片
- P05 user_persona：目标用户画像卡
- P06 conclusion：结论 + 关键举措
"""


def _pages():
    return [
        {"id": "p1", "type": "cover",
         "title": "新国潮智能床垫：AI 睡眠健康解决方案",
         "insight": "以 AI 感知与国潮设计重新定义睡眠体验",
         "components": [{"type": "card", "data": {
             "title": "产品主张", "items": ["新国潮设计", "AI 睡眠感知", "智能调节"]}}]},
        {"id": "p2", "type": "executive_summary",
         "title": "执行摘要：市场机遇与产品定位",
         "insight": "TAM 500 亿，聚焦中高端改善型睡眠市场",
         "components": [
             {"type": "metric", "data": {"value": "500亿", "label": "TAM"}},
             {"type": "metric", "data": {"value": "28%", "label": "CAGR"}},
             {"type": "card", "data": {"title": "核心差异化",
                                       "items": ["国潮美学设计", "AI 整夜监测", "自适应软硬调节"]}}]},
        {"id": "p3", "type": "market_overview",
         "title": "市场概览：睡眠经济持续升温",
         "insight": "睡眠健康成为消费升级新焦点",
         "components": [
             {"type": "chart", "id": "c1", "data": {"chart_type": "bar", "items": [
                 {"label": "2022", "value": 420}, {"label": "2023", "value": 460},
                 {"label": "2024", "value": 500}, {"label": "2025", "value": 560}]}},
             {"type": "card", "data": {"title": "驱动因素",
                                       "items": ["健康意识提升", "智能家居普及", "老龄化趋势"]}}]},
        {"id": "p4", "type": "feature_priority",
         "title": "功能优先级：从感知到干预",
         "insight": "P0 睡眠监测与自适应调节为核心壁垒",
         "components": [
             {"type": "card", "data": {"title": "P0 核心",
                                       "items": ["AI 睡眠分期", "自适应软硬调节", "鼾声干预"]}},
             {"type": "card", "data": {"title": "P1 增强",
                                       "items": ["智能闹钟", "睡眠报告", "健康联动"]}}]},
        {"id": "p5", "type": "user_persona",
         "title": "目标用户：新中产睡眠改善者",
         "insight": "30-45 岁城市新中产是核心客群",
         "components": [{"type": "card", "data": {
             "title": "用户画像", "items": ["城市白领", "睡眠质量焦虑", "愿为健康付费"]}}]},
        {"id": "p6", "type": "conclusion",
         "title": "结论：以 AI 睡眠科技打造国潮新品牌",
         "insight": "差异化切入，三年内成为细分市场头部",
         "components": [{"type": "card", "data": {
             "title": "关键举措", "items": ["强化 AI 感知壁垒", "国潮设计出圈", "渠道协同"]}}]},
    ]


def run_author(agent, presentation, out_dir, concurrency: int):
    _settings.PPT_DESIGN_CONCURRENCY = concurrency
    _settings.PPT_DESIGN_CONCURRENCY_MAX = max(concurrency, 6)
    _settings.PPT_DESIGN_RATE_PAUSE = 10
    out_dir.mkdir(parents=True, exist_ok=True)
    identity = cp.DeckIdentity(
        product_name="新国潮智能床垫", product_code="2026.08",
        theme_color=THEME["palette"]["accent"],
        muted_color=THEME["palette"]["muted"],
        text_color=THEME["palette"]["text"],
        bg_color=THEME["palette"]["bg"],
    )
    t0 = time.perf_counter()
    files, stats = agent._author_pages_v2(
        project_dir=out_dir, presentation=presentation, theme=THEME,
        design_spec=DESIGN_SPEC, images={}, identity=identity,
        cross_page_module=cp,
    )
    elapsed = time.perf_counter() - t0
    llm = _settings.PRESENTATION_LLM_MODEL
    return files, stats, elapsed, llm


def run_pipeline(project_dir: Path) -> Path | None:
    """finalize_svg + svg_to_pptx（与 agent._run 相同的调用方式）。

    svg_to_pptx 要求 spec_lock.md（agent._run 主流程会写，此处补最小版）。
    """
    lock = project_dir / "spec_lock.md"
    if not lock.is_file():
        lock.write_text(
            "<!-- ppt-master-schema: spec-lock/v1 -->\n"
            "# Execution Lock\n\n## canvas\n- viewBox: 0 0 1280 720\n- format: PPT 16:9\n\n"
            "## communication\n- primary_language: zh-CN\n- audience: 决策者与产品团队\n"
            "- objective: 完整传达产品论证（SCR）并驱动行动\n"
            "- core_message: 新国潮智能床垫 · AI 睡眠健康解决方案\n\n## mode\n- mode: custom\n\n"
            "## visual_style\n- visual_style: consulting-cyber-ivory-wine\n\n"
            "## colors\n- bg: #F7F6F0\n- surface: #FFFFFF\n- primary: #3D6491\n"
            "- accent: #3D6491\n- text: #111111\n- muted: #6F7275\n\n"
            "## typography\n- font_family: Noto Sans SC, Source Han Sans SC, PingFang SC, Microsoft YaHei, sans-serif\n"
            "- title: 26\n- body: 14\n"
            "- title_family: Noto Serif SC, Source Han Serif SC, Georgia, serif\n"
            "- body_family: Noto Sans SC, Source Han Sans SC, PingFang SC, Microsoft YaHei, sans-serif\n\n"
            "## icons\n- library: none\n- inventory: none\n\n"
            "## page_rhythm\n- P01: anchor\n- P02: dense\n- P03: dense\n"
            "- P04: dense\n- P05: dense\n- P06: dense\n",
            encoding="utf-8",
        )
    scripts = _ROOT / "agents" / "ppt-design-agent" / "vendor" / "ppt-master" / "scripts"
    python = sys.executable
    for script, args in (
        ("finalize_svg.py", [str(project_dir)]),
        ("svg_to_pptx.py", [str(project_dir), "-s", "final"]),
    ):
        proc = subprocess.run(
            [python, str(scripts / script), *args],
            capture_output=True, text=True, timeout=600, cwd=str(scripts),
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout)[-500:]
            print(f"[PIPELINE] {script} 失败: {detail}")
            return None
    exports = project_dir / "exports"
    candidates = list(exports.glob("*.pptx")) if exports.is_dir() else []
    if candidates:
        return max(candidates, key=lambda p: p.stat().st_mtime)
    return None


def main() -> None:
    skip_seq = "--skip-seq" in sys.argv  # 只跑并发（重试排除随机网络抖动后复测）
    agent = PptDesignAgent()
    presentation = {"theme": THEME, "pages": _pages()}
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    # 绝对路径：finalize/svg_to_pptx 以 scripts 目录为 cwd，相对路径会解析失败
    base = (Path("outputs/studio_assets/ppt_projects") / f"并发速度实测_{ts}").resolve()

    if not skip_seq:
        print(f"\n[RUN] 顺序（并发 1）…… 6 页真实 MiniMax-M3 调用")
        files_seq, st_seq, t_seq, model = run_author(agent, presentation, base / "seq", 1)
        print(f"[SEQ] 完成：{len(files_seq)} 页，耗时 {t_seq:.1f}s，"
              f"fallback={st_seq['fallbacks']} retries={st_seq['retries']}")
    else:
        model = _settings.PRESENTATION_LLM_MODEL

    print(f"\n[RUN] 并发 4 …… 6 页真实 MiniMax-M3 调用")
    files_con, st_con, t_con, _ = run_author(agent, presentation, base / "con", 4)
    print(f"[CON] 完成：{len(files_con)} 页，耗时 {t_con:.1f}s，"
          f"fallback={st_con['fallbacks']} retries={st_con['retries']}")

    print("\n" + "=" * 60)
    print(f"模型：{model}")
    if not skip_seq:
        print(f"顺序：{t_seq:.1f}s（{len(files_seq)} 页）  vs  并发 4：{t_con:.1f}s（{len(files_con)} 页）")
        print(f"提速比：{t_seq / t_con:.2f}×")
        print(f"fallback：seq={st_seq['fallbacks']} con={st_con['fallbacks']}（0 = 全部 LLM 创作）")
    else:
        print(f"并发 4：{t_con:.1f}s（{len(files_con)} 页）  fallback={st_con['fallbacks']} retries={st_con['retries']}")
    print("=" * 60)

    print("\n[PIPELINE] 对并发产物跑 finalize_svg + svg_to_pptx 全链路验证……")
    pptx = run_pipeline(base / "con")
    if pptx:
        print(f"[PIPELINE] ✅ PPTX 产出：{pptx.relative_to(BACKEND)}"
              f"（{pptx.stat().st_size / 1024:.0f} KB）")
    else:
        print("[PIPELINE] ❌ PPTX 产出失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
