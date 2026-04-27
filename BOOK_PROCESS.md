# KDP Coloring Book — Complete Production Process

> Complete reproducible guide. Anyone with this file can replicate the full workflow from scratch.
> Last updated: 2026-04-13 | Status: Book 1 interior PDF ready (59p, 0 fonts) | Cover pending.

---

## LESSONS LEARNED (read before starting)

- **Generate characters ONE BY ONE** — grid generation produces poor quality and misaligned characters
- **Landscape images** — AI often generates landscape (2816×1536). Use `clean.py --crop-portrait` to fix
- **Gemini artifacts** — floating heads or text in top-left / bottom corners. Use `clean.py --auto` or `--zones`
- **Gemini logo** — 4-pointed star watermark. Remove manually in Pillow (texture clone)
- **Scene pages** — generate 5-6 "group scene" images to interleave between individual pages every 3-4 characters
- **KDP categories** — do NOT use "Juvenile Nonfiction". Use Arts & Photography > Drawing > Manga
- **Font embedding** — use `pipeline/assemble.py` only (img2pdf, zero fonts). Never use reportlab for KDP interior
- **One-sided pages** — always add a blank white page after each coloring page (industry standard)

---

## STEP 1 — Generate pages in Gemini (ONE character at a time)

Open Gemini (gemini.google.com) and generate **one character per prompt**.

### Prompt template (copy, replace bracketed parts)
```
Provide Professional adult coloring book page of [CHARACTER NAME] ([brief physical description]),
full body centered, pure white background. Thick, bold black vector-style outlines.
Zero shading, zero gray fills, zero gradients. High contrast, clean line art,
300 DPI quality, minimalist style ready for coloring.
```

### Save convention
Save each image as: `images/<book-folder>/<book-prefix>_<character-id>.png`

Example for Book 1: `images/book1-90s/book1_naruto.png`
Example for Book 2: `images/book2-modern-anime/book2_flame_pillar.png`

### Also generate 5-6 "scene" pages (multiple characters together)
These are used to break up the book between individual pages.

```
Provide Professional adult coloring book page featuring [CHARACTER A] and [CHARACTER B]
in a dramatic action scene together, full body, pure white background.
Thick, bold black vector-style outlines. Zero shading, zero gray fills, zero gradients.
High contrast, clean line art, 300 DPI quality, minimalist style ready for coloring.
```

### All characters — Book 1 (90s Legends) — see `books/book1-90s-legends/config.py`
### All characters — Book 2 (Modern Anime) — see `books/book2-modern-anime/config.py`

### Tips
- If shading appears: add "CRITICAL: zero gray shading, white fill only inside outlines"
- For consistent style: start prompt with "Same art style as previous image:"
- If image is landscape: run `pipeline/clean.py --crop-portrait` (see Step 1b)

---

## STEP 1b — Clean artifacts (ALWAYS do this before assembling)

Gemini often adds artifacts: floating heads, text labels, ink symbols in corners.
Landscape images need to be cropped to portrait.

```bash
# From project root

# Auto-detect and whiten dark corner artifacts
python pipeline/clean.py images/book1-90s/book1_conan.png --auto

# Whiten specific rectangular zones (pixel coordinates: x1,y1,x2,y2)
python pipeline/clean.py images/book1-90s/book1_blade_clean.png --zones "0,0,600,680"

# Crop landscape image to portrait orientation
python pipeline/clean.py images/book1-90s/book1_slam1.png --crop-portrait

# Combine: crop first, then auto-clean corners
python pipeline/clean.py images/book1-90s/book1_slam1.png --crop-portrait --auto

# Preview without writing (dry-run)
python pipeline/clean.py images/book1-90s/book1_conan.png --auto --dry-run

# Save to a different path (keep original)
python pipeline/clean.py images/book1-90s/book1_slam1.png --crop-portrait --output images/book1-90s/book1_slam1_portrait.png
```

### Common artifact zones for Gemini images at 2816×1536

| Artifact               | Typical zone             |
|------------------------|--------------------------|
| Floating head top-left | `0,0,600,700`            |
| Flash / zigzag         | `0,0,500,600`            |
| Text label bottom      | `0,1350,1500,1536`       |
| Ink symbol bottom      | `800,1300,1400,1536`     |

Once cleaned, update the filename in `books/<book>/config.py → PAGE_SEQUENCE`.

---

## STEP 2 — Assemble interior PDF

```bash
# From project root
python pipeline/assemble.py --book book1-90s-legends
```

Output: `output/book1-90s-legends_interior_FINAL.pdf`

