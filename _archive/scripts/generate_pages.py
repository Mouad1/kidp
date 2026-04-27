"""
generate_pages.py
Generates coloring book pages via Google Gemini API.

Usage:
    python3 generate_pages.py --book 1          # generate book 1 only
    python3 generate_pages.py --book 2          # generate book 2 only
    python3 generate_pages.py                   # generate all books
    python3 generate_pages.py --id flame_pillar # regenerate one character

Setup:
    export GEMINI_API_KEY="your_key_from_aistudio.google.com"
"""

import os
import sys
import time
import argparse
import pathlib
from characters import BOOK_1_MILLENNIAL_DAD, BOOK_2_MODERN_ANIME, ALL_CHARACTERS

try:
    import google.generativeai as genai
except ImportError:
    print("Run: pip3 install google-generativeai")
    sys.exit(1)

# ── Config ────────────────────────────────────────────────────────────────────

OUTPUT_DIR = pathlib.Path(__file__).parent.parent / "images" / "generated"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

COLORING_BOOK_PREFIX = (
    "Black and white coloring book page, anime art style, "
    "thick clean outlines only, NO shading, NO gray fills, NO hatching, "
    "pure white background, crisp line art ready to color, "
    "high contrast, professional coloring book quality, "
    "single character centered on page, "
)

DELAY_BETWEEN_REQUESTS = 4  # seconds — stays within free tier limits

# ── Core ──────────────────────────────────────────────────────────────────────

def setup_gemini():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: Set your API key first:")
        print("  export GEMINI_API_KEY='your_key_from_aistudio.google.com'")
        sys.exit(1)
    genai.configure(api_key=api_key)


def generate_character(character: dict, force: bool = False) -> pathlib.Path:
    char_id = character["id"]
    output_path = OUTPUT_DIR / f"{char_id}.png"

    if output_path.exists() and not force:
        print(f"  ⏭  {char_id} — already exists, skipping")
        return output_path

    prompt = COLORING_BOOK_PREFIX + character["prompt"]
    print(f"  ⚡ Generating: {character['name']} ({char_id})...")

    try:
        model = genai.GenerativeModel("gemini-2.0-flash-preview-image-generation")
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_modalities=["IMAGE", "TEXT"]
            ),
        )

        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                output_path.write_bytes(part.inline_data.data)
                print(f"  ✅ Saved: {output_path.name}")
                return output_path

        print(f"  ⚠️  No image in response for {char_id}")
        return None

    except Exception as e:
        print(f"  ❌ Error for {char_id}: {e}")
        return None


def generate_book(characters: list, force: bool = False):
    total = len(characters)
    success = 0

    for i, char in enumerate(characters, 1):
        print(f"\n[{i}/{total}]", end=" ")
        result = generate_character(char, force=force)
        if result:
            success += 1
        if i < total:
            time.sleep(DELAY_BETWEEN_REQUESTS)

    print(f"\n✅ Done: {success}/{total} pages generated → {OUTPUT_DIR}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate KDP coloring book pages via Gemini")
    parser.add_argument("--book", type=int, choices=[1, 2], help="Generate book 1 or 2 only")
    parser.add_argument("--id", type=str, help="Regenerate a single character by id")
    parser.add_argument("--force", action="store_true", help="Overwrite existing images")
    args = parser.parse_args()

    setup_gemini()

    if args.id:
        char = next((c for c in ALL_CHARACTERS if c["id"] == args.id), None)
        if not char:
            print(f"Character id '{args.id}' not found.")
            print("Available ids:", [c["id"] for c in ALL_CHARACTERS])
            sys.exit(1)
        generate_character(char, force=True)

    elif args.book == 1:
        print(f"📖 Generating Book 1 — Millennial Dad ({len(BOOK_1_MILLENNIAL_DAD)} characters)")
        generate_book(BOOK_1_MILLENNIAL_DAD, force=args.force)

    elif args.book == 2:
        print(f"📖 Generating Book 2 — Modern Anime ({len(BOOK_2_MODERN_ANIME)} characters)")
        generate_book(BOOK_2_MODERN_ANIME, force=args.force)

    else:
        print(f"📚 Generating ALL books ({len(ALL_CHARACTERS)} characters)")
        generate_book(ALL_CHARACTERS, force=args.force)


if __name__ == "__main__":
    main()
