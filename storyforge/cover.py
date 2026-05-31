from storyforge.types import CharacterSheet
from storyforge.imagegen import ImageGenerator

_COVER_DIRECTIVE = (
    "Children's picture book front cover illustration, portrait orientation. "
    "The hero character is the focal point, consistent with the reference portrait. "
    "Rich, warm, painterly. Leave clear space at the top for a title. "
    "Do NOT render any text, words, or letters in the image."
)


def generate_cover(title: str, hero: CharacterSheet, image_gen: ImageGenerator) -> bytes:
    """Generate a cover image starring the hero.

    The title is added later programmatically (via PIL), never embedded in the image.
    """
    prompt = f"{hero.descriptor}. {hero.art_style}. {_COVER_DIRECTIVE}"
    return image_gen.generate(prompt, reference_images=[hero.canonical_portrait_png])
