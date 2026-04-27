"""
assemble_book1_final.py — Book 1 interior PDF (KDP-ready, zero fonts)

All pages are rendered as PIL images at 2550×3300px (8.5"×11" @ 300 DPI),
then assembled with img2pdf. No PDF fonts → no KDP font-embedding errors.

Usage:
    cd scripts && python3 assemble_book1_final.py
"""

import pathlib
import sys
import tempfile

try:
    import img2pdf
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Run: pip3 install Pillow img2pdf")
    sys.exit(1)

# ── KDP page specs at 300 DPI ──────────────────────────────────────────────────
PX_W  = 2550   # 8.5" × 300 DPI
PX_H  = 3300   # 11.0" × 300 DPI
DPI   = 300

# Margins in pixels
M_IN  = int(0.75 * DPI)   # inside/spine
M_OUT = int(0.50 * DPI)   # outside
M_TOP = int(0.50 * DPI)
M_BOT = int(0.50 * DPI)

DRAW_W = PX_W - M_IN - M_OUT
DRAW_H = PX_H - M_TOP - M_BOT

ROOT   = pathlib.Path(__file__).parent.parent
IMAGES = ROOT / "images"
OUTPUT = ROOT / "output"
OUTPUT.mkdir(parents=True, exist_ok=True)

# ── Font paths (only used by PIL to render pixels — never embedded in PDF) ────
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT_REG  = "/System/Library/Fonts/Supplemental/Arial.ttf"

# ── Page sequence ──────────────────────────────────────────────────────────────
PAGE_SEQUENCE = [
    ("book1_conan.png",                       "The Little Detective"),
    ("book1_slam1_portrait.png",              "The Basketball Genius"),
    ("book1_soccer-legend_portrait.png",      "The Soccer Legend"),
    ("book1_dragonball-superwarrior.png",     "The Super Warrior"),
    ("book1_groupe1.png",                     "Scene — The Gang"),
    ("book1_naruto.png",                      "The Hidden Leaf Ninja"),
    ("book1_vegeta_portrait.png",             "The Prince of Warriors"),
    ("book1_dark-avenger_portrait.png",       "The Dark Avenger"),
    ("book1_groupe7-grid.png",                "All Heroes — Overview"),
    ("book1_digimon.png",                     "The Digimon Tamer"),
    ("book1_blade_clean_portrait.png",        "The Blade Spinner"),
    ("book1_hunter_clean_portrait.png",       "The Hunter Kid"),
    ("book1_groupe2.png",                     "Scene — Adventure"),
    ("book1_prince_warrior.png",              "The Prince of Warriors"),
    ("book1_samurai-foul_portrait.png",       "The Silver Samurai Fool"),
    ("book1_groupe3.png",                     "Scene — Warriors Unite"),
    ("book1_Alchemist.png",                   "The Alchemist Brother"),
    ("book1_deathnote_portrait.png",          "The Death Strategist"),
    ("book1_soul-reaper_clean.png",           "The Soul Reaper"),
    ("book1_groupe5.png",                     "Scene — Legends"),
    ("book1_demon-buttler.png",               "The Demon Butler"),
    ("book1_groupe4.png",                     "Scene — Rivals"),
    ("book1_yugioh_portrait.png",             "The Card Master"),
    ("book1_chin_portrait.png",               "The Wandering Swordsman"),
    ("book1_groupe8-grid.png",                "All Heroes — Grid"),
    ("book1_remi.png",                        "The Young Traveler"),
    ("book1_groupe6.png",                     "Scene — Final Battle"),
]

assert len(PAGE_SEQUENCE) == 27, f"Expected 27 pages, got {len(PAGE_SEQUENCE)}"

TESTPEN_IMAGE = "book1_testpen.png"

# ── PIL helpers ────────────────────────────────────────────────────────────────

def _font(bold, size):
    try:
        return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)
    except Exception:
        return ImageFont.load_default()


def _blank_page():
    return Image.new("RGB", (PX_W, PX_H), "white")


def _fit(src_w, src_h, box_w, box_h):
    """Return (w, h, x, y) to center src inside box, preserving ratio."""
    ratio = min(box_w / src_w, box_h / src_h)
    w, h = int(src_w * ratio), int(src_h * ratio)
    x, y = (box_w - w) // 2, (box_h - h) // 2
    return w, h, x, y


def make_coloring_page(img_path):
    """Place image centered with margins on a white 2550×3300 page."""
    src = Image.open(img_path).convert("L").convert("RGB")
    page = _blank_page()
    w, h, xo, yo = _fit(src.width, src.height, DRAW_W, DRAW_H)
    src = src.resize((w, h), Image.LANCZOS)
    page.paste(src, (M_IN + xo, M_TOP + yo))
    return page


def make_title_page():
    page = _blank_page()
    draw = ImageDraw.Draw(page)
    lines = [
        ("90s Legends",                                   120, True,  (0,  0,  0)),
        ("Coloring Our Stories",                           72, True,  (0,  0,  0)),
        ("",                                               36, False, (255,255,255)),
        ("A coloring book for dads who never grew up",     46, False, (60, 60, 60)),
        ("",                                               24, False, (255,255,255)),
        ("Color with your kids — bring the heroes to life!", 38, False, (110,110,110)),
    ]
    total_h = sum(sz + 20 for _, sz, _, _ in lines)
    y = (PX_H - total_h) // 2
    for text, size, bold, color in lines:
        if text:
            f = _font(bold, size)
            bbox = draw.textbbox((0, 0), text, font=f)
            x = (PX_W - (bbox[2] - bbox[0])) // 2
            draw.text((x, y), text, font=f, fill=color)
        y += size + 20
    return page


