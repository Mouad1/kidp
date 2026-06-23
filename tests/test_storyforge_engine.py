import pytest
from storyforge.engine import resolve
from storyforge.types import Template, Variable, PageBeat, CharacterSheet
from storyforge.errors import ResolutionError


def _template():
    return Template(
        name="Explorer",
        mode="color",
        language_default="fr",
        art_style="watercolor",
        variables=[
            Variable(key="HERO_NAME", label="Name", type="text"),
            Variable(key="SETTING", label="World", type="select", options=["forest"]),
        ],
        pages=[
            PageBeat(beat="intro", text="{HERO_NAME} in {SETTING}",
                     image_prompt="{HERO} exploring {SETTING}"),
        ],
    )


def _hero():
    return CharacterSheet(
        descriptor="boy, 7, curly hair",
        canonical_portrait_png=b"\x89PNG",
        art_style="watercolor",
    )


def test_resolve_substitutes_variables_and_hero():
    specs = resolve(_template(), {"HERO_NAME": "Sami", "SETTING": "forest"}, _hero())
    assert len(specs) == 1
    assert specs[0].text == "Sami in forest"
    # {HERO} uses hero label (not raw descriptor) so model stays age-appropriate
    assert "Sami" in specs[0].image_prompt
    assert "boy, 7, curly hair" not in specs[0].image_prompt
    assert specs[0].page_number == 1
    assert specs[0].mode == "color"


def test_resolve_missing_variable_raises():
    with pytest.raises(ResolutionError, match="SETTING"):
        resolve(_template(), {"HERO_NAME": "Sami"}, _hero())


def test_hero_name_token_filled_from_variable_not_descriptor():
    specs = resolve(_template(), {"HERO_NAME": "Sami", "SETTING": "forest"}, _hero())
    assert "Sami" in specs[0].text
    # descriptor must NOT appear in image prompt — reference portrait handles likeness
    assert "boy, 7, curly hair" not in specs[0].image_prompt
    assert "Sami" in specs[0].image_prompt
