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
