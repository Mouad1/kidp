# StoryForge Structured Payload Schema — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the formal `global_project_data` / `page_specific_data` payload schema so every page generation uses explicitly extracted, real-photo-derived character traits — not generic template descriptors.

**Architecture:** A new `extract_character_identity()` Gemini call extracts explicit physical traits from the client's raw photo and stores them as `CharacterSheet.character_visual_identity`. The `generate_story_prompt()` builder in `faceswap.py` reads from this field for [HERO REPLACEMENT] instead of `hero.descriptor`. A `PageGenerationPayload` dataclass formalizes the global/page split, making the prompt builder pure and testable.

**Tech Stack:** Python 3.11 dataclasses, Gemini text model (`gemini-2.0-flash`), `google-genai` SDK, `pytest`

## Global Constraints

- Never install new dependencies — use only existing `google-genai` + stdlib
- All Gemini calls injectable via `client=` kwarg for offline tests
- `FakeImageGenerator` must remain offline (no real HTTP)
- `character_visual_identity` persisted in `hero/character_visual_identity.txt` (same convention as `descriptor.txt`)
- Backward compat: `character_visual_identity` defaults to `""` — fallback to `hero.descriptor` in prompt builder
- Branch: `feat/structured-payload-schema`

---

### Task 1: `extract_character_identity` in `gemini_backend.py`

**Files:**
- Modify: `storyforge/gemini_backend.py` (append after `extract_page_assets`)
- Test: `tests/test_storyforge_gemini_backend.py` (create if not exists, else append)

**Interfaces:**
- Produces: `extract_character_identity(photo_bytes: bytes, text_model: str = TEXT_MODEL, api_key: str | None = None, client=None) -> str`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_storyforge_gemini_backend.py

import pytest
from unittest.mock import MagicMock
from storyforge.gemini_backend import extract_character_identity

def test_extract_character_identity_calls_gemini_with_photo():
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value.text = (
        "A young girl with curly dark hair, big dark eyes, light brown skin, and a warm round face."
    )
    fake_photo = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100  # fake PNG bytes

    result = extract_character_identity(fake_photo, client=mock_client)

    assert result == "A young girl with curly dark hair, big dark eyes, light brown skin, and a warm round face."
    mock_client.models.generate_content.assert_called_once()
    call_args = mock_client.models.generate_content.call_args
    # Photo must be in contents
    contents = call_args.kwargs.get("contents") or call_args.args[1]
    assert any(hasattr(c, "data") for c in contents), "Photo Part not found in contents"


def test_extract_character_identity_strips_whitespace():
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value.text = "  curly red hair, green eyes.  \n"

    result = extract_character_identity(b"fake", client=mock_client)
    assert result == "curly red hair, green eyes."


def test_extract_character_identity_raises_on_missing_genai(monkeypatch):
    import storyforge.gemini_backend as backend
    original = backend.genai
    backend.genai = None
    with pytest.raises(RuntimeError, match="google-genai not installed"):
        extract_character_identity(b"fake", client=None)
    backend.genai = original
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_storyforge_gemini_backend.py -v
```
Expected: ImportError or AttributeError — `extract_character_identity` does not exist yet.

- [ ] **Step 3: Implement `extract_character_identity`**

Add after `extract_page_assets` in `storyforge/gemini_backend.py`:

```python
def extract_character_identity(photo_bytes: bytes, text_model: str = TEXT_MODEL, api_key: str | None = None, client=None) -> str:
    """Extract explicit physical traits from a client photo for consistent hero identity."""
    if genai is None:
        raise RuntimeError("google-genai not installed. Run: pip install google-genai")
    c = client
    if c is None:
        key = api_key or os.environ.get("GEMINI_API_KEY", "").strip()
        c = genai.Client(api_key=key)

    prompt = (
        "Look at this photo of a real person. "
        "Describe their physical appearance in one concise sentence covering: "
        "hair color and texture, eye color and shape, skin tone, and overall facial structure. "
        "Be specific and factual. No interpretation or storytelling. "
        "Example format: 'A young girl with curly dark brown hair, large dark brown eyes, warm olive skin, and a round joyful face.'"
    )
    img_part = genai_types.Part.from_bytes(data=photo_bytes, mime_type="image/png")
    response = c.models.generate_content(model=text_model, contents=[prompt, img_part])
    return (response.text or "").strip()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_storyforge_gemini_backend.py -v
