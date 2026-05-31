"""
pipeline/clean.py — Image artifact cleanup and preparation tool

A standalone utility for cleaning generated coloring-book images before
they are assembled into a PDF. Addresses three common issues with AI-generated
images:

    1. Dark corner / edge artifacts (grey or black blobs)
    2. Landscape orientation when portrait is needed
    3. Manual crop regions specified by the user

Usage:
    # Auto-detect and whiten dark corner artifacts
    python pipeline/clean.py path/to/image.png --auto

    # Whiten specific rectangular zones (in pixels: x1,y1,x2,y2)
    python pipeline/clean.py path/to/image.png --zones "0,0,200,200" "2350,0,2550,200"

    # Crop a landscape image to portrait (center crop)
    python pipeline/clean.py path/to/image.png --crop-portrait

    # Combine operations (order: crop first, then zones, then auto)
    python pipeline/clean.py path/to/image.png --crop-portrait --auto

    # Save to a different output path instead of overwriting
    python pipeline/clean.py path/to/image.png --auto --output path/to/output.png

Output:
    By default, overwrites the input file in-place.
    Use --output to specify a different destination.
    Use --dry-run to preview bounding boxes without writing.
"""

import argparse
from collections import deque
import pathlib
import sys

try:
    from PIL import Image, ImageDraw, ImageFilter
except ImportError:
    print("Missing dependency. Run:  pip install Pillow")
    sys.exit(1)

# ── Constants ──────────────────────────────────────────────────────────────────

# KDP full-page dimensions at 300 DPI (used as reference for auto-detection)
KDP_W = 2550
KDP_H = 3300

# Fraction of image dimensions to sample for auto corner detection
CORNER_FRACTION = 0.08   # 8% of width/height per corner

# Luminance threshold below which a pixel is considered "dark artifact"
# (0 = black, 255 = white)
DARK_THRESHOLD = 80

# Minimum fraction of corner pixels that must be dark before whitening is applied
DARK_DENSITY_MIN = 0.15  # 15%

# --lineart mode: strip colored fills while preserving achromatic pixels (outlines + gray edges).
# A pixel is "colored" when its RGB channels diverge significantly (high chroma).
# Pure white, gray, and black (all achromatic) are kept as-is — this preserves anti-aliased edges.
COLOR_STRIP_TOL = 25   # max RGB channel spread below which pixel is considered achromatic

# Fill-removal: erode black regions to distinguish thin strokes from large solid fills.
# Thin strokes (< FILL_REMOVAL_RADIUS*2 px wide) are eroded away → not in fill mask → preserved.
# Large filled areas survive erosion → detected as fills → whitened.
FILL_REMOVAL_RADIUS = 8   # passes of MaxFilter(3) ≈ erosion depth in pixels

# Solid-region detection thresholds (component-based, quality-preserving).
SOLID_DARK_THRESHOLD = 70
SOLID_MIN_AREA = 120
SOLID_MIN_OCCUPANCY = 0.38
SOLID_MAX_ASPECT = 3.5

# Gray cleanup thresholds (remove shading/gradients while preserving edge antialiasing).
GRAY_MIN = 95
GRAY_MAX = 235
EDGE_DARK_THRESHOLD = 90
EDGE_RADIUS = 0

# Final strict binarization threshold for optional hard BW output.
BINARY_THRESHOLD = 180


# ── Core operations ────────────────────────────────────────────────────────────

def whiten_zone(img: Image.Image, x1: int, y1: int, x2: int, y2: int) -> Image.Image:
    """
    Overwrite a rectangular region with pure white.

    Coordinates are clamped to image bounds automatically.
    """
    w, h  = img.size
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    if x2 <= x1 or y2 <= y1:
        print(f"  WARNING: Zone ({x1},{y1},{x2},{y2}) is empty after clamping — skipped.")
        return img
    draw = ImageDraw.Draw(img)
    draw.rectangle([x1, y1, x2, y2], fill=(255, 255, 255))
    return img


def _corner_zones(img: Image.Image) -> list[tuple[int, int, int, int]]:
    """
    Return bounding boxes for the four corners of the image.

    Each box covers CORNER_FRACTION of the image width and height.
    """
    w, h = img.size
    cw   = int(w * CORNER_FRACTION)
    ch   = int(h * CORNER_FRACTION)
    return [
        (0,      0,      cw,     ch),      # top-left
        (w - cw, 0,      w,      ch),      # top-right
        (0,      h - ch, cw,     h),       # bottom-left
        (w - cw, h - ch, w,      h),       # bottom-right
    ]


