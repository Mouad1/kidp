import json
import pytest
from storyforge.templates import (
    parse_template, validate_template, extract_tokens,
)
from storyforge.errors import TemplateError

VALID = {
    "name": "Explorer",
    "mode": "color",
    "language_default": "fr",
    "art_style": "watercolor",
    "variables": [
        {"key": "HERO_NAME", "label": "Name", "type": "text"},
        {"key": "SETTING", "label": "World", "type": "select",
         "options": ["forest", "space"]},
    ],
    "pages": [
        {"beat": "intro", "text": "{HERO_NAME} in {SETTING}",
         "image_prompt": "{HERO} in {SETTING}"},
    ],
}


def test_parse_valid_template():
    tpl = parse_template(VALID, slug="explorer")
    assert tpl.name == "Explorer"
    assert tpl.slug == "explorer"
    assert tpl.variables[1].options == ["forest", "space"]


def test_extract_tokens_finds_all_braced_tokens():
    assert extract_tokens("{HERO} meets {SETTING}") == {"HERO", "SETTING"}


def test_invalid_mode_rejected():
    bad = {**VALID, "mode": "rainbow"}
    with pytest.raises(TemplateError, match="mode"):
        validate_template(parse_template(bad, slug="x"))


def test_undeclared_token_rejected():
    bad = json.loads(json.dumps(VALID))
    bad["pages"][0]["text"] = "{UNDECLARED} appears"
    with pytest.raises(TemplateError, match="UNDECLARED"):
        validate_template(parse_template(bad, slug="x"))


def test_empty_pages_rejected():
    bad = {**VALID, "pages": []}
    with pytest.raises(TemplateError, match="pages"):
        validate_template(parse_template(bad, slug="x"))


def test_select_without_options_rejected():
    bad = json.loads(json.dumps(VALID))
    bad["variables"][1]["options"] = []
    with pytest.raises(TemplateError, match="options"):
        validate_template(parse_template(bad, slug="x"))