```
Expected: all 3 new tests PASS.

- [ ] **Step 5: Commit**

```bash
git add storyforge/gemini_backend.py tests/test_storyforge_gemini_backend.py
git commit -m "feat(gemini): extract_character_identity — physical traits from client photo"
```

---

### Task 2: Add `character_visual_identity` to `CharacterSheet` + persistence

**Files:**
- Modify: `storyforge/types.py` — add field to `CharacterSheet`
- Modify: `storyforge/identity.py` — populate in `build_hero`, persist/load in `save_sheet`/`load_sheet`
- Test: `tests/test_storyforge_identity.py` (append)

**Interfaces:**
- Consumes: `extract_character_identity(photo_bytes, client=None) -> str` from Task 1
- Produces: `CharacterSheet.character_visual_identity: str = ""`

- [ ] **Step 1: Write the failing test**

```python
# Append to tests/test_storyforge_identity.py

from storyforge.types import CharacterSheet

def test_character_sheet_has_character_visual_identity_field():
    sheet = CharacterSheet(
        descriptor="brave young hero",
        canonical_portrait_png=b"fake",
        art_style="watercolor",
        source_photos=[b"photo"],
        character_visual_identity="curly dark hair, big brown eyes, warm skin",
    )
    assert sheet.character_visual_identity == "curly dark hair, big brown eyes, warm skin"


def test_character_sheet_defaults_character_visual_identity_to_empty():
    sheet = CharacterSheet(
        descriptor="brave hero",
        canonical_portrait_png=b"fake",
        art_style="watercolor",
    )
    assert sheet.character_visual_identity == ""
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_storyforge_identity.py -v -k "character_visual_identity"
```
Expected: FAIL — `CharacterSheet.__init__()` does not accept `character_visual_identity`.

- [ ] **Step 3: Add field to `CharacterSheet` in `types.py`**

```python
@dataclass
class CharacterSheet:
    descriptor: str
    canonical_portrait_png: bytes
    art_style: str
    source_photos: list[bytes] = field(default_factory=list)
    character_visual_identity: str = ""
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest tests/test_storyforge_identity.py -v -k "character_visual_identity"
```
Expected: PASS.

- [ ] **Step 5: Write failing tests for `build_hero` and persistence**

```python
# Append to tests/test_storyforge_identity.py
from unittest.mock import MagicMock
from storyforge.identity import build_hero, save_sheet, load_sheet
import tempfile, pathlib

_FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20

def _make_fake_gen(output: bytes = _FAKE_PNG):
    gen = MagicMock()
    gen.generate.return_value = output
    return gen

def test_build_hero_calls_extract_and_populates_visual_identity():
    extract_fn = MagicMock(return_value="curly brown hair, dark eyes, warm skin")
    gen = _make_fake_gen()
    analyze = MagicMock(return_value="brave curious hero")

    sheet = build_hero(
        photos=[_FAKE_PNG],
        art_style="watercolor",
        gen=gen,
        analyze=analyze,
        extract_identity=extract_fn,
    )

    extract_fn.assert_called_once_with(_FAKE_PNG)
    assert sheet.character_visual_identity == "curly brown hair, dark eyes, warm skin"


