# StoryForge — Personalized Hero Storybooks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a `storyforge/` engine that turns real photos + a reusable story template + dashboard variables into a standard `books/<name>/config.py` with a visually consistent personalized hero, fully tested with dependency injection and surfaced through a no-refresh dashboard flow.

**Architecture:** Self-contained `storyforge/` package with one `ImageGenerator` Protocol as the single DI seam. Pure functions for template parsing and resolution; injected image generator for identity + page generation; emission reuses `pipeline/config_io.write_config` so all downstream PDF/cover/KDP code is unchanged.

**Tech Stack:** Python 3.10+, `google-genai`, FastAPI + Jinja2 + SSE (existing dashboard), Pillow, pytest, FastAPI `TestClient`.

Spec: `docs/superpowers/specs/2026-05-31-storyforge-personalized-heroes-design.md`

---

## File structure

| File | Responsibility |
|---|---|
| `storyforge/__init__.py` | Public API re-exports |
| `storyforge/types.py` | Dataclasses: `Variable`, `PageBeat`, `Template`, `CharacterSheet`, `PageSpec` |
| `storyforge/errors.py` | `TemplateError`, `ResolutionError` |
| `storyforge/imagegen.py` | `ImageGenerator` Protocol + `FakeImageGenerator` |
| `storyforge/gemini_backend.py` | Real `ImageGenerator` over `google-genai` |
| `storyforge/templates.py` | load/list/validate templates, extract variables |
| `storyforge/engine.py` | pure `resolve()` template+vars+hero → `list[PageSpec]` |
| `storyforge/identity.py` | `build_hero`, `save_sheet`, `load_sheet`, photo validation |
| `storyforge/generator.py` | `generate_page` (color/lineart prompt shaping) |
| `storyforge/builder.py` | `build_book` → write images + `config.py` |
| `templates/brave-little-explorer/template.json` | Example shipped template |
| `dashboard/app.py` | New storyforge endpoints (modify) |
| `dashboard/templates/storybook.html` | New flow UI |
| `tests/test_storyforge_*.py` | 6 test files |
| `README.storyforge.md` | Community install/use/share guide |

---

## Task 1: Package scaffold + types

**Files:**
- Create: `storyforge/__init__.py`
- Create: `storyforge/types.py`
- Create: `storyforge/errors.py`
- Test: `tests/test_storyforge_types.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_storyforge_types.py
from storyforge.types import Variable, PageBeat, Template, CharacterSheet, PageSpec


def test_template_holds_pages_and_variables():
    tpl = Template(
        name="Demo",
        mode="color",
        language_default="fr",
        art_style="watercolor",
        variables=[Variable(key="HERO_NAME", label="Name", type="text", options=[])],
        pages=[PageBeat(beat="intro", text="{HERO_NAME} smiles", image_prompt="{HERO} smiling")],
    )
    assert tpl.mode == "color"
    assert tpl.variables[0].key == "HERO_NAME"
    assert tpl.pages[0].beat == "intro"


def test_pagespec_defaults_reference_required_true():
    spec = PageSpec(page_number=1, text="hi", image_prompt="hero", mode="color")
    assert spec.reference_required is True


def test_character_sheet_fields():
    sheet = CharacterSheet(
        descriptor="boy, 7, curly hair",
        canonical_portrait_png=b"\x89PNG",
        art_style="watercolor",
        source_photos=[b"\x89PNG"],
    )
    assert sheet.descriptor.startswith("boy")
    assert sheet.canonical_portrait_png == b"\x89PNG"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_storyforge_types.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'storyforge'`

- [ ] **Step 3: Write minimal implementation**

```python
# storyforge/errors.py
class TemplateError(ValueError):
    """Raised when a template is malformed or references undeclared tokens."""


class ResolutionError(ValueError):
    """Raised when required variables are missing during resolution."""
```

```python
# storyforge/types.py
from dataclasses import dataclass, field


@dataclass
class Variable:
    key: str
    label: str
    type: str  # "text" | "select"
    options: list[str] = field(default_factory=list)


@dataclass
class PageBeat:
    beat: str
    text: str
    image_prompt: str


@dataclass
class Template:
    name: str
    mode: str  # "color" | "lineart"
    language_default: str
    art_style: str
    variables: list[Variable]
    pages: list[PageBeat]
    slug: str = ""


@dataclass
class CharacterSheet:
    descriptor: str
    canonical_portrait_png: bytes
    art_style: str
    source_photos: list[bytes] = field(default_factory=list)


@dataclass
class PageSpec:
    page_number: int
    text: str
    image_prompt: str
    mode: str
    reference_required: bool = True
```

```python
# storyforge/__init__.py
from storyforge.types import (
    Variable, PageBeat, Template, CharacterSheet, PageSpec,
)
from storyforge.errors import TemplateError, ResolutionError

__all__ = [
    "Variable", "PageBeat", "Template", "CharacterSheet", "PageSpec",
    "TemplateError", "ResolutionError",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_storyforge_types.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add storyforge/__init__.py storyforge/types.py storyforge/errors.py tests/test_storyforge_types.py
git commit -m "feat(storyforge): add package scaffold, dataclasses, and errors"
```

---

## Task 2: ImageGenerator Protocol + FakeImageGenerator

**Files:**
- Create: `storyforge/imagegen.py`
- Test: `tests/test_storyforge_imagegen.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_storyforge_imagegen.py
from storyforge.imagegen import FakeImageGenerator, PNG_MAGIC


def test_fake_returns_png_and_records_calls():
    gen = FakeImageGenerator()
    out = gen.generate("a hero", reference_images=[b"ref"])
    assert out.startswith(PNG_MAGIC)
    assert len(gen.calls) == 1
    assert gen.calls[0]["prompt"] == "a hero"
    assert gen.calls[0]["reference_images"] == [b"ref"]


def test_fake_handles_no_reference():
    gen = FakeImageGenerator()
    gen.generate("solo")
    assert gen.calls[0]["reference_images"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_storyforge_imagegen.py -v`
