from pathlib import Path

from storyforge.imagegen import ImageGenerator
from storyforge.types import CharacterSheet

MAX_PHOTO_BYTES = 12 * 1024 * 1024  # 12 MB per photo

_PORTRAIT_PROMPT = (
    "Create a single front-facing character portrait of this person reimagined as a "
    "friendly children's book hero. Keep the face recognizable: same hair, eyes, and "
    "distinctive features. Full head and shoulders, neutral background. Art style: {art_style}."
)


def validate_photos(photos: list[bytes]) -> None:
    if not photos:
        raise ValueError("Provide at least one photo to build a hero.")
    if len(photos) > 3:
        raise ValueError("Provide at most 3 photos.")
    for p in photos:
        if not p:
            raise ValueError("Empty photo payload.")
        if len(p) > MAX_PHOTO_BYTES:
            raise ValueError("Photo exceeds the 12 MB size limit.")


def build_hero(photos, art_style, gen: ImageGenerator, analyze) -> CharacterSheet:
    validate_photos(photos)
    descriptor = analyze(photos)
    portrait = gen.generate(
        _PORTRAIT_PROMPT.format(art_style=art_style),
        reference_images=list(photos),
    )
    return CharacterSheet(
        descriptor=descriptor,
        canonical_portrait_png=portrait,
        art_style=art_style,
        source_photos=list(photos),
    )


def save_sheet(book_dir, sheet: CharacterSheet) -> None:
    hero_dir = Path(book_dir) / "hero"
    hero_dir.mkdir(parents=True, exist_ok=True)
    (hero_dir / "canonical_portrait.png").write_bytes(sheet.canonical_portrait_png)
    (hero_dir / "descriptor.txt").write_text(sheet.descriptor, encoding="utf-8")
    (hero_dir / "art_style.txt").write_text(sheet.art_style, encoding="utf-8")
    for i, photo in enumerate(sheet.source_photos):
        (hero_dir / f"source_{i}.png").write_bytes(photo)


def load_sheet(book_dir) -> CharacterSheet:
    hero_dir = Path(book_dir) / "hero"
    portrait = (hero_dir / "canonical_portrait.png").read_bytes()
    descriptor = (hero_dir / "descriptor.txt").read_text(encoding="utf-8")
    art_style = (hero_dir / "art_style.txt").read_text(encoding="utf-8")
    photos = [p.read_bytes() for p in sorted(hero_dir.glob("source_*.png"))]
    return CharacterSheet(
        descriptor=descriptor,
        canonical_portrait_png=portrait,
        art_style=art_style,
        source_photos=photos,
    )