def test_save_and_load_sheet_round_trips_visual_identity():
    sheet = CharacterSheet(
        descriptor="brave hero",
        canonical_portrait_png=_FAKE_PNG,
        art_style="watercolor",
        source_photos=[_FAKE_PNG],
        character_visual_identity="curly brown hair, dark eyes",
    )
    with tempfile.TemporaryDirectory() as tmp:
        save_sheet(tmp, sheet)
        loaded = load_sheet(tmp)
    assert loaded.character_visual_identity == "curly brown hair, dark eyes"
```

- [ ] **Step 6: Run to verify they fail**

```bash
python3 -m pytest tests/test_storyforge_identity.py -v -k "build_hero_calls_extract or round_trips"
```
Expected: FAIL — `build_hero` missing `extract_identity` param; `save_sheet`/`load_sheet` missing persistence logic.

- [ ] **Step 7: Update `build_hero`, `save_sheet`, `load_sheet` in `identity.py`**

```python
def build_hero(photos, art_style, gen: ImageGenerator, analyze, extract_identity=None) -> CharacterSheet:
    validate_photos(photos)
    descriptor = analyze(photos)
    # Extract visual identity from first photo (real call or injected fn for tests)
    character_visual_identity = ""
    if extract_identity is not None:
        character_visual_identity = extract_identity(photos[0])

    portrait = gen.generate(
        _PORTRAIT_PROMPT.format(art_style=art_style),
        reference_images=list(photos),
    )
    return CharacterSheet(
        descriptor=descriptor,
        canonical_portrait_png=portrait,
        art_style=art_style,
        source_photos=list(photos),
        character_visual_identity=character_visual_identity,
    )


def save_sheet(book_dir, sheet: CharacterSheet) -> None:
    hero_dir = Path(book_dir) / "hero"
    hero_dir.mkdir(parents=True, exist_ok=True)
    (hero_dir / "canonical_portrait.png").write_bytes(sheet.canonical_portrait_png)
    (hero_dir / "descriptor.txt").write_text(sheet.descriptor, encoding="utf-8")
    (hero_dir / "art_style.txt").write_text(sheet.art_style, encoding="utf-8")
    (hero_dir / "character_visual_identity.txt").write_text(sheet.character_visual_identity, encoding="utf-8")
    for i, photo in enumerate(sheet.source_photos):
        (hero_dir / f"source_{i}.png").write_bytes(photo)


def load_sheet(book_dir) -> CharacterSheet:
    hero_dir = Path(book_dir) / "hero"
    portrait = (hero_dir / "canonical_portrait.png").read_bytes()
    descriptor = (hero_dir / "descriptor.txt").read_text(encoding="utf-8")
    art_style = (hero_dir / "art_style.txt").read_text(encoding="utf-8")
    cvi_path = hero_dir / "character_visual_identity.txt"
    character_visual_identity = cvi_path.read_text(encoding="utf-8") if cvi_path.exists() else ""
    photos = [p.read_bytes() for p in sorted(hero_dir.glob("source_*.png"))]
    return CharacterSheet(
        descriptor=descriptor,
        canonical_portrait_png=portrait,
        art_style=art_style,
        source_photos=photos,
        character_visual_identity=character_visual_identity,
    )
```

- [ ] **Step 8: Run all identity tests**

```bash
python3 -m pytest tests/test_storyforge_identity.py -v
```
Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add storyforge/types.py storyforge/identity.py tests/test_storyforge_identity.py
git commit -m "feat(identity): character_visual_identity field — extracted from client photo"
```

---

### Task 3: Wire dashboard `build_hero` call to extract real identity

**Files:**
- Modify: `dashboard/app.py` — find where `build_hero` is called and add `extract_identity=` kwarg

**Interfaces:**
- Consumes: `extract_character_identity` from `storyforge.gemini_backend`
- Consumes: `build_hero(..., extract_identity=...)` from Task 2

- [ ] **Step 1: Locate all `build_hero` calls**

```bash
grep -n "build_hero" dashboard/app.py
```