def _corner_is_dark(img: Image.Image, box: tuple[int, int, int, int]) -> bool:
    """
    Return True if a sufficient fraction of pixels in the corner box are dark.

    Works on RGB and grayscale images.
    """
    region = img.crop(box).convert("L")   # convert to luminance
    pixels = list(region.getdata())
    if not pixels:
        return False
    dark_count = sum(1 for p in pixels if p < DARK_THRESHOLD)
    density    = dark_count / len(pixels)
    return density >= DARK_DENSITY_MIN


def strip_colors(img: Image.Image, verbose: bool = True) -> Image.Image:
    """
    Remove colored fills while preserving achromatic pixels (outlines and anti-aliased edges).

    A pixel is "colored" when max(R,G,B) - min(R,G,B) > COLOR_STRIP_TOL.
    Colored pixels → pure white (fill removed).
    Achromatic pixels (black, gray, white) → kept as-is (outlines + soft edges preserved).

    This approach avoids thinning anti-aliased strokes, unlike luminance-based thresholding.
    """
    rgb    = img.convert("RGB")
    pixels = list(rgb.getdata())
    result = []
    stripped_count = 0
    for r, g, b in pixels:
        spread = max(r, g, b) - min(r, g, b)
        if spread > COLOR_STRIP_TOL:
            result.append((255, 255, 255))
            stripped_count += 1
        else:
            result.append((r, g, b))
    out = Image.new("RGB", img.size)
    out.putdata(result)
    if verbose:
        total = len(pixels)
        print(f"  [lineart] colored pixels stripped={stripped_count} ({100 * stripped_count / total:.1f}%)")
    return out


def remove_black_fills(img: Image.Image, radius: int = FILL_REMOVAL_RADIUS, verbose: bool = True) -> Image.Image:
    """
    Remove solid black islands without destroying thin outlines.

    Uses connected-component analysis on very dark pixels and removes only components
    that are both sufficiently large and sufficiently dense inside their bounding box.
    This preserves expressive line quality better than global binarization.
    """
    _ = radius  # kept for backward compatibility with existing call sites

    gray = img.convert("L")
    w, h = gray.size
    lum = list(gray.getdata())
    dark = [v < SOLID_DARK_THRESHOLD for v in lum]
    visited = bytearray(w * h)
    rgb_data = list(img.convert("RGB").getdata())

    removed_pixels = 0
    removed_components = 0

    def _neighbors(idx: int):
        x = idx % w
        y = idx // w
        if x > 0:
            yield idx - 1
        if x < w - 1:
            yield idx + 1
        if y > 0:
            yield idx - w
        if y < h - 1:
            yield idx + w
        if x > 0 and y > 0:
            yield idx - w - 1
        if x < w - 1 and y > 0:
            yield idx - w + 1
        if x > 0 and y < h - 1:
            yield idx + w - 1
        if x < w - 1 and y < h - 1:
            yield idx + w + 1

    for start in range(w * h):
        if visited[start] or not dark[start]:
            continue

        q = deque([start])
        visited[start] = 1
        comp = []
        min_x = max_x = start % w
        min_y = max_y = start // w

        while q:
            idx = q.popleft()
            comp.append(idx)
            x = idx % w
            y = idx // w
            if x < min_x:
                min_x = x
            if x > max_x:
                max_x = x
            if y < min_y:
                min_y = y
            if y > max_y:
                max_y = y

            for nb in _neighbors(idx):
                if not visited[nb] and dark[nb]:
                    visited[nb] = 1
                    q.append(nb)

        area = len(comp)
        bbox_area = (max_x - min_x + 1) * (max_y - min_y + 1)
        occupancy = (area / bbox_area) if bbox_area else 0.0
        width = max_x - min_x + 1
        height = max_y - min_y + 1
        aspect = (max(width, height) / max(1, min(width, height)))

        if area >= SOLID_MIN_AREA and occupancy >= SOLID_MIN_OCCUPANCY and aspect <= SOLID_MAX_ASPECT:
            for idx in comp:
                rgb_data[idx] = (255, 255, 255)
            removed_pixels += area
            removed_components += 1

    out = Image.new("RGB", img.size)
    out.putdata(rgb_data)
    if verbose:
        total = w * h
        print(
            f"  [fill-removal] removed {removed_components} dense dark component(s), "
            f"{removed_pixels} px ({100 * removed_pixels / total:.1f}%)"
        )
    return out


