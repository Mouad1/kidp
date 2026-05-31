# StoryForge — Personalized Hero Storybooks Design

> Status: approved in brainstorming (2026-05-31). Next: implementation plan.

## Goal

Add a module that turns **(real photos of a person) + (a reusable story template) + (variables set on
the dashboard)** into a standard `books/<name>/config.py` that the existing pipeline assembles into a
print-ready PDF. The hero must stay visually consistent across every page. The engine must be cleanly
isolated, dependency-injected, fully tested, and shippable as a community-installable product where
templates are the shareable unit.

## Decisions locked (from brainstorming)

1. **Identity = hybrid (C):** build a locked character sheet (text descriptor + one canonical
   generated portrait), then condition every page on that canonical portrait + descriptor.
2. **Templates = story skeletons (A):** sequence of page beats with `{TOKENS}`; declared variables
   become dashboard form fields.
3. **Output = color and line-art, switchable per template (C).**
4. **Books = reuse existing model (A):** the engine emits a standard `books/<name>/config.py`; all
   downstream (assemble, cover, KDP metadata, dashboard book view) is unchanged.
5. **Shareability = isolated engine shipped in-repo (C):** self-contained `storyforge/` package with
   clean interfaces + DI so it could later be extracted to a pip package; templates are drop-in.

## Architecture

```
Photos ─▶ identity.build_hero() ─▶ Character Sheet {descriptor, canonical_portrait, art_style, photos}
Template + Variables + Hero ─▶ engine.resolve() ─▶ list[PageSpec]
PageSpec ─▶ generator.generate_page() (photo-conditioned) ─▶ page PNG
All pages + identity ─▶ builder.build_book() ─▶ books/<name>/config.py + images/<name>/
                                                          │
                                                          ▼
                                          existing pipeline/assemble.py ─▶ PDF
```

### Modules (each one responsibility, independently testable)

| Module | Responsibility | Injected dependency |
|---|---|---|
| `storyforge/types.py` | Dataclasses: `Variable`, `PageBeat`, `Template`, `CharacterSheet`, `PageSpec`, `BuildResult` | none (pure) |
| `storyforge/imagegen.py` | `ImageGenerator` Protocol + `FakeImageGenerator` for tests | none |
| `storyforge/gemini_backend.py` | Real `ImageGenerator` impl over `google-genai` | google-genai |
| `storyforge/identity.py` | `build_hero(photos, art_style, gen, text_fn)` → `CharacterSheet`; persist/load sheet | `ImageGenerator`, text-analyze fn |
| `storyforge/templates.py` | `load_template`, `list_templates`, `validate_template`, `extract_variables` | filesystem |
| `storyforge/engine.py` | `resolve(template, variables, hero)` → `list[PageSpec]` (pure, no I/O) | none |
| `storyforge/generator.py` | `generate_page(spec, hero, gen)` → PNG bytes (color or line-art) | `ImageGenerator` |
| `storyforge/builder.py` | `build_book(name, template, variables, hero, pages)` → write `config.py` + images | `config_io.write_config` |

The `ImageGenerator` Protocol is the single DI seam. Tests inject `FakeImageGenerator`; no test touches
the network or the Gemini API.

### ImageGenerator interface

```python
class ImageGenerator(Protocol):
    def generate(self, prompt: str, reference_images: list[bytes] | None = None) -> bytes:
        """Return PNG bytes for the prompt, optionally conditioned on reference images."""
```

## Identity locking (consistency core)

`build_hero(photos, art_style, gen, analyze)`:

1. Validate photos: 1–3 images, each a readable PNG/JPEG under a size cap.
2. `analyze(photos)` → text descriptor (age range, hair, eyes, distinctive features). `analyze` is an
   injected callable so it can be faked in tests.
3. `gen.generate(portrait_prompt, reference_images=photos)` → canonical front-facing hero portrait in
   `art_style`.
