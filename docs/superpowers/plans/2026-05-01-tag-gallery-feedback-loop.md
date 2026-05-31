# Tag Reference Gallery + Feedback Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a tag reference gallery (inline panel showing Gemini-generated examples per tag) and a prompt feedback loop (text feedback → AI-refined prompt diff → confirm → regenerate) to the KDP dashboard.

**Architecture:** Two new Python scripts handle generation and refinement; the FastAPI backend gains one new endpoint and an assets static mount; `book.html` gains a gallery sub-panel in the prompt builder and a feedback section per page card. No new dependencies — reuses `google-genai`, existing `generate_image`/`save_image` helpers, and the `rewrite_page.py` subprocess pattern.

**Tech Stack:** Python 3.11, FastAPI, google-genai (Gemini 2.5 Flash Image + Flash text), Jinja2/Tailwind CSS (no build step)

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `pipeline/generate_tag_examples.py` | **Create** | One-shot script: generate 1 PNG per tag, store in `assets/tag_examples/` |
| `pipeline/refine_prompt.py` | **Create** | Subprocess script: feedback + current prompt → refined prompt + change list (JSON) |
| `assets/tag_examples/{category}/{slug}.png` | **Create (generated)** | Static reference images served by FastAPI |
| `dashboard/app.py` | **Modify** | Mount `/assets`, extend `/api/prompt/tags`, add `POST /api/feedback/{book_name}` |
| `dashboard/templates/book.html` | **Modify** | Gallery sub-panel in prompt builder + feedback UI per page card |
| `tests/test_tag_gallery.py` | **Create** | Tests for new backend endpoints and slug helper |

---

## Task 1: Tag Example Generator Script

**Files:**
- Create: `pipeline/generate_tag_examples.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_tag_gallery.py
import pytest
from pipeline.generate_tag_examples import slugify, CATEGORY_TAGS

def test_slugify_basic():
    assert slugify("thick outlines") == "thick_outlines"

def test_slugify_special_chars():
    assert slugify("Art Nouveau") == "art_nouveau"
    assert slugify("Mandala-infused") == "mandala_infused"

def test_category_tags_has_all_categories():
    assert set(CATEGORY_TAGS.keys()) == {"style", "pose", "elements", "theme"}

def test_category_tags_nonempty():
    for cat, tags in CATEGORY_TAGS.items():
        assert len(tags) > 0, f"Category {cat!r} is empty"
```

- [ ] **Step 2: Run test — verify it fails**

```bash
cd /Users/mouadbelghiti/mo-projects/kidp
python -m pytest tests/test_tag_gallery.py -v
```
Expected: `ModuleNotFoundError: No module named 'pipeline.generate_tag_examples'`

- [ ] **Step 3: Create the script**