Expected: FAIL with `ModuleNotFoundError` / `ImportError`

- [ ] **Step 3: Write minimal implementation**

```python
# storyforge/imagegen.py
from typing import Protocol

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

# Smallest valid 1x1 transparent PNG.
_TINY_PNG = (
    PNG_MAGIC
    + bytes.fromhex(
        "0000000d49484452000000010000000108060000001f15c489"
        "0000000a49444154789c6360000000020001e221bc33"
        "0000000049454e44ae426082"
    )
)


class ImageGenerator(Protocol):
    def generate(self, prompt: str, reference_images: list[bytes] | None = None) -> bytes:
        """Return PNG bytes for the prompt, optionally conditioned on reference images."""
        ...


class FakeImageGenerator:
    """Deterministic in-memory generator for tests. Records every call."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def generate(self, prompt: str, reference_images: list[bytes] | None = None) -> bytes:
        self.calls.append({"prompt": prompt, "reference_images": reference_images})
        return _TINY_PNG
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_storyforge_imagegen.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add storyforge/imagegen.py tests/test_storyforge_imagegen.py
git commit -m "feat(storyforge): add ImageGenerator protocol and FakeImageGenerator"
```

---

## Task 3: Template loading + validation

**Files:**
- Create: `storyforge/templates.py`
- Test: `tests/test_storyforge_templates.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_storyforge_templates.py
import json
import pytest
from storyforge.templates import (
    parse_template, validate_template, extract_tokens,
)
from storyforge.errors import TemplateError

VALID = {
    "name": "Explorer",
    "mode": "color",
    "language_default": "fr",
    "art_style": "watercolor",
    "variables": [
        {"key": "HERO_NAME", "label": "Name", "type": "text"},
        {"key": "SETTING", "label": "World", "type": "select",
         "options": ["forest", "space"]},
    ],
    "pages": [
        {"beat": "intro", "text": "{HERO_NAME} in {SETTING}",
         "image_prompt": "{HERO} in {SETTING}"},
    ],
}


def test_parse_valid_template():
    tpl = parse_template(VALID, slug="explorer")
    assert tpl.name == "Explorer"
    assert tpl.slug == "explorer"
    assert tpl.variables[1].options == ["forest", "space"]


def test_extract_tokens_finds_all_braced_tokens():
    assert extract_tokens("{HERO} meets {SETTING}") == {"HERO", "SETTING"}


def test_invalid_mode_rejected():
    bad = {**VALID, "mode": "rainbow"}
    with pytest.raises(TemplateError, match="mode"):
        validate_template(parse_template(bad, slug="x"))


def test_undeclared_token_rejected():
    bad = json.loads(json.dumps(VALID))
    bad["pages"][0]["text"] = "{UNDECLARED} appears"
    with pytest.raises(TemplateError, match="UNDECLARED"):
        validate_template(parse_template(bad, slug="x"))


def test_empty_pages_rejected():
    bad = {**VALID, "pages": []}
    with pytest.raises(TemplateError, match="pages"):
        validate_template(parse_template(bad, slug="x"))


def test_select_without_options_rejected():
    bad = json.loads(json.dumps(VALID))
    bad["variables"][1]["options"] = []
    with pytest.raises(TemplateError, match="options"):
        validate_template(parse_template(bad, slug="x"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_storyforge_templates.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# storyforge/templates.py
import json
import re
from pathlib import Path

from storyforge.types import Variable, PageBeat, Template
from storyforge.errors import TemplateError

ROOT = Path(__file__).parent.parent
TEMPLATES_DIR = ROOT / "templates"

RESERVED_TOKENS = {"HERO", "HERO_NAME"}
_TOKEN_RE = re.compile(r"\{([A-Z_][A-Z0-9_]*)\}")


def extract_tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text or ""))


def parse_template(data: dict, slug: str = "") -> Template:
    try:
        variables = [
            Variable(
                key=v["key"],
                label=v.get("label", v["key"]),
                type=v.get("type", "text"),
                options=list(v.get("options", [])),
            )
            for v in data.get("variables", [])
        ]
        pages = [
            PageBeat(
                beat=p.get("beat", ""),
                text=p["text"],
                image_prompt=p["image_prompt"],
            )
            for p in data.get("pages", [])
        ]
        return Template(
            name=data["name"],
            mode=data.get("mode", "color"),
            language_default=data.get("language_default", "fr"),
            art_style=data.get("art_style", ""),
            variables=variables,
            pages=pages,
            slug=slug,
        )
    except (KeyError, TypeError) as exc:
        raise TemplateError(f"Malformed template {slug!r}: missing field {exc}") from exc


def validate_template(tpl: Template) -> Template:
    if tpl.mode not in ("color", "lineart"):
        raise TemplateError(f"Invalid mode {tpl.mode!r} (must be 'color' or 'lineart')")
    if not tpl.pages:
        raise TemplateError("Template has no pages")

    declared = {v.key for v in tpl.variables} | RESERVED_TOKENS
    for v in tpl.variables:
        if v.type not in ("text", "select"):
            raise TemplateError(f"Variable {v.key!r} has invalid type {v.type!r}")
        if v.type == "select" and not v.options:
            raise TemplateError(f"Select variable {v.key!r} requires non-empty options")

    for i, page in enumerate(tpl.pages, start=1):
        used = extract_tokens(page.text) | extract_tokens(page.image_prompt)
        undeclared = used - declared
        if undeclared:
            raise TemplateError(
                f"Page {i} uses undeclared token(s): {', '.join(sorted(undeclared))}"
            )
    return tpl


def load_template(slug: str) -> Template:
    path = TEMPLATES_DIR / slug / "template.json"
    if not path.exists():
        raise TemplateError(f"Template {slug!r} not found at {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TemplateError(f"Template {slug!r} is not valid JSON: {exc}") from exc
    return validate_template(parse_template(data, slug=slug))


def list_templates() -> list[Template]:
    if not TEMPLATES_DIR.exists():
        return []
    out = []
    for child in sorted(TEMPLATES_DIR.iterdir()):
        if (child / "template.json").exists():
            try:
                out.append(load_template(child.name))
            except TemplateError:
                continue
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_storyforge_templates.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add storyforge/templates.py tests/test_storyforge_templates.py
git commit -m "feat(storyforge): add template loading and validation"
```