def make_copyright_page():
    page = _blank_page()
    draw = ImageDraw.Draw(page)
    lines = [
        ("© 2026 All rights reserved.",                               32, True,  (40, 40, 40)),
        ("",                                                           18, False, (255,255,255)),
        ("No part of this publication may be reproduced",             26, False, (80, 80, 80)),
        ("or distributed without prior written permission.",          26, False, (80, 80, 80)),
        ("",                                                           18, False, (255,255,255)),
        ("All characters are original fictional archetypes",          26, False, (80, 80, 80)),
        ("inspired by the golden age of anime.",                      26, False, (80, 80, 80)),
        ("",                                                           18, False, (255,255,255)),
        ("Printed in the United States of America",                   26, False, (80, 80, 80)),
        ("First Edition",                                              26, False, (80, 80, 80)),
    ]
    total_h = sum(sz + 16 for _, sz, _, _ in lines)
    y = (PX_H - total_h) // 2
    for text, size, bold, color in lines:
        if text:
            f = _font(bold, size)
            bbox = draw.textbbox((0, 0), text, font=f)
            x = (PX_W - (bbox[2] - bbox[0])) // 2
            draw.text((x, y), text, font=f, fill=color)
        y += size + 16
    return page


def make_back_page():
    page = _blank_page()
    draw = ImageDraw.Draw(page)
    lines = [
        ("Thank you for coloring with us!",              55, True,  (0,  0,  0)),
        ("",                                              30, False, (255,255,255)),
        ("If you enjoyed this book,",                    40, False, (60, 60, 60)),
        ("please leave a review on Amazon.",             40, False, (60, 60, 60)),
        ("",                                             24, False, (255,255,255)),
        ("It means the world to us",                     34, False, (110,110,110)),
        ("and helps other families discover it.",        34, False, (110,110,110)),
    ]
    total_h = sum(sz + 20 for _, sz, _, _ in lines)
    y = (PX_H - total_h) // 2
    for text, size, bold, color in lines:
        if text:
            f = _font(bold, size)
            bbox = draw.textbbox((0, 0), text, font=f)
            x = (PX_W - (bbox[2] - bbox[0])) // 2
            draw.text((x, y), text, font=f, fill=color)
        y += size + 20
    return page


def save_tmp(pil_img):
    """Save PIL image to a temp PNG and return the path."""
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    pil_img.save(tmp.name, dpi=(DPI, DPI))
    return pathlib.Path(tmp.name)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    tmp_files = []
    page_paths = []
    missing = []

    def add(pil_img, label=""):
        p = save_tmp(pil_img)
        tmp_files.append(p)
        page_paths.append(p)
        return p

    print("Building pages...")

    # Front matter
    add(make_title_page(),     "Title page")
    add(make_copyright_page(), "Copyright page")

    # Testpen page — once only, right before the first coloring page
    testpen_path = IMAGES / TESTPEN_IMAGE
    if testpen_path.exists():
        print("  [testpen]  Color test page (once)")
        add(make_coloring_page(testpen_path))
        add(_blank_page())   # its back = blank
    else:
        print(f"  ⚠️  MISSING: {TESTPEN_IMAGE}")

    # Content pages — blank white on the back of every page
    for i, (filename, label) in enumerate(PAGE_SEQUENCE):
        img_path = IMAGES / filename
        if not img_path.exists():
            print(f"  ⚠️  MISSING: {filename}")
            missing.append(filename)
            continue

        print(f"  p{(i*2)+1:02d}  {label}")
        add(make_coloring_page(img_path))
        add(_blank_page())   # blank back — industry standard

    # Back matter
    add(make_back_page(), "Back page")

    # Assemble with img2pdf (zero fonts in output)
    output_path = OUTPUT / "book1_interior_FINAL.pdf"
    layout = img2pdf.get_layout_fun(
        (img2pdf.in_to_pt(8.5), img2pdf.in_to_pt(11.0))
    )
    with open(output_path, "wb") as f:
        f.write(img2pdf.convert([str(p) for p in page_paths], layout_fun=layout))

    # Cleanup temp files
    for p in tmp_files:
        p.unlink(missing_ok=True)

    total = len(page_paths)
    print(f"\n✅  Saved: {output_path}")
    print(f"    Total pages : {total}")
    print(f"    File size   : {output_path.stat().st_size / 1024 / 1024:.1f} MB")
    if missing:
        print(f"\n⚠️  Missing ({len(missing)}): {missing}")

    # Verify zero fonts
    with open(output_path, "rb") as f:
        raw = f.read()
    font_hits = raw.count(b"Helvetica") + raw.count(b"/Font ")
    print(f"    Font refs in PDF: {font_hits}  {'✅ clean' if font_hits == 0 else '⚠️ check'}")


if __name__ == "__main__":
    main()