```python
# pipeline/generate_tag_examples.py
"""
One-shot script: generate 1 Gemini coloring-book image per tag and store
in assets/tag_examples/{category}/{slug}.png.

Safe to re-run: skips files that already exist unless --force is passed.

Usage:
    python3 pipeline/generate_tag_examples.py
    python3 pipeline/generate_tag_examples.py --category style
    python3 pipeline/generate_tag_examples.py --force
"""
import argparse
import os
import pathlib
import sys
import time

_ROOT = pathlib.Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    print("Missing dependency. Run:  pip install google-genai")
    sys.exit(1)

from pipeline.prompt import (
    STYLE_TAGS, POSE_TAGS, ELEMENT_TAGS, THEME_TAGS, _BASE_TEMPLATE
)
from pipeline.generate import generate_image, save_image

IMAGE_MODEL = "gemini-2.5-flash-image"
RATE_LIMIT_DELAY = 4  # seconds between API calls
ASSETS_DIR = _ROOT / "assets" / "tag_examples"

CATEGORY_TAGS: dict[str, list[str]] = {
    "style":    STYLE_TAGS,
    "pose":     POSE_TAGS,
    "elements": ELEMENT_TAGS,
    "theme":    THEME_TAGS,
}

# Neutral character used in all reference images
_NEUTRAL_CHARACTER = "a young anime-style hero, full body, standing"


def slugify(tag: str) -> str:
    """'Art Nouveau' → 'art_nouveau'"""
    return tag.lower().replace(" ", "_").replace("-", "_").replace("/", "_")


def build_example_prompt(tag: str, category: str) -> str:
    """Build a neutral coloring-book prompt with just this one tag applied."""
    if category == "style":
        character_prompt = f"{_NEUTRAL_CHARACTER}, {tag}"
    elif category == "pose":
        character_prompt = f"{_NEUTRAL_CHARACTER}, {tag}"
    elif category == "elements":
        character_prompt = f"{_NEUTRAL_CHARACTER}, with {tag}"
    else:  # theme
        character_prompt = f"{_NEUTRAL_CHARACTER}, {tag} style"
    return _BASE_TEMPLATE.format(character_prompt=character_prompt)


def run(filter_category: str | None = None, force: bool = False) -> None:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY environment variable is not set.")
        sys.exit(1)
    client = genai.Client(api_key=api_key)

    categories = (
        {filter_category: CATEGORY_TAGS[filter_category]}
        if filter_category
        else CATEGORY_TAGS
    )

    total = sum(len(tags) for tags in categories.values())
    print(f"Generating {total} tag example image(s)...\n")

    generated = skipped = failed = 0

    for category, tags in categories.items():
        for tag in tags:
            slug = slugify(tag)
            out_path = ASSETS_DIR / category / f"{slug}.png"
            if out_path.exists() and not force:
                print(f"  SKIP  [{category}/{slug}]")
                skipped += 1
                continue

            print(f"  GEN   [{category}/{slug}]  {tag!r}")
            try:
                prompt = build_example_prompt(tag, category)
                data = generate_image(client, prompt)
                save_image(data, out_path)
                print(f"        Saved: {out_path.relative_to(_ROOT)}")
                generated += 1
                time.sleep(RATE_LIMIT_DELAY)
            except Exception as exc:
                print(f"        ERROR: {exc}")
                failed += 1

    print(f"\nDone. Generated={generated}  Skipped={skipped}  Failed={failed}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate tag reference images")
    parser.add_argument("--category", choices=list(CATEGORY_TAGS.keys()),
                        help="Generate only one category")
    parser.add_argument("--force", action="store_true",
                        help="Re-generate even if file already exists")
    args = parser.parse_args()
    run(filter_category=args.category, force=args.force)
```

- [ ] **Step 4: Run test — verify it passes**

```bash
python -m pytest tests/test_tag_gallery.py::test_slugify_basic tests/test_tag_gallery.py::test_slugify_special_chars tests/test_tag_gallery.py::test_category_tags_has_all_categories tests/test_tag_gallery.py::test_category_tags_nonempty -v
```
Expected: 4 PASSED

- [ ] **Step 5: Dry-run to verify structure (no API call)**

```bash
python3 pipeline/generate_tag_examples.py --help
```
Expected: help text with `--category` and `--force` options.

- [ ] **Step 6: Commit**

```bash
git add pipeline/generate_tag_examples.py tests/test_tag_gallery.py
git commit -m "feat: add pipeline/generate_tag_examples.py with slugify helper"
```

---

## Task 2: Prompt Refinement Script

**Files:**
- Create: `pipeline/refine_prompt.py`

- [ ] **Step 1: Write the test**

```python
# append to tests/test_tag_gallery.py

def test_refine_prompt_script_exists():
    """Script must be importable and have a run() function."""
    from pipeline import refine_prompt
    assert callable(refine_prompt.run)
```

- [ ] **Step 2: Run test — verify it fails**

```bash
python -m pytest tests/test_tag_gallery.py::test_refine_prompt_script_exists -v
```
Expected: `ModuleNotFoundError: cannot import name 'refine_prompt'`

- [ ] **Step 3: Create the script**