def remove_gray_fills_preserve_edges(img: Image.Image, verbose: bool = True) -> Image.Image:
    """
    Remove shading/gradients while preserving line quality around edges.

    Mid-tone gray pixels are whitened to suppress residual gradients/shading while
    preserving true dark outlines.
    """
    gray = img.convert("L")
    gray_data = list(gray.getdata())
    edge_seed = gray.point(lambda p: 0 if p < EDGE_DARK_THRESHOLD else 255)

    near_edges = edge_seed
    for _ in range(EDGE_RADIUS):
        near_edges = near_edges.filter(ImageFilter.MinFilter(3))
    near_edges_data = list(near_edges.getdata())

    rgb_data = list(img.convert("RGB").getdata())
    cleaned = 0
    result = []
    for lum, near, px in zip(gray_data, near_edges_data, rgb_data):
        if near > 250 and GRAY_MIN <= lum <= GRAY_MAX:
            result.append((255, 255, 255))
            cleaned += 1
        else:
            result.append(px)

    out = Image.new("RGB", img.size)
    out.putdata(result)
    if verbose:
        total = len(result)
        print(f"  [gray-clean] whitened {cleaned} gray pixels ({100 * cleaned / total:.1f}%)")
    return out


def enforce_binary_lineart(img: Image.Image, threshold: int = BINARY_THRESHOLD, verbose: bool = True) -> Image.Image:
    """
    Force strict black/white output to eliminate gradients and gray shading.

    After fill cleanup, any remaining grayscale anti-shading is converted to pure
    binary line art: dark pixels -> black, all others -> white.
    """
    gray = img.convert("L")
    # Mode "1" applies a hard threshold and stores 0/255 only.
    bw = gray.point(lambda p: 0 if p < threshold else 255, mode="1").convert("RGB")
    if verbose:
        black = sum(1 for p in bw.convert("L").getdata() if p == 0)
        total = bw.width * bw.height
        print(f"  [binary] strict BW applied, black pixels={black} ({100 * black / total:.1f}%)")
    return bw


def auto_clean_corners(img: Image.Image, verbose: bool = True) -> tuple[Image.Image, int]:
    """
    Detect and whiten dark corner artifacts automatically.

    Returns the cleaned image and the number of corners that were whitened.
    """
    zones    = _corner_zones(img)
    names    = ["top-left", "top-right", "bottom-left", "bottom-right"]
    cleaned  = 0
    for box, name in zip(zones, names):
        if _corner_is_dark(img, box):
            if verbose:
                print(f"  [auto] Whitening dark corner: {name}  {box}")
            img     = whiten_zone(img, *box)
            cleaned += 1
        elif verbose:
            print(f"  [auto] Corner OK (no artifact): {name}")
    return img, cleaned