---

## Task 4: Engine resolution (pure)

**Files:**
- Create: `storyforge/engine.py`
- Test: `tests/test_storyforge_engine.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_storyforge_engine.py
import pytest
from storyforge.engine import resolve
from storyforge.types import Template, Variable, PageBeat, CharacterSheet
from storyforge.errors import ResolutionError


def _template():
    return Template(
        name="Explorer",
        mode="color",
        language_default="fr",
        art_style="watercolor",
        variables=[
            Variable(key="HERO_NAME", label="Name", type="text"),
            Variable(key="SETTING", label="World", type="select", options=["forest"]),
        ],
        pages=[
            PageBeat(beat="intro", text="{HERO_NAME} in {SETTING}",
                     image_prompt="{HERO} exploring {SETTING}"),
        ],
    )


def _hero():
    return CharacterSheet(
        descriptor="boy, 7, curly hair",
        canonical_portrait_png=b"\x89PNG",
        art_style="watercolor",
    )


def test_resolve_substitutes_variables_and_hero():
    specs = resolve(_template(), {"HERO_NAME": "Sami", "SETTING": "forest"}, _hero())
    assert len(specs) == 1
    assert specs[0].text == "Sami in forest"
    assert specs[0].image_prompt == "boy, 7, curly hair exploring forest"
    assert specs[0].page_number == 1
    assert specs[0].mode == "color"


def test_resolve_missing_variable_raises():
    with pytest.raises(ResolutionError, match="SETTING"):
        resolve(_template(), {"HERO_NAME": "Sami"}, _hero())


def test_hero_name_token_filled_from_variable_not_descriptor():
    specs = resolve(_template(), {"HERO_NAME": "Sami", "SETTING": "forest"}, _hero())
    # HERO_NAME comes from the variable; HERO (image) comes from the descriptor
    assert "Sami" in specs[0].text
    assert "boy, 7, curly hair" in specs[0].image_prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_storyforge_engine.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# storyforge/engine.py
from storyforge.templates import extract_tokens, RESERVED_TOKENS
from storyforge.types import Template, CharacterSheet, PageSpec
from storyforge.errors import ResolutionError


def _substitute(text: str, mapping: dict[str, str]) -> str:
    out = text
    for token, value in mapping.items():
        out = out.replace("{" + token + "}", value)
    return out


def resolve(template: Template, variables: dict[str, str], hero: CharacterSheet) -> list[PageSpec]:
    # Collect all non-reserved tokens used anywhere.
    used: set[str] = set()
    for page in template.pages:
        used |= extract_tokens(page.text) | extract_tokens(page.image_prompt)
    required = {t for t in used if t not in RESERVED_TOKENS}
    missing = required - set(variables)
    if missing:
        raise ResolutionError(f"Missing required variable(s): {', '.join(sorted(missing))}")

    text_mapping = dict(variables)
    image_mapping = dict(variables)
    image_mapping["HERO"] = hero.descriptor

    specs: list[PageSpec] = []
    for i, page in enumerate(template.pages, start=1):
        specs.append(
            PageSpec(
                page_number=i,
                text=_substitute(page.text, text_mapping),
                image_prompt=_substitute(page.image_prompt, image_mapping),
                mode=template.mode,
            )
        )
    return specs
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_storyforge_engine.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add storyforge/engine.py tests/test_storyforge_engine.py
git commit -m "feat(storyforge): add pure template resolution engine"
```

---

## Task 5: Identity — build hero, validate photos, save/load sheet

**Files:**
- Create: `storyforge/identity.py`
- Test: `tests/test_storyforge_identity.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_storyforge_identity.py
import pytest
from storyforge.identity import build_hero, save_sheet, load_sheet, validate_photos
from storyforge.imagegen import FakeImageGenerator, PNG_MAGIC
from storyforge.errors import TemplateError

PNG = PNG_MAGIC + b"rest-of-bytes"


def test_validate_photos_rejects_empty():
    with pytest.raises(ValueError, match="at least one"):
        validate_photos([])


def test_validate_photos_rejects_too_many():
    with pytest.raises(ValueError, match="most 3"):
        validate_photos([PNG, PNG, PNG, PNG])


def test_build_hero_uses_photos_as_reference_and_returns_sheet():
    gen = FakeImageGenerator()
    sheet = build_hero(
        photos=[PNG],
        art_style="watercolor",
        gen=gen,
        analyze=lambda photos: "boy, 7, curly hair",
    )
    assert sheet.descriptor == "boy, 7, curly hair"
    assert sheet.art_style == "watercolor"
    assert sheet.canonical_portrait_png.startswith(PNG_MAGIC)
    # The portrait generation must be conditioned on the uploaded photos.
    assert gen.calls[0]["reference_images"] == [PNG]
    assert "watercolor" in gen.calls[0]["prompt"]


def test_save_and_load_sheet_round_trip(tmp_path):
    gen = FakeImageGenerator()
    sheet = build_hero([PNG], "watercolor", gen, lambda p: "desc")
    save_sheet(tmp_path, sheet)
    loaded = load_sheet(tmp_path)
    assert loaded.descriptor == "desc"
    assert loaded.canonical_portrait_png == sheet.canonical_portrait_png
    assert loaded.art_style == "watercolor"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_storyforge_identity.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# storyforge/identity.py
from pathlib import Path

from storyforge.imagegen import ImageGenerator
from storyforge.types import CharacterSheet

MAX_PHOTO_BYTES = 12 * 1024 * 1024  # 12 MB per photo

_PORTRAIT_PROMPT = (
    "Create a single front-facing character portrait of this person reimagined as a "
    "friendly children's book hero. Keep the face recognizable: same hair, eyes, and "
    "distinctive features. Full head and shoulders, neutral background. Art style: {art_style}."
)


def validate_photos(photos: list[bytes]) -> None:
    if not photos:
        raise ValueError("Provide at least one photo to build a hero.")
    if len(photos) > 3:
        raise ValueError("Provide at most 3 photos.")
    for p in photos:
        if not p:
            raise ValueError("Empty photo payload.")
        if len(p) > MAX_PHOTO_BYTES:
            raise ValueError("Photo exceeds the 12 MB size limit.")


def build_hero(photos, art_style, gen: ImageGenerator, analyze) -> CharacterSheet:
    validate_photos(photos)
    descriptor = analyze(photos)
    portrait = gen.generate(
        _PORTRAIT_PROMPT.format(art_style=art_style),
        reference_images=list(photos),
    )
    return CharacterSheet(
        descriptor=descriptor,
        canonical_portrait_png=portrait,
        art_style=art_style,
        source_photos=list(photos),
    )


def save_sheet(book_dir, sheet: CharacterSheet) -> None:
    hero_dir = Path(book_dir) / "hero"
    hero_dir.mkdir(parents=True, exist_ok=True)
    (hero_dir / "canonical_portrait.png").write_bytes(sheet.canonical_portrait_png)
    (hero_dir / "descriptor.txt").write_text(sheet.descriptor, encoding="utf-8")
    (hero_dir / "art_style.txt").write_text(sheet.art_style, encoding="utf-8")
    for i, photo in enumerate(sheet.source_photos):
        (hero_dir / f"source_{i}.png").write_bytes(photo)


def load_sheet(book_dir) -> CharacterSheet:
    hero_dir = Path(book_dir) / "hero"
    portrait = (hero_dir / "canonical_portrait.png").read_bytes()
    descriptor = (hero_dir / "descriptor.txt").read_text(encoding="utf-8")
    art_style = (hero_dir / "art_style.txt").read_text(encoding="utf-8")
    photos = [p.read_bytes() for p in sorted(hero_dir.glob("source_*.png"))]
    return CharacterSheet(
        descriptor=descriptor,
        canonical_portrait_png=portrait,
        art_style=art_style,
        source_photos=photos,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_storyforge_identity.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add storyforge/identity.py tests/test_storyforge_identity.py
git commit -m "feat(storyforge): add hero identity builder with photo conditioning"
```