```python
# pipeline/refine_prompt.py
"""
Subprocess script: given a current image prompt and user feedback,
ask Gemini to return a refined prompt and a human-readable list of changes.

Usage (called by dashboard/app.py as a subprocess):
    python3 pipeline/refine_prompt.py --prompt "..." --feedback "..."

Stdout: JSON  {"refined_prompt": "...", "changes": ["...", "..."]}
Exit 0 = success, Exit 1 = error (JSON with "error" key).
"""
import argparse
import json
import os
import sys

try:
    from google import genai
    from google.genai import types
except ImportError:
    print(json.dumps({"error": "Missing dependency: pip install google-genai"}))
    sys.exit(1)


def run(current_prompt: str, feedback: str) -> None:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print(json.dumps({"error": "GEMINI_API_KEY missing"}))
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    system_prompt = (
        "You are an expert KDP coloring book and children's storybook image prompt engineer.\n"
        "Your job is to refine an existing image generation prompt based on user feedback.\n\n"
        "RULES:\n"
        "- Never mention specific colors or dark fills in the refined prompt.\n"
        "- If the original prompt contains 'PURE BLACK AND WHITE', preserve that instruction.\n"
        "- Keep the refined prompt concise and actionable (under 400 words).\n"
        "- List each change you made in plain English (3-8 words each).\n\n"
        "OUTPUT: Return ONLY valid JSON with this exact shape:\n"
        '{"refined_prompt": "...", "changes": ["Change description 1", "Change description 2"]}'
    )

    user_message = (
        f"Current prompt:\n{current_prompt}\n\n"
        f"User feedback:\n{feedback}"
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
            ),
        )
        print(response.text)
    except Exception as exc:
        print(json.dumps({"error": str(exc)}))
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True, help="Current image prompt")
    parser.add_argument("--feedback", required=True, help="User feedback text")
    args = parser.parse_args()
    run(current_prompt=args.prompt, feedback=args.feedback)
```

- [ ] **Step 4: Run test — verify it passes**

```bash
python -m pytest tests/test_tag_gallery.py::test_refine_prompt_script_exists -v
```
Expected: PASSED

- [ ] **Step 5: Commit**

```bash
git add pipeline/refine_prompt.py tests/test_tag_gallery.py
git commit -m "feat: add pipeline/refine_prompt.py (prompt refinement via Gemini)"
```

---

## Task 3: Backend — Extend Tags Endpoint + Mount Assets + Feedback Endpoint

**Files:**
- Modify: `dashboard/app.py`

Key existing lines to reference:
- Line 1-35: imports — add `StaticFiles` here
- Line 638-648: `GET /api/prompt/tags` — extend response shape
- After line 648: insert new feedback endpoint
- Near top of file after `app = FastAPI(...)`: mount `/assets`

- [ ] **Step 1: Write the tests**

```python
# append to tests/test_tag_gallery.py
import pathlib
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

def _make_client():
    from dashboard.app import app
    return TestClient(app)

def test_prompt_tags_returns_examples_key():
    """Extended /api/prompt/tags must include *_examples keys."""
    client = _make_client()
    resp = client.get("/api/prompt/tags")
    assert resp.status_code == 200
    data = resp.json()
    assert "style" in data
    assert "style_examples" in data
    assert "pose_examples" in data
    assert "elements_examples" in data
    assert "theme_examples" in data

def test_prompt_tags_examples_are_url_strings():
    client = _make_client()
    data = client.get("/api/prompt/tags").json()
    for slug, url in data["style_examples"].items():
        assert url.startswith("/assets/tag_examples/style/")
        assert url.endswith(".png")

def test_feedback_endpoint_missing_key_returns_422():
    client = _make_client()
    resp = client.post("/api/feedback/book1-90s-legends", json={"feedback": "too static"})
    assert resp.status_code == 422  # missing current_prompt and page_ref
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
python -m pytest tests/test_tag_gallery.py::test_prompt_tags_returns_examples_key tests/test_tag_gallery.py::test_prompt_tags_examples_are_url_strings tests/test_tag_gallery.py::test_feedback_endpoint_missing_key_returns_422 -v
```
Expected: first two FAIL (`style_examples` key missing), third may pass or fail.

- [ ] **Step 3: Import StaticFiles and mount `/assets`**

Find the line `app = FastAPI()` (or similar) in `dashboard/app.py`. Just after the app creation, add:

```python
# In dashboard/app.py — after `app = FastAPI(...)`
from fastapi.staticfiles import StaticFiles as _StaticFiles
_ASSETS_DIR = ROOT / "assets"
_ASSETS_DIR.mkdir(exist_ok=True)
app.mount("/assets", _StaticFiles(directory=str(_ASSETS_DIR)), name="assets")
```

- [ ] **Step 4: Extend `/api/prompt/tags`**

