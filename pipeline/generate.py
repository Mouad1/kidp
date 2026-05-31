"""
pipeline/generate.py — Automated image generation via Gemini API

Reads CHARACTERS from any book's config.py, builds the full coloring-book
prompt for each character, calls Gemini, and saves the image to IMAGES_DIR.

Already-generated images are skipped automatically — safe to re-run after
a failure without re-generating everything from scratch.

Usage:
    export GEMINI_API_KEY="your-key-here"          # or put it in .env

    # Generate all characters for a book
    python pipeline/generate.py --book book2-modern-anime

    # Generate a single character by id
    python pipeline/generate.py --book book2-modern-anime --id gojo

    # Dry-run: print prompts without calling the API
    python pipeline/generate.py --book book2-modern-anime --dry-run

After generation, clean each image and add it to PAGE_SEQUENCE:
    python pipeline/clean.py images/book2-modern-anime/book2_gojo.png --crop-portrait --auto

Get your API key at: https://aistudio.google.com/apikey
"""

import argparse
import hashlib
import importlib.util
import os
import pathlib
import sys
import time
import types

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    print("Missing dependency. Run:  pip install google-genai")
    sys.exit(1)

# Ensure the project root is on sys.path so `pipeline.prompt` is importable
# whether the script is run as `python3 pipeline/generate.py` or as a module.
_ROOT = pathlib.Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline.prompt import build_prompt, compact_character_description

# Gemini model used for image generation
IMAGE_MODEL = "gemini-2.5-flash-image"

# Seconds to wait between API calls (avoid rate-limit errors)
RATE_LIMIT_DELAY = 4

ROOT = _ROOT


# ── Config loader (same pattern as assemble.py) ────────────────────────────────

def load_config(book_name: str) -> types.ModuleType:
    config_path = ROOT / "books" / book_name / "config.py"
    if not config_path.exists():
        print(f"ERROR: Config not found: {config_path}")
        sys.exit(1)
    spec   = importlib.util.spec_from_file_location(f"books.{book_name}.config", config_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "CHARACTERS"):
        print("ERROR: config.py has no CHARACTERS list — nothing to generate.")
        sys.exit(1)
    return module


# ── Image generation ───────────────────────────────────────────────────────────

def generate_image(client: genai.Client, prompt: str) -> bytes:
    """
    Call Gemini image generation and return the raw PNG bytes.

    Raises RuntimeError if the response contains no image part.
    """
    response = client.models.generate_content(
        model=IMAGE_MODEL,
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
        ),
    )
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            return part.inline_data.data
    raise RuntimeError("Gemini returned no image. Response text: "
                       + str(response.candidates[0].content.parts))


def save_image(data: bytes, out_path: pathlib.Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)


def check_color_contamination(img) -> bool:
    """Check if more than 1% of pixels are significantly colored (chroma > 25)."""
    rgb = img.convert("RGB")
    pixels = list(rgb.getdata())
    colored = sum(1 for r, g, b in pixels if max(r, g, b) - min(r, g, b) > 25)
    return (colored / len(pixels)) > 0.01

# ── Main ───────────────────────────────────────────────────────────────────────

