# Tag Reference Gallery + Feedback Loop — Design Spec

**Date:** 2026-05-01
**Status:** Approved

## Context

Generating coloring book and story images requires repeated trial-and-error cycles: pick a tag (e.g. "chibi style"), generate, see the result doesn't match expectations, go back, adjust prompt manually, regenerate. The root cause is lack of visual reference at the moment of decision, and no structured way to express dissatisfaction with a result.

This spec defines two complementary features that together close the iteration loop:
1. **Tag Reference Gallery** — inline panel showing Gemini-generated examples per tag so users know what each option produces before generating
2. **Feedback Loop** — after generation, text feedback is translated by Gemini into specific prompt changes, shown as a diff for confirmation, then applied and regenerated automatically

## Feature 1: Tag Reference Gallery

### Generation Script
**File:** `pipeline/generate_tag_examples.py`

- Iterates over all tags in `pipeline/prompt.py`: `STYLE_TAGS`, `POSE_TAGS`, `ELEMENT_TAGS`, `THEME_TAGS`
- For each tag, builds a neutral coloring book prompt with the tag applied (reuses `build_prompt` from `pipeline/prompt.py`)
- Calls Gemini image generation API (`IMAGE_MODEL = "gemini-2.5-flash-image"`)
- Saves output to `assets/tag_examples/{category}/{tag_slug}.png` (slug = tag lowercased, spaces → underscores)
- Skips files that already exist — safe to re-run
- CLI: `python3 pipeline/generate_tag_examples.py [--category style|pose|element|theme] [--force]`

**Storage layout:**
```
assets/tag_examples/
  style/
    thick_outlines.png
    thin_detailed_lines.png
    chibi_style.png
    realistic_proportions.png
    manga_style.png
  pose/
    standing_portrait.png
    action_pose.png
    ...
  element/
    weapon.png
    energy_aura.png
    ...
  theme/
    art_nouveau.png
    mandala_infused.png
    ...
```

### Backend
**File:** `dashboard/app.py`

`GET /api/prompt/tags` already exists at line 638 and returns all tag lists. **Extend** it (don't replace) to include example image URLs alongside each tag:

```python
# Before (existing):
return {"style": STYLE_TAGS, "pose": POSE_TAGS, ...}

# After (extended):
return {
    "style": [{"tag": t, "example": f"/assets/tag_examples/style/{slugify(t)}.png"} for t in STYLE_TAGS],
    ...
}
```

Serve `assets/tag_examples/` as static files via FastAPI `StaticFiles` mount at `/assets`. Frontend already calls `/api/prompt/tags` — update JS to consume new shape.

### Frontend
**File:** `dashboard/templates/book.html`

The current 3-column layout is: `[220px char list] [1fr page grid] [340px prompt builder]`.

Modification: the 340px right panel (prompt builder) gains a **gallery sub-panel** that slides open when a tag is clicked.

- Tag buttons in prompt builder become interactive: click = highlight + populate gallery panel
- Gallery panel shows: tag name + example image (from `/api/tag-examples`)
- Panel appears inline below the clicked tag section (not a modal, not a sidebar — inline expand)
- If no example exists yet (script not run), show a placeholder with "Generate examples: `python3 pipeline/generate_tag_examples.py`"
- Loaded once on page init via `GET /api/tag-examples`, cached in JS `let tagExamples = {}`

---

## Feature 2: Feedback Loop

### User Flow
```
[Image displayed in dashboard page card]
    ↓ user types feedback in textarea
    "too many black fills, pose is too static, simplify background"
[POST /api/feedback/{book_name}/{page_id}]
    ↓ Gemini receives: current_prompt + user_feedback
    → returns: refined_prompt + list of changes
[Dashboard shows diff panel: old vs new prompt, changes highlighted in yellow]
    ↓ user clicks "Appliquer"
[config.py updated via config_io.py + generate triggered for this page_id]
    ↓ existing streaming terminal output
[New image displayed in page card]
```

### Backend
**File:** `dashboard/app.py`

New endpoint following the `rewrite_page` pattern (spawn subprocess → return JSON):
```
POST /api/feedback/{book_name}
Body: {
  "feedback": str,
  "current_prompt": str,
  "page_ref": str   # character id (coloring) or str(page_number) (story)
}
→ { "refined_prompt": str, "changes": [str, ...] }
```

Spawns `pipeline/refine_prompt.py` as subprocess (same pattern as `rewrite_page.py`). Uses `gemini-2.5-flash` text model from settings.

**`page_ref` disambiguation:**
- Coloring book (CATEGORY="coloring"): `page_ref` = character `id` string (e.g. `"gojo"`)
- Story book (CATEGORY="story"): `page_ref` = `str(page_number)` (e.g. `"3"`)

Save refined prompt: reuse `PUT /api/book/{book_name}/config` (line 555) — send full config with updated `image_prompt` for the matching page/character.

**New script:** `pipeline/refine_prompt.py`
```
Args: --feedback "..." --prompt "..."
Gemini prompt:
  You are a KDP coloring book prompt engineer.
  Current prompt: {prompt}
  User feedback: {feedback}
  Rules: never mention colors, keep "PURE BLACK AND WHITE lineart" for coloring books.
  Output JSON: {"refined_prompt": "...", "changes": ["description of each change"]}
```

### Frontend
**File:** `dashboard/templates/book.html`

Each page card in the grid gains:
- Collapsed feedback section (chevron toggle to show/hide)
- Textarea: `placeholder="ex: trop noir, pose trop statique, simplifie l'arrière-plan"`
- Button: "🔄 Analyser le feedback"
- On response: diff panel appears inline below textarea
  - Each change listed as a bullet: `+ Added dynamic action pose` / `- Removed dark background`
  - Full refined prompt shown in collapsed `<details>`
- Button: "✅ Appliquer & Régénérer" → saves prompt via existing config_io + triggers generate for this page_id

### Prompt save
**File:** `dashboard/app.py` / `pipeline/config_io.py`

Reuse existing `PUT /api/book/{book_name}/config` (line 555). Frontend sends full config with `image_prompt` updated for the matching page/character. No new save logic needed.

---

## Files Changed

| File | Change |
|------|--------|
| `pipeline/generate_tag_examples.py` | **New** — one-shot tag example generator |
| `pipeline/refine_prompt.py` | **New** — Gemini prompt refinement script (feedback → diff) |
| `assets/tag_examples/` | **New** — static image storage |
| `dashboard/app.py` | Extend `GET /api/prompt/tags` with image URLs; mount `/assets`; add `POST /api/feedback/{book_name}`; reuse `PUT /api/book/{book_name}/config` |
| `dashboard/templates/book.html` | Inline gallery panel in prompt builder + feedback UI per page card |

---

## Verification

1. Run `python3 pipeline/generate_tag_examples.py` → `assets/tag_examples/` populated, no errors
2. Start dashboard `make dashboard` → `GET /api/tag-examples` returns JSON with image URLs
3. Open book page → click style tag in prompt builder → gallery panel shows example image
4. Click different tag → gallery updates to new example
5. Open page card feedback section → type feedback → click "Analyser" → diff appears with changes listed
6. Click "Appliquer & Régénérer" → config.py updated, generation triggers, streaming output visible, new image appears
7. Re-run `generate_tag_examples.py` with existing files → no re-generation (skip logic works)