Replace the existing endpoint (lines 638-648):

```python
# dashboard/app.py — replace the existing GET /api/prompt/tags
@app.get("/api/prompt/tags")
async def api_prompt_tags():
    def _examples(category: str, tags: list[str]) -> dict[str, str]:
        return {
            t.lower().replace(" ", "_").replace("-", "_").replace("/", "_"):
            f"/assets/tag_examples/{category}/{t.lower().replace(' ', '_').replace('-', '_').replace('/', '_')}.png"
            for t in tags
        }

    return {
        "style":            STYLE_TAGS,
        "style_examples":   _examples("style",    STYLE_TAGS),
        "pose":             POSE_TAGS,
        "pose_examples":    _examples("pose",     POSE_TAGS),
        "elements":         ELEMENT_TAGS,
        "elements_examples":_examples("elements", ELEMENT_TAGS),
        "theme":            THEME_TAGS,
        "theme_examples":   _examples("theme",    THEME_TAGS),
        "group_dynamics":   GROUP_DYNAMICS,
    }
```

- [ ] **Step 5: Add Pydantic model + feedback endpoint**

After the existing `GlobalReplaceModel` class (~line 495), add:

```python
# dashboard/app.py

class FeedbackModel(BaseModel):
    feedback: str
    current_prompt: str
    page_ref: str  # character id (coloring) or str(page_number) (story)


@app.post("/api/feedback/{book_name}")
async def api_feedback(book_name: str, data: FeedbackModel):
    if not os.environ.get("GEMINI_API_KEY"):
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY non configuré.")

    process = await asyncio.create_subprocess_exec(
        sys.executable, str(ROOT / "pipeline" / "refine_prompt.py"),
        "--prompt",    data.current_prompt,
        "--feedback",  data.feedback,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=os.environ.copy(),
    )
    stdout, _ = await process.communicate()

    if process.returncode != 0:
        raise HTTPException(status_code=500,
                            detail=f"Script failed: {stdout.decode()}")

    out_text = stdout.decode().strip()
    try:
        parsed = json.loads(out_text)
        if "error" in parsed:
            raise HTTPException(status_code=500, detail=parsed["error"])
        return parsed   # {"refined_prompt": "...", "changes": [...]}
    except json.JSONDecodeError:
        raise HTTPException(status_code=500,
                            detail=f"Bad JSON from Gemini: {out_text[:300]}")
```

- [ ] **Step 6: Run tests — verify they pass**

```bash
python -m pytest tests/test_tag_gallery.py::test_prompt_tags_returns_examples_key tests/test_tag_gallery.py::test_prompt_tags_examples_are_url_strings tests/test_tag_gallery.py::test_feedback_endpoint_missing_key_returns_422 -v
```
Expected: 3 PASSED

- [ ] **Step 7: Commit**

```bash
git add dashboard/app.py tests/test_tag_gallery.py
git commit -m "feat: extend /api/prompt/tags with examples, add /api/feedback endpoint, mount /assets"
```

---

## Task 4: Frontend — Gallery Panel in Prompt Builder

**Files:**
- Modify: `dashboard/templates/book.html`

The prompt builder renders via `renderTagSection(label, key, selectedTags, stateKey)` (around line 262). `allTags` is loaded once on page init. We add a `tagExamples` cache and a gallery panel that updates on tag click.

- [ ] **Step 1: Add `tagExamples` cache variable**

Find `let allTags = null;` (~line 172) and add directly below:

```javascript
// dashboard/templates/book.html — after `let allTags = null;`
let tagExamples = null;  // {style_examples: {slug: url}, pose_examples: {...}, ...}
```

- [ ] **Step 2: Populate `tagExamples` when `allTags` is fetched**

Find the block that fetches `/api/prompt/tags` (~line 504):

```javascript
// BEFORE (existing):
if (!allTags) {
  const tagRes = await fetch('/api/prompt/tags');
  allTags = await tagRes.json();
}

// AFTER (replace with):
if (!allTags) {
  const tagRes = await fetch('/api/prompt/tags');
  const tagData = await tagRes.json();
  allTags = {
    style:         tagData.style,
    pose:          tagData.pose,
    elements:      tagData.elements,
    theme:         tagData.theme,
    group_dynamics: tagData.group_dynamics,
  };
  tagExamples = {
    style:    tagData.style_examples    || {},
    pose:     tagData.pose_examples     || {},
    elements: tagData.elements_examples || {},
    theme:    tagData.theme_examples    || {},
  };
}
```

