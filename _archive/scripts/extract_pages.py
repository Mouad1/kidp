"""
extract_pages.py
Extracts individual coloring pages from a Gemini-generated grid image.

Recommended usage (4×2 grid = standard Gemini output):
    python3 extract_pages.py --input ../images/8\ in\ one\ crossover.png --cols 4 --rows 2 --prefix book1

For images where rows are well-detected but columns are noisy:
    python3 extract_pages.py --input ../images/book-v1.png --auto-rows --cols 4 --prefix book1

Auto-detect (works best on clean grids like the crossover):
    python3 extract_pages.py --input ../images/8\ in\ one\ crossover.png --auto --prefix book1

Debug/preview mode (shows detected grid without saving):
    python3 extract_pages.py --input ../images/book-v1.png --cols 4 --rows 5 --debug
"""

import sys
import argparse
import pathlib
import numpy as np

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageEnhance
except ImportError:
    print("Run: pip3 install Pillow numpy")
    sys.exit(1)

OUTPUT_DIR = pathlib.Path(__file__).parent.parent / "images" / "extracted"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Separator detection ───────────────────────────────────────────────────────

def find_separator_bands(arr: np.ndarray, axis: int,
                          white_threshold: float = 220,
                          white_ratio: float = 0.85) -> list[tuple[int,int]]:
    """
    Find white separator bands (rows or columns mostly white).
    Returns list of (start, end) tuples for each band.
    axis=0 → scan rows | axis=1 → scan cols
    """
    if axis == 0:
        means = np.mean(arr >= white_threshold, axis=1)
    else:
        means = np.mean(arr >= white_threshold, axis=0)

    bands = []
    in_band = False
    start = 0
    for i, v in enumerate(means):
        if v >= white_ratio and not in_band:
            in_band = True
            start = i
        elif v < white_ratio and in_band:
            in_band = False
            bands.append((start, i))
    if in_band:
        bands.append((start, len(means)))
    return bands


def merge_nearby_bands(bands: list[tuple[int,int]], min_gap: int) -> list[tuple[int,int]]:
    """Merge separator bands that are closer than min_gap pixels."""
    if not bands:
        return []
    merged = [bands[0]]
    for start, end in bands[1:]:
        prev_start, prev_end = merged[-1]
        if start - prev_end <= min_gap:
            merged[-1] = (prev_start, end)
        else:
            merged.append((start, end))
    return merged


def filter_edge_bands(bands: list[tuple[int,int]], total: int,
                       edge_margin: int = 60) -> list[tuple[int,int]]:
    """Remove bands that are too close to image edges (those are just borders)."""
    return [b for b in bands if b[0] > edge_margin and b[1] < total - edge_margin]


def bands_to_midpoints(bands: list[tuple[int,int]]) -> list[int]:
    return [int((s + e) / 2) for s, e in bands]


def keep_n_evenly_spaced(midpoints: list[int], n: int, total: int) -> list[int]:
    """
    From a list of candidate separator midpoints, keep the N ones that
    best divide the image into equal cells. Handles false positives.
    """
    if len(midpoints) <= n:
        return midpoints

    # Try all combinations of n midpoints, pick the one that minimizes
    # variance in cell sizes
    from itertools import combinations
    best = None
    best_variance = float('inf')
    for combo in combinations(midpoints, n):
        bounds = [0] + list(combo) + [total]
        sizes = [bounds[i+1] - bounds[i] for i in range(len(bounds)-1)]
        variance = np.var(sizes)
        if variance < best_variance:
            best_variance = variance
            best = combo
    return list(best)


