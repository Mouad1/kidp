from storyforge.imagegen import ImageGenerator
from storyforge.types import PageSpec, CharacterSheet

_LINEART_DIRECTIVE = (
    "CRITICAL: pure black-and-white coloring-book line art. The ONLY ink is BLACK "
    "outlines on pure WHITE paper. Zero color, zero gray fills, zero shading, zero "
    "gradients. Every enclosed area stays white, ready to color. High contrast, 300 DPI. "
    "No text. Scene: "
)


def _build_prompt(spec: PageSpec, hero: CharacterSheet) -> str:
    if spec.mode == "lineart":
        return _LINEART_DIRECTIVE + spec.image_prompt
    return f"{spec.image_prompt}, {hero.art_style}. No text, no words, no letters."


def generate_page(spec: PageSpec, hero: CharacterSheet, gen: ImageGenerator) -> bytes:
    prompt = _build_prompt(spec, hero)
    return gen.generate(prompt, reference_images=[hero.canonical_portrait_png])