- [ ] **Step 3: Add gallery panel HTML**

Find `<div id="pb-solo"` (~line 113) and add a gallery panel sibling just below it:

```html
<!-- dashboard/templates/book.html — after <div id="pb-solo" ...> -->
<div id="tag-gallery-panel" class="hidden bg-gray-50 border border-gray-200 rounded-xl p-3 mt-2">
  <div class="flex items-center justify-between mb-2">
    <span id="tg-label" class="text-xs font-semibold text-gray-600"></span>
    <button onclick="document.getElementById('tag-gallery-panel').classList.add('hidden')"
            class="text-gray-400 hover:text-gray-600 text-xs">✕</button>
  </div>
  <img id="tg-img" src="" alt="Tag example"
       class="w-full rounded-lg border border-gray-200 bg-white"
       onerror="this.parentElement.innerHTML='<p class=\'text-xs text-gray-400 p-2\'>No example yet. Run:<br><code>python3 pipeline/generate_tag_examples.py</code></p>'" />
</div>
```

- [ ] **Step 4: Add `showTagExample(tag, category)` function**

Find `function attachTagListeners` (~line 281) and add before it:

```javascript
// dashboard/templates/book.html

function _slugify(tag) {
  return tag.toLowerCase().replace(/ /g, '_').replace(/-/g, '_').replace(/\//g, '_');
}

function showTagExample(tag, category) {
  if (!tagExamples) return;
  const examples = tagExamples[category] || {};
  const slug = _slugify(tag);
  const url = examples[slug];
  const panel = document.getElementById('tag-gallery-panel');
  const img   = document.getElementById('tg-img');
  const label = document.getElementById('tg-label');
  label.textContent = tag;
  img.src = url || '';
  panel.classList.remove('hidden');
}
```

- [ ] **Step 5: Wire tag-pill clicks to `showTagExample`**

Find `attachTagListeners` function (~line 281). After the existing toggle logic, add:

```javascript
// dashboard/templates/book.html — inside attachTagListeners, after the existing toggle block
// Map stateKey → category name for gallery lookup
const keyToCategory = { styleTags: 'style', poseTags: 'pose', elementTags: 'elements', themeTags: 'theme' };

document.querySelectorAll('.tag-pill').forEach(btn => {
  // Remove old click listener by cloning (avoids double-fire on re-render)
  const fresh = btn.cloneNode(true);
  btn.parentNode.replaceChild(fresh, btn);
});

document.querySelectorAll('.tag-pill').forEach(btn => {
  btn.addEventListener('click', () => {
    const tag  = btn.dataset.tag;
    const key  = btn.dataset.key;
    const mode = btn.dataset.mode || 'solo';
    // Original toggle logic
    if (mode === 'solo') {
      const idx = soloState[key].indexOf(tag);
      if (idx === -1) soloState[key].push(tag);
      else soloState[key].splice(idx, 1);
      renderSoloBuilder();
    } else {
      const idx = groupState[key].indexOf(tag);
      if (idx === -1) groupState[key].push(tag);
      else groupState[key].splice(idx, 1);
      renderGroupBuilder();
    }
    updateSoloPreview();
    // Gallery side-effect
    const cat = keyToCategory[key];
    if (cat) showTagExample(tag, cat);
  });
});
```

> **Note:** The existing `attachTagListeners` uses `querySelectorAll('.tag-pill').forEach(btn => { btn.addEventListener(...)`. Replace the entire body of that function with the block above to avoid double-binding.

- [ ] **Step 6: Manual verify**

```bash
source .env.local && make dashboard
# Open http://localhost:8000/book/book1-90s-legends
# Open prompt builder for any character
# Click a style tag pill
# Gallery panel should appear below with tag name shown
# If no examples generated yet: onerror message appears
```

- [ ] **Step 7: Commit**

```bash
git add dashboard/templates/book.html
git commit -m "feat: add tag reference gallery panel in prompt builder"
```

---

## Task 5: Frontend — Feedback UI Per Page Card

