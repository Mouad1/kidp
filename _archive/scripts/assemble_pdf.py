"""
assemble_pdf.py
Assembles coloring book images into a KDP-ready PDF.

Usage:
    # From a folder of extracted pages (recommended workflow)
    python3 assemble_pdf.py --from-folder ../images/extracted --prefix book1 \
        --title "90s Anime Legends" --author "Pen Name" --output my_book.pdf

    # From characters list (generated workflow)
    python3 assemble_pdf.py --book 1
    python3 assemble_pdf.py --book 2

KDP Specs (8.5x11, B&W interior):
    - Page size: 8.5" x 11"
    - Margins: inside 0.75", outside/top/bottom 0.5"
    - Resolution: 300 DPI
    - No crop marks on interior PDF
"""

import sys
import argparse
import pathlib

try:
    from PIL import Image
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.pdfgen import canvas
except ImportError:
    print("Run: pip3 install Pillow reportlab")
    sys.exit(1)

from characters import BOOK_1_MILLENNIAL_DAD, BOOK_2_MODERN_ANIME

# ── KDP Specs ─────────────────────────────────────────────────────────────────

PAGE_W = 8.5 * inch
PAGE_H = 11.0 * inch
MARGIN_INSIDE  = 0.75 * inch
MARGIN_OUTSIDE = 0.5  * inch
MARGIN_TOP     = 0.5  * inch
MARGIN_BOTTOM  = 0.5  * inch

# Drawable area
DRAW_W = PAGE_W - MARGIN_INSIDE - MARGIN_OUTSIDE
DRAW_H = PAGE_H - MARGIN_TOP - MARGIN_BOTTOM

BOOKS = {
    1: {"characters": BOOK_1_MILLENNIAL_DAD, "title": "90s Anime Legends Coloring Book"},
    2: {"characters": BOOK_2_MODERN_ANIME,   "title": "New Generation Anime Coloring Book"},
}

OUTPUT_DIR = pathlib.Path(__file__).parent.parent / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Helpers ───────────────────────────────────────────────────────────────────

def fit_image_in_box(img_w, img_h, box_w, box_h):
    """Return (w, h, x_offset, y_offset) to center image in box, preserving ratio."""
    ratio = min(box_w / img_w, box_h / img_h)
    w = img_w * ratio
    h = img_h * ratio
    x = (box_w - w) / 2
    y = (box_h - h) / 2
    return w, h, x, y


def convert_to_grayscale_rgb(img_path: pathlib.Path) -> pathlib.Path:
    """Convert RGBA/color image to RGB grayscale for PDF embedding."""
    img = Image.open(img_path).convert("L").convert("RGB")
    out_path = img_path.with_suffix(".converted.png")
    img.save(out_path, dpi=(300, 300))
    return out_path


def add_title_page(c: canvas.Canvas, title: str):
    c.setPageSize((PAGE_W, PAGE_H))
    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(PAGE_W / 2, PAGE_H / 2 + 0.5 * inch, title)
    c.setFont("Helvetica", 16)
    c.drawCentredString(PAGE_W / 2, PAGE_H / 2 - 0.1 * inch, "A Coloring Book for All Ages")
    c.showPage()


def add_back_page(c: canvas.Canvas):
    c.setPageSize((PAGE_W, PAGE_H))
    c.setFont("Helvetica", 12)
    c.drawCentredString(PAGE_W / 2, PAGE_H / 2 + 0.3 * inch, "Thank you for coloring with us!")
    c.drawCentredString(PAGE_W / 2, PAGE_H / 2, "Leave a review on Amazon — it means the world.")
    c.showPage()


def add_character_page(c: canvas.Canvas, img_path: pathlib.Path, char_name: str, page_num: int):
    c.setPageSize((PAGE_W, PAGE_H))

    # Convert to grayscale RGB for clean B&W PDF
    converted = convert_to_grayscale_rgb(img_path)

    # Compute image placement within drawable area
    img = Image.open(converted)
    img_w, img_h = img.size
    w, h, x_off, y_off = fit_image_in_box(img_w, img_h, DRAW_W, DRAW_H)

    x = MARGIN_INSIDE + x_off
    y = MARGIN_BOTTOM + y_off

    c.drawImage(str(converted), x, y, width=w, height=h, preserveAspectRatio=True)

    # Character name at bottom
    c.setFont("Helvetica", 10)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawCentredString(PAGE_W / 2, MARGIN_BOTTOM / 2, char_name)

    # Page number
    c.drawRightString(PAGE_W - MARGIN_OUTSIDE, MARGIN_BOTTOM / 2, str(page_num))

    c.showPage()

    # Clean up temp file
    converted.unlink(missing_ok=True)


