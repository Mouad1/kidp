# StoryForge

Turn a real photo into a personalized hero storybook.

StoryForge generates a complete, print-ready children's book where the hero is a
specific person (your kid, a friend, a gift recipient) drawn consistently across
every page. You write the story once as a reusable **template**; the engine fills
in the variables and keeps the character looking the same on every page by feeding
a canonical reference portrait into each generation call.

It plugs into the existing KDP pipeline: a finished StoryForge book is a normal
`books/<name>/config.py`, so assembly, covers, and KDP export all work unchanged.

---

## Quick start

### 1. Requirements

- Python 3.10+
- A Google Gemini API key

```bash
pip install google-genai fastapi uvicorn jinja2 python-multipart pillow img2pdf
export GEMINI_API_KEY="your-key-here"     # or put it in .env.local
```

### 2. Run the dashboard

```bash
python3 dashboard/app.py
# open http://localhost:8000/storybook
```

The `/storybook` page walks you through three steps, with no page reloads:

1. **Story** — pick a template, name the book, fill in the variables.
2. **Hero photo** — drop 1–3 photos of the person; StoryForge builds a consistent reference character.
3. **Generate** — every page is drawn starring your hero, then saved as a book.

### 3. Use it from Python

```python
from storyforge import (
    load_template, build_hero, save_sheet, resolve, generate_page, build_book,
)
from storyforge.gemini_backend import GeminiBackend, analyze_photos

tpl = load_template("brave-little-explorer")
gen = GeminiBackend()

photos = [open("kid.png", "rb").read()]
hero = build_hero(photos, tpl.art_style, gen, analyze_photos)

specs = resolve(tpl, {
    "HERO_NAME": "Sami", "SETTING": "enchanted forest",
    "VALUE": "courage", "SIDEKICK": "fox",
}, hero)

pages = [generate_page(s, hero, gen) for s in specs]
build_book("samis-adventure", "Sami's Adventure", "You", tpl.mode, specs, pages, hero)
```

---

## Templates

A template is a folder under `templates/<slug>/template.json`. The schema:

| Field | Meaning |
|---|---|
| `name` | Display name. |
| `mode` | `"color"` (full color story) or `"lineart"` (coloring book). |
| `language_default` | Default text language, e.g. `"fr"`. |
| `art_style` | Style string appended to every image prompt; drives visual consistency. |
| `variables` | List of `{key, label, type, options?}`. `type` is `"text"` or `"select"`; `select` requires `options`. |
| `pages` | List of `{beat, text, image_prompt}`. Order = page order. |

### Reserved tokens

Use `{...}` to inject values into `text` and `image_prompt`:

- `{HERO}` — replaced by the hero's visual descriptor in image prompts (keeps the character consistent). Reserved, do not declare as a variable.
- `{HERO_NAME}` — the hero's name in story text. Reserved.
- `{YOUR_VARIABLE}` — any key you declare under `variables`.

Every token that appears in `text` or `image_prompt` must be either a reserved
token or a declared variable, otherwise the template is rejected at load time.

### Example

See [templates/brave-little-explorer/template.json](templates/brave-little-explorer/template.json)
for a complete 4-page color template.

---

## Sharing a template

A template is fully self-contained in its folder. To share:

1. Copy `templates/<your-slug>/` to anyone with StoryForge installed.
2. They drop it into their own `templates/` directory.
3. It shows up automatically in the `/storybook` dropdown and `list_templates()`.

No code changes, no registration. Templates are pure data.

---

## Architecture

```
storyforge/
  types.py          Variable, PageBeat, Template, CharacterSheet, PageSpec
  templates.py      load / parse / validate templates, token extraction
  engine.py         resolve(template, variables, hero) -> list[PageSpec]  (pure)
  identity.py       build_hero / save_sheet / load_sheet  (consistent character)
  generator.py      generate_page(spec, hero, gen)
  builder.py        build_book(...) -> books/<name>/config.py
  imagegen.py       ImageGenerator Protocol + FakeImageGenerator (DI seam)
  gemini_backend.py GeminiBackend (real Gemini image + photo analysis)
```

The single dependency seam is the `ImageGenerator` Protocol:

```python
class ImageGenerator(Protocol):
    def generate(self, prompt: str, reference_images=None) -> bytes: ...
```

`GeminiBackend` is the production implementation; `FakeImageGenerator` records
calls and returns a tiny PNG. Every test runs offline — no network, no API key.

### Consistency

`build_hero` analyzes the photos into a text descriptor and generates one
**canonical portrait**. That portrait is passed as a reference image into every
page generation, so the hero looks the same throughout the book.

---

## Testing

```bash
python3 -m pytest tests/test_storyforge_*.py -v
```

31 tests cover types, templates, the pure resolver, identity, page generation,
the book builder, the Gemini backend wiring, the public API, the example
template, and the dashboard endpoints — all without touching the network.
