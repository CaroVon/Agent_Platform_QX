"""统一采集层（collect_amazon_data）与 0-credit 回放测试（mock 源，离线）。"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

_SYS_ROOT = Path(__file__).resolve().parents[2]
for p in (str(_SYS_ROOT), str(_SYS_ROOT / "agent-platform")):
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ.setdefault("DEEPSEEK_API_KEY", "sk-test")

from amazon_matrix_mod.run_mod import collect_amazon_data, run_pipeline  # noqa: E402


@pytest.fixture()
def collected(tmp_path):
    out = str(tmp_path / "mod_test")
    summary, payload = collect_amazon_data(
        keyword="wireless mouse", top_n=10, source="mock", out_dir=out)
    return summary, payload, out


def test_collect_summary_structure(collected):
    summary, payload, out = collected
    assert summary["n_products"] == len(payload["rows"]) > 0
    assert summary["source"] == "mock"
    assert summary["price_range"]["min"] <= summary["price_range"]["max"]
    assert summary["credits"] == 1 + summary["n_products"]
    assert 0 < len(summary["top_asins"]) <= 8
    assert os.path.isdir(summary["data_dir"])
    # 归档层：manifest + rows.json（mock 无 raw products）
    assert os.path.isfile(os.path.join(summary["data_dir"], "manifest.json"))
    assert os.path.isfile(os.path.join(summary["data_dir"], "rows.json"))


def test_replay_zero_credit_and_provenance(collected):
    summary, _payload, out = collected
    result = run_pipeline(
        keyword="wireless mouse", source="mock", skip_llm=True,
        reuse=[summary["data_dir"]], out_dir=out)
    # 0-credit 回放：credits 与 fetched_at 从归档 manifest 还原（数据溯源一致）
    assert result["cost_estimate"]["rainforest_credits"] == summary["credits"]
    assert result["fetched_at"] == summary["fetched_at"]
    assert len(result["products"]) == summary["n_products"]
    # 关键产物落盘
    for key in ("markdown", "csv", "matrix_chart", "zoning"):
        assert result["artifacts_paths"].get(key), f"缺少产物 {key}"


def test_mod_charts_rendered(collected):
    summary, _payload, out = collected
    result = run_pipeline(
        keyword="wireless mouse", source="mock", skip_llm=True,
        reuse=[summary["data_dir"]], out_dir=out)
    charts = result.get("mod_charts") or {}
    # 7 个确定性组件全部渲染（无 Playwright 时为 SVG 形态）
    assert set(charts) == {
        "market_donut", "demand_bars", "price_bands", "zone_grid",
        "matrix_scatter", "spec_matrix", "sku_channels",
    }
    for name, meta in charts.items():
        assert meta.get("svg") or meta.get("png"), f"{name} 无图表文件"
        svg_path = os.path.join(out, meta.get("png") or meta.get("svg"))
        assert os.path.isfile(svg_path) and os.path.getsize(svg_path) > 500
    index_path = os.path.join(out, "charts", "charts_index.json")
    assert json.load(open(index_path, encoding="utf-8"))["charts"]
