import argparse
import sys
import pathlib
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from pipeline.assemble import load_config, PX_H, PX_W, DPI, M_IN, M_OUT, M_TOP, M_BOT, _font, _fit, draw_text_wrapped, save_tmp
from PIL import ImageDraw

def make_cover(book_name: str) -> None:
    """Generate a basic attractive cover."""
    cfg = load_config(book_name)
    pages = getattr(cfg, "PAGE_SEQUENCE", [])
    if not pages:
        print("No pages to use for cover")
        return
        
    # Spine width (approx 0.25" for 100 pages = 75px)
    SPINE = 75
    # KDP Cover is Back + Spine + Front = (11 + 11)x8.5 (assuming portrait pages) 
    # But wait, our coloring pages are portrait or landscape?
    # Our interior is 11x8.5 Landscape... so pages are 8.5" w x 11" h?
    # Actually PX_W=3300 (11.0"), PX_H=2550 (8.5"). So the PDF is Landscape 11x8.5.
    
    # Just render a simple front cover image 11" x 8.5"
    page = Image.new("RGB", (PX_W, PX_H), "black")
    draw = ImageDraw.Draw(page)
    
    img_path = pathlib.Path(cfg.IMAGES_DIR) / pages[0][0]
    if img_path.exists():
        src = Image.open(img_path).convert("RGB")
        w, h, xo, yo = _fit(src.width, src.height, PX_W - 400, PX_H - 1200)
        src = src.resize((w, h), Image.LANCZOS)
        page.paste(src, (200 + xo, 600 + yo))
    
    f_title = _font(True, 180)
    f_sub = _font(False, 90)
    
    draw_text_wrapped(draw, cfg.TITLE, f_title, PX_W - 200, 100, 200, fill=(255, 215, 0), align="center")
    draw_text_wrapped(draw, cfg.SUBTITLE, f_sub, PX_W - 400, 200, 450, fill=(255, 255, 255), align="center")
    draw_text_wrapped(draw, "By " + cfg.AUTHOR, f_sub, PX_W - 400, 200, PX_H - 300, fill=(200, 200, 200), align="center")

    out_path = pathlib.Path("output") / f"{book_name}_COVER.png"
    page.save(out_path, dpi=(DPI, DPI))
    print(f"Cover saved to {out_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--book", required=True)
    args = parser.parse_args()
    make_cover(args.book)