---

## Task 6: Page generator (color vs line-art prompt shaping)

**Files:**
- Create: `storyforge/generator.py`
- Test: `tests/test_storyforge_generator.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_storyforge_generator.py
from storyforge.generator import generate_page
from storyforge.types import PageSpec, CharacterSheet
from storyforge.imagegen import FakeImageGenerator, PNG_MAGIC

HERO = CharacterSheet(
    descriptor="boy, 7",
    canonical_portrait_png=b"\x89PNG-portrait",
    art_style="soft watercolor",
)


def test_color_page_appends_art_style_and_uses_portrait_reference():
    gen = FakeImageGenerator()
    spec = PageSpec(page_number=1, text="hi", image_prompt="boy, 7 exploring forest", mode="color")
    out = generate_page(spec, HERO, gen)
    assert out.startswith(PNG_MAGIC)
    call = gen.calls[0]
    assert "soft watercolor" in call["prompt"]
    assert "exploring forest" in call["prompt"]
    assert call["reference_images"] == [HERO.canonical_portrait_png]


def test_lineart_page_uses_coloring_directive():
    gen = FakeImageGenerator()
    spec = PageSpec(page_number=2, text="hi", image_prompt="boy, 7 in forest", mode="lineart")
    generate_page(spec, HERO, gen)
    prompt = gen.calls[0]["prompt"].lower()
    assert "black" in prompt and "white" in prompt
    assert "no color" in prompt or "no colour" in prompt or "zero" in prompt
    assert gen.calls[0]["reference_images"] == [HERO.canonical_portrait_png]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_storyforge_generator.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# storyforge/generator.py
from storyforge.imagegen import ImageGenerator
from storyforge.types import PageSpec, CharacterSheet

_LINEART_DIRECTIVE = (
    "CRITICAL: pure black-and-white coloring-book line art. The ONLY ink is BLACK "
    "outlines on pure WHITE paper. Zero color, zero gray fills, zero shading, zero "
    "gradients. Every enclosed area stays white, ready to color. High contrast, 300 DPI. "
    "No text. Scene: "
)


def _build_prompt(spec: PageSpec, hero: CharacterSheet) -> str:
    if spec.mode == "lineart":
        return _LINEART_DIRECTIVE + spec.image_prompt
    return f"{spec.image_prompt}, {hero.art_style}. No text, no words, no letters."


def generate_page(spec: PageSpec, hero: CharacterSheet, gen: ImageGenerator) -> bytes:
    prompt = _build_prompt(spec, hero)
    return gen.generate(prompt, reference_images=[hero.canonical_portrait_png])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_storyforge_generator.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add storyforge/generator.py tests/test_storyforge_generator.py
git commit -m "feat(storyforge): add page generator with color/lineart prompt shaping"
```

---

## Task 7: Book builder (emit images + config.py)

**Files:**
- Create: `storyforge/builder.py`
- Test: `tests/test_storyforge_builder.py`