The assembler reads `books/book1-90s-legends/config.py` and:
- Renders all pages as PIL images at 2550×3300 px (8.5"×11" @ 300 DPI)
- Adds title page + copyright page (text baked as pixels — zero embedded fonts)
- Places the testpen page once, right before the first coloring page
- Inserts a blank white page after every coloring page (industry standard)
- Assembles with img2pdf — zero embedded fonts → zero KDP rejection risk
- Verifies font count in the output PDF

**Page structure (book 1 example — 27 content pages):**
```
Title page             (1)
Copyright page         (2)
Testpen page           (3)
Blank back             (4)
27 × (coloring + blank) = 54 pages
Back-matter page       (59)
Total: 59 pages
```

**To add a new book:**
```bash
cp -r books/book1-90s-legends books/book3-shonen
# Edit books/book3-shonen/config.py: TITLE, SUBTITLE, AUTHOR, IMAGES_DIR, PAGE_SEQUENCE
python pipeline/assemble.py --book book3-shonen
```

---

## STEP 2b — Choose your pen name

A **pen name** is a fake author name you put on your book instead of your real name.
It protects your privacy and lets you build a brand identity on Amazon.

### Why use one
- Your real name is NOT shown on Amazon
- You can have multiple pen names for different niches (anime, fantasy, kids, etc.)
- It does not need to be registered anywhere — just enter it consistently in KDP

### How to choose one
Pick a first + last name. Aim for:
- Easy to remember and spell
- Sounds like a creative/artistic person
- Neutral (works for all markets: US, UK, etc.)

**Ideas for an anime coloring book brand:**

| Style | Examples |
|---|---|
| Japanese-inspired | Kai Mori, Ryu Tanaka, Hana Sato, Yuki Hara |
| Western creative | Max Blake, Alex Storm, Sam Noir, Leo Ink |
| Gender-neutral | Jordan Kai, Riley Moon, Ash Vance |

**Tip:** search your pen name on Amazon first — make sure no author already has it.
Once chosen, set it in `books/<book>/config.py → AUTHOR` and use it for all books.

---

## STEP 3 — Design the full-wrap cover

> KDP requires a **single PDF**: back cover + spine + front cover, side by side.
> Minimum 79 pages to add spine text. Book 1 at 59 pages → spine too narrow for text.

### Step 3a — Get your exact cover dimensions from KDP

1. Go to `kdp.amazon.com` → Bookshelf → **Cover Calculator**
2. Enter: Paperback | B&W | White paper | 8.5×11 in | your page count
3. Note the full-wrap dimensions (e.g. `17.56" × 11.25"`)
4. (Optional) Download the PDF template — shows exact bleed, spine, and safe zones

### Step 3b — Option A: KDP Cover Creator (fastest)

1. On the KDP cover upload page → click **"Launch Cover Creator"**
2. Upload your front cover image (`images/book1-90s/book1_cover_clean.png`)
3. KDP places it as the front cover automatically
4. Choose background color for back + spine
5. Add title, author name, optional description
6. Click **"Save & Submit"**

✅ Free, no external tools — best for first book
❌ Less design control than Canva

### Step 3c — Option B: Canva full-wrap (more control)

1. Go to canva.com → Create a design → **Custom size**
2. Enter dimensions from KDP Calculator in inches (e.g. `17.56 × 11.25`)
3. Canvas layout (left → right): `[ BACK COVER ][ SPINE ][ FRONT COVER ]`

