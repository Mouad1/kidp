from storyforge.generator import generate_page, _SCENE_GUIDED_PROMPT
from storyforge.types import PageSpec, CharacterSheet
from storyforge.imagegen import FakeImageGenerator, PNG_MAGIC

HERO = CharacterSheet(
    descriptor="boy, 7",
    canonical_portrait_png=b"\x89PNG-portrait",
    art_style="soft watercolor",
    source_photos=[b"\x89PNG-photo1"],
)

_SCENE = PageSpec(page_number=1, text="hi", image_prompt="boy in a magical forest", mode="color")
_TEMPLATE_PNG = b"\x89PNG-scene-template"


def test_color_page_appends_art_style_and_uses_portrait_reference():
    gen = FakeImageGenerator()
    spec = PageSpec(page_number=1, text="hi", image_prompt="boy, 7 exploring forest", mode="color")
    out = generate_page(spec, HERO, gen)
    assert out.startswith(PNG_MAGIC)
    call = gen.calls[0]
    assert "soft watercolor" in call["prompt"]
    assert "exploring forest" in call["prompt"]
    assert HERO.canonical_portrait_png in call["reference_images"]
    assert call["preamble_images"] is None


def test_lineart_page_uses_coloring_directive():
    gen = FakeImageGenerator()
    spec = PageSpec(page_number=2, text="hi", image_prompt="boy, 7 in forest", mode="lineart")
    generate_page(spec, HERO, gen)
    prompt = gen.calls[0]["prompt"].lower()
    assert "black" in prompt and "white" in prompt
    assert "no color" in prompt or "no colour" in prompt or "zero" in prompt
    assert HERO.canonical_portrait_png in gen.calls[0]["reference_images"]
    assert gen.calls[0]["preamble_images"] is None


# ---------- scene-guided mode (non-regression) ----------

def test_scene_guided_template_is_first_reference_not_preamble():
    """Template image must be FIRST in reference_images (scene guide), NOT in preamble.

    Regression guard: preamble approach caused Gemini to reproduce the template
    unchanged (model treats preamble as source, outputs it verbatim).
    Using reference_images forces a fresh generation guided by scene + portrait.
    """
    gen = FakeImageGenerator()
    generate_page(_SCENE, HERO, gen, template_image=_TEMPLATE_PNG)
    call = gen.calls[0]
    refs = call["reference_images"] or []
    # Template is first reference (scene guide)
    assert refs[0] == _TEMPLATE_PNG
    # Preamble must be None — no preamble in scene-guided mode
    assert call["preamble_images"] is None


def test_scene_guided_includes_portrait_and_source_photos():
    """Portrait + source photos must follow template in reference_images."""
    gen = FakeImageGenerator()
    generate_page(_SCENE, HERO, gen, template_image=_TEMPLATE_PNG)
    refs = gen.calls[0]["reference_images"] or []
    assert HERO.canonical_portrait_png in refs
    for photo in HERO.source_photos:
        assert photo in refs


def test_scene_guided_prompt_contains_art_style_and_scene_keyword():
    """Scene-guided prompt must include art_style and reference-image instructions."""
    gen = FakeImageGenerator()
    generate_page(_SCENE, HERO, gen, template_image=_TEMPLATE_PNG)
    prompt = gen.calls[0]["prompt"]
    assert HERO.art_style in prompt
    assert "Reference image 1" in prompt


def test_no_template_image_uses_generation_mode():
    """Without template image → standard generation (no preamble, scene in prompt)."""
    gen = FakeImageGenerator()
    generate_page(_SCENE, HERO, gen, template_image=None)
    call = gen.calls[0]
    assert call["preamble_images"] is None
    assert "Reference image 1" not in call["prompt"]
    assert HERO.art_style in call["prompt"]