def crop_to_portrait(img: Image.Image) -> Image.Image:
    """
    Crop a landscape image to portrait by taking the center vertical strip.

    If the image is already portrait (height >= width), it is returned unchanged.
    The output retains the full height; width is cropped to match KDP proportions
    (8.5 / 11 = ~0.773 aspect ratio) when possible, otherwise to full height.
    """
    w, h = img.size
    if h >= w:
        print(f"  [crop] Image is already portrait ({w}x{h}) — no crop needed.")
        return img

    # Target width for portrait: maintain 8.5:11 ratio relative to full height
    target_w = int(h * (8.5 / 11.0))
    target_w = min(target_w, w)   # can't exceed actual width

    # Content-aware horizontal center: bias crop toward dark-line mass so we
    # keep the character in frame instead of always taking exact center strip.
    gray = img.convert("L")
    px = gray.load()
    step_y = max(1, h // 300)
    weights = [0] * w
    for y in range(0, h, step_y):
        for x in range(w):
            lum = px[x, y]
            # Weight dark strokes more heavily; ignore near-white background.
            if lum < 245:
                weights[x] += (255 - lum)

    total = sum(weights)
    if total > 0:
        center_x = int(sum(i * wgt for i, wgt in enumerate(weights)) / total)
    else:
        center_x = w // 2

    x1 = max(0, min(w - target_w, center_x - (target_w // 2)))
    x2 = x1 + target_w
    print(f"  [crop] Landscape {w}x{h} -> portrait {target_w}x{h}  (x: {x1}..{x2}, center_x={center_x})")
    return img.crop((x1, 0, x2, h))


def parse_zone(zone_str: str) -> tuple[int, int, int, int]:
    """
    Parse a zone string "x1,y1,x2,y2" into a tuple of ints.

    Raises ValueError with a helpful message if the format is invalid.
    """
    try:
        parts = [int(v.strip()) for v in zone_str.split(",")]
        if len(parts) != 4:
            raise ValueError("Expected exactly 4 values")
        x1, y1, x2, y2 = parts
        if x1 >= x2 or y1 >= y2:
            raise ValueError("x1 must be < x2 and y1 must be < y2")
        return x1, y1, x2, y2
    except ValueError as e:
        raise ValueError(
            f"Invalid zone '{zone_str}': {e}. "
            "Format must be 'x1,y1,x2,y2' with x1<x2 and y1<y2."
        ) from e


# ── CLI ────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Clean and prepare coloring-book images for KDP assembly.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python pipeline/clean.py images/book1-90s/book1_conan.png --auto
    python pipeline/clean.py images/book1-90s/book1_conan.png --zones "0,0,300,300"
    python pipeline/clean.py images/book1-90s/book1_conan.png --crop-portrait --auto
    python pipeline/clean.py images/book1-90s/book1_conan.png --auto --output /tmp/preview.png
        """,
    )
    parser.add_argument(
        "image",
        type=pathlib.Path,
        help="Path to the image file to clean (PNG, JPG, etc.)",
    )
    parser.add_argument(
        "--zones",
        nargs="+",
        metavar="x1,y1,x2,y2",
        help="One or more rectangular zones to whiten (pixel coordinates).",
    )
    parser.add_argument(
        "--lineart",
        action="store_true",
        help="Apply quality-preserving cleanup: strip colors, remove solid black fills, and clean gray shading.",
    )
    parser.add_argument(
        "--strict-bw",
        action="store_true",
        help="Optional hard binarization (0/255 only). More aggressive, can reduce detail quality.",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Auto-detect and whiten dark corner artifacts.",
    )
    parser.add_argument(
        "--crop-portrait",
        action="store_true",
        help="Crop a landscape image to portrait orientation (center crop).",
    )
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        default=None,
        metavar="PATH",
        help="Output path. Defaults to overwriting the input file in-place.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without writing any file.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    img_path = args.image.resolve()
    if not img_path.exists():
        print(f"ERROR: Image not found: {img_path}")
        sys.exit(1)

    if not (args.zones or args.auto or args.crop_portrait or args.lineart):
        print("ERROR: Specify at least one operation: --zones, --auto, --crop-portrait, or --lineart")
        sys.exit(1)

    out_path = (args.output or img_path).resolve()

    print(f"Image : {img_path}")
    print(f"Output: {out_path}")
    if args.dry_run:
        print("(dry-run — no file will be written)\n")

    img = Image.open(img_path).convert("RGB")
    print(f"Size  : {img.width}x{img.height} px\n")

    # Operations are applied in a logical order:
    # 1. Crop to correct orientation first (changes dimensions)
    # 2. Strip colors (lineart) before zone cleaning — outlines are now pure black
    # 3. Then whiten specific zones (coordinates refer to the cropped image)
    # 4. Auto-detect corners last (so it operates on the final geometry)

    if args.crop_portrait:
        img = crop_to_portrait(img)

    if args.lineart:
        img = strip_colors(img)
        img = remove_black_fills(img)
        img = remove_gray_fills_preserve_edges(img)
        if args.strict_bw:
            img = enforce_binary_lineart(img)

    if args.zones:
        for zone_str in args.zones:
            try:
                x1, y1, x2, y2 = parse_zone(zone_str)
            except ValueError as e:
                print(f"ERROR: {e}")
                sys.exit(1)
            print(f"  [zone] Whitening ({x1},{y1}) -> ({x2},{y2})")
            img = whiten_zone(img, x1, y1, x2, y2)

    if args.auto:
        img, n_cleaned = auto_clean_corners(img, verbose=True)
        print(f"\n  [auto] {n_cleaned} corner(s) cleaned.")

    if args.dry_run:
        print("\nDry-run complete — image not saved.")
        return

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out_path), dpi=(300, 300))
    size_kb = out_path.stat().st_size / 1024
    print(f"\nSaved: {out_path}  ({size_kb:.0f} KB)")


if __name__ == "__main__":
    main()
