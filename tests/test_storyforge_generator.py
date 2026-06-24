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

def test_scene_guided_template_uses_scene_reference_not_preamble():
    """Template image must be in scene_reference_images (composition guide), not preamble.

    Regression guard: preamble caused Gemini to reproduce the template unchanged.
    scene_reference_images lets the model generate a fresh image guided by layout.
    """
    gen = FakeImageGenerator()
    generate_page(_SCENE, HERO, gen, template_image=_TEMPLATE_PNG)
    call = gen.calls[0]
    assert call["scene_reference_images"] == [_TEMPLATE_PNG]
    assert call["preamble_images"] is None


def test_scene_guided_includes_portrait_and_source_photos():
    """Portrait + source photos must be in reference_images."""
    gen = FakeImageGenerator()
    generate_page(_SCENE, HERO, gen, template_image=_TEMPLATE_PNG)
    refs = gen.calls[0]["reference_images"] or []
    assert HERO.canonical_portrait_png in refs
    for photo in HERO.source_photos:
        assert photo in refs


def test_scene_guided_prompt_contains_structured_blocks():
    """Scene-guided prompt must include structured prompt sections and art style."""
    gen = FakeImageGenerator()
    generate_page(_SCENE, HERO, gen, template_image=_TEMPLATE_PNG)
    prompt = gen.calls[0]["prompt"]
    assert HERO.art_style in prompt
    assert "[ENVIRONMENT LOCK]" in prompt
    assert "[HERO REPLACEMENT]" in prompt
    assert "[WARDROBE CONTINUITY]" in prompt
    assert "[ACTION MATCH]" in prompt


def test_no_template_image_uses_generation_mode():
    """Without template image → standard generation (no scene_reference, no preamble)."""
    gen = FakeImageGenerator()
    generate_page(_SCENE, HERO, gen, template_image=None)
    call = gen.calls[0]
    assert call["preamble_images"] is None
    assert call["scene_reference_images"] is None
    assert "[ENVIRONMENT LOCK]" not in call["prompt"]
    assert HERO.art_style in call["prompt"]


def test_scene_guided_with_predefined_structured_data():
    """When PageSpec contains predefined anchors, wardrobe, and action, they are used in the prompt."""
    spec = PageSpec(
        page_number=3,
        text="Sami sits on a rug.",
        image_prompt="boy sitting on a rug in a blue tent",
        mode="color",
        core_background_anchors=["blue tent canvas", "patterned Persian rug", "wooden support poles"],
        hero_action_and_emotion="sitting cross-legged and smiling warmly",
        fixed_wardrobe_description="a striped green hoodie and blue jeans",
    )
    gen = FakeImageGenerator()
    generate_page(spec, HERO, gen, template_image=_TEMPLATE_PNG)
    prompt = gen.calls[0]["prompt"]
    
    assert "blue tent canvas, patterned Persian rug, wooden support poles" in prompt
    assert "sitting cross-legged and smiling warmly" in prompt
    assert "a striped green hoodie and blue jeans" in prompt
    # Prompt references scene composition guide and face reference photos
    assert "scene" in prompt
    assert "reference photos" in prompt