- [ ] **Step 2: Import `extract_character_identity` at top of `dashboard/app.py`**

Find the existing storyforge import block and add:
```python
from storyforge.gemini_backend import extract_character_identity
```

- [ ] **Step 3: Update each `build_hero` call**

Replace each call like:
```python
hero = build_hero(photos=photos, art_style=art_style, gen=gen, analyze=analyze_fn)
```
with:
```python
hero = build_hero(
    photos=photos,
    art_style=art_style,
    gen=gen,
    analyze=analyze_fn,
    extract_identity=lambda photo: extract_character_identity(photo),
)
```

- [ ] **Step 4: Verify app starts without error**

```bash
python3 -c "from dashboard.app import app; print('import OK')"
```
Expected: `import OK`

- [ ] **Step 5: Commit**

```bash
git add dashboard/app.py
git commit -m "feat(dashboard): wire extract_character_identity into build_hero call"
```

---

### Task 4: Use `character_visual_identity` in `faceswap.py` prompt builder

**Files:**
- Modify: `storyforge/faceswap.py` — `run_hybrid_faceswap` reads `hero.character_visual_identity`
- Modify: `tests/test_storyforge_generator.py` — add test for populated identity in prompt

**Interfaces:**
- Consumes: `CharacterSheet.character_visual_identity: str` from Task 2
- Consumes: `generate_story_prompt(character_visual_identity=...)` — already correct param name

- [ ] **Step 1: Write failing test**

```python
# Append to tests/test_storyforge_generator.py

from storyforge.types import CharacterSheet, PageSpec

_TEMPLATE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64

def test_character_visual_identity_used_in_prompt_when_set():
    """When hero.character_visual_identity is set, it must appear in [HERO REPLACEMENT] block."""
    hero_with_identity = CharacterSheet(
        descriptor="generic descriptor",
        canonical_portrait_png=_TEMPLATE_PNG,
        art_style="watercolor",
        source_photos=[_TEMPLATE_PNG],
        character_visual_identity="curly dark hair, big brown eyes, warm olive skin",
    )
    spec = PageSpec(
        page_number=1,
        text="Sami enters the cave.",
        image_prompt="boy entering cave",
        mode="color",
    )
    from storyforge.generator import generate_page
    from storyforge.imagegen import FakeImageGenerator
    gen = FakeImageGenerator()
    generate_page(spec, hero_with_identity, gen, template_image=_TEMPLATE_PNG)
    prompt = gen.calls[0]["prompt"]
    assert "curly dark hair, big brown eyes, warm olive skin" in prompt
    assert "generic descriptor" not in prompt


def test_fallback_to_descriptor_when_visual_identity_empty():
    """When character_visual_identity is empty, fall back to hero.descriptor."""
    hero_no_identity = CharacterSheet(
        descriptor="brave young explorer",
        canonical_portrait_png=_TEMPLATE_PNG,
        art_style="watercolor",
        source_photos=[_TEMPLATE_PNG],
        character_visual_identity="",
    )
    spec = PageSpec(
        page_number=1, text="x", image_prompt="y", mode="color",
    )
    from storyforge.generator import generate_page
    from storyforge.imagegen import FakeImageGenerator
    gen = FakeImageGenerator()
    generate_page(spec, hero_no_identity, gen, template_image=_TEMPLATE_PNG)
    prompt = gen.calls[0]["prompt"]
    assert "brave young explorer" in prompt
```

- [ ] **Step 2: Run to verify fails**

```bash
python3 -m pytest tests/test_storyforge_generator.py -v -k "visual_identity"
```
Expected: FAIL — prompt uses `hero.descriptor` regardless.

- [ ] **Step 3: Update `run_hybrid_faceswap` in `faceswap.py`**

Change the `character_visual_identity` assignment:

