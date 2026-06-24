from storyforge.imagegen import ImageGenerator
from storyforge.types import PageSpec, CharacterSheet

_LINEART_DIRECTIVE = (
    "CRITICAL: pure black-and-white coloring-book line art. The ONLY ink is BLACK "
    "outlines on pure WHITE paper. Zero color, zero gray fills, zero shading, zero "
    "gradients. Every enclosed area stays white, ready to color. High contrast, 300 DPI. "
    "No text. Scene: "
)


_SCENE_GUIDED_PROMPT = (
    "Children's storybook illustration. "
    "Reference image 1 is the scene template: recreate the SAME background, composition, "
    "lighting, secondary characters, props, and setting — but generate the scene fresh so "
    "the hero's appearance is guided by the portrait in the remaining reference images. "
    "Art style: {art_style}. No text, no letters."
)

_GENERATION_PROMPT = (
    "Children's storybook illustration. "
    "Scene: {scene}. "
    "Art style: {art_style}. "
    "The hero's appearance must match the portrait reference photo. "
    "No text, no words, no letters."
)


def generate_page(
    spec: PageSpec,
    hero: CharacterSheet,
    gen: ImageGenerator,
    template_image: bytes | None = None,
) -> bytes:
    if template_image is not None:
        from storyforge.faceswap import run_hybrid_faceswap
        return run_hybrid_faceswap(spec, hero, gen, template_image)

    if spec.mode == "lineart":
        prompt = _LINEART_DIRECTIVE + spec.image_prompt
    else:
        prompt = _GENERATION_PROMPT.format(scene=spec.image_prompt, art_style=hero.art_style)
    refs = [hero.canonical_portrait_png] + list(hero.source_photos)
    return gen.generate(prompt, reference_images=refs)
