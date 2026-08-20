"""
============================================================
Research Agent —— 市场研究 + 竞品分析
============================================================

输入: 产品想法（idea）
输出:
  - market_research:     MarketResearch     （market_size / competitors / pain_points / trends）
  - competitor_analysis: CompetitorAnalysis （竞品画像 / 对比矩阵 / 差异化机会）
"""

from __future__ import annotations

from typing import Any

from agent_platform.harness.agent_loop import BaseAgent
from agent_platform.memory.memory_store import MemoryStore
from agent_platform.schemas import (
    AgentResult,
    MarketResearch,
    CompetitorAnalysis,
    PriceCompetitorMatrix,
)

from agents.research_agent.prompts import (
    COMPETITOR_ANALYSIS_SYSTEM,
    COMPETITOR_MATRIX_SYSTEM,
    MARKET_RESEARCH_SYSTEM,
)


def _state_bool(state: dict, key: str, default: bool) -> bool:
    """state 布尔读取（缺省/空串/None → default）。"""
    v = state.get(key)
    if v is None or v == "":
        return default
    return bool(v)


class ResearchAgent(BaseAgent):
    """市场研究专家：搜索市场事实 → 结构化市场研究与竞品分析。"""

    name = "research_agent"
    description = "全网搜索市场信息，产出市场规模、竞品、用户痛点与行业趋势"
    output_schema = MarketResearch
    system_prompt = MARKET_RESEARCH_SYSTEM

    MAX_SOURCES = 40
    SEARCH_QUERIES_PER_ROUND = 8

    # ── 来源权重分类（报告类资料权重最高） ─────────────────────
    # 0.9  市场研究报告 / 权威咨询机构
    # 0.8  政府 / 学术 / 官方机构
    # 0.7  行业媒体 / 新闻
    # 0.65 公司官网 / 官方文档
    # 0.5  一般网站
    # 0.4  论坛 / 博客 / 百科 / 问答
    REPORT_DOMAINS = (
        "grandviewresearch.com", "statista.com", "mordorintelligence.com",
        "theinsightpartners.com", "gminsights.com", "marketresearchfuture.com",
        "businessresearchinsights.com", "wiseguyreports.com", "researchandmarkets.com",
        "marketsandmarkets.com", "fortunebusinessinsights.com", "technavio.com",
        "frost.com", "idc.com", "gartner.com", "deloitte.com", "pwc.com",
        "kpmg.com", "mckinsey.com", "bain.com", "bcg.com", "sigmaintell.com",
        "iresearch.cn", "askci.com", "qianzhan.com", "leadleo.com", "iyiou.com",
        "cbnresearch.com", "51report.com", "chinaso.com",
    )
    LOW_DOMAINS = (
        "zhihu.com", "baike.baidu.com", "wikipedia.org", "reddit.com",
        "quora.com", "csdn.net", "jianshu.com", "medium.com", "cnblogs.com",
        "weibo.com", "douban.com", "bilibili.com", "xiaohongshu.com",
        "zhuanlan.zhihu.com",
    )

    @classmethod
    def _score_source(cls, url: str, title: str = "") -> tuple[float, str]:
        """来源权重：返回 (分数, 标签)。报告类最高。"""
        u = (url or "").lower()
        t = (title or "").lower()
        if any(d in u for d in cls.REPORT_DOMAINS):
            return 0.9, "高（研究报告）"
        if any(x in u for x in (".gov", ".edu", ".org.cn", "gov.cn")):
            return 0.8, "高（官方机构）"
        if any(x in u for x in ("36kr.com", "huxiu.com", "tmtpost.com", "techcrunch.com",
                                "theverge.com", "jiemian.com", "latepost.com", "pandaily.com",
                                "tech.qq.com", "tech.sina.com", "163.com", "ifeng.com")):
            return 0.7, "中高（行业媒体）"
        if any(d in u for d in cls.LOW_DOMAINS):
            return 0.4, "低（社区/百科）"
        # 标题含报告/白皮书/研报关键词 → 中高
        if any(k in t for k in ("报告", "白皮书", "研报", "market report", "industry report",
                                "white paper", "research report")):
            return 0.75, "中高（报告类）"
        return 0.5, "中（一般网站）"

    @staticmethod
    def _weight_label(weight: float) -> str:
        if weight >= 0.8:
            return "高"
        if weight >= 0.6:
            return "中高"
        if weight >= 0.45:
            return "中"
        return "低"

    def _search_sources(self, idea: str, queries: list[str]) -> list[dict]:
        """真实检索：多查询 Tavily 搜索 → 去重来源列表（含权重，编号顺序即引用顺序）。"""
        from agent_platform.tools.search_tools import WebSearchTool

        tool = WebSearchTool()
        seen: set[str] = set()
        sources: list[dict] = []
        for q in queries:
            try:
                results = tool.run(q, max_results=8)
            except Exception:  # noqa: BLE001 —— 搜索失败降级为空来源
                results = []
            for r in results:
                url = (r.url or "").strip()
                if not url or url in seen:
                    continue
                seen.add(url)
                weight, detail = self._score_source(url, r.title)
                sources.append({
                    "title": r.title,
                    "url": url,
                    "content": (r.content or "")[:300],
                    "weight": weight,
                    "weight_label": self._weight_label(weight),
                    "weight_detail": detail,
                    "selected": True,
                })
                if len(sources) >= self.MAX_SOURCES:
                    return sources
        return sources

    def gather_sources(self, idea: str, queries: list[str] | None = None) -> dict:
        """资料搜集（供 source_gathering 节点调用）：搜索 → 权重标注 → 待用户审核。"""
        queries = queries or [
            f"{idea} 市场规模 行业报告",
            f"{idea} 竞品 主要品牌 产品",
            f"{idea} 行业趋势 用户需求",
            f"{idea} 目标用户 痛点 场景",
            f"{idea} 产品评测 对比",
            f"{idea} 市场 份额 增长",
            f"{idea} 商业模式 定价",
            f"{idea} 政策 标准 认证",
        ]
        sources = self._search_sources(idea, queries)
        return {
            "sources": sources,
            "total": len(sources),
            "selected": sum(1 for s in sources if s.get("selected")),
        }

    @staticmethod
    def _render_sources(sources: list[dict]) -> str:
        """编号参考资料块：模型只能引用其中的 [编号]。"""
        if not sources:
            return "（检索未返回可用来源：所有数据必须标注'估算'，禁止编造来源）"
        return "\n".join(
            f"[{i + 1}] {s['title']} | {s['url']}\n    {s['content']}"
            for i, s in enumerate(sources)
        )

    def research_market(self, idea: str, memory: MemoryStore | None = None, memory_namespace: str = "default", instruction: str = "", sources: list[dict] | None = None) -> AgentResult:
        """市场研究：真实检索（或使用用户审核后的资料）+ 综合 → MarketResearch。

        sources 传入时（source_gathering 节点审核后）只使用该列表；
        为 None 时自行搜索（重生成路径）。
        """
        if sources is None:
            sources = self._search_sources(idea, queries=[
                f"{idea} 市场规模 行业报告",
                f"{idea} 竞品 主要品牌",
                f"{idea} 行业趋势 用户需求",
                f"{idea} 目标用户 痛点",
            ])
        objective = (
            f"对产品想法「{idea}」进行市场研究。"
            "调研市场规模与增长、主要竞品、目标用户痛点与行业趋势，"
            "每个结论尽量给出具体数据与依据。"
        )
        if instruction:
            objective += f"\n\n【本次修订要求】{instruction}"
        result = self.loop.run(
            agent_name=self.name,
            system_prompt=MARKET_RESEARCH_SYSTEM,
            objective=objective,
            schema=MarketResearch,
            inputs={
                "idea": idea,
                "参考资料（编号来源，仅允许引用其中内容并标注 [编号]）": self._render_sources(sources),
            },
            memory_namespace=memory_namespace,
        )

        # 确定性兜底：source 缺失时回填第一个真实来源 URL，保证可溯源
        if result.success and sources:
            data = result.data or {}
            ms = data.get("market_size") or {}
            if not ms.get("source"):
                ms["source"] = sources[0]["url"]
                data["market_size"] = ms
            if not data.get("sources"):
                data["sources"] = [
                    {"url": s["url"], "title": s.get("title", ""), "weight": s.get("weight", 0.5)}
                    for s in sources[:5]
                ]
            result.data = data
        return result

    def analyze_competitors(
        self,
        idea: str,
        market_research: MarketResearch,
        memory: MemoryStore | None = None,
        memory_namespace: str = "default",
        instruction: str = "",
        sources: list[dict] | None = None,
    ) -> AgentResult:
        """竞品分析：基于市场研究 → CompetitorAnalysis。"""
        objective = (
            f"基于产品想法「{idea}」的市场研究成果，产出深度竞品分析："
            "为每个主要竞品建立画像（定位/目标客群/定价/优劣势/威胁等级），"
            "构建对比矩阵，并指出我方可切入的差异化机会。"
        )
        if instruction:
            objective += f"\n\n【本次修订要求】{instruction}"
        if sources is None:
            sources = self._search_sources(idea, queries=[
                f"{idea} 竞品 评测 定价",
                f"{idea} 竞品分析 市场份额",
            ])
        result = self.loop.run(
            agent_name="competitor_analysis_agent",
            system_prompt=COMPETITOR_ANALYSIS_SYSTEM,
            objective=objective,
            schema=CompetitorAnalysis,
            inputs={
                "idea": idea,
                "参考资料（编号来源，仅允许引用其中内容并标注 [编号]）": self._render_sources(sources),
            },
            artifacts={"market_research": market_research},
            memory_namespace=memory_namespace,
        )
        return result

    def analyze_competitor_matrix(
        self,
        idea: str,
        market_research: MarketResearch,
        our_asin: str | None = None,
        product_id: str | None = None,
        top_n: int = 50,
        skip_llm: bool = False,
        source: str = "rainforest",
        full: bool = True,
        with_visuals: bool = True,
        theme_id: str | None = None,
        memory: MemoryStore | None = None,
        memory_namespace: str = "default",
    ) -> AgentResult:
        """数据驱动竞品矩阵（MOD）：基于市场研究 → 关键词 → Rainforest 采集 →
        4 区规则 → LLM 解读 → 矩阵图/CSV/MD 落盘 →（full）14 章 + M3 + PPT。

        上游：market_research（必填）
        输出：PriceCompetitorMatrix artifact + studio_assets/{product_id}/competitor_matrix/
              （full 时含 competitor_matrix.pptx / deck_audit.json）
        说明：本节点为确定性数据管道（不经过 LLM 生成循环），LLM 仅做 4 区解读；
              解读失败即报错（已确认策略，不降级）。PPT 构建失败降级为 md+SVG。
        """
        keyword = (getattr(market_research, "keyword", None) or idea or "").strip()
        if not keyword:
            return AgentResult(success=False, error="缺少主关键词（idea 或 state.keyword 为空）")
        market_context = ""
        if market_research.market_size:
            market_context = market_research.market_size.summary or ""
        try:
            from amazon_matrix_mod.run_mod import run_pipeline

            data = run_pipeline(
                keyword=keyword,
                top_n=top_n,
                our_asin=our_asin,
                product_id=product_id,
                market_context=market_context,
                skip_llm=skip_llm,
                source=source,
                full=full,
                with_visuals=with_visuals,
                theme_id=theme_id,
            )
            PriceCompetitorMatrix.model_validate(data)
            return AgentResult(success=True, data=data)
        except Exception as exc:  # noqa: BLE001 —— 失败即报错（节点层重试 2 次后 failed）
            return AgentResult(success=False, error=f"竞品矩阵管道失败: {exc}")

    def execute(
        self,
        task: str,
        state: dict[str, Any],
        memory: MemoryStore | None = None,
        memory_namespace: str = "default",
    ) -> AgentResult:
        """工作流统一入口：按任务名分派。"""
        idea = state.get("idea", "")
        if task == "market_research":
            return self.research_market(
                idea,
                memory=memory,
                memory_namespace=memory_namespace,
                instruction=str(state.get("instruction") or ""),
                sources=state.get("_approved_sources"),
            )

        if task == "competitor_matrix":
            research_data = state.get("research")
            research = (
                MarketResearch.model_validate(research_data)
                if research_data is not None
                else None
            )
            if research is None:
                return AgentResult(success=False, error="缺少上游市场研究成果")
            return self.analyze_competitor_matrix(
                idea,
                research,
                our_asin=state.get("our_asin"),
                product_id=state.get("product_id"),
                # 抓取量默认 20（search 1 + product 20 ≈ 21 credits；
                # state.top_n / 环境变量 MOD_TOP_N 可覆盖）
                top_n=int(state.get("top_n") or 20),
                skip_llm=bool(state.get("skip_llm")),
                source=str(state.get("source") or "rainforest"),
                full=_state_bool(state, "mod_full", True),
                with_visuals=_state_bool(state, "mod_visuals", True),
                theme_id=state.get("ppt_theme") or None,
                memory=memory,
                memory_namespace=memory_namespace,
            )

        if task == "competitor_analysis":
            research_data = state.get("research")
            research = (
                MarketResearch.model_validate(research_data)
                if research_data is not None
                else None
            )
            if research is None:
                return AgentResult(success=False, error="缺少上游市场研究成果")
            return self.analyze_competitors(
                idea,
                research,
                memory=memory,
                memory_namespace=memory_namespace,
                instruction=str(state.get("instruction") or ""),
                sources=state.get("_approved_sources"),
            )

        return AgentResult(success=False, error=f"未知任务: {task}")