```python
# Before:
character_visual_identity = hero.descriptor or "main character"

# After:
character_visual_identity = (
    hero.character_visual_identity
    if hero.character_visual_identity
    else (hero.descriptor or "main character")
)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_storyforge_generator.py -v -k "visual_identity"
```
Expected: PASS.

- [ ] **Step 5: Full test suite green**

```bash
python3 -m pytest -v
```
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add storyforge/faceswap.py tests/test_storyforge_generator.py
git commit -m "feat(faceswap): use character_visual_identity over descriptor for hero swap prompt"
```

---

### Task 5: Formalize `PageGenerationPayload` dataclass

**Files:**
- Modify: `storyforge/types.py` — add two new dataclasses
- Modify: `storyforge/faceswap.py` — `generate_story_prompt` accepts `PageGenerationPayload`
- Test: `tests/test_storyforge_faceswap.py` (create)

**Interfaces:**
- Produces: `GlobalProjectData`, `PageGenerationPayload` dataclasses
- Produces: `generate_story_prompt(payload: PageGenerationPayload) -> str`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_storyforge_faceswap.py

from storyforge.types import GlobalProjectData, PageGenerationPayload
from storyforge.faceswap import generate_story_prompt

_GLOBAL = GlobalProjectData(
    client_photo_reference="joujou.jpg",
    character_visual_identity="curly dark hair, big dark eyes, light brown skin",
    fixed_wardrobe_description="pink t-shirt dress with ruffled collar, purple hair bow",
)

_PAGE = PageGenerationPayload(
    global_data=_GLOBAL,
    base_template_image="book3_page_9.png",
    core_background_anchors=["stone floor", "golden doorway", "glowing purple smoke"],
    hero_action_and_emotion="standing looking up happily as old man slides bangles on her wrists",
    art_style="digital watercolor",
)


def test_payload_prompt_contains_environment_lock():
    prompt = generate_story_prompt(_PAGE)
    assert "[ENVIRONMENT LOCK]" in prompt
    assert "stone floor" in prompt
    assert "golden doorway" in prompt


def test_payload_prompt_contains_hero_replacement():
    prompt = generate_story_prompt(_PAGE)
    assert "[HERO REPLACEMENT]" in prompt
    assert "joujou.jpg" in prompt
    assert "curly dark hair, big dark eyes" in prompt


def test_payload_prompt_contains_wardrobe_continuity():
    prompt = generate_story_prompt(_PAGE)
    assert "[WARDROBE CONTINUITY]" in prompt
    assert "pink t-shirt dress" in prompt


def test_payload_prompt_contains_action_match():
    prompt = generate_story_prompt(_PAGE)
    assert "[ACTION MATCH]" in prompt
    assert "standing looking up happily" in prompt


def test_payload_prompt_references_template_image():
    prompt = generate_story_prompt(_PAGE)
    assert "book3_page_9.png" in prompt
```

- [ ] **Step 2: Run to verify fails**

```bash
python3 -m pytest tests/test_storyforge_faceswap.py -v
```
Expected: ImportError — `GlobalProjectData`, `PageGenerationPayload` not defined.

- [ ] **Step 3: Add dataclasses to `types.py`**

```python
@dataclass
class GlobalProjectData:
    client_photo_reference: str
    character_visual_identity: str
    fixed_wardrobe_description: str


@dataclass
class PageGenerationPayload:
    global_data: GlobalProjectData
    base_template_image: str
    core_background_anchors: list[str]
    hero_action_and_emotion: str
    art_style: str
```

- [ ] **Step 4: Refactor `generate_story_prompt` in `faceswap.py` to accept `PageGenerationPayload`**

