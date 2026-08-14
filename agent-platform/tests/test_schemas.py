"""Schema 契约测试 —— 校验各 Agent 输出模型的结构约束。"""

import pytest
from pydantic import ValidationError

from agent_platform.schemas import (
    CompetitorAnalysis,
    MarketResearch,
    ProductAssetPackage,
    ProductStrategy,
    SlideDeck,
    UXDesign,
)
from agent_platform.schemas.requirement import RequirementSpec
from agent_platform.schemas.presentation import Slide, SlideBlock


def test_market_research_minimal():
    mr = MarketResearch.model_validate(
        {"market_size": {"summary": "百亿市场"}, "competitors": [], "customer_pain_points": [], "industry_trends": []}
    )
    assert mr.market_size.summary == "百亿市场"
    assert mr.competitors == []


def test_market_research_requires_market_size():
    with pytest.raises(ValidationError):
        MarketResearch.model_validate({"competitors": [], "customer_pain_points": [], "industry_trends": []})


def test_product_strategy_roundtrip():
    data = {
        "positioning": "AI 驱动的健身教练",
        "personas": [
            {"name": "小雅", "role": "健身新手", "goals": ["减脂"], "pain_points": ["不会安排计划"]}
        ],
        "features": [{"name": "智能计划", "priority": "P0"}],
        "roadmap": [{"phase": "Phase 1", "title": "MVP", "milestones": ["上线"]}],
        "prd_sections": [{"title": "产品概述", "content": "## 概述\n正文"}],
    }
    ps = ProductStrategy.model_validate(data)
    assert ps.personas[0].name == "小雅"
    assert ps.features[0].priority == "P0"
    # 序列化往返保持稳定（前端渲染的数据契约）
    assert ProductStrategy.model_validate(ps.model_dump()) == ps


def test_feature_priority_enum_enforced():
    with pytest.raises(ValidationError):
        ProductStrategy.model_validate({"positioning": "x", "features": [{"name": "a", "priority": "P9"}]})


def test_ux_design_minimal():
    ux = UXDesign.model_validate({"user_flow": [], "pages": [], "components": []})
    assert ux.user_flow == []


def test_slide_deck_structure():
    deck = SlideDeck.model_validate(
        {
            "topic": "AI 健身应用",
            "slides": [
                {
                    "id": "s1",
                    "title": "封面",
                    "layout_type": "cover",
                    "blocks": [
                        {"id": "b1", "block_type": "title", "content": "AI 健身应用", "emphasis": "high"}
                    ],
                    "visual_metadata": {"hero": "title"},
                }
            ],
            "sections": [{"title": "市场分析", "slide_ids": ["s1"]}],
        }
    )
    assert deck.slides[0].layout_type == "cover"
    assert deck.slides[0].blocks[0].emphasis == "high"
    assert deck.sections[0].slide_ids == ["s1"]


def test_slide_invalid_layout_rejected():
    with pytest.raises(ValidationError):
        Slide.model_validate({"id": "s1", "title": "x", "layout_type": "3d_rotate"})


def test_asset_package_with_partial_results():
    """部分节点失败时资产包仍可构建（null 字段允许）。"""
    pkg = ProductAssetPackage.model_validate(
        {
            "idea": "AI 健身应用",
            "requirement": {"idea": "AI 健身应用", "goals": ["g"]},
            "research": None,
            "strategy": None,
            "design": None,
            "presentation": None,
            "meta": {
                "idea": "AI 健身应用",
                "created_at": "2026-01-01T00:00:00+00:00",
                "node_status": {"research": "failed"},
                "errors": {"research": "boom"},
            },
        }
    )
    assert pkg.research is None
    assert pkg.meta.node_status["research"] == "failed"


def test_requirement_spec_defaults():
    req = RequirementSpec.model_validate({"idea": "AI 教育助手"})
    assert req.goals == []
    assert req.target_users == []
