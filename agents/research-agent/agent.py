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

import os
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

    def collect_amazon_sources(self, keyword: str, product_id: str | None = None,
                               top_n: int = 20, source: str = "rainforest") -> dict:
        """亚马逊采集（供 source_gathering 节点调用）：统一采集入口 → 共享数据层归档。

        返回轻量摘要（top ASIN/价格带/分区分布/data_dir）；后续 competitor_matrix
        节点以 reuse=[data_dir] 0-credit 回放，两条分支共用同一份原始数据。
        """
        from amazon_matrix_mod.run_mod import collect_amazon_data

        summary, _payload = collect_amazon_data(
            keyword=keyword, top_n=top_n, source=source, product_id=product_id)
        return summary

    @staticmethod
    def _market_research_system() -> str:
        """市场研究 system prompt + 亚马逊产品研究 skill（P3 注入）。"""
        from agent_platform.skills.loader import SkillLoader

        return SkillLoader().render_into(
            "amazon-product-research", MARKET_RESEARCH_SYSTEM,
            marker="【亚马逊产品研究 Skill（方法论参考；来源引用仍以本次参考资料为准）】")

    @staticmethod
    def _competitor_analysis_system() -> str:
        """竞品分析 system prompt + 亚马逊竞品分析 skill（P3 注入）。"""
        from agent_platform.skills.loader import SkillLoader

        return SkillLoader().render_into(
            "amazon-competitor-analysis", COMPETITOR_ANALYSIS_SYSTEM,
            marker="【亚马逊竞品分析 Skill（拆解/对比矩阵方法论）】")

    @staticmethod
    def _render_amazon_block(amazon: dict | None) -> str:
        """亚马逊实时数据块（统一采集层摘要 → 编号化参考资料，供研究/竞品分析引用）。"""
        if not amazon:
            return "（本次未采集亚马逊数据）"
        if amazon.get("error"):
            return f"（亚马逊采集失败：{amazon['error']}）"
        pr = amazon.get("price_range") or {}
        lines = [
            f"- 主关键词：{amazon.get('keyword')} ｜ 站点：{amazon.get('marketplace')}",
            f"- 样本量：{amazon.get('n_products')} 个竞品 ASIN ｜ 采集时间：{amazon.get('fetched_at')}"
            f"（来源：{amazon.get('source')} API，credits≈{amazon.get('credits')}）",
            f"- 价格带：${pr.get('min')} – ${pr.get('max')}（均价 ${pr.get('avg')}）"
            f" ｜ 平均评分：{amazon.get('rating_avg')}",
            f"- 分区分布：{amazon.get('zone_counts')} ｜ 评论样本：{amazon.get('reviews_count')} 条",
            "",
            "Top 销量竞品（真实数据，标注 [A编号] 引用）：",
        ]
        for i, t in enumerate(amazon.get("top_asins") or [], 1):
            lines.append(
                f"[A{i}] {t.get('brand') or '—'} | {t.get('title', '')[:60]} | "
                f"${t.get('current_price')} | 评分 {t.get('rating')} | "
                f"评论 {t.get('review_count')} | 月销≈{t.get('est_monthly_sales')} | "
                f"BSR {t.get('bsr')} | 分区 {t.get('zone')}"
            )
        return "\n".join(lines)

    @staticmethod
    def _compact_matrix(matrix: dict | None) -> dict:
        """竞品矩阵 → 竞品分析可消费的紧凑视图（去重列表，保留洞察与头部样本）。"""
        if not matrix:
            return {}
        products = matrix.get("products") or []
        zone_counts: dict[str, int] = {}
        for p in products:
            z = str(p.get("zone") or "neutral")
            zone_counts[z] = zone_counts.get(z, 0) + 1
        full = matrix.get("full") or {}
        compact = {
            "keyword": matrix.get("keyword"),
            "n_products": len(products),
            "zoning_rules": matrix.get("zoning_rules") or {},
            "llm_interpretation": matrix.get("llm_interpretation") or {},
            "zone_counts": zone_counts,
            "top_products": sorted(
                products, key=lambda p: -(p.get("est_monthly_sales") or 0))[:8],
            "executive_summary": full.get("executive_summary") or "",
            "review_insights": (full.get("m3_insights") or {}).get("insights") or [],
        }
        return {k: v for k, v in compact.items() if v not in ("", None, {}, [])}

    @staticmethod
    def _render_sources(sources: list[dict]) -> str:
        """编号参考资料块：模型只能引用其中的 [编号]。"""
        if not sources:
            return "（检索未返回可用来源：所有数据必须标注'估算'，禁止编造来源）"
        return "\n".join(
            f"[{i + 1}] {s['title']} | {s['url']}\n    {s['content']}"
            for i, s in enumerate(sources)
        )

    def research_market(self, idea: str, memory: MemoryStore | None = None, memory_namespace: str = "default", instruction: str = "", sources: list[dict] | None = None, amazon_collection: dict | None = None) -> AgentResult:
        """市场研究：真实检索（或使用用户审核后的资料）+ 亚马逊实时数据 + 综合 → MarketResearch。

        sources 传入时（source_gathering 节点审核后）只使用该列表；
        为 None 时自行搜索（重生成路径）。
        amazon_collection 为统一采集层的亚马逊摘要（B/C 共享数据），落地真实价格/销量。
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
        if amazon_collection and not amazon_collection.get("error"):
            objective += (
                "\n\n【亚马逊实时数据（已采集，真实价格/销量，引用标注 [A编号]）】"
                "竞品定价与销量结论必须优先采用该数据；网络资料覆盖不到的亚马逊事实"
                "（如具体月销、BSR）以本数据为准。"
            )
        if instruction:
            objective += f"\n\n【本次修订要求】{instruction}"
        inputs = {
            "idea": idea,
            "参考资料（编号来源，仅允许引用其中内容并标注 [编号]）": self._render_sources(sources),
        }
        if amazon_collection is not None:
            inputs["亚马逊实时数据（统一采集层，真实数据）"] = self._render_amazon_block(amazon_collection)
        result = self.loop.run(
            agent_name=self.name,
            system_prompt=self._market_research_system(),
            objective=objective,
            schema=MarketResearch,
            inputs=inputs,
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
        # 确定性回填：keyword 缺失时对齐统一采集关键词（矩阵/演示引用口径一致）
        if result.success and amazon_collection:
            data = result.data or {}
            if not (data.get("keyword") or "").strip():
                data["keyword"] = str(amazon_collection.get("keyword") or "")
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
        competitor_matrix: dict | None = None,
        amazon_collection: dict | None = None,
    ) -> AgentResult:
        """竞品分析：基于市场研究 + 亚马逊竞品矩阵（真实数据）→ CompetitorAnalysis。

        competitor_matrix 为 MOD 节点产物（分区/解读/评论洞察/Top ASIN）；
        与网络资料双源交叉验证。
        """
        objective = (
            f"基于产品想法「{idea}」的市场研究成果，产出深度竞品分析："
            "为每个主要竞品建立画像（定位/目标客群/定价/优劣势/威胁等级），"
            "构建对比矩阵，并指出我方可切入的差异化机会。"
        )
        if competitor_matrix or (amazon_collection and not amazon_collection.get("error")):
            objective += (
                "\n\n【双源要求】本次同时提供「网络资料」与「亚马逊竞品矩阵（真实采集数据）」："
                "竞品的定价/销量/评分等硬数据必须以亚马逊矩阵为准（引用 [A编号] 或分区名）；"
                "网络资料用于定位/客群/战略动因等定性信息。两者冲突时以亚马逊数据为准并指出差异。"
            )
        if instruction:
            objective += f"\n\n【本次修订要求】{instruction}"
        if sources is None:
            sources = self._search_sources(idea, queries=[
                f"{idea} 竞品 评测 定价",
                f"{idea} 竞品分析 市场份额",
            ])
        inputs = {
            "idea": idea,
            "参考资料（编号来源，仅允许引用其中内容并标注 [编号]）": self._render_sources(sources),
        }
        if amazon_collection is not None:
            inputs["亚马逊实时数据（统一采集层，真实数据）"] = self._render_amazon_block(amazon_collection)
        artifacts = {"market_research": market_research}
        if competitor_matrix:
            artifacts["amazon_competitor_matrix（真实采集：分区规则/四区解读/评论洞察/Top竞品）"] = \
                self._compact_matrix(competitor_matrix)
        result = self.loop.run(
            agent_name="competitor_analysis_agent",
            system_prompt=self._competitor_analysis_system(),
            objective=objective,
            schema=CompetitorAnalysis,
            inputs=inputs,
            artifacts=artifacts,
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
        reuse_data_dir: str | None = None,
        archive_keyword: str | None = None,
        memory: MemoryStore | None = None,
        memory_namespace: str = "default",
    ) -> AgentResult:
        """数据驱动竞品矩阵（MOD）：共享数据层回放（或现场采集）→
        4 区规则 → LLM 解读 → 矩阵图/CSV/MD 落盘 →（full）14 章 + M3 + PPT。

        上游：market_research（必填）；amazon_collection（可选，统一采集层）
        输出：PriceCompetitorMatrix artifact + studio_assets/{product_id}/competitor_matrix/
              （full 时含 competitor_matrix.pptx / deck_audit.json）
        说明：本节点为确定性数据管道（不经过 LLM 生成循环），LLM 仅做 4 区解读；
              解读失败即报错（已确认策略，不降级）。PPT 构建失败降级为 md+SVG。
        """
        # 数据一致性：优先使用统一采集层的关键词与归档（0-credit 回放）
        keyword = (archive_keyword
                   or getattr(market_research, "keyword", None)
                   or idea or "").strip()
        if not keyword:
            return AgentResult(success=False, error="缺少主关键词（idea 或 state.keyword 为空）")
        market_context = ""
        if market_research.market_size:
            market_context = market_research.market_size.summary or ""
        try:
            from amazon_matrix_mod.run_mod import run_pipeline

            reuse = [reuse_data_dir] if reuse_data_dir and os.path.isdir(reuse_data_dir) else None
            if reuse:
                print(f"[矩阵] 回放统一采集层归档（0 credit）：{reuse_data_dir}")
            data = run_pipeline(
                keyword=keyword,
                top_n=top_n,
                our_asin=our_asin,
                product_id=product_id,
                market_context=market_context,
                skip_llm=skip_llm,
                source=source,
                reuse=reuse,
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
        amazon = state.get("amazon_collection") or None
        if task == "market_research":
            return self.research_market(
                idea,
                memory=memory,
                memory_namespace=memory_namespace,
                instruction=str(state.get("instruction") or ""),
                sources=state.get("_approved_sources"),
                amazon_collection=amazon,
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
            # 统一采集层回放：亚马逊数据已在 source_gathering 归档（0 credit）
            reuse_dir = None
            archive_keyword = None
            if amazon and amazon.get("data_dir"):
                candidate = str(amazon["data_dir"])
                if os.path.isdir(candidate):
                    reuse_dir = candidate
                    archive_keyword = str(amazon.get("keyword") or "") or None
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
                reuse_data_dir=reuse_dir,
                archive_keyword=archive_keyword,
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
                competitor_matrix=state.get("competitor_matrix"),
                amazon_collection=amazon,
            )

        return AgentResult(success=False, error=f"未知任务: {task}")
