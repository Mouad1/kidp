"""
pipeline/assemble.py — Generic KDP coloring-book assembler

Produces a KDP-ready interior PDF from any book config in books/<book>/config.py.
All pages are rendered as PIL images at 2550x3300 px (8.5"x11" @ 300 DPI),
then assembled with img2pdf. No PDF fonts -> no KDP font-embedding errors.

Usage:
    python pipeline/assemble.py --book book1-90s-legends
    python pipeline/assemble.py --book book2-modern-anime

Output:
    output/<book>_interior_FINAL.pdf

Config contract (books/<book>/config.py must define):
    TITLE              str
    SUBTITLE           str
    AUTHOR             str
    IMAGES_DIR         pathlib.Path  — folder containing all coloring images
    TESTPEN            str           — filename of the pen-test page (or empty string)
    PAGE_SEQUENCE      list[tuple[str, str]]  — (filename, label) pairs
    TITLE_PAGE_LINES   list[tuple[str, int, bool, tuple]]  — text layout
    COPYRIGHT_PAGE_LINES  same format
    BACK_PAGE_LINES       same format
"""

import argparse
import importlib.util
import pathlib
import sys
import tempfile
import types

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

try:
    import img2pdf
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Missing dependencies. Run:  pip install Pillow img2pdf")
    sys.exit(1)

try:
    from pipeline.draw_utils import draw_text_wrapped
except ImportError as e:
    print(f"Warning: Failed to import draw_text_wrapped: {e}")
    draw_text_wrapped = None

# ── KDP page specs at 300 DPI ──────────────────────────────────────────────────
PX_W = 3300    # 11.0" x 300 DPI (Landscape)
PX_H = 2550    # 8.5" x 300 DPI (Landscape)
DPI  = 300

# Margins in pixels (KDP guidelines)
M_IN  = int(0.75 * DPI)   # wider gutter for spine readability
M_OUT = int(0.50 * DPI)   # safe zone
M_TOP = int(0.50 * DPI)   # safe zone
M_BOT = int(0.50 * DPI)   # safe zone

DRAW_W = PX_W - M_IN - M_OUT
DRAW_H = PX_H - M_TOP - M_BOT

# System font paths (used only by PIL to bake pixels — never embedded in PDF)
FONT_BOLD = "/System/Library/Fonts/Supplemental/Futura.ttc"
FONT_REG  = "/System/Library/Fonts/Supplemental/Futura.ttc"

ROOT   = pathlib.Path(__file__).parent.parent
OUTPUT = ROOT / "output"
OUTPUT.mkdir(parents=True, exist_ok=True)


# ── Font helper ────────────────────────────────────────────────────────────────

def _font(bold: bool, size: int) -> ImageFont.FreeTypeFont:
    """Load a system font; fall back to PIL's built-in default if unavailable."""
    try:
        return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)
    except Exception:
        return ImageFont.load_default()


# ── Page factories ─────────────────────────────────────────────────────────────

def _blank_page() -> Image.Image:
    """Return a white 2550x3300 RGB PIL image."""
    return Image.new("RGB", (PX_W, PX_H), "white")


def _fit(src_w: int, src_h: int, box_w: int, box_h: int) -> tuple[int, int, int, int]:
    """Return (w, h, x_offset, y_offset) to center src inside box, preserving aspect ratio."""
    ratio = min(box_w / src_w, box_h / src_h)
    w, h  = int(src_w * ratio), int(src_h * ratio)
    x, y  = (box_w - w) // 2, (box_h - h) // 2
    return w, h, x, y


def make_coloring_page(img_path: pathlib.Path) -> Image.Image:
    """
    Place a coloring image centered within the printable area on a white page.
    """
    src  = Image.open(img_path).convert("L").convert("RGB")
    page = _blank_page()
    w, h, xo, yo = _fit(src.width, src.height, DRAW_W, DRAW_H)
    src  = src.resize((w, h), Image.LANCZOS)
    page.paste(src, (M_IN + xo, M_TOP + yo))
    return page

