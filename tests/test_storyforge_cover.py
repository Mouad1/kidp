from storyforge.types import CharacterSheet
from storyforge.cover import generate_cover
from storyforge.imagegen import FakeImageGenerator, PNG_MAGIC


def test_generate_cover_uses_portrait_reference_and_returns_png():
    hero = CharacterSheet(descriptor="a girl with curly hair",
                          canonical_portrait_png=PNG_MAGIC + b"portrait",
                          art_style="soft watercolor")
    gen = FakeImageGenerator()

    out = generate_cover("Joudia's World", hero, gen)

    assert out.startswith(PNG_MAGIC)
    assert len(gen.calls) == 1
    call = gen.calls[0]
    assert hero.canonical_portrait_png in call["reference_images"]
    assert "soft watercolor" in call["prompt"]
    assert "Joudia's World" not in call["prompt"]
