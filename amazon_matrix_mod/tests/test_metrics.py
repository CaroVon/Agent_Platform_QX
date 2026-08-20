"""metrics 派生指标单测。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from amazon_matrix_mod import metrics  # noqa: E402


def test_parse_recent_sales_k():
    assert metrics.parse_recent_sales("3K+ bought in past month") == 3000
    assert metrics.parse_recent_sales("500+ bought in past month") == 500
    assert metrics.parse_recent_sales("1M+ bought") == 1000000


def test_parse_recent_sales_none():
    assert metrics.parse_recent_sales(None) is None
    assert metrics.parse_recent_sales("") is None
    assert metrics.parse_recent_sales("abc") is None


def test_est_sales_from_bsr():
    assert metrics.est_sales_from_bsr(10) == 3000
    assert metrics.est_sales_from_bsr(300) == 800
    assert metrics.est_sales_from_bsr(20000) == 20
    assert metrics.est_sales_from_bsr(None) is None


def test_derive_metrics_prefers_recent_sales():
    row = {"asin": "B0X", "recent_sales_raw": "5K+ bought in past month", "bsr": 9999}
    out = metrics.derive_metrics(row)
    assert out["est_monthly_sales"] == 5000


def test_derive_metrics_fallback_bsr():
    row = {"asin": "B0X", "recent_sales_raw": None, "bsr": 100}
    out = metrics.derive_metrics(row)
    assert out["est_monthly_sales"] == 1500


def test_derive_metrics_defaults():
    row = {"asin": "B0X"}
    out = metrics.derive_metrics(row)
    assert out["est_monthly_sales"] is None
    assert out["is_fba"] is False


def test_normalize_rating():
    assert metrics.normalize_rating(4.5) == 4.5
    assert metrics.normalize_rating(450) == 4.5
    assert metrics.normalize_rating(4500) == 4.5
    assert metrics.normalize_rating(None) is None