**Files:**
- Modify: `dashboard/templates/book.html`

The page/character cards are in the center column grid. Each card shows image + metadata. We add a collapsible feedback section below each card.

- [ ] **Step 1: Find where page cards are rendered**

```bash
grep -n "char-card\|page-card\|data-id\|data-char" dashboard/templates/book.html | head -20
```
Note the selector used to identify each card and which `data-*` attribute holds the character id or page number.

- [ ] **Step 2: Add feedback HTML to each card**

Find the template for a card (the `makeCharRow` or equivalent function). Locate where each card's inner HTML ends and add a feedback section. Example for a coloring-book character card (adapt data attributes as needed):

```html
<!-- Inside each page/character card — after image display area -->
<div class="feedback-section mt-2 border-t border-gray-100 pt-2">
  <button class="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1"
          onclick="toggleFeedback(this)">
    ▸ Améliorer ce prompt
  </button>
  <div class="feedback-body hidden mt-2 space-y-2">
    <textarea rows="2"
              class="feedback-input w-full text-xs border border-gray-200 rounded-lg p-2 resize-none"
              placeholder="ex: trop noir, pose trop statique, simplifie l'arrière-plan"></textarea>
    <button class="analyse-btn w-full text-xs bg-indigo-50 text-indigo-700 border border-indigo-200 rounded-lg px-3 py-1.5 hover:bg-indigo-100"
            onclick="analyseFeedback(this)">
      🔄 Analyser le feedback
    </button>
    <div class="diff-panel hidden space-y-2">
      <ul class="changes-list text-xs text-gray-600 space-y-1"></ul>
      <details class="text-xs">
        <summary class="cursor-pointer text-gray-400 hover:text-gray-600">Voir prompt complet</summary>
        <pre class="refined-prompt-text mt-1 whitespace-pre-wrap text-gray-500 text-xs bg-gray-50 p-2 rounded"></pre>
      </details>
      <button class="apply-btn w-full text-xs bg-green-600 text-white rounded-lg px-3 py-1.5 hover:bg-green-700"
              onclick="applyFeedback(this)">
        ✅ Appliquer &amp; Régénérer
      </button>
    </div>
  </div>
</div>
```

- [ ] **Step 3: Add JS helper functions**

Add these functions near the bottom of the `<script>` block (before the closing `</script>`):

```javascript
// dashboard/templates/book.html

function toggleFeedback(btn) {
  const body = btn.nextElementSibling;
  const open = !body.classList.contains('hidden');
  body.classList.toggle('hidden', open);
  btn.textContent = open ? '▸ Améliorer ce prompt' : '▾ Améliorer ce prompt';
}

async function analyseFeedback(btn) {
  const card     = btn.closest('[data-char-id], [data-page-num]');
  const pageRef  = card?.dataset.charId || card?.dataset.pageNum || '';
  const body     = btn.closest('.feedback-body');
  const feedback = body.querySelector('.feedback-input').value.trim();
  const promptEl = card?.querySelector('[data-field="prompt"]');
  const currentPrompt = promptEl?.value || '';

  if (!feedback) { showToast('Écris un feedback d\'abord'); return; }
  if (!currentPrompt) { showToast('Prompt introuvable sur cette carte'); return; }

  btn.disabled = true;
  btn.textContent = '⏳ Analyse...';

  try {
    const res = await fetch(`/api/feedback/{{ book_name }}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ feedback, current_prompt: currentPrompt, page_ref: pageRef }),
    });
    if (!res.ok) {
      const err = await res.json();
      showToast('Erreur: ' + (err.detail || res.status));
      return;
    }
    const data = await res.json();

    const diffPanel = body.querySelector('.diff-panel');
    const changesList = body.querySelector('.changes-list');
    const refinedText = body.querySelector('.refined-prompt-text');

    changesList.innerHTML = data.changes.map(c =>
      `<li class="flex gap-1"><span class="text-yellow-600">→</span>${escHtml(c)}</li>`
    ).join('');
    refinedText.textContent = data.refined_prompt;
    diffPanel.dataset.refinedPrompt = data.refined_prompt;
    diffPanel.classList.remove('hidden');

  } finally {
    btn.disabled = false;
    btn.textContent = '🔄 Analyser le feedback';
  }
}

