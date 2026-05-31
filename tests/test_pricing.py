import pytest
from pipeline.pricing import default_pricing_settings, compute_price


def test_default_settings_have_required_keys():
    s = default_pricing_settings()
    for key in ("currency", "bw_per_page", "color_per_page",
                "paper_quality", "cover_cost", "markup_multiplier"):
        assert key in s
    assert "standard" in s["paper_quality"]


def test_compute_price_color_with_cover():
    s = {
        "currency": "USD",
        "bw_per_page": 0.012,
        "color_per_page": 0.07,
        "paper_quality": {"standard": 1.0, "premium": 1.5},
        "cover_cost": 1.00,
        "markup_multiplier": 2.5,
    }
    out = compute_price(page_count=16, color=True, paper_quality="standard",
                        has_cover=True, settings=s)
    assert out["currency"] == "USD"
    assert out["printing_cost"] == 2.12
    assert out["price"] == 5.30


def test_compute_price_bw_premium_no_cover():
    s = default_pricing_settings()
    s.update({"bw_per_page": 0.01, "paper_quality": {"premium": 2.0},
              "cover_cost": 0.5, "markup_multiplier": 2.0})
    out = compute_price(page_count=10, color=False, paper_quality="premium",
                        has_cover=False, settings=s)
    assert out["printing_cost"] == 0.20
    assert out["price"] == 0.40


def test_unknown_paper_quality_raises():
    with pytest.raises(ValueError):
        compute_price(8, True, "ultra", True, default_pricing_settings())
