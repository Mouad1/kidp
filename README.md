# KDP Coloring Book Pipeline

> Karpathy-style: one file that does everything, read top to bottom, no magic.
> Last updated: 2026-04-13 | Book 1: interior PDF ready (59p, 0 fonts) | Book 2: images pending

---

## What this repo does

Generates print-ready KDP interior PDFs for anime coloring books.
Each book lives as a self-contained folder under `books/`. The generic pipeline
reads any book's `config.py` and produces a PDF in `output/`.

No framework, no database, no cloud. Everything is local Python + PIL + img2pdf.

---

## Directory layout

```
kidp/
├── README.md                            <- you are here (quick reference)
├── BOOK_PROCESS.md                      <- complete step-by-step guide (share with team/video)
├── .gitignore
├── pipeline/
│   ├── assemble.py                      <- generic assembler: reads any config.py → PDF
│   └── clean.py                         <- artifact cleanup and portrait crop utility
├── books/
│   ├── book1-90s-legends/
│   │   └── config.py                    <- Book 1 source of truth (27 pages, ready)
│   └── book2-modern-anime/
│       └── config.py                    <- Book 2 source of truth (images pending)
├── images/
│   ├── book1-90s/                       <- 27 coloring PNGs + cover for Book 1
│   └── book2-modern-anime/              <- Book 2 images (2 generated so far)
├── output/                              <- final PDFs (git-ignored, regenerate anytime)
├── scripts/
│   └── assemble_book1_final.py          <- legacy reference script (kept, do not use)
├── tasks/
│   ├── todo.md                          <- project roadmap
│   └── lessons.md                       <- learned lessons (update after each correction)
└── _archive/                            <- old scripts, legacy PDFs, grid images (ignore)
```

---

## The pipeline in 4 commands

### 1 — Generate images in Gemini (manual, one at a time)

```
Provide Professional adult coloring book page of [CHARACTER NAME] ([description]),
full body centered, pure white background. Thick, bold black vector-style outlines.
Zero shading, zero gray fills, zero gradients. High contrast, clean line art,
300 DPI quality, minimalist style ready for coloring.
```

Save to `images/<book-folder>/` using the naming pattern in the book's `config.py`.

**Lessons:**
- ONE character per prompt — grid generation produces poor quality
- If shading appears: add "CRITICAL: zero gray shading, white fill only inside outlines"
- Generate 5-6 group scene pages to interleave every 3-4 individual characters

### 2 — Clean artifacts

```bash
# Auto-detect dark corner artifacts
python pipeline/clean.py images/book1-90s/book1_conan.png --auto

# Whiten specific zones (pixel coords: x1,y1,x2,y2)
python pipeline/clean.py images/book1-90s/book1_blade_clean.png --zones "0,0,600,680"

# Crop landscape image to portrait
python pipeline/clean.py images/book1-90s/book1_slam1.png --crop-portrait

# Combine: crop then auto-clean
python pipeline/clean.py images/book1-90s/book1_slam1.png --crop-portrait --auto

# Dry run (preview without writing)
python pipeline/clean.py images/book1-90s/book1_conan.png --auto --dry-run
```

Common artifact zones for Gemini images at 2816×1536:

| Artifact               | Typical zone             |
|------------------------|--------------------------|
| Floating head top-left | `0,0,600,700`            |
| Flash / zigzag         | `0,0,500,600`            |
| Text label bottom      | `0,1350,1500,1536`       |
| Ink symbol bottom      | `800,1300,1400,1536`     |

### 3 — Assemble interior PDF

```bash
# From the project root
python pipeline/assemble.py --book book1-90s-legends
```

Output: `output/book1-90s-legends_interior_FINAL.pdf`

The assembler:
- Loads `books/book1-90s-legends/config.py` dynamically
- Renders all pages as PIL images at 2550×3300 px (8.5"×11" @ 300 DPI)
- Adds front matter (title + copyright) and back matter (thank-you page)
- Inserts a blank white page behind every coloring page (industry standard)
- Assembles with img2pdf — zero embedded fonts → zero KDP rejection risk
- Verifies font count in the output PDF

**Page structure (book 1 — 27 content pages):**
```
Title page + Copyright page  (2)
Testpen page + blank back    (2)
27 × (coloring + blank)      (54)
Back-matter page             (1)
Total: 59 pages
```

### 4 — Design cover + publish on KDP

See `BOOK_PROCESS.md` → Steps 3 and 4 for full cover and KDP instructions.

---

## How to add a new book

```bash
# 1. Copy config template
cp -r books/book1-90s-legends books/book3-shonen

# 2. Edit the config
#    → Set TITLE, SUBTITLE, AUTHOR, IMAGES_DIR, PAGE_SEQUENCE
#    → IMAGES_DIR is auto-relative (no hardcoded paths)

# 3. Put images in images/book3-shonen/

# 4. Assemble
python pipeline/assemble.py --book book3-shonen
```

The config contract:

| Variable               | Type                                  | Description                              |
|------------------------|---------------------------------------|------------------------------------------|
| `TITLE`                | `str`                                 | Full book title                          |
| `SUBTITLE`             | `str`                                 | Subtitle / tagline                       |
| `AUTHOR`               | `str`                                 | Pen name (set before publishing)         |
| `IMAGES_DIR`           | `pathlib.Path`                        | Path to the images folder (relative OK)  |
| `TESTPEN`              | `str`                                 | Filename of the color-test page (or `""`) |
| `PAGE_SEQUENCE`        | `list[tuple[str, str]]`               | `(filename, label)` pairs                |
| `TITLE_PAGE_LINES`     | `list[tuple[str, int, bool, tuple]]`  | Text layout for title page               |
| `COPYRIGHT_PAGE_LINES` | same                                  | Text layout for copyright page           |
| `BACK_PAGE_LINES`      | same                                  | Text layout for back-matter page         |

---

## Book status

| Book               | Images | Interior PDF      | Cover              | Published |
|--------------------|--------|-------------------|--------------------|-----------|
| book1-90s-legends  | Ready  | Ready (59p, 0 fonts) | Pending (Canva) | No        |
| book2-modern-anime | 2/15+  | Not yet           | No                 | No        |

---

## KDP settings

- Trim: **8.5×11 in** | No bleed | B&W | White paper
- Categories: Arts & Photography > Drawing > Manga + Adult Coloring Books
- Price: $12.99 US / £9.99 UK | Marketplaces: US + UK only
- 59 pages → spine too narrow for text (need 79+ pages to add spine text)

---

## Dependencies

```bash
pip install Pillow img2pdf
```

Python 3.10+ required (uses `tuple[...]` type hints).

---

## Automation vision

```bash
# Currently: step 3 is automated, steps 1/2/4 are manual
python pipeline/generate.py --book book3-shonen   # TODO: Gemini API
python pipeline/clean_all.py --book book3-shonen   # TODO: bulk clean
python pipeline/assemble.py --book book3-shonen    # DONE
python pipeline/publish.py --book book3-shonen     # TODO: Selenium / KDP API
```
