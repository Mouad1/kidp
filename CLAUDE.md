# KDP Pipeline — Agent Instructions

> Read this before doing anything. These rules override all defaults.

## Project overview

KDP coloring book pipeline. Generates print-ready PDFs for Amazon KDP using AI-generated images.
See `README.md` for the full pipeline. See `BOOK_PROCESS.md` for the step-by-step guide.

## Skills active in this project

This project uses the following skills — invoke them automatically when relevant:

| Skill | When to use |
|---|---|
| `frontend-design` | Any dashboard, UI, or web component work |
| `web-design-guidelines` | Before starting any new visual interface |
| `memory` | When user asks to remember something or recall past context |
| `brainstorming` | Before any new feature or architectural change |

### Superpowers (install once)
```bash
/plugin install superpowers@claude-plugins-official
```
Active skills: `brainstorming`, `writing-plans`, `systematic-debugging`, `test-driven-development`

### claude-mem (persistent memory)
```bash
npx claude-mem install
```
Persistent context across sessions. Web viewer at http://localhost:37777

## Critical rules

1. **Never mention color names in image prompts** — "black coat" → "coat with detailed patterns". Black fills = uncolorable pages.
2. **Never embed fonts in PDFs** — use `img2pdf` only. Never use `reportlab` for KDP interior.
3. **IMAGES_DIR must be relative** — use `pathlib.Path(__file__).parent.parent.parent / "images" / <folder>`. Never hardcode absolute paths.
4. **API key = env var only** — `GEMINI_API_KEY`. Never in code or committed files.
5. **One character per Gemini prompt** — grid generation produces poor quality.

## Pipeline commands

```bash
# Generate images (requires GEMINI_API_KEY)
python3 pipeline/generate.py --book book2-modern-anime
python3 pipeline/generate.py --book book2-modern-anime --id gojo    # single character
python3 pipeline/generate.py --book book2-modern-anime --dry-run    # preview prompts

# Clean artifacts
python3 pipeline/clean.py images/book2-modern-anime/book2_gojo.png --crop-portrait --auto

# Assemble PDF
python3 pipeline/assemble.py --book book1-90s-legends

# Dashboard (once created)
python3 dashboard/app.py
```

## Backlog

Toutes les idées et features en attente → `BACKLOG.md`
Ajouter une idée : une ligne `[ ]` dans la section qui correspond. Ne pas perdre d'idée.

---

## Book status

| Book | Images | PDF | Cover | Published |
|---|---|---|---|---|
| book1-90s-legends | ✅ Ready | ✅ Ready (59p) | ⏳ Canva | No — KDP metadata ✅ |
| book2-modern-anime | ✅ 24 generated | ✅ Ready (51p) | ⏳ Canva | No — KDP metadata ✅ |

## File layout

```
pipeline/generate.py    ← image generation (Gemini API)
pipeline/clean.py       ← artifact cleanup
pipeline/assemble.py    ← PDF assembly (img2pdf, 0 fonts)
books/*/config.py       ← source of truth per book
images/*/               ← coloring PNGs
output/                 ← final PDFs (git-ignored)
dashboard/              ← web UI for pipeline management
tasks/lessons.md        ← ALWAYS update after corrections
```

## After any correction

Update `tasks/lessons.md` immediately with the pattern and why it matters.