```python
from storyforge.types import PageSpec, CharacterSheet, PageGenerationPayload

def generate_story_prompt(payload: PageGenerationPayload) -> str:
    g = payload.global_data
    anchors = ", ".join(payload.core_background_anchors) if payload.core_background_anchors else "background elements"
    return (
        f"A stylized digital illustration in {payload.art_style} style executing a precise 1-to-1 character swap. "
        f"The overall medium, brushwork style, composition layout, and lighting palette must perfectly mimic [{payload.base_template_image}].\n\n"
        f"[ENVIRONMENT LOCK]:\n"
        f"Replicate the exact composition, perspective, and background details from [{payload.base_template_image}] without any alterations. "
        f"The scene must explicitly retain: {anchors}.\n\n"
        f"[HERO REPLACEMENT]:\n"
        f"Completely remove the original protagonist from [{payload.base_template_image}]. "
        f"Replace them with the specific character from the photo [{g.client_photo_reference}]. "
        f"The replacement hero must consistently possess these exact traits: {g.character_visual_identity}. "
        f"Maintain the same art style ({payload.art_style}), expression, and medium.\n\n"
        f"[WARDROBE CONTINUITY]:\n"
        f"The character must be dressed exactly in: {g.fixed_wardrobe_description}.\n\n"
        f"[ACTION MATCH]:\n"
        f"The new character must precisely mirror the native composition layout by being positioned exactly where the original hero was, "
        f"executing this exact action: {payload.hero_action_and_emotion}. Do not modify the positioning or reactions of any other secondary characters present in the template."
    )
```

- [ ] **Step 5: Update `run_hybrid_faceswap` to build and use `PageGenerationPayload`**

```python
from storyforge.types import PageSpec, CharacterSheet, PageGenerationPayload, GlobalProjectData

# Inside run_hybrid_faceswap, replace the direct generate_story_prompt(...) call with:

global_data = GlobalProjectData(
    client_photo_reference=client_photo_reference,
    character_visual_identity=character_visual_identity,
    fixed_wardrobe_description=fixed_wardrobe_description,
)
payload = PageGenerationPayload(
    global_data=global_data,
    base_template_image=base_template_image,
    core_background_anchors=core_background_anchors,
    hero_action_and_emotion=hero_action_and_emotion,
    art_style=hero.art_style,
)
prompt = generate_story_prompt(payload)
```

- [ ] **Step 6: Full test suite green**

```bash
python3 -m pytest -v
```
Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add storyforge/types.py storyforge/faceswap.py tests/test_storyforge_faceswap.py
git commit -m "feat(types): PageGenerationPayload schema — formalize global/page-specific split"
```

---

## Self-Review

**Spec coverage:**
- `global_project_data.client_photo_reference` → `GlobalProjectData.client_photo_reference` ✓
- `global_project_data.character_visual_identity` → extracted via `extract_character_identity()` + stored in `CharacterSheet` ✓
- `global_project_data.fixed_wardrobe_description` → already in `Template.fixed_wardrobe_description`, flows through ✓
- `page_specific_data.base_template_image` → `PageGenerationPayload.base_template_image` (derived from `page_number`) ✓
- `page_specific_data.core_background_anchors` → `PageGenerationPayload.core_background_anchors` ✓
- `page_specific_data.hero_action_and_emotion` → `PageGenerationPayload.hero_action_and_emotion` ✓
- Prompt blocks [ENVIRONMENT LOCK] / [HERO REPLACEMENT] / [WARDROBE CONTINUITY] / [ACTION MATCH] ✓
- Backward compat: `character_visual_identity` defaults to `""`, fallback to `descriptor` ✓
- Persistence: `save_sheet`/`load_sheet` round-trip for `character_visual_identity` ✓

**No placeholders detected.**

**Type consistency:**
- `extract_character_identity(photo_bytes: bytes) -> str` — used in Task 1, Task 2, Task 3 ✓
- `CharacterSheet.character_visual_identity: str = ""` — defined Task 2, consumed Task 4 ✓
- `GlobalProjectData` / `PageGenerationPayload` — defined Task 5, consumed Task 5 ✓
- `generate_story_prompt(payload: PageGenerationPayload) -> str` — defined and consumed Task 5 ✓