async function applyFeedback(btn) {
  const card      = btn.closest('[data-char-id], [data-page-num]');
  const charId    = card?.dataset.charId || '';
  const pageNum   = card?.dataset.pageNum || '';
  const diffPanel = btn.closest('.diff-panel');
  const refined   = diffPanel.dataset.refinedPrompt;
  if (!refined) { showToast('Aucun prompt raffiné trouvé'); return; }

  // Update the prompt field on the card so it's included in next save
  const promptEl = card?.querySelector('[data-field="prompt"]');
  if (promptEl) promptEl.value = refined;

  // Save full config with updated prompt
  await saveConfig();

  // Trigger single-item generation
  if (charId) {
    streamGenerate('{{ book_name }}', charId);
  } else if (pageNum) {
    streamGenerate('{{ book_name }}', pageNum);
  }
  showToast('Prompt mis à jour — génération lancée');
}

function escHtml(str) {
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
```

> **Note:** `saveConfig()` and `streamGenerate(bookName, id)` are existing JS functions in `book.html`. Verify their exact names with `grep -n "function saveConfig\|function streamGenerate" dashboard/templates/book.html` before using.

- [ ] **Step 4: Verify existing function names**

```bash
grep -n "function saveConfig\|function streamGenerate\|function save\|stream.*generate\|generate.*stream" \
  dashboard/templates/book.html | head -15
```

Adjust the function names in Step 3 if different.

- [ ] **Step 5: Manual verify**

```bash
source .env.local && make dashboard
# Open http://localhost:8000/book/book1-90s-legends
# Expand a character card → click "Améliorer ce prompt"
# Type "make the pose more dynamic"
# Click "Analyser le feedback" → diff panel should appear with changes list
# Click "Appliquer & Régénérer" → prompt field updates, generation starts
```

- [ ] **Step 6: Commit**

```bash
git add dashboard/templates/book.html
git commit -m "feat: add feedback loop UI (analyse + apply + regen) per page card"
```

---

## Task 6: Generate Tag Examples (One-Shot Run)

**Files:**
- Create (generated): `assets/tag_examples/`

- [ ] **Step 1: Run the generator**

```bash
source .env.local && python3 pipeline/generate_tag_examples.py
```

Expected output:
```
Generating 22 tag example image(s)...

  GEN   [style/thick_outlines]  'thick outlines'
        Saved: assets/tag_examples/style/thick_outlines.png
  ...
Done. Generated=22  Skipped=0  Failed=0
```

- [ ] **Step 2: Verify files exist**

```bash
find assets/tag_examples -name "*.png" | wc -l
```
Expected: `22` (5 style + 5 pose + 7 elements + 5 theme = 22)

- [ ] **Step 3: Verify gallery works end-to-end**

```bash
source .env.local && make dashboard
# Open http://localhost:8000/book/book1-90s-legends
# Open prompt builder for any character
# Click "chibi style" tag → gallery panel appears with the generated reference image
```

- [ ] **Step 4: Add assets directory to gitignore exception**

`assets/tag_examples/` should be committed (shared reference, not user data). Verify `.gitignore` doesn't exclude it:

```bash
git check-ignore -v assets/tag_examples/style/thick_outlines.png
```
Expected: no output (not ignored). If ignored, add to `.gitignore`:
```
!assets/tag_examples/
```

- [ ] **Step 5: Commit generated examples**

```bash
git add assets/tag_examples/
git commit -m "chore: add generated tag reference images (22 examples)"
```

---

## Self-Review Checklist

- [x] **Spec coverage:** Feature 1 (gallery) → Tasks 1 + 3 + 4 + 6. Feature 2 (feedback loop) → Tasks 2 + 3 + 5. Both covered.
- [x] **No placeholders:** All code steps show full implementation. No TBDs.
- [x] **Type consistency:** `slugify()` in Task 1 matches `_slugify()` in Task 4 frontend (different names — both defined locally, no conflict). `CATEGORY_TAGS` keys `"style","pose","elements","theme"` match `tagExamples` keys throughout. `FeedbackModel.page_ref` used as string in both backend and frontend.
- [x] **Backward compatibility:** `allTags` still has `style: [string]` — existing tag-pill logic unchanged. New `style_examples` keys are additive.
