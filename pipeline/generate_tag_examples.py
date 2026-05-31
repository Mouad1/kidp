# pipeline/generate_tag_examples.py
"""
One-shot script: generate 1 Gemini coloring-book image per tag and store
in assets/tag_examples/{category}/{slug}.png.

Safe to re-run: skips files that already exist unless --force is passed.

Usage:
    python3 pipeline/generate_tag_examples.py
    python3 pipeline/generate_tag_examples.py --category style
    python3 pipeline/generate_tag_examples.py --force
"""
import argparse
import os
import pathlib
import sys
import time

_ROOT = pathlib.Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from google import genai
except ImportError:
    print("Missing dependency. Run:  pip install google-genai")
    sys.exit(1)

from pipeline.prompt import (
    STYLE_TAGS, POSE_TAGS, ELEMENT_TAGS, THEME_TAGS, _BASE_TEMPLATE
)
from pipeline.generate import generate_image, save_image

IMAGE_MODEL = "gemini-2.5-flash-image"
RATE_LIMIT_DELAY = 4  # seconds between API calls
ASSETS_DIR = _ROOT / "assets" / "tag_examples"

CATEGORY_TAGS: dict[str, list[str]] = {
    "style":    STYLE_TAGS,
    "pose":     POSE_TAGS,
    "elements": ELEMENT_TAGS,
    "theme":    THEME_TAGS,
}

# Neutral character used in all reference images
_NEUTRAL_CHARACTER = "a young anime-style hero, full body, standing"


def slugify(tag: str) -> str:
    """'Art Nouveau' → 'art_nouveau'"""
    return tag.lower().replace(" ", "_").replace("-", "_").replace("/", "_")


def build_example_prompt(tag: str, category: str) -> str:
    """Build a neutral coloring-book prompt with just this one tag applied."""
    if category == "style":
        character_prompt = f"{_NEUTRAL_CHARACTER}, {tag}"
    elif category == "pose":
        character_prompt = f"{_NEUTRAL_CHARACTER}, {tag}"
    elif category == "elements":
        character_prompt = f"{_NEUTRAL_CHARACTER}, with {tag}"
    else:  # theme
        character_prompt = f"{_NEUTRAL_CHARACTER}, {tag} style"
    return _BASE_TEMPLATE.format(character_prompt=character_prompt)


def run(filter_category: str | None = None, force: bool = False) -> None:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY environment variable is not set.")
        sys.exit(1)
    client = genai.Client(api_key=api_key)

    categories = (
        {filter_category: CATEGORY_TAGS[filter_category]}
        if filter_category
        else CATEGORY_TAGS
    )

    total = sum(len(tags) for tags in categories.values())
    print(f"Generating {total} tag example image(s)...\n")

    generated = skipped = failed = 0

    for category, tags in categories.items():
        for tag in tags:
            slug = slugify(tag)
            out_path = ASSETS_DIR / category / f"{slug}.png"
            if out_path.exists() and not force:
                print(f"  SKIP  [{category}/{slug}]")
                skipped += 1
                continue

            print(f"  GEN   [{category}/{slug}]  {tag!r}")
            try:
                prompt = build_example_prompt(tag, category)
                data = generate_image(client, prompt)
                save_image(data, out_path)
                print(f"        Saved: {out_path.relative_to(_ROOT)}")
                generated += 1
                time.sleep(RATE_LIMIT_DELAY)
            except Exception as exc:
                print(f"        ERROR: {exc}")
                failed += 1

    print(f"\nDone. Generated={generated}  Skipped={skipped}  Failed={failed}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate tag reference images")
    parser.add_argument("--category", choices=list(CATEGORY_TAGS.keys()),
                        help="Generate only one category")
    parser.add_argument("--force", action="store_true",
                        help="Re-generate even if file already exists")
    args = parser.parse_args()
    run(filter_category=args.category, force=args.force)
