# tests/test_tag_gallery.py
import pytest
from pipeline.generate_tag_examples import slugify, CATEGORY_TAGS

def test_slugify_basic():
    assert slugify("thick outlines") == "thick_outlines"

def test_slugify_special_chars():
    assert slugify("Art Nouveau") == "art_nouveau"
    assert slugify("Mandala-infused") == "mandala_infused"

def test_category_tags_has_all_categories():
    assert set(CATEGORY_TAGS.keys()) == {"style", "pose", "elements", "theme"}

def test_category_tags_nonempty():
    for cat, tags in CATEGORY_TAGS.items():
        assert len(tags) > 0, f"Category {cat!r} is empty"


def test_refine_prompt_script_exists():
    """Script must be importable and have a run() function."""
    from pipeline import refine_prompt
    assert callable(refine_prompt.run)


def _make_client():
    from dashboard.app import app
    from fastapi.testclient import TestClient
    return TestClient(app)

def test_prompt_tags_returns_examples_key():
    """Extended /api/prompt/tags must include *_examples keys."""
    client = _make_client()
    resp = client.get("/api/prompt/tags")
    assert resp.status_code == 200
    data = resp.json()
    assert "style" in data
    assert "style_examples" in data
    assert "pose_examples" in data
    assert "elements_examples" in data
    assert "theme_examples" in data

def test_prompt_tags_examples_are_url_strings():
    client = _make_client()
    data = client.get("/api/prompt/tags").json()
    for slug, url in data["style_examples"].items():
        assert url.startswith("/assets/tag_examples/style/")
        assert url.endswith(".png")

def test_feedback_endpoint_missing_key_returns_422():
    client = _make_client()
    resp = client.post("/api/feedback/book1-90s-legends", json={"feedback": "too static"})
    assert resp.status_code == 422  # missing current_prompt and page_ref