# ── Main ──────────────────────────────────────────────────────────────────────

def assemble(book_num: int, images_dir: pathlib.Path, add_title: bool, add_back: bool):
    book = BOOKS[book_num]
    characters = book["characters"]
    title = book["title"]

    output_path = OUTPUT_DIR / f"book_{book_num}_interior.pdf"
    c = canvas.Canvas(str(output_path), pagesize=(PAGE_W, PAGE_H))

    if add_title:
        add_title_page(c, title)

    page_num = 1
    missing = []

    for char in characters:
        img_path = images_dir / f"{char['id']}.png"

        if not img_path.exists():
            print(f"  ⚠️  Missing: {img_path.name} — skipping")
            missing.append(char["id"])
            continue

        print(f"  📄 Adding page {page_num}: {char['name']}")
        add_character_page(c, img_path, char["name"], page_num)
        page_num += 1

    if add_back:
        add_back_page(c)

    c.save()

    print(f"\n✅ PDF saved: {output_path}")
    print(f"   Pages: {page_num - 1} character pages")
    if missing:
        print(f"   ⚠️  Missing images ({len(missing)}): {missing}")
        print(f"   Run: python3 generate_pages.py --book {book_num}")

    return output_path


def assemble_from_folder(folder: pathlib.Path, prefix: str, title: str,
                          author: str, output_name: str, add_title: bool, add_back: bool,
                          interleave: pathlib.Path = None):
    """Assemble all PNGs matching prefix in a folder into a PDF.

    interleave: if provided, insert this image after every character page.
    """
    images = sorted(folder.glob(f"{prefix}_*.png"))
    if not images:
        images = sorted(folder.glob("*.png"))  # fallback: all PNGs

    if not images:
        print(f"No images found in {folder}")
        sys.exit(1)

    output_path = OUTPUT_DIR / output_name
    c = canvas.Canvas(str(output_path), pagesize=(PAGE_W, PAGE_H))

    if add_title:
        add_title_page(c, title)

    page_num = 1
    for img_path in images:
        print(f"  📄 Page {page_num}: {img_path.name}")
        add_character_page(c, img_path, "", page_num)
        page_num += 1

        if interleave:
            print(f"  📄 Page {page_num}: [overview]")
            add_character_page(c, interleave, "", page_num)
            page_num += 1

    if add_back:
        add_back_page(c)

    c.save()
    total = page_num - 1
    print(f"\n✅ PDF saved: {output_path}")
    print(f"   {total} pages | Title: '{title}' | Author: {author}")


def main():
    parser = argparse.ArgumentParser(description="Assemble KDP coloring book PDF")

    # Folder mode (from extracted pages)
    parser.add_argument("--from-folder", type=str, default=None,
                        help="Assemble all PNGs from this folder")
    parser.add_argument("--prefix", type=str, default="page",
                        help="Filename prefix filter (e.g. 'book1' matches book1_01.png)")
    parser.add_argument("--title", type=str, default="Anime Coloring Book",
                        help="Book title for the title page")
    parser.add_argument("--author", type=str, default="Anonymous",
                        help="Author name for metadata")
    parser.add_argument("--output", type=str, default=None,
                        help="Output PDF filename (default: auto-generated)")

    # Character list mode
    parser.add_argument("--book", type=int, choices=[1, 2], default=None)
    parser.add_argument("--images-dir", type=str, default=None)

    parser.add_argument("--interleave", type=str, default=None,
                        help="Image to insert after every character page (e.g. the full grid overview)")
    parser.add_argument("--no-title-page", action="store_true")
    parser.add_argument("--no-back-page", action="store_true")
    args = parser.parse_args()

    add_title = not args.no_title_page
    add_back = not args.no_back_page

    if args.from_folder:
        folder = pathlib.Path(args.from_folder)
        if not folder.exists():
            print(f"Folder not found: {folder}")
            sys.exit(1)
        output_name = args.output or f"{args.prefix}_interior.pdf"
        interleave = pathlib.Path(args.interleave) if args.interleave else None
        if interleave and not interleave.exists():
            print(f"Interleave image not found: {interleave}")
            sys.exit(1)
        assemble_from_folder(folder, args.prefix, args.title, args.author,
                             output_name, add_title, add_back, interleave=interleave)

    elif args.book:
        if args.images_dir:
            images_dir = pathlib.Path(args.images_dir)
        else:
            images_dir = pathlib.Path(__file__).parent.parent / "images" / "generated"
        if not images_dir.exists():
            print(f"Images directory not found: {images_dir}")
            sys.exit(1)
        assemble(args.book, images_dir, add_title, add_back)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