def run(book_name: str, filter_id: str | None, dry_run: bool, force: bool = False, auto_clean: bool = False) -> None:
    cfg         = load_config(book_name)
    images_dir  = pathlib.Path(cfg.IMAGES_DIR)
    book_prefix = book_name.split("-")[0]   # "book2-modern-anime" → "book2"
    category    = getattr(cfg, "CATEGORY", "coloring")
    story_format = getattr(cfg, "STORY_FORMAT", "colored")
    
    if category == "story":
        items = getattr(cfg, "PAGES", [])
    else:
        items = getattr(cfg, "CHARACTERS", [])

    if filter_id:
        if category == "story":
            try:
                page_num = int(filter_id)
                items = [p for p in items if p["page_number"] == page_num]
            except ValueError:
                items = []
        else:
            items = [c for c in items if c["id"] == filter_id]
            
        if not items:
            print(f"ERROR: id/page '{filter_id}' not found.")
            sys.exit(1)

    print(f"\nBook  : {cfg.TITLE} ({category.upper()})")
    print(f"Model : {IMAGE_MODEL}")
    print(f"Total : {len(items)} item(s) to process")
    print(f"Output: {images_dir}\n")

    if dry_run:
        print("=== DRY RUN — no API calls will be made ===\n")

    if not dry_run:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print("ERROR: GEMINI_API_KEY environment variable is not set.")
            print("       Get your key at: https://aistudio.google.com/apikey")
            print("       Then run:  export GEMINI_API_KEY=your-key")
            sys.exit(1)
        client = genai.Client(api_key=api_key)

    generated = 0
    skipped   = 0
    failed    = []

    for i, item in enumerate(items):
        if category == "story":
            item_id = str(item["page_number"])
            out_path = images_dir / f"{book_name}_page_{item_id}.png"
            display_name = f"Page {item_id}"
            
            story_base = getattr(cfg, "STORY_BASE_PROMPT", "")
            raw_prompt = f"{story_base}\n\nScene: {item.get('image_prompt', '')}"
        else:
            item_id = item["id"]
            out_path = images_dir / f"{book_prefix}_{item_id}.png"
            display_name = f"{item.get('name', 'Unknown')} ({item.get('series', '')})"
            raw_prompt = item.get("prompt", "")

        print(f"[{i+1:02d}/{len(items):02d}] {display_name}")

        if out_path.exists() and not force:
            print(f"         SKIP — already exists: {out_path.name}")
            skipped += 1
            continue

        if category == "story":
            from pipeline.prompt import build_story_prompt
            is_coloring = (story_format == "coloring")
            full_prompt = build_story_prompt(story_base=story_base, scene=item.get("image_prompt", ""), is_coloring=is_coloring)
        else:
            compact_prompt = compact_character_description(raw_prompt)
            prompt_hash = hashlib.sha1(compact_prompt.encode("utf-8")).hexdigest()[:12]
            print(f"         Prompt id: {item_id} sha1:{prompt_hash}")
            print(f"         Prompt core: {compact_prompt[:220]}")
            full_prompt = build_prompt(description=compact_prompt)

        if dry_run:
            print(f"         PROMPT: {full_prompt[:120]}...")
            continue

        print(f"         Generating...")
        try:
            data = generate_image(client, full_prompt)
            save_image(data, out_path)
            size_kb = len(data) / 1024
            print(f"         Saved: {out_path.name}  ({size_kb:.0f} KB)")
            generated += 1

            if category != "story" or story_format == "coloring":
                # --- Post-generation validation & auto-cleanup ---
                try:
                    from PIL import Image
                    from pipeline.clean import strip_colors, remove_black_fills, remove_gray_fills_preserve_edges, auto_clean_corners
                    
                    img = Image.open(out_path).convert("RGB")
                    is_contaminated = check_color_contamination(img)
                    
                    dirty = False
                    if is_contaminated:
                        print(f"         WARNING: Color contamination detected! Auto-applying --lineart")
                        dirty = True
                    if auto_clean:
                        dirty = True
                    
                    if dirty:
                        img = strip_colors(img, verbose=False)
                        img = remove_black_fills(img, verbose=False)
                        img = remove_gray_fills_preserve_edges(img, verbose=False)
                        
                        if auto_clean:
                            img, corners = auto_clean_corners(img, verbose=False)
                            if corners > 0:
                                print(f"         Auto-cleaned {corners} corner(s).")
                                
                        img.save(str(out_path), dpi=(300, 300))
                        new_size = out_path.stat().st_size / 1024
                        print(f"         Cleaned and re-saved  ({new_size:.0f} KB)")
                except Exception as clean_err:
                    print(f"         WARNING: Post-generation cleanup failed: {clean_err}")

        except Exception as e:
            print(f"         FAILED: {e}")
            failed.append(item_id)

        # Rate limit: wait between calls
        if i < len(items) - 1:
            time.sleep(RATE_LIMIT_DELAY)

    # ── Summary ────────────────────────────────────────────────────────────────
    print(f"\n{'='*50}")
    if dry_run:
        print(f"Dry-run complete. {len(items)} prompts printed.")
    else:
        print(f"Done.  Generated: {generated}  |  Skipped: {skipped}  |  Failed: {len(failed)}")
        if failed:
            print(f"\nFailed IDs (re-run with --id to retry individually):")
            for fid in failed:
                print(f"  python pipeline/generate.py --book {book_name} --id {fid}")
        if generated > 0:
            print(f"\nNext step — clean each new image:")
            print(f"  python pipeline/clean.py images/book2-modern-anime/book2_<id>.png --crop-portrait --auto")
            print(f"Then uncomment the corresponding lines in books/{book_name}/config.py → PAGE_SEQUENCE")


# ── CLI ────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate coloring-book images via Gemini API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python pipeline/generate.py --book book2-modern-anime
    python pipeline/generate.py --book book2-modern-anime --id gojo
    python pipeline/generate.py --book book2-modern-anime --dry-run

Environment:
    GEMINI_API_KEY   Required. Get at https://aistudio.google.com/apikey
        """,
    )
    parser.add_argument("--book", required=True, metavar="BOOK_FOLDER",
                        help="Folder name inside books/ (e.g. book2-modern-anime)")
    parser.add_argument("--id", default=None, metavar="CHARACTER_ID",
                        help="Generate only this character (e.g. gojo). Default: all.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print prompts without calling the API.")
    parser.add_argument("--force", action="store_true",
                        help="Regenerate even if the image already exists.")
    parser.add_argument("--auto-clean", action="store_true",
                        help="Automatically run lineart and corner cleanup after generation.")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run(args.book, args.id, args.dry_run, getattr(args, 'force', False), getattr(args, 'auto_clean', False))