4. Return `CharacterSheet(descriptor, canonical_portrait_png, art_style, source_photos)`.
5. `save_sheet(book_dir, sheet)` writes `books/<name>/hero/canonical_portrait.png`,
   `descriptor.txt`, and copies of source photos. `load_sheet(book_dir)` reads it back.

Every later page call passes `reference_images=[canonical_portrait]` (the hero) so the face is
re-derived from the locked portrait each time → maximum page-to-page consistency.

`{HERO}` is a reserved token: at resolve time it is replaced by the descriptor text in the image
prompt, and the canonical portrait is attached as the reference image at generation time.

## Template format (`templates/<slug>/template.json`)

```json
{
  "name": "The Brave Little Explorer",
  "mode": "color",
  "language_default": "fr",
  "variables": [
    { "key": "HERO_NAME", "label": "Child's name", "type": "text" },
    { "key": "SETTING", "label": "World", "type": "select",
      "options": ["enchanted forest", "space station", "underwater city"] },
    { "key": "VALUE", "label": "Lesson learned", "type": "text" }
  ],
  "art_style": "soft watercolor children's book illustration, warm palette",
  "pages": [
    { "beat": "intro",
      "text": "{HERO_NAME} woke up in the {SETTING}, ready for adventure.",
      "image_prompt": "{HERO} standing at the edge of a {SETTING}, morning light" }
  ]
}
```

Rules enforced by `validate_template`:

- `mode` ∈ {`color`, `lineart`}.
- `pages` non-empty; each page has `text` and `image_prompt`.
- Every `{TOKEN}` used in any `text`/`image_prompt` is either the reserved `HERO`/`HERO_NAME` or a
  declared variable `key`.
- Each variable has `key`, `label`, `type` ∈ {`text`, `select`}; `select` requires non-empty `options`.
- Invalid templates raise `TemplateError` with a precise message (boundary validation).

A template folder dropped into `templates/` auto-appears in the dashboard — the "installable/shareable"
property. One example template ships with the repo.

## Engine resolution (pure)

`resolve(template, variables, hero)`:

- For each page beat, substitute declared `{TOKENS}` from `variables`, replace `{HERO}` with
  `hero.descriptor` in the image prompt and `{HERO_NAME}`/etc. as configured.
- Missing required variable → `ResolutionError` listing the missing keys.
- Returns `list[PageSpec(page_number, text, image_prompt, mode, reference_required=True)]`.
- No filesystem, no network — trivially unit-testable.

## Page generation

`generate_page(spec, hero, gen)`:

- `color` mode: prompt = `spec.image_prompt + ", " + template.art_style`, reference = canonical portrait.
- `lineart` mode: wrap with the existing coloring-book line-art directive (reuse `pipeline.prompt`
  conventions) so output matches the current KDP coloring contract; reference = canonical portrait.
- Calls `gen.generate(prompt, reference_images=[hero.canonical_portrait_png])`.
- Returns PNG bytes. Saving is done by the builder.

## Book emission

`build_book(name, template, variables, hero, page_pngs)`:

- Writes each page PNG to `images/<name>/`.
- Builds a `data` dict matching the existing `config_io.write_config` contract:
  `category="story"` (or `"coloring"` for lineart), `story_format`, `languages`, `pages` (with text
  + image_prompt + page_number), `page_sequence`, identity title/author from variables, etc.
- Calls `config_io.write_config(name, data)` → standard `books/<name>/config.py`.
- Result: the book appears in the existing dashboard book list and assembles with no new PDF code.

## Dashboard UX (no page refresh, high reactivity)

New "Personalized Storybook" flow, same FastAPI + SSE + vanilla-JS pattern as existing generate/clean
streams in `dashboard/app.py`:

1. **Pick template** → `GET /api/storyforge/templates`; variable form renders dynamically client-side.
2. **Upload photos** → `POST /api/storyforge/<name>/photos` (multipart); instant client thumbnails.
3. **Build hero** → `GET /stream/storyforge/<name>/hero` (SSE progress); canonical portrait appears
   inline; Approve / Regenerate without reload.
