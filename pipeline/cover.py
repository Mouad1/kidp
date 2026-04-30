"""
pipeline/cover.py — AI-generated book cover using Gemini image model.

Usage:
    python pipeline/cover.py --book boo3-test

Output: output/<book_name>_COVER.png

COVER STYLE RULES (Amazigh Children's Story — reference: "Joudia and Baba Inouva"):
─────────────────────────────────────────────────────────────────────────────────
1. ART STYLE      : Cinematic digital illustration, painterly, children's book quality.
                    Warm vs cool color contrast. Rich atmospheric depth.
2. MOOD/LIGHT     : Night scene. Deep blue/indigo sky with stars. One warm golden
                    light source from inside an open door, spilling onto the character.
3. SETTING        : Traditional Amazigh/Berber mountain village. Log and stone cabins
                    with warm glowing windows. Snow-capped Atlas Mountains in background.
                    Pine trees. Stone path leading to a wooden door.
4. CHARACTERS     : Joudia (young girl, dark curly hair, warm sweater/cardigan,
                    skirt and boots) at the foreground. Baba Inouva (elderly man,
                    white/grey hair, dark clothes) standing in the doorway.
                    A magical glowing orange mountain flower between them.
5. COMPOSITION    : Portrait orientation. Character in lower center/left.
                    Door + elder occupying right side with warm interior glow.
                    Mountains + village receding into the dark background.
6. TITLE TEXT     : Do NOT embed text — title is added programmatically.
7. COLOR PALETTE  : Deep indigo and cool blue-greys for exterior/night.
                    Warm amber/golden for interior light and magical flower.
                    Muted teal/green for pine trees and foliage.
"""

import argparse
import io
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    print("Missing dependency. Run:  pip install google-genai")
    sys.exit(1)

from PIL import Image, ImageDraw, ImageFont

from pipeline.assemble import load_config

IMAGE_MODEL = "gemini-2.5-flash-image"
OUTPUT = ROOT / "output"


# ── Cover prompt builder ───────────────────────────────────────────────────────

COVER_STYLE_BASE = """
Cinematic digital illustration for a children's picture book cover. Portrait orientation (3:4 ratio).

ART STYLE: Painterly, rich, warm. Soft edges with atmospheric depth. Think Disney/Pixar concept art meets
classical storybook illustration. High detail in foreground, soft bokeh in background.
Night scene lit by a single warm golden interior light spilling through an open wooden door.

SETTING: Traditional Amazigh/Berber mountain village at twilight/night. Background:
snow-capped Atlas Mountains, deep indigo sky with a few bright stars, pine forest silhouette.
Middle ground: rustic stone and timber village houses with warm glowing windows.
Foreground: stone steps leading to a heavy wooden carved door.

MOOD: Magical and intimate. A story of love, identity, and belonging. Warm vs cool color contrast
creates a sense of safety and wonder.

COMPOSITION RULES:
- Lower center/left foreground: young girl character, facing the open door
- Right side: the door open, elderly man standing in the warm threshold
- A magical glowing element (flower/light) between the two characters serves as focal point
- Mountains and village recede into cool dark background
- Rich atmospheric perspective: dark cool edges, warm golden center

COLOR PALETTE:
- Exterior/night: deep indigo, cool blue-grey, muted teal-green for pines
- Interior warmth: amber, golden-yellow, orange
- Magical element: glowing warm orange with golden sparkles
- Character clothing: warm earth tones (tan/beige cardigan, dark skirt)

CRITICAL: No embedded text, no watermarks, no captions in the image.
"""


def _build_cover_prompt(cfg) -> str:
    title = getattr(cfg, "TITLE", "")

    # ── Build character block from actual config ────────────────────────────────
    char_block = ""

    # Story books: use STORY_BASE_PROMPT if present
    story_base = getattr(cfg, "STORY_BASE_PROMPT", "")
    if story_base:
        char_block = f"\nCHARACTERS AND STYLE (from story bible):\n{story_base[:800]}\n"

    # Coloring books: use CHARACTERS list
    characters = getattr(cfg, "CHARACTERS", None)
    if characters and not char_block:
        char_lines = []
        for c in characters[:6]:  # max 6 characters for the prompt
            if isinstance(c, dict):
                name = c.get("name") or c.get("id", "")
                prompt_desc = c.get("prompt", "").strip()
                if name and prompt_desc:
                    char_lines.append(f"- {name}: {prompt_desc[:150]}")
                elif name:
                    char_lines.append(f"- {name}")
        if char_lines:
            char_block = "\nCHARACTERS:\n" + "\n".join(char_lines) + "\n"

    if not char_block:
        char_block = f"\nThe main characters from the story '{title}' as described in their narrative.\n"

    return COVER_STYLE_BASE + char_block + f"\nThis is the cover for the children's book '{title}'."


# ── Title overlay ──────────────────────────────────────────────────────────────