**Context for the engineer:** `pipeline/config_io.write_config(book_name, data)` writes
`books/<book_name>/config.py`. `read_config(book_name)` reads it back to a dict. The builder must
produce a `data` dict those functions accept. For a story book use `category="story"`,
`story_format="colored"` (color mode) or `"coloring"` (lineart mode), and `pages` as a list of dicts
with `page_number`, `text` (dict or str), and `image_prompt`. The page image filenames follow the
existing story convention: `<book_name>_page_<n>.png` (see `config_io.write_config` page_sequence
branch for `category == "story"`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_storyforge_builder.py
import pathlib
import pytest

from storyforge.builder import build_book
from storyforge.types import PageSpec, CharacterSheet
from pipeline.config_io import read_config

ROOT = pathlib.Path(__file__).parent.parent


@pytest.fixture
def cleanup_book():
    name = "test-storyforge-tmp"
    yield name
    import shutil
    shutil.rmtree(ROOT / "books" / name, ignore_errors=True)
    shutil.rmtree(ROOT / "images" / name, ignore_errors=True)


def test_build_book_writes_config_and_images(cleanup_book):
    name = cleanup_book
    hero = CharacterSheet(descriptor="boy", canonical_portrait_png=b"\x89PNG", art_style="watercolor")
    specs = [
        PageSpec(page_number=1, text="Sami begins", image_prompt="boy starts", mode="color"),
        PageSpec(page_number=2, text="Sami learns", image_prompt="boy learns", mode="color"),
    ]
    page_pngs = [b"\x89PNG-1", b"\x89PNG-2"]

    build_book(
        book_name=name,
        title="Sami's Adventure",
        author="Test Author",
        mode="color",
        specs=specs,
        page_pngs=page_pngs,
        hero=hero,
    )

    # Images written
    assert (ROOT / "images" / name / f"{name}_page_1.png").read_bytes() == b"\x89PNG-1"
    assert (ROOT / "images" / name / f"{name}_page_2.png").read_bytes() == b"\x89PNG-2"

    # Config round-trips through the existing contract
    cfg = read_config(name)
    assert cfg["title"] == "Sami's Adventure"
    assert cfg["author"] == "Test Author"
    assert cfg["category"] == "story"
    assert len(cfg["pages"]) == 2
    assert cfg["pages"][0]["text"]["fr"] == "Sami begins" or cfg["pages"][0]["text"] == "Sami begins"


def test_build_book_lineart_uses_coloring_category(cleanup_book):
    name = cleanup_book
    hero = CharacterSheet(descriptor="boy", canonical_portrait_png=b"\x89PNG", art_style="watercolor")
    specs = [PageSpec(page_number=1, text="hi", image_prompt="boy", mode="lineart")]
    build_book(name, "T", "A", "lineart", specs, [b"\x89PNG-1"], hero)
    cfg = read_config(name)
    assert cfg["category"] == "coloring"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_storyforge_builder.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# storyforge/builder.py
import pathlib

from pipeline.config_io import write_config
from storyforge.identity import save_sheet
from storyforge.types import PageSpec, CharacterSheet

ROOT = pathlib.Path(__file__).parent.parent


def build_book(
    book_name: str,
    title: str,
    author: str,
    mode: str,
    specs: list[PageSpec],
    page_pngs: list[bytes],
    hero: CharacterSheet,
) -> None:
    images_dir = ROOT / "images" / book_name
    images_dir.mkdir(parents=True, exist_ok=True)

    for spec, png in zip(specs, page_pngs):
        (images_dir / f"{book_name}_page_{spec.page_number}.png").write_bytes(png)

    category = "story" if mode == "color" else "coloring"
    story_format = "colored" if mode == "color" else "coloring"

    pages = [
        {
            "page_number": spec.page_number,
            "text": {"fr": spec.text, "ar": "", "en": spec.text, "es": ""},
            "moral": "",
            "image_prompt": spec.image_prompt,
        }
        for spec in specs
    ]

    data = {
        "category": category,
        "story_format": story_format,
        "story_layout": "top_bottom",
        "languages": ["fr"],
        "story_base_prompt": hero.art_style,
        "intro_text": "",
        "values_learned": "",
        "pages": pages,
        "title": title,
        "subtitle": "",
        "author": author,
        "images_folder": book_name,
        "characters": [],
    }
    write_config(book_name, data)

    save_sheet(ROOT / "books" / book_name, hero)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_storyforge_builder.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add storyforge/builder.py tests/test_storyforge_builder.py
git commit -m "feat(storyforge): add book builder emitting standard config.py"
```

---

## Task 8: Gemini backend (real ImageGenerator) + analyze function

**Files:**
- Create: `storyforge/gemini_backend.py`
- Test: `tests/test_storyforge_gemini_backend.py`

**Context:** This is the only module that touches the network. We do NOT call the real API in tests.
The test only asserts the prompt/reference assembly by monkeypatching the client. Mirror the call
shape used in `pipeline/generate.py` (`client.models.generate_content` with
`response_modalities=["IMAGE", "TEXT"]`) and `pipeline/story_gen.py` for text.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_storyforge_gemini_backend.py
from storyforge.gemini_backend import GeminiBackend


class _FakePart:
    def __init__(self, data):
        self.inline_data = type("I", (), {"data": data})() if data else None


class _FakeResp:
    def __init__(self, data):
        self.candidates = [type("C", (), {"content": type("Ct", (), {"parts": [_FakePart(data)]})()})()]


def test_generate_returns_inline_image_bytes(monkeypatch):
    backend = GeminiBackend.__new__(GeminiBackend)  # skip __init__ (no API key needed)

    class _Models:
        def generate_content(self, **kwargs):
            _Models.captured = kwargs
            return _FakeResp(b"PNGDATA")

    backend._client = type("Client", (), {"models": _Models()})()
    backend._image_model = "gemini-2.5-flash-image"

    out = backend.generate("draw a hero", reference_images=[b"ref"])
    assert out == b"PNGDATA"
    assert _Models.captured["model"] == "gemini-2.5-flash-image"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_storyforge_gemini_backend.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# storyforge/gemini_backend.py
import os

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:  # pragma: no cover
    genai = None
    genai_types = None

IMAGE_MODEL = "gemini-2.5-flash-image"
TEXT_MODEL = "gemini-2.5-flash"


class GeminiBackend:
    """Real ImageGenerator over google-genai. The only module that touches the network."""

    def __init__(self, api_key: str | None = None, image_model: str = IMAGE_MODEL):
        if genai is None:
            raise RuntimeError("google-genai not installed. Run: pip install google-genai")
        key = api_key or os.environ.get("GEMINI_API_KEY", "").strip()
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set.")
        self._client = genai.Client(api_key=key)
        self._image_model = image_model

    def generate(self, prompt: str, reference_images: list[bytes] | None = None) -> bytes:
        contents = [prompt]
        if reference_images:
            for img in reference_images:
                contents.append(
                    genai_types.Part.from_bytes(data=img, mime_type="image/png")
                )
        response = self._client.models.generate_content(
            model=self._image_model,
            contents=contents,
            config=genai_types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )
        for part in response.candidates[0].content.parts:
            if getattr(part, "inline_data", None) is not None:
                return part.inline_data.data
        raise RuntimeError("Gemini returned no image.")


def analyze_photos(photos: list[bytes], text_model: str = TEXT_MODEL, api_key: str | None = None) -> str:
    """Produce a compact physical descriptor of the person for hero consistency."""
    key = api_key or os.environ.get("GEMINI_API_KEY", "").strip()
    client = genai.Client(api_key=key)
    parts = [
        "Describe this person's physical appearance for a consistent children's book "
        "character: approximate age, hair color and style, eye color, skin tone, and any "
        "distinctive features. Reply with one compact comma-separated phrase, no sentences.",
    ]
    for img in photos:
        parts.append(genai_types.Part.from_bytes(data=img, mime_type="image/png"))
    response = client.models.generate_content(model=text_model, contents=parts)
    return (response.text or "").strip()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_storyforge_gemini_backend.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add storyforge/gemini_backend.py tests/test_storyforge_gemini_backend.py
git commit -m "feat(storyforge): add real Gemini image backend and photo analyzer"
```

---

## Task 9: Public API re-exports

**Files:**
- Modify: `storyforge/__init__.py`
- Test: `tests/test_storyforge_public_api.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_storyforge_public_api.py
import storyforge


def test_public_api_surface():
    for name in [
        "build_hero", "save_sheet", "load_sheet",
        "load_template", "list_templates", "validate_template",
        "resolve", "generate_page", "build_book",
        "FakeImageGenerator",
    ]:
        assert hasattr(storyforge, name), f"missing public export: {name}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_storyforge_public_api.py -v`
Expected: FAIL with `AssertionError: missing public export: build_hero`

- [ ] **Step 3: Write minimal implementation**

Replace the contents of `storyforge/__init__.py` with:

```python
# storyforge/__init__.py
from storyforge.types import (
    Variable, PageBeat, Template, CharacterSheet, PageSpec,
)
from storyforge.errors import TemplateError, ResolutionError
from storyforge.imagegen import ImageGenerator, FakeImageGenerator
from storyforge.templates import (
    load_template, list_templates, validate_template, parse_template, extract_tokens,
)
from storyforge.engine import resolve
from storyforge.identity import build_hero, save_sheet, load_sheet, validate_photos
from storyforge.generator import generate_page
from storyforge.builder import build_book

__all__ = [
    "Variable", "PageBeat", "Template", "CharacterSheet", "PageSpec",
    "TemplateError", "ResolutionError",
    "ImageGenerator", "FakeImageGenerator",
    "load_template", "list_templates", "validate_template", "parse_template", "extract_tokens",
    "resolve", "build_hero", "save_sheet", "load_sheet", "validate_photos",
    "generate_page", "build_book",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_storyforge_public_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add storyforge/__init__.py tests/test_storyforge_public_api.py
git commit -m "feat(storyforge): expose public API surface"
```

---

## Task 10: Example template ships in-repo

**Files:**
- Create: `templates/brave-little-explorer/template.json`
- Test: `tests/test_storyforge_example_template.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_storyforge_example_template.py
from storyforge.templates import load_template


def test_example_template_loads_and_validates():
    tpl = load_template("brave-little-explorer")
    assert tpl.name
    assert tpl.mode in ("color", "lineart")
    assert len(tpl.pages) >= 3
    keys = {v.key for v in tpl.variables}
    assert "HERO_NAME" in keys
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_storyforge_example_template.py -v`
Expected: FAIL with `TemplateError: Template 'brave-little-explorer' not found`

- [ ] **Step 3: Write minimal implementation**

```json
{
  "name": "The Brave Little Explorer",
  "mode": "color",
  "language_default": "fr",
  "art_style": "soft watercolor children's book illustration, warm palette, gentle lighting",
  "variables": [
    { "key": "HERO_NAME", "label": "Child's name", "type": "text" },
    { "key": "SETTING", "label": "World", "type": "select",
      "options": ["enchanted forest", "space station", "underwater city"] },
    { "key": "VALUE", "label": "Lesson learned", "type": "text" },
    { "key": "SIDEKICK", "label": "Companion animal", "type": "text" }
  ],
  "pages": [
    { "beat": "intro",
      "text": "{HERO_NAME} woke up at the edge of the {SETTING}, ready for a big adventure.",
      "image_prompt": "{HERO} standing at the edge of a {SETTING}, soft morning light, curious expression" },
    { "beat": "friend",
      "text": "Along the way, {HERO_NAME} met a friendly {SIDEKICK} who became a loyal friend.",
      "image_prompt": "{HERO} meeting a friendly {SIDEKICK} in the {SETTING}, warm and joyful" },
    { "beat": "challenge",
      "text": "Together they faced a tricky problem, and {HERO_NAME} felt a little scared.",
      "image_prompt": "{HERO} and a {SIDEKICK} facing a challenge in the {SETTING}, dramatic but gentle" },
    { "beat": "resolution",
      "text": "By being brave, {HERO_NAME} learned the power of {VALUE}.",
      "image_prompt": "{HERO} smiling proudly in the {SETTING} with a {SIDEKICK}, triumphant glow" }
  ]
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_storyforge_example_template.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add templates/brave-little-explorer/template.json tests/test_storyforge_example_template.py
git commit -m "feat(storyforge): ship example 'Brave Little Explorer' template"
```

---

## Task 11: Dashboard endpoints (templates, photos, hero, generate)

**Files:**
- Modify: `dashboard/app.py`
- Test: `tests/test_storyforge_api.py`

**Context:** Existing endpoints use FastAPI on the `app` object in `dashboard/app.py`, return SSE via
`StreamingResponse` with `media_type="text/event-stream"`, and load configs via `pipeline.config_io`.
Photos and hero live under `books/<name>/hero/`. To keep handlers testable, add a provider function
`_image_backend()` that returns a `GeminiBackend`; tests override it via `app.dependency_overrides` or
by monkeypatching the module attribute. Use a module-level `_backend_provider` callable so tests can
swap in a `FakeImageGenerator`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_storyforge_api.py
import io
import pathlib
import shutil
import pytest
from fastapi.testclient import TestClient

import dashboard.app as appmod
from storyforge.imagegen import FakeImageGenerator

ROOT = pathlib.Path(__file__).parent.parent
client = TestClient(appmod.app)


@pytest.fixture(autouse=True)
def fake_backend(monkeypatch):
    fake = FakeImageGenerator()
    monkeypatch.setattr(appmod, "_backend_provider", lambda: fake)
    monkeypatch.setattr(appmod, "_analyze_provider", lambda photos: "boy, 7, curly hair")
    yield fake


@pytest.fixture
def cleanup():
    name = "test-storyforge-api"
    yield name
    shutil.rmtree(ROOT / "books" / name, ignore_errors=True)
    shutil.rmtree(ROOT / "images" / name, ignore_errors=True)


def test_list_templates_includes_example():
    r = client.get("/api/storyforge/templates")
    assert r.status_code == 200
    slugs = [t["slug"] for t in r.json()]
    assert "brave-little-explorer" in slugs


def test_upload_photos_then_build_hero(cleanup):
    name = cleanup
    png = b"\x89PNG\r\n\x1a\n" + b"x" * 100
    r = client.post(
        f"/api/storyforge/{name}/photos",
        files=[("photos", ("a.png", io.BytesIO(png), "image/png"))],
    )
    assert r.status_code == 200
    assert (ROOT / "books" / name / "hero" / "source_0.png").exists()

    # Build hero (SSE stream) using template art style
    r = client.get(f"/stream/storyforge/{name}/hero?slug=brave-little-explorer")
    assert r.status_code == 200
    assert (ROOT / "books" / name / "hero" / "canonical_portrait.png").exists()


def test_generate_book_creates_config(cleanup, fake_backend):
    name = cleanup
    png = b"\x89PNG\r\n\x1a\n" + b"x" * 100
    client.post(f"/api/storyforge/{name}/photos",
                files=[("photos", ("a.png", io.BytesIO(png), "image/png"))])
    client.get(f"/stream/storyforge/{name}/hero?slug=brave-little-explorer")

    r = client.get(
        f"/stream/storyforge/{name}/generate",
        params={
            "slug": "brave-little-explorer",
            "title": "Sami's Adventure",
            "author": "Tester",
            "HERO_NAME": "Sami",
            "SETTING": "enchanted forest",
            "VALUE": "courage",
            "SIDEKICK": "fox",
        },
    )
    assert r.status_code == 200
    assert (ROOT / "books" / name / "config.py").exists()
    from pipeline.config_io import read_config
    cfg = read_config(name)
    assert cfg["title"] == "Sami's Adventure"
    assert len(cfg["pages"]) == 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_storyforge_api.py -v`
Expected: FAIL (endpoints 404 / attributes missing)

- [ ] **Step 3: Write minimal implementation**

Add near the top of `dashboard/app.py` (after existing imports):

```python
from storyforge.templates import list_templates as _sf_list_templates, load_template as _sf_load_template
from storyforge.identity import build_hero as _sf_build_hero, save_sheet as _sf_save_sheet, load_sheet as _sf_load_sheet
from storyforge.engine import resolve as _sf_resolve
from storyforge.generator import generate_page as _sf_generate_page
from storyforge.builder import build_book as _sf_build_book


def _backend_provider():
    from storyforge.gemini_backend import GeminiBackend
    return GeminiBackend(api_key=_resolve_gemini_api_key())


def _analyze_provider(photos):
    from storyforge.gemini_backend import analyze_photos
    return analyze_photos(photos, api_key=_resolve_gemini_api_key())
```

Add the endpoints (place them with the other `@app` routes):

```python
@app.get("/api/storyforge/templates")
def storyforge_templates():
    out = []
    for t in _sf_list_templates():
        out.append({
            "slug": t.slug,
            "name": t.name,
            "mode": t.mode,
            "art_style": t.art_style,
            "variables": [
                {"key": v.key, "label": v.label, "type": v.type, "options": v.options}
                for v in t.variables
            ],
            "pages": len(t.pages),
        })
    return out


@app.post("/api/storyforge/{name}/photos")
async def storyforge_photos(name: str, photos: list[UploadFile] = File(...)):
    if not photos:
        raise HTTPException(status_code=400, detail="No photos uploaded.")
    if len(photos) > 3:
        raise HTTPException(status_code=400, detail="At most 3 photos.")
    hero_dir = ROOT / "books" / name / "hero"
    hero_dir.mkdir(parents=True, exist_ok=True)
    for old in hero_dir.glob("source_*.png"):
        old.unlink()
    for i, photo in enumerate(photos):
        data = await photo.read()
        if not data:
            raise HTTPException(status_code=400, detail="Empty photo.")
        if len(data) > 12 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Photo too large (max 12 MB).")
        (hero_dir / f"source_{i}.png").write_bytes(data)
    return {"saved": len(photos)}


@app.get("/stream/storyforge/{name}/hero")
def storyforge_hero(name: str, slug: str):
    def stream():
        try:
            tpl = _sf_load_template(slug)
            hero_dir = ROOT / "books" / name / "hero"
            photos = [p.read_bytes() for p in sorted(hero_dir.glob("source_*.png"))]
            yield "data: Building hero from photos...\n\n"
            sheet = _sf_build_hero(photos, tpl.art_style, _backend_provider(), _analyze_provider)
            _sf_save_sheet(ROOT / "books" / name, sheet)
            yield "data: Hero ready.\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:  # surface boundary errors in the stream
            yield f"data: ERROR: {exc}\n\n"
    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/stream/storyforge/{name}/generate")
def storyforge_generate(name: str, request: Request, slug: str, title: str, author: str = ""):
    variables = {
        k: v for k, v in request.query_params.items()
        if k not in ("slug", "title", "author")
    }

    def stream():
        try:
            tpl = _sf_load_template(slug)
            hero = _sf_load_sheet(ROOT / "books" / name)
            specs = _sf_resolve(tpl, variables, hero)
            gen = _backend_provider()
            page_pngs = []
            for spec in specs:
                yield f"data: Generating page {spec.page_number}/{len(specs)}...\n\n"
                page_pngs.append(_sf_generate_page(spec, hero, gen))
            _sf_build_book(name, title, author, tpl.mode, specs, page_pngs, hero)
            yield "data: Book ready.\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            yield f"data: ERROR: {exc}\n\n"
    return StreamingResponse(stream(), media_type="text/event-stream")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_storyforge_api.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Run the full suite for non-regression**

Run: `python -m pytest -q`
Expected: all tests pass (existing + new)

- [ ] **Step 6: Commit**

```bash
git add dashboard/app.py tests/test_storyforge_api.py
git commit -m "feat(storyforge): add dashboard endpoints for templates, photos, hero, generate"
```

---

## Task 12: Dashboard UI flow (no page refresh)

**Files:**
- Create: `dashboard/templates/storybook.html`
- Modify: `dashboard/app.py` (add the page route)

**Context:** Follow the existing vanilla-JS + `fetch` + `EventSource` patterns already used in
`dashboard/templates/book.html` and `story.html`. No framework. All updates patch the DOM in place.

- [ ] **Step 1: Add the page route in `dashboard/app.py`**

```python
@app.get("/storybook", response_class=HTMLResponse)
def storybook_page(request: Request):
    return templates.TemplateResponse("storybook.html", {"request": request})
```

- [ ] **Step 2: Create `dashboard/templates/storybook.html`**

Build a single-page flow with these sections (vanilla JS, no reload):

1. Template `<select>` populated from `GET /api/storyforge/templates`; on change, render the
   variable form fields dynamically (text → `<input>`, select → `<select>` with options).
2. A book-name input (slugified client-side).
3. Drag-drop photo input (`<input type="file" multiple accept="image/*">`) with client-side
   thumbnail previews via `URL.createObjectURL`; POST to `/api/storyforge/{name}/photos` on change.
4. "Build hero" button → open `new EventSource('/stream/storyforge/'+name+'/hero?slug='+slug)`;
   append log lines; on `[DONE]` show the portrait `<img src="/images/.. ">` — but since the
   portrait is under `books/<name>/hero/`, add a tiny route to serve it (Step 3). Show
   Approve / Regenerate buttons. No reload.
5. Variable form + "Generate book" button → `new EventSource('/stream/storyforge/'+name+
   '/generate?'+params)`; stream per-page progress lines; on `[DONE]`, show a link to
   `/book/<name>` and insert a success banner. No reload.

Keep the markup consistent with the existing dashboard styling (reuse classes from `index.html`).

- [ ] **Step 3: Add a hero-portrait route in `dashboard/app.py`**

```python
@app.get("/api/storyforge/{name}/portrait")
def storyforge_portrait(name: str):
    path = ROOT / "books" / name / "hero" / "canonical_portrait.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail="No portrait yet.")
    return FileResponse(str(path), media_type="image/png")
```

- [ ] **Step 4: Add a nav link to the flow**

In `dashboard/templates/index.html`, add a link/button to `/storybook` labeled
"Personalized Storybook" in the existing nav/header area.

- [ ] **Step 5: Manual smoke test**

Run: `python3 dashboard/app.py` then open `http://localhost:8000/storybook`.
Verify: template select populates, variable fields render on change, photo thumbnails appear without
reload. (Hero/generate require a real `GEMINI_API_KEY`.)

- [ ] **Step 6: Commit**

```bash
git add dashboard/templates/storybook.html dashboard/templates/index.html dashboard/app.py
git commit -m "feat(storyforge): add no-refresh dashboard flow for personalized storybooks"
```

---

## Task 13: Community install/use/share guide + roadmap update

**Files:**
- Create: `README.storyforge.md`
- Modify: `BACKLOG.md` (mark StoryForge done), `tasks/todo.md` (add module status)

- [ ] **Step 1: Write `README.storyforge.md`**

Cover: what it is, install (`pip install -r requirements` or `pip install google-genai Pillow img2pdf fastapi jinja2 uvicorn`), set `GEMINI_API_KEY`, run the dashboard, open `/storybook`, how the
hero consistency works (hybrid character sheet), and **how to share a template** (drop a folder in
`templates/<slug>/template.json` with the documented schema). Include the template JSON schema and the
reserved tokens (`HERO`, `HERO_NAME`).

- [ ] **Step 2: Update roadmap files**

In `BACKLOG.md` under "✅ Fait", add:
```markdown
- [x] StoryForge — personalized hero storybooks from real photos (engine + dashboard + tests)
```
In `tasks/todo.md`, add a "StoryForge" section noting the module is implemented with tests.

- [ ] **Step 3: Run the full suite**

Run: `python -m pytest -q`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add README.storyforge.md BACKLOG.md tasks/todo.md
git commit -m "docs(storyforge): add community guide and update roadmap"
```

---

## Self-review notes

- **Spec coverage:** identity (T5/T8), templates (T3/T10), engine (T4), generator (T6), builder (T7),
  Gemini backend (T8), dashboard no-refresh flow (T11/T12), tests for every module (T1-T11),
  community guide (T13). All spec sections mapped.
- **DI seam:** `ImageGenerator` Protocol + `FakeImageGenerator`; backend swapped via
  `_backend_provider`/`_analyze_provider` in tests. No test hits the network.
- **Non-regression:** full `pytest -q` run in T11 and T13.
- **Naming consistency:** `build_hero`, `save_sheet`, `load_sheet`, `resolve`, `generate_page`,
  `build_book` used identically across tasks and the public API.
- **Reuses existing contract:** builder emits via `config_io.write_config`; downstream PDF/cover/KDP
  unchanged.