4. **Fill variables** → live client-side preview of resolved page-1 text.
5. **Generate book** → `GET /stream/storyforge/<name>/generate` (SSE per-page progress); thumbnails
   fill in live.
6. On finish → new book row inserted into the list via DOM patch; opens in existing book view.

All updates via `fetch` + targeted DOM patches and `EventSource` — never a full reload.

New endpoints in `dashboard/app.py`:

- `GET /api/storyforge/templates` → list templates (name, slug, variables, mode).
- `POST /api/storyforge/{name}/photos` → save uploaded photos to the book's hero dir.
- `GET /stream/storyforge/{name}/hero` → SSE: build + persist character sheet.
- `GET /api/storyforge/{name}/hero` → return current sheet status + portrait URL.
- `GET /stream/storyforge/{name}/generate` → SSE: resolve + generate all pages + build config.
- Reuse existing `/images/{name}/{file}` for thumbnails.

The dashboard route handlers stay thin: they construct the real `GeminiBackend`, then call
`storyforge` functions. The Gemini backend is the only place the network is touched, so handlers are
testable with `TestClient` + injected `FakeImageGenerator` via a small provider override.

## Error handling (boundaries only)

- Template load/validate: malformed JSON, bad `mode`, undeclared tokens, empty pages → `TemplateError`.
- Photo upload: wrong type, too large, wrong count → HTTP 400 with message.
- Missing `GEMINI_API_KEY` when building the real backend → clear error surfaced in the SSE stream.
- Gemini empty response → `RuntimeError` surfaced in the stream (reuse existing pattern).
- Internal pure functions trust their inputs; no defensive checks for impossible states.

## Testing (non-regression, DI)

New files in `tests/`:

- `test_storyforge_templates.py` — load/validate/reject malformed templates; variable extraction.
- `test_storyforge_engine.py` — token substitution, `{HERO}` reservation, missing-variable errors (pure).
- `test_storyforge_identity.py` — `build_hero` with `FakeImageGenerator` + fake analyze; sheet
  save/load round-trip; photo validation.
- `test_storyforge_generator.py` — color vs line-art prompt shaping; reference image passed through
  (asserted via `FakeImageGenerator` capturing args).
- `test_storyforge_builder.py` — emitted `config.py` round-trips through `config_io.read_config` and
  matches the existing contract.
- `test_storyforge_api.py` — dashboard endpoints via FastAPI `TestClient` with `FakeImageGenerator`
  injected; asserts no full-page reload contract (JSON/SSE responses).

`FakeImageGenerator` returns a deterministic 1×1 PNG and records every `(prompt, reference_images)`
call so tests assert prompt shaping and photo-conditioning without the network.

## File layout

```
storyforge/
  __init__.py          # public API re-exports
  types.py
  imagegen.py          # Protocol + FakeImageGenerator
  gemini_backend.py    # real ImageGenerator
  identity.py
  templates.py
  engine.py
  generator.py
  builder.py
templates/
  brave-little-explorer/template.json
dashboard/
  app.py               # + storyforge endpoints
  templates/storybook.html   # new flow UI
tests/
  test_storyforge_templates.py
  test_storyforge_engine.py
  test_storyforge_identity.py
  test_storyforge_generator.py
  test_storyforge_builder.py
  test_storyforge_api.py
README.storyforge.md   # community install/use/share guide
```

## Out of scope (YAGNI)

- No model fine-tuning / training (hybrid reference conditioning only).
- No new PDF/cover/KDP code (reuse existing).
- No pip packaging today (kept extractable, not extracted).
- No multi-hero books in v1 (single hero per book).

## Community installability

- `README.storyforge.md`: clone repo, `pip install -r requirements`, set `GEMINI_API_KEY`, run the
  dashboard, drop a template folder in `templates/`, generate a personalized book.
- Templates are plain JSON folders → trivial to share and contribute.
