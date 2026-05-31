import pytest
from storyforge.types import Template, PageBeat, Variable, CharacterSheet
from storyforge.expand import expand_narrative
from storyforge.errors import ResolutionError


def _tpl():
    return Template(
        name="T", mode="color", language_default="en",
        art_style="watercolor",
        variables=[Variable("HERO_NAME", "Name", "text")],
        pages=[
            PageBeat("intro", "{HERO_NAME} starts.", "{HERO} at home"),
            PageBeat("end", "{HERO_NAME} learns courage.", "{HERO} smiling"),
        ],
    )


def _hero():
    return CharacterSheet(descriptor="a boy", canonical_portrait_png=b"x", art_style="watercolor")


def fake_text_fn(prompt, page_count):
    return [
        {"text": f"{{HERO_NAME}} page {i}", "image_prompt": "{HERO} scene"}
        for i in range(1, page_count + 1)
    ]


def test_expand_produces_exact_page_count_and_resolves_tokens():
    specs = expand_narrative(_tpl(), {"HERO_NAME": "Sami"}, _hero(), 4, fake_text_fn)
    assert len(specs) == 4
    assert specs[0].page_number == 1
    assert "Sami" in specs[0].text
    assert "a boy" in specs[0].image_prompt


def test_expand_rejects_wrong_count():
    def bad(prompt, page_count):
        return [{"text": "{HERO_NAME} x", "image_prompt": "{HERO} y"}]
    with pytest.raises(ResolutionError):
        expand_narrative(_tpl(), {"HERO_NAME": "Sami"}, _hero(), 4, bad)
