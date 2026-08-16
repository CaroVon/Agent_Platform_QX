"""
CyberPPT 证据包构建器测试 —— 上游语义层 → 证据表/关键数字/SCR 提示
"""

import pytest

from agent_platform.harness.evidence_pack import (
    DENSITY_BUDGET,
    build_evidence_pack,
    render_evidence_pack,
)
from agent_platform.schemas.design import UXDesign
from agent_platform.schemas.product import ProductStrategy
from agent_platform.schemas.product_document import ProductDocument, ProjectInfo
from agent_platform.schemas.research import (
    CompetitorAnalysis,
    CompetitorProfile,
    MarketResearch,
    MarketSize,
)


def _document() -> ProductDocument:
    return ProductDocument(
        project_info=ProjectInfo(idea="AI 健身应用"),
        research=MarketResearch(
            market_size=MarketSize(
                summary="百亿健身市场高速增长",
                tam="500亿",
                sam="200亿",
                som="20亿",
                cagr="30%",
                source="艾媒咨询",
            ),
            competitors=[{"name": "Keep", "positioning": "大众健身"}],
            customer_pain_points=["不会安排训练计划", "缺乏坚持动力"],
            industry_trends=["AI 教练化", "家庭健身设备智能化"],
        ),
        competitor_analysis=CompetitorAnalysis(
            competitive_landscape="头部集中",
            competitors=[
                CompetitorProfile(name="Keep", positioning="大众健身", strengths=["用户量大"], weaknesses=["个性化弱"])
            ],
            differentiation_opportunities=["AI 个性化计划"],
        ),
        strategy=ProductStrategy(
            positioning="AI 私教",
            personas=[{"name": "小雅", "role": "新手", "goals": ["坚持训练"], "pain_points": ["不会安排"]}],
            features=[{"name": "智能计划", "description": "自动生成训练计划"}],
            roadmap=[{"phase": "Phase 1", "title": "MVP", "milestones": ["上线核心功能"]}],
        ),
        design=UXDesign(user_flow=[{"step": "注册", "description": "创建账号"}]),
    )


def test_build_evidence_pack_structure():
    pack = build_evidence_pack(_document())
    assert pack["key_numbers"]
    assert any(n["metric"] == "TAM" and n["value"] == "500亿" for n in pack["key_numbers"])
    table = pack["evidence_table"]
    assert table
    assert table[0]["id"].startswith("E")
    assert table[0]["source"]
    hints = pack["narrative_hints"]
    assert hints["situation"].startswith("市场现状")
    assert hints["complication"]
    assert hints["resolution"].startswith("解法")
    assert pack["density_budget"] == DENSITY_BUDGET


def test_evidence_ids_unique_and_ordered():
    pack = build_evidence_pack(_document())
    ids = [e["id"] for e in pack["evidence_table"]]
    assert len(ids) == len(set(ids))
    assert ids == [f"E{i:03d}" for i in range(1, len(ids) + 1)]


def test_render_evidence_pack_contains_scaffolding():
    pack = build_evidence_pack(_document())
    text = render_evidence_pack(pack)
    assert "SCR 叙事提示" in text
    assert "SITUATION:" in text and "COMPLICATION:" in text and "RESOLUTION:" in text
    assert "关键数字" in text
    assert "TAM=500亿" in text
    assert "E001" in text
    assert "每页组件预算" in text


def test_build_evidence_pack_empty_document():
    pack = build_evidence_pack(None)
    assert pack["evidence_table"] == []
    assert pack["key_numbers"] == []
    assert pack["narrative_hints"]["resolution"] == ""
    assert pack["density_budget"] == DENSITY_BUDGET


@pytest.mark.parametrize("long_text", ["x" * 500])
def test_clip_truncates_long_claims(long_text):
    from agent_platform.harness.evidence_pack import _clip

    assert len(_clip(long_text)) <= 80