def _add_title_overlay(img: Image.Image, cfg) -> Image.Image:
    """Composite title and subtitle text onto the cover image."""
    draw = ImageDraw.Draw(img)
    W, H = img.size

    title    = getattr(cfg, "TITLE", "").upper()
    subtitle = getattr(cfg, "SUBTITLE", "").upper()  # Always uppercase for subtitle
    author   = getattr(cfg, "AUTHOR", "")

    # ── Title font: storybook/fairytale serif ─────────────────────────────────
    title_font_paths = [
        "/System/Library/Fonts/Supplemental/Big Caslon Medium.ttf",
        "/System/Library/Fonts/Supplemental/Didot.ttc",
        "/System/Library/Fonts/Supplemental/Cochin.ttc",
        "/System/Library/Fonts/Supplemental/Baskerville.ttc",
        "/System/Library/Fonts/Supplemental/Hoefler Text.ttc",
        "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
        "/System/Library/Fonts/Supplemental/Georgia.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    # ── Subtitle font: light all-caps sans-serif ──────────────────────────────
    subtitle_font_paths = [
        "/System/Library/Fonts/Supplemental/Gill Sans.ttc",
        "/System/Library/Fonts/Supplemental/Futura.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    # ── Author font ───────────────────────────────────────────────────────────
    author_font_paths = subtitle_font_paths

    def load_font(paths, size):
        for p in paths:
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
        return ImageFont.load_default()

    title_size = max(72, W // 8)
    sub_size   = max(24, W // 28)
    auth_size  = max(20, W // 34)

    f_title  = load_font(title_font_paths, title_size)
    f_sub    = load_font(subtitle_font_paths, sub_size)
    f_author = load_font(author_font_paths, auth_size)

    def shadow_text(text, font, x, y, fill, shadow_color=(0, 0, 0, 210), spread=3):
        for dx in range(-spread, spread + 1, spread):
            for dy in range(-spread, spread + 1, spread):
                if dx != 0 or dy != 0:
                    draw.text((x + dx, y + dy), text, font=font, fill=shadow_color)
        draw.text((x, y), text, font=font, fill=fill)

    # ── Title (word-wrapped, centered at top) ─────────────────────────────────
    words = title.split()
    lines, current = [], ""
    for w in words:
        test = (current + " " + w).strip()
        bbox = draw.textbbox((0, 0), test, font=f_title)
        if bbox[2] - bbox[0] > W * 0.88 and current:
            lines.append(current)
            current = w
        else:
            current = test
    if current:
        lines.append(current)

    y = int(H * 0.025)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=f_title)
        lw = bbox[2] - bbox[0]
        x = (W - lw) // 2
        shadow_text(line, f_title, x, y, fill=(255, 210, 20))
        y += (bbox[3] - bbox[1]) + int(title_size * 0.10)

    # ── Subtitle (light, all-caps, tracking) ──────────────────────────────────
    if subtitle:
        # Manual letter-spacing by inserting thin spaces
        spaced = "  ".join(list(subtitle))  # 2 spaces between each char → simulates tracking
        # If too wide, fall back to normal
        bbox = draw.textbbox((0, 0), spaced, font=f_sub)
        if bbox[2] - bbox[0] > W * 0.90:
            spaced = subtitle
        bbox = draw.textbbox((0, 0), spaced, font=f_sub)
        sx = (W - (bbox[2] - bbox[0])) // 2
        shadow_text(spaced, f_sub, sx, y + 6, fill=(240, 240, 240), shadow_color=(0, 0, 0, 160), spread=2)

    # ── Author (bottom, light grey) ───────────────────────────────────────────
    if author:
        author_str = f"by  {author.upper()}"
        bbox = draw.textbbox((0, 0), author_str, font=f_author)
        ax = (W - (bbox[2] - bbox[0])) // 2
        ay = H - int(auth_size * 3.5)
        shadow_text(author_str, f_author, ax, ay, fill=(200, 200, 200), shadow_color=(0, 0, 0, 160), spread=2)

    return img


# ── Main ───────────────────────────────────────────────────────────────────────

def make_cover(book_name: str, prompt_override: str | None = None) -> None:
    """Generate an AI-powered cover for the given story book."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY environment variable is not set.")
        print("       export GEMINI_API_KEY=your-key")
        sys.exit(1)

    cfg   = load_config(book_name)
    title = getattr(cfg, "TITLE", book_name)

    print(f"Book  : {title}")
    print(f"Model : {IMAGE_MODEL}")

    prompt = prompt_override if prompt_override else _build_cover_prompt(cfg)
    if prompt_override:
        print("Using custom prompt override.")
    print(f"\nPrompt ({len(prompt)} chars):\n{prompt[:200]}...")
    print("\nGenerating cover art with Gemini...")

    client = genai.Client(api_key=api_key)
    try:
        response = client.models.generate_content(
            model=IMAGE_MODEL,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )
    except Exception as e:
        print(f"ERROR: Gemini API call failed: {e}")
        sys.exit(1)

    img_data = None
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            img_data = part.inline_data.data
            break

    if not img_data:
        print("ERROR: Gemini returned no image.")
        print("Response:", response.candidates[0].content.parts)
        sys.exit(1)

    img = Image.open(io.BytesIO(img_data)).convert("RGB")
    print(f"Cover art received: {img.size[0]}×{img.size[1]} px")

    img = _add_title_overlay(img, cfg)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT / f"{book_name}_COVER.png"
    img.save(out_path, dpi=(300, 300))
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate AI cover for a KDP story book.")
    parser.add_argument("--book", required=True, metavar="BOOK_FOLDER",
                        help="Folder name inside books/ (e.g. boo3-test)")
    parser.add_argument("--prompt-override", metavar="PROMPT", default=None,
                        help="Override the auto-generated cover prompt (optional)")
    args = parser.parse_args()
    make_cover(args.book, prompt_override=args.prompt_override)