def smart_detect_separators(img: Image.Image, cols: int, rows: int,
                              search_window: int = 100,
                              white_threshold: int = 220) -> tuple[list[int], list[int]]:
    """
    Find separator positions by searching for the whitest row/column
    near each expected equal-division position.
    Robust when decorative background elements make full-row detection fail.
    """
    arr = np.array(img.convert("L"), dtype=np.float32)
    h, w = arr.shape

    row_white = np.array([np.mean(arr[y, :] >= white_threshold) for y in range(h)])
    col_white = np.array([np.mean(arr[:, x] >= white_threshold) for x in range(w)])

    def best_near(profile, expected, window):
        start = max(0, expected - window)
        end   = min(len(profile), expected + window)
        return int(np.argmax(profile[start:end])) + start

    col_mids = [best_near(col_white, w * i // cols, search_window) for i in range(1, cols)]
    row_mids = [best_near(row_white, h * i // rows, search_window) for i in range(1, rows)]

    print(f"  Smart separators — rows: {row_mids} | cols: {col_mids}")
    return col_mids, row_mids


def auto_detect_separators(img: Image.Image, expected_cols: int = None,
                             expected_rows: int = None) -> tuple[list[int], list[int]]:
    """
    Auto-detect grid separators. If expected_cols/rows given, selects the
    N best separator positions (handles false positives in content).
    """
    arr = np.array(img.convert("L"), dtype=np.float32)
    h, w = arr.shape

    # Detect raw bands
    raw_col_bands = find_separator_bands(arr, axis=1)
    raw_row_bands = find_separator_bands(arr, axis=0)

    # Merge bands that are close together (content white areas merging with separators)
    min_gap_col = max(10, w // 20)
    min_gap_row = max(10, h // 20)

    col_bands = merge_nearby_bands(raw_col_bands, min_gap=min_gap_col)
    row_bands = merge_nearby_bands(raw_row_bands, min_gap=min_gap_row)

    # Remove edge bands
    col_bands = filter_edge_bands(col_bands, w)
    row_bands = filter_edge_bands(row_bands, h)

    col_mids = bands_to_midpoints(col_bands)
    row_mids = bands_to_midpoints(row_bands)

    # If expected count given, select best N separators
    if expected_cols:
        n_col_seps = expected_cols - 1
        if len(col_mids) > n_col_seps:
            col_mids = keep_n_evenly_spaced(col_mids, n_col_seps, w)
        elif len(col_mids) < n_col_seps:
            # Fall back to equal division
            cell_w = w // expected_cols
            col_mids = [cell_w * i for i in range(1, expected_cols)]

    if expected_rows:
        n_row_seps = expected_rows - 1
        if len(row_mids) > n_row_seps:
            row_mids = keep_n_evenly_spaced(row_mids, n_row_seps, h)
        elif len(row_mids) < n_row_seps:
            cell_h = h // expected_rows
            row_mids = [cell_h * i for i in range(1, expected_rows)]

    return col_mids, row_mids


def midpoints_to_slices(midpoints: list[int], total: int, min_size: int = 50) -> list[tuple[int,int]]:
    bounds = [0] + midpoints + [total]
    return [(bounds[i], bounds[i+1]) for i in range(len(bounds)-1)
            if bounds[i+1] - bounds[i] >= min_size]


# ── Cell processing ───────────────────────────────────────────────────────────

def trim_cell(cell: Image.Image, padding: int = 15) -> Image.Image:
    """Trim white borders and add small padding."""
    gray = np.array(cell.convert("L"))
    mask = gray < 230
    if not mask.any():
        return cell
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]
    rmin = max(0, rmin - padding)
    rmax = min(cell.height - 1, rmax + padding)
    cmin = max(0, cmin - padding)
    cmax = min(cell.width - 1, cmax + padding)
    return cell.crop((cmin, rmin, cmax + 1, rmax + 1))


def inner_crop(cell: Image.Image, pct: float = 0.08) -> Image.Image:
    """
    Crop a percentage from each side to remove bleed from adjacent pages.
    Use when the grid image is a catalog/mockup with overlapping page shadows.
    pct=0.08 removes 8% from each side (top, bottom, left, right).
    """
    w, h = cell.size
    dx = int(w * pct)
    dy = int(h * pct)
    return cell.crop((dx, dy, w - dx, h - dy))


def crop_to_inner_content(cell: Image.Image,
                           dark_threshold: int = 80,
                           strong_border_ratio: float = 0.5,
                           edge_depth: int = 100,
                           safe_inset: int = 8,
                           inset: int = 5) -> Image.Image:
    """
    Detect the Gemini cell border and crop to just inside it.

    Strategy per edge:
    - Find the peak dark row/col in the first `edge_depth` pixels
    - If peak ratio >= strong_border_ratio → strong border found, crop just past it
    - Otherwise → border was cut by separator, use `safe_inset` from edge

    Left/Right/Bottom borders are always strong (ratio ~1.0).
    Top border of rows 2+ may be cut → falls back to safe_inset.
    """
    arr = np.array(cell.convert("L"), dtype=np.float32)
    ch, cw = arr.shape

    def find_border_peak(axis: int, from_end: bool) -> int:
        total  = ch if axis == 0 else cw
        other  = cw if axis == 0 else ch
        za, zb = int(other * 0.20), int(other * 0.80)

        best_pos, best_ratio = 0, 0.0
        for i in range(min(edge_depth, total)):
            idx  = (total - 1 - i) if from_end else i
            line = arr[idx, za:zb] if axis == 0 else arr[za:zb, idx]
            r    = float(np.mean(line < dark_threshold))
            if r > best_ratio:
                best_ratio, best_pos = r, idx

        if best_ratio >= strong_border_ratio:
            # Strong border: crop just past it
            return best_pos
        else:
            # Weak/missing border (cut by separator): safe inset from edge
            return (total - 1 - safe_inset) if from_end else safe_inset

    top    = find_border_peak(0, False)
    bottom = find_border_peak(0, True)
    left   = find_border_peak(1, False)
    right  = find_border_peak(1, True)

    x0 = min(left   + inset, cw // 2)
    y0 = min(top    + inset, ch // 2)
    x1 = max(right  - inset + 1, cw // 2 + 1)
    y1 = max(bottom - inset + 1, ch // 2 + 1)

    return cell.crop((x0, y0, x1, y1))


def find_page_frame(cell: Image.Image, border_threshold: int = 180,
                     min_fill: float = 0.55) -> Image.Image:
    """
    Detect the actual page frame (rectangular border) within a cell and crop to it.
    Works on catalog/mockup images where each thumbnail has a visible page outline.

    Strategy:
    1. Find the largest white rectangle (the page itself, not shadows/adjacent content)
    2. Crop to that rectangle with a small inset to exclude the border line itself
    """
    gray = np.array(cell.convert("L"), dtype=np.float32)
    h, w = gray.shape

    # White region = inside the page frame (bright content)
    white_mask = gray >= border_threshold

    # Find the largest axis-aligned rectangle filled mostly with white
    # Simplified: scan from center outward to find tight white bounding box
    # that contains at least min_fill of white pixels

    # Start from 10% inset on each side and expand inward until we find
    # a region that is mostly white content (the page interior)
    best_box = None
    best_score = 0.0

    for inset_pct in [0.05, 0.08, 0.10, 0.12, 0.15, 0.18, 0.20]:
        dx = int(w * inset_pct)
        dy = int(h * inset_pct)
        box = (dx, dy, w - dx, h - dy)
        region = white_mask[dy:h-dy, dx:w-dx]
        if region.size == 0:
            continue
        fill = region.mean()
        # Prefer box with high white fill but as large as possible
        score = fill * (region.size / (w * h))
        if fill >= min_fill and score > best_score:
            best_score = score
            best_box = box

    if best_box is None:
        return cell  # fallback: return as-is

    return cell.crop(best_box)


def _upscale_progressive(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """
    Upscale in ×2 steps with sharpening between each pass.
    Much crisper than a single large LANCZOS jump.
    """
    w, h = img.size
    while w * 2 <= target_w or h * 2 <= target_h:
        w, h = min(w * 2, target_w * 2), min(h * 2, target_h * 2)
        img = img.resize((w, h), Image.LANCZOS)
        img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=120, threshold=2))
    # Final resize to exact target
    if (img.width, img.height) != (target_w, target_h):
        img = img.resize((target_w, target_h), Image.LANCZOS)
    return img


def _try_esrgan(img: Image.Image) -> Image.Image | None:
    """
    AI upscaling via Real-ESRGAN anime ×4 model, loaded through spandrel.
    Model is downloaded once to ~/.cache/kidp/esrgan_anime.pth (~17MB).
    Install: pip install spandrel torch torchvision
    """
    try:
        import torch
        import urllib.request
        import spandrel

        MODEL_URL = (
            "https://github.com/xinntao/Real-ESRGAN/releases/download/"
            "v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth"
        )
        cache_dir = pathlib.Path.home() / ".cache" / "kidp"
        cache_dir.mkdir(parents=True, exist_ok=True)
        model_path = cache_dir / "RealESRGAN_x4plus_anime_6B.pth"

        if not model_path.exists():
            print("    ⬇️  Downloading ESRGAN anime model (~17MB)...")
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(MODEL_URL, context=ctx) as resp, \
                 open(model_path, "wb") as f:
                f.write(resp.read())
            print("    ✅ Model downloaded")

        device = "cuda" if torch.cuda.is_available() else "cpu"
        descriptor = spandrel.ModelLoader(device=device).load_from_file(str(model_path))
        model = descriptor.model.eval().to(device)

        arr = np.array(img.convert("RGB"), dtype=np.float32) / 255.0
        tensor = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0).to(device)

        with torch.no_grad():
            out = model(tensor)

        out_arr = (out.squeeze(0).permute(1, 2, 0).clamp(0, 1).cpu().numpy() * 255).astype(np.uint8)
        return Image.fromarray(out_arr)

    except Exception as e:
        print(f"    ⚠️  ESRGAN error: {e}")
        return None


def enhance_for_coloring(img: Image.Image) -> Image.Image:
    """
    Post-upscale enhancement pass:
    1. Grayscale — no color leaks
    2. Autocontrast — full 0-255 tonal range
    3. UnsharpMask — crisp line edges
    4. Contrast boost — pure black lines on white
    """
    gray = img.convert("L")
    gray = ImageOps.autocontrast(gray, cutoff=1)
    gray = gray.filter(ImageFilter.UnsharpMask(radius=2, percent=200, threshold=2))
    gray = ImageEnhance.Contrast(gray).enhance(1.8)
    return gray.convert("RGB")


def center_on_kdp_page(cell: Image.Image, enhance: bool = True,
                        use_esrgan: bool = False) -> Image.Image:
    """Center cell on an 8.5×11 white KDP page at 300 DPI.

    Upscaling strategy (best → fallback):
      use_esrgan=True  → Real-ESRGAN anime ×4 (requires realesrgan + basicsr)
      default          → progressive ×2 steps with mid-pass sharpening
    """
    page_w, page_h = int(8.5 * 300), int(11.0 * 300)
    margin = int(0.5 * 300)
    max_w, max_h = page_w - 2 * margin, page_h - 2 * margin

    scale = min(max_w / cell.width, max_h / cell.height)
    target_w, target_h = int(cell.width * scale), int(cell.height * scale)

    # ── Upscale ──────────────────────────────────────────────────────────────
    if use_esrgan:
        esrgan_out = _try_esrgan(cell)
        if esrgan_out is not None:
            # ESRGAN outputs ×4 — resize to exact target
            resized = esrgan_out.resize((target_w, target_h), Image.LANCZOS)
            print("    ✨ ESRGAN upscale applied")
        else:
            print("    ⚠️  ESRGAN not available, falling back to progressive upscale")
            resized = _upscale_progressive(cell.convert("RGB"), target_w, target_h)
    else:
        resized = _upscale_progressive(cell.convert("RGB"), target_w, target_h)

    # ── Enhance ──────────────────────────────────────────────────────────────
    if enhance:
        resized = enhance_for_coloring(resized)

    # ── Place on KDP page ────────────────────────────────────────────────────
    page = Image.new("RGB", (page_w, page_h), "white")
    x, y = (page_w - target_w) // 2, (page_h - target_h) // 2
    page.paste(resized.convert("RGB"), (x, y))
    return page


def debug_preview(img: Image.Image, col_mids: list[int], row_mids: list[int],
                   output_path: pathlib.Path):
    """Save a preview image with detected grid lines drawn in red."""
    preview = img.convert("RGB").copy()
    draw = ImageDraw.Draw(preview)
    for x in col_mids:
        draw.line([(x, 0), (x, img.height)], fill=(255, 0, 0), width=3)
    for y in row_mids:
        draw.line([(0, y), (img.width, y)], fill=(255, 0, 0), width=3)
    preview.save(output_path)
    print(f"  🔍 Debug preview saved: {output_path}")


# ── Main extraction ───────────────────────────────────────────────────────────

def extract(input_path: pathlib.Path, cols: int, rows: int,
            auto: bool, auto_rows: bool, auto_cols: bool, smart: bool,
            prefix: str, trim: bool, kdp_format: bool, debug: bool,
            inner_crop_pct: float = 0.0, find_frame: bool = False,
            crop_border: bool = False, enhance: bool = True,
            use_esrgan: bool = False):

    img = Image.open(input_path)
    w, h = img.size
    print(f"Input: {input_path.name} ({w}×{h})")

    # Determine separator positions
    if smart:
        col_mids, row_mids = smart_detect_separators(img, cols, rows)
    elif auto:
        col_mids, row_mids = auto_detect_separators(img, expected_cols=cols, expected_rows=rows)
    elif auto_rows:
        # Auto-detect rows, divide cols equally
        _, row_mids = auto_detect_separators(img, expected_rows=rows)
        cell_w = w // cols
        col_mids = [cell_w * i for i in range(1, cols)]
    elif auto_cols:
        # Auto-detect cols, divide rows equally
        col_mids, _ = auto_detect_separators(img, expected_cols=cols)
        cell_h = h // rows
        row_mids = [cell_h * i for i in range(1, rows)]
    else:
        # Manual equal division
        cell_w = w // cols
        cell_h = h // rows
        col_mids = [cell_w * i for i in range(1, cols)]
        row_mids = [cell_h * i for i in range(1, rows)]

    col_slices = midpoints_to_slices(col_mids, w)
    row_slices = midpoints_to_slices(row_mids, h)

    n_cols = len(col_slices)
    n_rows = len(row_slices)
    total = n_cols * n_rows
    print(f"Grid: {n_cols} cols × {n_rows} rows = {total} cells")

    if debug:
        debug_path = OUTPUT_DIR / f"{prefix}_debug_grid.png"
        debug_preview(img, col_mids, row_mids, debug_path)
        return

    count = 0
    for r, (r0, r1) in enumerate(row_slices):
        for c, (c0, c1) in enumerate(col_slices):
            count += 1
            cell = img.crop((c0, r0, c1, r1))

            if inner_crop_pct > 0:
                cell = inner_crop(cell, pct=inner_crop_pct)

            if crop_border:
                cell = crop_to_inner_content(cell)

            if find_frame:
                cell = find_page_frame(cell)

            if trim:
                cell = trim_cell(cell)

            if kdp_format:
                cell = center_on_kdp_page(cell, enhance=enhance, use_esrgan=use_esrgan)
            else:
                if enhance:
                    cell = enhance_for_coloring(cell)
                else:
                    cell = cell.convert("RGB")

            filename = f"{prefix}_{count:02d}.png"
            out_path = OUTPUT_DIR / filename
            cell.save(out_path, dpi=(300, 300))
            print(f"  ✅ [{count:02d}/{total}] {filename} → {cell.size[0]}×{cell.size[1]}")

    print(f"\n✅ Done: {count} pages → {OUTPUT_DIR}")


def main():
    parser = argparse.ArgumentParser(description="Extract coloring pages from a Gemini grid image")
    parser.add_argument("--input", type=str, required=True)
    parser.add_argument("--cols", type=int, default=4, help="Number of columns (default: 4)")
    parser.add_argument("--rows", type=int, default=2, help="Number of rows (default: 2)")

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--auto", action="store_true",
                      help="Auto-detect both rows and cols (best for clean grids like 4×2)")
    mode.add_argument("--auto-rows", action="store_true",
                      help="Auto-detect rows, divide cols equally (best when cols are noisy)")
    mode.add_argument("--auto-cols", action="store_true",
                      help="Auto-detect cols, divide rows equally")
    mode.add_argument("--smart", action="store_true",
                      help="Smart auto-detect: finds actual whitest rows/cols near expected positions")

    parser.add_argument("--prefix", type=str, default="page")
    parser.add_argument("--no-trim", action="store_true")
    parser.add_argument("--no-kdp", action="store_true")
    parser.add_argument("--debug", action="store_true",
                        help="Show detected grid lines without extracting pages")
    parser.add_argument("--inner-crop", type=float, default=0.0, metavar="PCT",
                        help="Remove PCT%% from each side to fix catalog bleed (e.g. 0.08 = 8%%)")
    parser.add_argument("--find-frame", action="store_true",
                        help="Auto-detect page frame rectangle within each cell (best for catalog/mockup images)")
    parser.add_argument("--crop-border", action="store_true",
                        help="Detect and remove Gemini cell border lines, keeping only the artwork inside")
    parser.add_argument("--no-enhance", action="store_true",
                        help="Skip image enhancement (autocontrast + sharpen + contrast boost)")
    parser.add_argument("--esrgan", action="store_true",
                        help="Use Real-ESRGAN anime model for AI upscaling (requires: pip install realesrgan basicsr)")
    args = parser.parse_args()

    input_path = pathlib.Path(args.input)
    if not input_path.exists():
        print(f"File not found: {input_path}")
        sys.exit(1)

    extract(
        input_path=input_path,
        cols=args.cols,
        rows=args.rows,
        auto=args.auto,
        auto_rows=args.auto_rows,
        auto_cols=args.auto_cols,
        smart=args.smart,
        prefix=args.prefix,
        trim=not args.no_trim,
        kdp_format=not args.no_kdp,
        debug=args.debug,
        inner_crop_pct=args.inner_crop,
        find_frame=args.find_frame,
        crop_border=args.crop_border,
        enhance=not args.no_enhance,
        use_esrgan=args.esrgan,
    )


if __name__ == "__main__":
    main()