def make_text_only_page(text: str) -> Image.Image:
    """
    Render a page purely containing story text, vertically centered.
    """
    page = _blank_page()
    if not text or not draw_text_wrapped:
        return page
    
    draw = ImageDraw.Draw(page)
    f_text = _font(False, 65)  # 14pt-16pt equivalent
    
    # Calculate approx text height
    # Very rough estimate assuming line wraps
    test_h = draw_text_wrapped(ImageDraw.Draw(Image.new('RGB', (1,1))), text, f_text, DRAW_W - 200, 0, 0, fill=(0,0,0), line_spacing=1.5, align="left")
    
    y_start = max(M_TOP, (PX_H - test_h) // 2)
    draw_text_wrapped(draw, text, f_text, DRAW_W - 200, M_IN + 100, y_start, fill=(0, 0, 0), line_spacing=1.5, align="left")
    return page

def make_overlay_story_page(img_path: pathlib.Path, text: str) -> Image.Image:
    """
    Render full page image with text overlay at the bottom.
    """
    src  = Image.open(img_path).convert("RGB")
    page = _blank_page()
    
    # Full page resize (crop to fill or fit, let's fit it largely)
    w, h, xo, yo = _fit(src.width, src.height, DRAW_W, DRAW_H)
    src  = src.resize((w, h), Image.LANCZOS)
    page.paste(src, (M_IN + xo, M_TOP + yo))
    
    if text and draw_text_wrapped:
        # Create a semi-transparent box at the bottom
        overlay = Image.new('RGBA', (DRAW_W, int(DRAW_H * 0.3)), (255, 255, 255, 200))
        page.paste(overlay, (M_IN, M_TOP + int(DRAW_H * 0.7)), mask=overlay)
        
        draw = ImageDraw.Draw(page)
        f_text = _font(False, 65)  # 14pt-16pt equivalent
        draw_text_wrapped(draw, text, f_text, DRAW_W - 100, M_IN + 50, M_TOP + int(DRAW_H * 0.7) + 50, fill=(0, 0, 0), line_spacing=1.5, align="left")
        
    return page

def make_story_page(img_path: pathlib.Path, text: str) -> Image.Image:
    """
    Place a story image at the top 70% and the story text at the bottom 30%.
    """
    src  = Image.open(img_path).convert("RGB")
    page = _blank_page()
    
    # Image in upper 70% (11" x 6" approx)
    img_h_max = int(DRAW_H * 0.7)
    w, h, xo, yo = _fit(src.width, src.height, DRAW_W, img_h_max)
    src  = src.resize((w, h), Image.LANCZOS)
    page.paste(src, (M_IN + xo, M_TOP + yo))
    
    if text and draw_text_wrapped:
        draw = ImageDraw.Draw(page)
        f_text = _font(False, 65) # 14-16pt equivalent
        text_y_start = M_TOP + img_h_max + 100 # Put text naturally in the bottom 30% area
        draw_text_wrapped(draw, text, f_text, DRAW_W - 200, M_IN + 100, text_y_start, fill=(0, 0, 0), line_spacing=1.5, align="left")
        
    return page


def _render_centered_text_page(lines: list) -> Image.Image:
    """
    Render a vertically-centered text page from a list of line descriptors.

    Each line is a tuple: (text, font_size_px, bold, rgb_color).
    An empty text string acts as a spacer of the given height.
    """
    page  = _blank_page()
    draw  = ImageDraw.Draw(page)
    # Calculate total block height (font_size + 20 px gap per line)
    gap   = 20
    total_h = sum(sz + gap for _, sz, _, _ in lines)
    y = (PX_H - total_h) // 2
    for text, size, bold, color in lines:
        if text:
            f    = _font(bold, size)
            bbox = draw.textbbox((0, 0), text, font=f)
            x    = (PX_W - (bbox[2] - bbox[0])) // 2
            draw.text((x, y), text, font=f, fill=color)
        y += size + gap
    return page


def make_title_page(cfg: types.ModuleType) -> Image.Image:
    """Render the title page using layout from config.TITLE_PAGE_LINES."""
    return _render_centered_text_page(cfg.TITLE_PAGE_LINES)


def make_copyright_page(cfg: types.ModuleType) -> Image.Image:
    """Render the copyright page using layout from config.COPYRIGHT_PAGE_LINES."""
    return _render_centered_text_page(cfg.COPYRIGHT_PAGE_LINES)


def make_intro_page(cfg: types.ModuleType) -> Image.Image:
    """Render the intro page."""
    intro_text = getattr(cfg, "INTRO_TEXT", "")
    if isinstance(intro_text, dict):
        intro_text = intro_text.get(lang, "")
    if not intro_text:
        return None
    page = _blank_page()
    draw = ImageDraw.Draw(page)
    f_title = _font(True, 120)
    f_text = _font(False, 65)
    
    title = "Introduction"
    bbox = draw.textbbox((0, 0), title, font=f_title)
    x = (PX_W - (bbox[2] - bbox[0])) // 2
    y = M_TOP + 300
    draw.text((x, y), title, font=f_title, fill=(0, 0, 0))
    
    if draw_text_wrapped:
        draw_text_wrapped(draw, intro_text, f_text, DRAW_W - 200, M_IN + 100, y + 250, fill=(0, 0, 0), line_spacing=1.5, align="left")
    return page


def make_values_page(cfg: types.ModuleType) -> Image.Image:
    """Render the values learned page."""
    values_text = getattr(cfg, "VALUES_LEARNED", "")
    if isinstance(values_text, dict):
        values_text = values_text.get(lang, "")
    if not values_text:
        return None
    page = _blank_page()
    draw = ImageDraw.Draw(page)
    f_title = _font(True, 120)
    f_text = _font(False, 65)
    
    title = "Valeurs Apprises"
    bbox = draw.textbbox((0, 0), title, font=f_title)
    x = (PX_W - (bbox[2] - bbox[0])) // 2
    y = M_TOP + 300
    draw.text((x, y), title, font=f_title, fill=(0, 0, 0))
    
    if draw_text_wrapped:
        draw_text_wrapped(draw, values_text, f_text, DRAW_W - 200, M_IN + 100, y + 250, fill=(0, 0, 0), line_spacing=1.5, align="left")
    return page


def make_back_page(cfg: types.ModuleType) -> Image.Image:
    """Render the back-matter page using layout from config.BACK_PAGE_LINES."""
    return _render_centered_text_page(cfg.BACK_PAGE_LINES)


# ── Temp file helpers ──────────────────────────────────────────────────────────

def save_tmp(pil_img: Image.Image) -> pathlib.Path:
    """Save a PIL image to a named temp PNG and return its path."""
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    pil_img.save(tmp.name, dpi=(DPI, DPI))
    return pathlib.Path(tmp.name)


# ── Config loader ──────────────────────────────────────────────────────────────

def load_config(book_name: str) -> types.ModuleType:
    """
    Dynamically load books/<book_name>/config.py as a Python module.

    Raises SystemExit with a clear message if the book folder or config file
    is missing, or if the config is missing required attributes.
    """
    config_path = ROOT / "books" / book_name / "config.py"
    if not config_path.exists():
        print(f"ERROR: Config not found: {config_path}")
        print(f"       Create books/{book_name}/config.py to define this book.")
        sys.exit(1)

    spec   = importlib.util.spec_from_file_location(f"books.{book_name}.config", config_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    required = ["TITLE", "SUBTITLE", "AUTHOR", "IMAGES_DIR", "TESTPEN",
                "PAGE_SEQUENCE", "TITLE_PAGE_LINES", "COPYRIGHT_PAGE_LINES",
                "BACK_PAGE_LINES"]
    missing_attrs = [attr for attr in required if not hasattr(module, attr)]
    if missing_attrs:
        print(f"ERROR: config.py is missing required attributes: {missing_attrs}")
        sys.exit(1)

    return module


# ── Assembler ──────────────────────────────────────────────────────────────────

def assemble(book_name: str) -> None:
    """
    Build the full interior PDF for the given book.

    Page structure (KDP coloring-book standard):
        1. Title page
        2. Copyright page
        3. Testpen page + blank back  (if TESTPEN image exists)
        4. For each page in PAGE_SEQUENCE:
               coloring page + blank back
        5. Back-matter page
    """
    cfg = load_config(book_name)

    images_dir = pathlib.Path(cfg.IMAGES_DIR)
    if not images_dir.is_dir():
        print(f"ERROR: IMAGES_DIR does not exist: {images_dir}")
        sys.exit(1)

    languages = getattr(cfg, "LANGUAGES", ["fr"])
    if not isinstance(languages, list) or not languages:
        languages = ["fr"]
        
    for lang in languages:
        print(f"\n=======================================================")
        print(f"Assembling: {cfg.TITLE}  [Lang: {lang.upper()}]")
        print(f"Book folder: books/{book_name}")
        print(f"Images dir:  {images_dir}")
        print(f"=======================================================\n")

        tmp_files  = []
        page_paths = []
        missing    = []
        
        def add(pil_img: Image.Image, label: str = "") -> pathlib.Path:
            """Bake PIL image to temp PNG and register it in the page list."""
            p = save_tmp(pil_img)
            tmp_files.append(p)
            page_paths.append(p)
            if label:
                print(f"  {label}")
            return p

        story_format = getattr(cfg, "STORY_FORMAT", "colored")
        is_story = getattr(cfg, "CATEGORY", "coloring") == "story"
        
        def add_blank(label="[blank]    Blank back"):
            if story_format == "coloring" or not is_story:
                p = save_tmp(_blank_page())
                tmp_files.append(p)
                page_paths.append(p)
                print(f"  {label}")
                return p


        # Front matter
        add(make_title_page(cfg),     label="[title]    Title page")
        add(make_copyright_page(cfg), label="[copy]     Copyright page")
        
        intro_page = make_intro_page(cfg)
        if intro_page:
            add(intro_page, label="[intro]    Introduction")
            add_blank(label="[blank]    Intro back")

        # Testpen page — once only, right before the first coloring page
        if cfg.TESTPEN:
            testpen_path = images_dir / cfg.TESTPEN
            if testpen_path.exists():
                add(make_coloring_page(testpen_path), label="[testpen]  Color test page")
                add_blank(label="[blank]    Testpen back")
            else:
                print(f"  WARNING: TESTPEN image not found: {testpen_path}")

        # Content pages
        story_format = getattr(cfg, "STORY_FORMAT", "colored")
        story_layout = getattr(cfg, "STORY_LAYOUT", "top_bottom")
        pages_data = getattr(cfg, "PAGES", [])
        
        page_num_pdf = 1
        for i, (filename, label) in enumerate(cfg.PAGE_SEQUENCE):
            img_path = images_dir / filename
            if not img_path.exists():
                print(f"  WARNING: MISSING image: {filename}")
                missing.append(filename)
                continue
                
            page_text = ""
            # Find corresponding text if it's a story
            is_story = getattr(cfg, "CATEGORY", "coloring") == "story"
            if is_story:
                for p_data in pages_data:
                    if p_data.get("page_number", 0) == i + 1:
                        page_text = p_data.get("text", {}).get(lang, "")
                        break
            
            if is_story and story_layout == "separate":
                add(make_text_only_page(page_text), label=f"  p{page_num_pdf:02d}  {label} (Text)")
                page_num_pdf += 1
                add_blank()
                page_num_pdf += 1
                
                add(make_coloring_page(img_path), label=f"  p{page_num_pdf:02d}  {label} (Image)")
                page_num_pdf += 1
                add_blank()
                page_num_pdf += 1
                
            elif is_story and story_layout == "overlay":
                add(make_overlay_story_page(img_path, page_text), label=f"  p{page_num_pdf:02d}  {label} (Overlay)")
                page_num_pdf += 1
                add_blank()
                page_num_pdf += 1
                
            else:
                if is_story:
                    add(make_story_page(img_path, page_text), label=f"  p{page_num_pdf:02d}  {label} (Top/Bottom)")
                else:
                    add(make_coloring_page(img_path), label=f"  p{page_num_pdf:02d}  {label}")
                page_num_pdf += 1
                add_blank()   # blank back — coloring-book industry standard
                page_num_pdf += 1

        values_page = make_values_page(cfg)
        if values_page:
            add(values_page, label="[values]   Values Learned")
            add_blank(label="[blank]    Values back")

        # Back matter
        add(make_back_page(cfg), label="[back]     Back matter page")

        if not page_paths:
            print("ERROR: No pages were assembled. Check your IMAGES_DIR and PAGE_SEQUENCE.")
            sys.exit(1)

        # ── Assemble with img2pdf (produces zero-font PDF) ─────────────────────────
        output_path = OUTPUT / f"{book_name}_{lang}_interior_FINAL.pdf"
        layout = img2pdf.get_layout_fun(
            (img2pdf.in_to_pt(8.5), img2pdf.in_to_pt(11.0))
        )
        with open(output_path, "wb") as fh:
            fh.write(img2pdf.convert([str(p) for p in page_paths], layout_fun=layout))

        # Cleanup temp files
        for p in tmp_files:
            p.unlink(missing_ok=True)

        # ── Summary ────────────────────────────────────────────────────────────────
        total = len(page_paths)
        size_mb = output_path.stat().st_size / 1024 / 1024
        print(f"\nSaved: {output_path}")
        print(f"  Total pages : {total}")
        print(f"  File size   : {size_mb:.1f} MB")
        if missing:
            print(f"\nWARNING — {len(missing)} missing image(s):")
            for m in missing:
                print(f"    {m}")

        # Verify zero embedded fonts (KDP requirement)
        with open(output_path, "rb") as fh:
            raw = fh.read()
        font_hits = raw.count(b"Helvetica") + raw.count(b"/Font ")
        status = "clean" if font_hits == 0 else "WARNING — check for embedded fonts"
        print(f"  Font refs in PDF: {font_hits}  [{status}]\n")


# ── CLI ────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generic KDP coloring-book assembler.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python pipeline/assemble.py --book book1-90s-legends
    python pipeline/assemble.py --book book2-modern-anime

The book folder must contain a config.py. See books/book1-90s-legends/config.py
for a full example.
        """,
    )
    parser.add_argument(
        "--book",
        required=True,
        metavar="BOOK_FOLDER",
        help="Name of the folder inside books/ (e.g. book1-90s-legends)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    assemble(args.book)