**Front cover (right ~8.5"):**
- Upload `images/book1-90s/book1_cover_clean.png` as background
- Add title text + subtitle + author pen name

**Spine (center strip, ~0.14"):**
- Leave blank (spine too narrow at 59 pages — text not readable)
- Minimum 79 pages required for legible spine text

**Back cover (left ~8.5"):**
```
Remember staying up late to catch the next episode?

This book is for you — the dad who grew up with these legends,
and now wants to pass that magic to your kids.

Inside: 27 full-page coloring illustrations
drawn in bold, clean line art.
No shading. No fills. Just your colors.

· Large 8.5 × 11 format — plenty of room for all ages
· One-sided pages — no bleed-through, ever
· Perfect for a rainy afternoon, a road trip, or just because

Pick up a pencil. Sit next to your kid.
Bring the heroes back to life — together.
```
- Leave a **2" × 1.2" white rectangle** at bottom-right → KDP barcode zone
- Keep all content 0.25" away from edges (bleed zone)

**Export:** Share → Download → PDF Print → `output/book1-90s-legends_cover_FULLWRAP.pdf`

---

## STEP 4 — Publish on KDP

Go to `kdp.amazon.com` → Add New Title → Paperback.

### Upload
- **Manuscript:** `output/book1-90s-legends_interior_FINAL.pdf`
- **Cover:** `output/book1-90s-legends_cover_FULLWRAP.pdf`

### Metadata fields

| Field | Book 1 | Book 2 |
|---|---|---|
| Title | 90s Legends: Coloring Our Stories | Modern Legends: Coloring Our Stories |
| Subtitle | A Timeless Quest — Anime Coloring Book for Dads & Kids | A New Era — Anime Coloring Book for Dads & Kids |
| Author | [Your pen name] | [Your pen name] |
| Price US | $12.99 | $10.99 |
| Price UK | £9.99 | £8.99 |
| Marketplaces | US + UK only | US + UK only |

### Description template
```html
<b>Relive your childhood while coloring with your kids!</b><br><br>

This coloring book is made for millennial dads who grew up watching 90s anime —
and now want to share that magic with their children.<br><br>

Inside you'll find:<br>
• 27 full-page coloring illustrations<br>
• Iconic anime-inspired characters from the 90s golden era<br>
• Large 8.5×11 format — perfect for all ages<br>
• One-sided pages to prevent bleed-through<br><br>

<b>Perfect as a gift for Father's Day, birthdays, or just because.</b>
```

### Keywords — Book 1 (90s / Millennial)
```
anime coloring book for adults
nostalgic anime coloring book
90s anime coloring book
coloring book for dads
anime coloring book millennial
retro anime coloring book adults
father son coloring book anime
```

### Keywords — Book 2 (Modern 2020s)
```
anime coloring book 2024
demon slayer coloring book
jujutsu kaisen coloring book pages
new anime coloring book teens
modern anime coloring book adults
anime coloring book for teenagers
jjk aot coloring book
```

### Categories — Book 1 & 2

| Slot | Path | What to search in KDP |
|---|---|---|
| Primary | Books > Arts & Photography > Drawing > Manga | `manga drawing` |
| Secondary | Books > Humor & Entertainment > Puzzles & Games > Coloring Books for Adults | `adult coloring` |

> Do NOT use "Juvenile Nonfiction" — these books target millennial adults.

---

## File checklist before publishing

| File | Location | Status |
|---|---|---|
| Interior PDF | `output/book1-90s-legends_interior_FINAL.pdf` | Ready (59p, 0 fonts) |
| Cover front image | `images/book1-90s/book1_cover_clean.png` | Ready |
| Cover full-wrap PDF | `output/book1-90s-legends_cover_FULLWRAP.pdf` | To create (Step 3) |
| Pen name | `books/book1-90s-legends/config.py → AUTHOR` | To set |
| KDP account + tax | kdp.amazon.com | Must complete |

---

## Full pipeline summary

```
Gemini (1 prompt per character)
       ↓
images/<book>/<book>_<id>.png  × individual characters + scene pages
       ↓
python pipeline/clean.py <image> --crop-portrait --auto   (per image with artifacts)
       ↓
Update PAGE_SEQUENCE in books/<book>/config.py
       ↓
python pipeline/assemble.py --book <book-folder>
       ↓
output/<book>_interior_FINAL.pdf  (KDP-ready, 0 fonts)
       ↓
Canva / KDP Cover Creator → output/<book>_cover_FULLWRAP.pdf
       ↓
kdp.amazon.com → Upload interior + cover → Publish
```

**Total time per book: ~4-6 hours**
- 2h image generation (27 prompts × ~5 min each)
- 30min artifact cleanup
- 15min PDF assembly (`python pipeline/assemble.py`)
- 2h cover design
- 30min KDP form + submit

---

## Automation vision (future)

When the pipeline matures, the full workflow per book will be:

```bash
# 1. Generate all images via Gemini API (currently manual)
python pipeline/generate.py --book book3-shonen

# 2. Bulk clean artifacts (currently per-image)
python pipeline/clean_all.py --book book3-shonen

# 3. Assemble PDF (already automated)
python pipeline/assemble.py --book book3-shonen

# 4. Upload to KDP (future — Selenium or KDP API)
python pipeline/publish.py --book book3-shonen
```

Currently **step 3 is fully automated**. Steps 1, 2, 4 are manual.
The config.py contract makes steps 1 and 2 automatable: just populate `PAGE_SEQUENCE`.

---

## Dependencies

```bash
pip install Pillow img2pdf
```

Python 3.10+ required.
