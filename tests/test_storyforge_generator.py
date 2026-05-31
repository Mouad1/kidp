from storyforge.generator import generate_page
from storyforge.types import PageSpec, CharacterSheet
from storyforge.imagegen import FakeImageGenerator, PNG_MAGIC

HERO = CharacterSheet(
    descriptor="boy, 7",
    canonical_portrait_png=b"\x89PNG-portrait",
    art_style="soft watercolor",
)


def test_color_page_appends_art_style_and_uses_portrait_reference():
    gen = FakeImageGenerator()
    spec = PageSpec(page_number=1, text="hi", image_prompt="boy, 7 exploring forest", mode="color")
    out = generate_page(spec, HERO, gen)
    assert out.startswith(PNG_MAGIC)
    call = gen.calls[0]
    assert "soft watercolor" in call["prompt"]
    assert "exploring forest" in call["prompt"]
    assert call["reference_images"] == [HERO.canonical_portrait_png]


def test_lineart_page_uses_coloring_directive():
    gen = FakeImageGenerator()
    spec = PageSpec(page_number=2, text="hi", image_prompt="boy, 7 in forest", mode="lineart")
    generate_page(spec, HERO, gen)
    prompt = gen.calls[0]["prompt"].lower()
    assert "black" in prompt and "white" in prompt
    assert "no color" in prompt or "no colour" in prompt or "zero" in prompt
    assert gen.calls[0]["reference_images"] == [HERO.canonical_portrait_png]
