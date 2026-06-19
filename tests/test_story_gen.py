"""Tests pour pipeline/story_gen.py — generate_from_source."""
from pipeline.story_gen import generate_from_source


def _fake_gemini(source_text, page_count):
    return {
        "story_base_prompt": "watercolor illustration",
        "default_character_description": "young girl, brown curly hair, olive skin",
        "intro_text": "Une belle aventure",
        "values_learned": "- Courage",
        "pages": [
            {
                "page_number": i + 1,
                "text": {"fr": f"Page {i+1}", "ar": "", "en": f"Page {i+1}", "es": ""},
                "moral": "",
                "image_prompt": f"Scene {i+1}, {{HERO}} standing in a meadow",
            }
            for i in range(page_count)
        ],
    }


def test_generate_from_text_returns_pages(monkeypatch):
    monkeypatch.setattr("pipeline.story_gen._call_gemini", _fake_gemini)
    result = generate_from_source("Une histoire de courage", page_count=3)
    assert len(result["pages"]) == 3
    assert result["story_base_prompt"] == "watercolor illustration"


def test_default_character_description_extracted(monkeypatch):
    monkeypatch.setattr("pipeline.story_gen._call_gemini", _fake_gemini)
    result = generate_from_source("Une histoire", page_count=2)
    assert result["default_character_description"] == "young girl, brown curly hair, olive skin"


def test_hero_placeholder_in_template_prompts(monkeypatch):
    monkeypatch.setattr("pipeline.story_gen._call_gemini", _fake_gemini)
    result = generate_from_source("Une histoire", page_count=2)
    for page in result["pages"]:
        assert "{HERO}" in page["image_prompt"]


def test_config_prompts_have_substituted_hero(monkeypatch):
    monkeypatch.setattr("pipeline.story_gen._call_gemini", _fake_gemini)
    result = generate_from_source("Une histoire", page_count=2)
    char_desc = result["default_character_description"]
    for page in result["config_pages"]:
        assert "{HERO}" not in page["image_prompt"]
        assert char_desc in page["image_prompt"]


def test_url_passthrough(monkeypatch):
    captured = {}

    def fake(source_text, page_count):
        captured["source"] = source_text
        return _fake_gemini(source_text, page_count)

    monkeypatch.setattr("pipeline.story_gen._call_gemini", fake)
    generate_from_source("https://youtube.com/watch?v=abc123", page_count=2)
    assert "youtube.com" in captured["source"]
