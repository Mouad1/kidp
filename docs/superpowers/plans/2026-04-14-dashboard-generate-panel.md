# Dashboard Generate Panel — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a slide-in side panel on the book detail page with a full image generation form (subject, description, style tags, pose tags, elements, post-processing toggles, live prompt preview) that streams Gemini output inline.

**Architecture:** New `/api/generate-custom` POST endpoint in `dashboard/app.py` accepts a JSON body with all form fields, assembles the Gemini prompt server-side, and streams output via SSE. The book detail template `book.html` gains a side panel component driven by vanilla JS — no framework. The existing `pipeline/generate.py` PROMPT_TEMPLATE is extracted into a shared helper so both CLI and dashboard use identical prompt assembly logic.

**Tech Stack:** FastAPI + Jinja2 (existing), vanilla JS + Tailwind CDN (existing), Google Gemini `gemini-2.5-flash-image` (existing)

---

## File Map

| File | Change |
|---|---|
| `pipeline/prompt.py` | **Create** — shared prompt assembly function extracted from generate.py |
| `pipeline/generate.py` | **Modify** — import prompt assembly from prompt.py instead of inline |
| `dashboard/app.py` | **Modify** — add POST `/api/generate-custom` SSE endpoint |
| `dashboard/templates/book.html` | **Modify** — add side panel HTML + JS |

---

### Task 1: Extract prompt assembly into `pipeline/prompt.py`

**Why:** Both CLI (`generate.py`) and dashboard need identical prompt logic. Single source of truth.

**Files:**
- Create: `pipeline/prompt.py`
- Modify: `pipeline/generate.py` (lines 43–54 — the PROMPT_TEMPLATE block)

- [ ] **Step 1: Create `pipeline/prompt.py`**

```python
"""
pipeline/prompt.py — Shared prompt assembly for Gemini image generation.

Used by both pipeline/generate.py (CLI) and dashboard/app.py (web).
"""

# Tags available for style/pose/elements — kept here so dashboard can read them
STYLE_TAGS = [
    "thick outlines",
    "thin detailed lines",
    "chibi style",
    "realistic proportions",
    "manga style",
]

POSE_TAGS = [
    "standing portrait",
    "action pose",
    "dynamic battle scene",
    "calm expression",
    "walking forward",
]

ELEMENT_TAGS = [
    "weapon",
    "energy aura",
    "companion animal",
    "background elements",
    "shadow army silhouettes",
    "magical effects",
    "detailed environment",
]

_BASE_TEMPLATE = (
    "Provide Professional adult coloring book page of {character_prompt}, "
    "full body centered, pure white background. "
    "Thick, bold black vector-style outlines only. "
    "CRITICAL: zero black fills, zero solid black areas anywhere on the body or clothing — "
    "all interior areas must be pure white and left empty for coloring. "
    "Zero shading, zero gray fills, zero gradients, zero color fills of any kind. "
    "High contrast, clean line art, 300 DPI quality, minimalist style ready for coloring."
)


def build_prompt(
    description: str,
    style_tags: list[str] | None = None,
    pose_tags: list[str] | None = None,
    element_tags: list[str] | None = None,
) -> str:
    """
    Assemble the full Gemini prompt from a character description and optional tag lists.

    Args:
        description:  Physical description of the character (no color names).
        style_tags:   Selected art style tags (e.g. ["thick outlines"]).
        pose_tags:    Selected pose/mood tags (e.g. ["action pose"]).
        element_tags: Selected element tags (e.g. ["energy aura", "weapon"]).

    Returns:
        The complete prompt string ready to send to Gemini.
    """
    parts = [description]
    for tag_list in (style_tags, pose_tags, element_tags):
        if tag_list:
            parts.extend(tag_list)

    character_prompt = ", ".join(p.strip() for p in parts if p.strip())
    return _BASE_TEMPLATE.format(character_prompt=character_prompt)
```

- [ ] **Step 2: Update `pipeline/generate.py` to use `prompt.py`**

Replace lines 43–54 (the `PROMPT_TEMPLATE` block and its usage in `run()`) with an import:

```python
# At top of file, after existing imports:
from pipeline.prompt import build_prompt

# Remove the PROMPT_TEMPLATE constant entirely.

# In run(), replace:
#   full_prompt = PROMPT_TEMPLATE.format(character_prompt=char["prompt"])
# with:
full_prompt = build_prompt(description=char["prompt"])
```

The full updated `run()` call site (around line 95):
```python
full_prompt = build_prompt(description=char["prompt"])
```

- [ ] **Step 3: Verify CLI still works**

```bash
cd /Users/mouadbelghiti/mo-projects/kidp
python3 pipeline/generate.py --book book2-modern-anime --id gojo --dry-run
```

Expected output includes the full prompt text with "CRITICAL: zero black fills..." and exits cleanly with "Dry-run complete."

- [ ] **Step 4: Commit**

```bash
git add pipeline/prompt.py pipeline/generate.py
git commit -m "refactor: extract prompt assembly into pipeline/prompt.py"
```

---

### Task 2: Add `/api/generate-custom` SSE endpoint in `dashboard/app.py`

**Files:**
- Modify: `dashboard/app.py` — add one new route after the existing `stream_generate` route

- [ ] **Step 1: Add imports at the top of `dashboard/app.py`**

Add after the existing imports:
```python
from fastapi import Form
from pipeline.prompt import build_prompt, STYLE_TAGS, POSE_TAGS, ELEMENT_TAGS
```

- [ ] **Step 2: Add the `/api/tags` route** (so the frontend can fetch tag lists dynamically)

Add after `api_book`:
```python
@app.get("/api/tags")
async def api_tags():
    """Return available style/pose/element tags for the generate panel."""
    return {
        "style":    STYLE_TAGS,
        "pose":     POSE_TAGS,
        "elements": ELEMENT_TAGS,
    }
```

- [ ] **Step 3: Add the `/stream/generate-custom/{book_name}` SSE endpoint**

Add after `stream_generate`:

```python
@app.post("/stream/generate-custom/{book_name}")
async def stream_generate_custom(
    book_name: str,
    subject: str = Form(...),
    description: str = Form(...),
    filename: str = Form(...),
    style_tags: str = Form(""),
    pose_tags: str = Form(""),
    element_tags: str = Form(""),
    auto_clean: str = Form("false"),
    auto_crop: str = Form("false"),
    add_to_sequence: str = Form("false"),
):
    """
    Generate a single custom image via Gemini and optionally clean/crop it.
    Streams progress as SSE. Form fields match the dashboard panel inputs.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "")

    cfg = _load_config(book_name)
    if not cfg:
        async def err():
            yield "data: ERROR: book not found\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(err(), media_type="text/event-stream")

    images_dir = pathlib.Path(cfg.IMAGES_DIR)
    images_dir.mkdir(parents=True, exist_ok=True)

    # Parse tag lists (comma-separated from form)
    def _parse_tags(raw: str) -> list[str]:
        return [t.strip() for t in raw.split(",") if t.strip()]

    full_prompt = build_prompt(
        description=description,
        style_tags=_parse_tags(style_tags),
        pose_tags=_parse_tags(pose_tags),
        element_tags=_parse_tags(element_tags),
    )

    out_path = images_dir / filename

    async def event_stream():
        if not api_key:
            yield "data: ERROR: GEMINI_API_KEY not set — restart dashboard with the env var.\n\n"
            yield "data: [DONE]\n\n"
            return

        yield f"data: Prompt: {full_prompt[:120]}...\n\n"
        yield f"data: Generating {filename}...\n\n"

        try:
            from google import genai as _genai
            from google.genai import types as _gtypes
            client = _genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model="gemini-2.5-flash-image",
                contents=full_prompt,
                config=_gtypes.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"],
                ),
            )
            img_data = None
            for part in response.candidates[0].content.parts:
                if part.inline_data is not None:
                    img_data = part.inline_data.data
                    break

            if img_data is None:
                yield "data: ERROR: Gemini returned no image (may have refused the prompt).\n\n"
                yield "data: [DONE]\n\n"
                return

            out_path.write_bytes(img_data)
            size_kb = len(img_data) / 1024
            yield f"data: Saved: {filename}  ({size_kb:.0f} KB)\n\n"

        except Exception as e:
            yield f"data: ERROR: {e}\n\n"
            yield "data: [DONE]\n\n"
            return

        # Post-processing
        if auto_crop == "true" or auto_clean == "true":
            flags = []
            if auto_crop == "true":
                flags.append("--crop-portrait")
            if auto_clean == "true":
                flags.append("--auto")
            yield f"data: Cleaning: {' '.join(flags)}...\n\n"
            cmd = [sys.executable, str(ROOT / "pipeline" / "clean.py"), str(out_path)] + flags
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            async for line in process.stdout:
                yield f"data: {line.decode().rstrip()}\n\n"
            await process.wait()

        # Add to PAGE_SEQUENCE in config.py
        if add_to_sequence == "true":
            yield f"data: Adding to PAGE_SEQUENCE...\n\n"
            config_path = ROOT / "books" / book_name / "config.py"
            content = config_path.read_text()
            new_entry = f'    ("{filename}", "{subject}"),\n'
            # Insert before the closing ] of PAGE_SEQUENCE
            if new_entry not in content:
                content = content.replace(
                    "]\n\n# ── Title-page layout",
                    f"{new_entry}]\n\n# ── Title-page layout"
                )
                config_path.write_text(content)
                yield f"data: Added to PAGE_SEQUENCE: {filename}\n\n"
            else:
                yield f"data: Already in PAGE_SEQUENCE — skipped.\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

- [ ] **Step 4: Verify the endpoint is registered**

```bash
cd /Users/mouadbelghiti/mo-projects/kidp
python3 -c "from dashboard.app import app; routes = [r.path for r in app.routes]; print([r for r in routes if 'generate' in r])"
```

Expected: `['/stream/generate/{book_name}', '/stream/generate-custom/{book_name}']`

- [ ] **Step 5: Commit**

```bash
git add dashboard/app.py
git commit -m "feat: add /stream/generate-custom SSE endpoint with prompt assembly"
```

---

### Task 3: Add the generate side panel to `book.html`

**Files:**
- Modify: `dashboard/templates/book.html`

The panel is a fixed-width `<aside>` that slides in from the right. The main content area shrinks when the panel is open (flex layout). All JS is inline vanilla.

- [ ] **Step 1: Replace the entire `book.html` with the updated version**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{{ book.title }} — KDP Dashboard</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    .tag-btn { display:inline-flex;align-items:center;font-size:.75rem;padding:.2rem .6rem;border-radius:9999px;cursor:pointer;border:1px solid #c7d2fe;background:#eef2ff;color:#4338ca;transition:all .15s; }
    .tag-btn.active { background:#4f46e5;color:#fff;border-color:#4f46e5; }
    .tag-btn:hover { background:#e0e7ff; }
    .tag-btn.active:hover { background:#4338ca; }
    #gen-panel { transition: width .2s ease; }
  </style>
</head>
<body class="bg-gray-50 text-gray-900 min-h-screen">

<header class="bg-white border-b border-gray-200 px-6 py-3 flex items-center gap-4 sticky top-0 z-10">
  <a href="/" class="text-gray-400 hover:text-gray-700 text-sm">← Dashboard</a>
  <h1 class="text-base font-bold">{{ book.title }}</h1>
  <span class="text-xs text-gray-400">{{ book_name }}</span>
</header>

<div class="flex" style="min-height:calc(100vh - 53px)">

  <!-- ── Main content ── -->
  <div class="flex-1 overflow-y-auto p-6 space-y-4 min-w-0">

    <!-- Action bar -->
    <div class="flex flex-wrap gap-2">
      <button onclick="openPanel()"
              class="flex items-center gap-2 bg-indigo-600 text-white text-sm rounded-lg px-4 py-2 hover:bg-indigo-700 transition-colors">
        🤖 Generate Image
      </button>
      <button onclick="runStream('/stream/clean/{{ book_name }}', '🧹 Cleaning all images...')"
              class="flex items-center gap-2 bg-gray-700 text-white text-sm rounded-lg px-4 py-2 hover:bg-gray-600 transition-colors"
              title="Runs auto-crop + artifact removal on every PNG in the images folder">
        🧹 Clean All
        <span class="text-xs text-gray-400 ml-1">auto-crop · remove artifacts</span>
      </button>
      <button onclick="runStream('/stream/assemble/{{ book_name }}', '⚙️ Assembling PDF...')"
              class="flex items-center gap-2 bg-green-600 text-white text-sm rounded-lg px-4 py-2 hover:bg-green-700 transition-colors"
              title="Assembles all images in PAGE_SEQUENCE into a KDP-ready PDF (0 fonts)">
        ⚙️ Assemble PDF
        <span class="text-xs text-green-300 ml-1">{{ book.in_sequence }} pages → PDF</span>
      </button>
    </div>

    <!-- Stats -->
    <div class="grid grid-cols-4 gap-3">
      <div class="bg-white border border-gray-200 rounded-xl p-4 text-center">
        <p class="text-2xl font-bold">{{ book.present }}</p>
        <p class="text-xs text-gray-500 mt-1">In sequence</p>
      </div>
      <div class="bg-white border border-gray-200 rounded-xl p-4 text-center">
        <p class="text-2xl font-bold {% if book.missing %}text-red-600{% else %}text-green-600{% endif %}">{{ book.missing | length }}</p>
        <p class="text-xs text-gray-500 mt-1">Missing</p>
      </div>
      <div class="bg-white border border-gray-200 rounded-xl p-4 text-center">
        <p class="text-2xl font-bold {% if book.suspicious %}text-yellow-600{% else %}text-green-600{% endif %}">{{ book.suspicious | length }}</p>
        <p class="text-xs text-gray-500 mt-1">⚠ Suspicious</p>
      </div>
      <div class="bg-white border border-gray-200 rounded-xl p-4 text-center">
        {% if book.pdf %}
          <p class="text-2xl font-bold text-green-600">✓</p>
          <p class="text-xs text-gray-500 mt-1">PDF {{ book.pdf.size_mb }} MB</p>
        {% else %}
          <p class="text-2xl font-bold text-gray-300">–</p>
          <p class="text-xs text-gray-500 mt-1">No PDF yet</p>
        {% endif %}
      </div>
    </div>

    <!-- Warnings -->
    {% if book.suspicious %}
    <div class="bg-yellow-50 border border-yellow-200 rounded-xl p-4 text-sm text-yellow-900">
      <p class="font-semibold mb-1">⚠ Possibly uncolorable — small file size detected</p>
      <p class="text-xs text-yellow-700 mb-3">Images under 150 KB may have solid black fills. Open the image to confirm, then regenerate.</p>
      <div class="flex flex-wrap gap-2">
        {% for fname in book.suspicious %}
        <button onclick="prefillRegen('{{ fname }}')"
                class="text-xs bg-yellow-200 text-yellow-900 rounded px-2 py-1 hover:bg-yellow-300">
          🔄 Regen {{ fname }}
        </button>
        {% endfor %}
      </div>
    </div>
    {% endif %}

    {% if book.missing %}
    <div class="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-900">
      <p class="font-semibold mb-2">❌ Missing images</p>
      <ul class="text-xs space-y-0.5 font-mono">{% for f in book.missing %}<li>{{ f }}</li>{% endfor %}</ul>
    </div>
    {% endif %}

    <!-- Images table -->
    <div class="bg-white border border-gray-200 rounded-xl overflow-hidden">
      <div class="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
        <h2 class="font-semibold text-sm">Images in PAGE_SEQUENCE</h2>
        <span class="text-xs text-gray-400">{{ book.images_detail | length }} pages</span>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="bg-gray-50 text-xs text-gray-500 uppercase tracking-wide">
            <tr>
              <th class="px-4 py-2 text-left">#</th>
              <th class="px-4 py-2 text-left">File</th>
              <th class="px-4 py-2 text-left">Label</th>
              <th class="px-4 py-2 text-right">Size</th>
              <th class="px-4 py-2 text-center">Status</th>
              <th class="px-4 py-2 text-center">Actions</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100">
            {% for img in book.images_detail %}
            <tr class="hover:bg-gray-50 {% if img.file in book.suspicious %}bg-yellow-50{% endif %}">
              <td class="px-4 py-2 text-gray-400 text-xs">{{ loop.index }}</td>
              <td class="px-4 py-2 font-mono text-xs">{{ img.file }}</td>
              <td class="px-4 py-2 text-gray-700">{{ img.label }}</td>
              <td class="px-4 py-2 text-right text-xs {% if img.size_kb < 150 %}text-yellow-600 font-medium{% else %}text-gray-500{% endif %}">{{ img.size_kb }} KB</td>
              <td class="px-4 py-2 text-center">
                {% if img.file in book.suspicious %}
                  <span class="bg-yellow-100 text-yellow-800 text-xs px-2 py-0.5 rounded-full">⚠ Check</span>
                {% else %}
                  <span class="bg-green-100 text-green-800 text-xs px-2 py-0.5 rounded-full">✓ OK</span>
                {% endif %}
              </td>
              <td class="px-4 py-2 text-center text-xs space-x-2">
                <button onclick="runStream('/stream/clean/{{ book_name }}?filename={{ img.file }}', 'Cleaning {{ img.file }}')"
                        class="text-gray-400 hover:text-gray-700 underline">clean</button>
                <button onclick="prefillRegen('{{ img.file }}', '{{ img.label }}')"
                        class="text-indigo-500 hover:text-indigo-700 underline">regen</button>
              </td>
            </tr>
            {% endfor %}
            {% for f in book.missing %}
            <tr class="bg-red-50">
              <td class="px-4 py-2 text-gray-400 text-xs">–</td>
              <td class="px-4 py-2 font-mono text-xs text-red-600">{{ f }}</td>
              <td class="px-4 py-2 text-red-400">Missing</td>
              <td class="px-4 py-2 text-right text-xs text-red-400">–</td>
              <td class="px-4 py-2 text-center"><span class="bg-red-100 text-red-800 text-xs px-2 py-0.5 rounded-full">Missing</span></td>
              <td class="px-4 py-2 text-center">–</td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>

    <!-- Extra images -->
    {% if book.extra_images %}
    <div class="bg-white border border-gray-200 rounded-xl p-5">
      <h2 class="font-semibold text-sm mb-3">Generated but not in PAGE_SEQUENCE</h2>
      <div class="flex flex-wrap gap-2">
        {% for fname in book.extra_images %}
        <span class="bg-gray-100 text-gray-700 text-xs px-2 py-1 rounded font-mono">{{ fname }}</span>
        {% endfor %}
      </div>
      <p class="text-xs text-gray-400 mt-3">Add to <code>books/{{ book_name }}/config.py → PAGE_SEQUENCE</code></p>
    </div>
    {% endif %}

    <!-- Console output -->
    <div id="console-wrapper" class="hidden">
      <div class="flex items-center justify-between mb-2">
        <h3 class="font-semibold text-sm" id="console-title">Output</h3>
        <button onclick="closeConsole()" class="text-xs text-gray-400 hover:text-gray-600">✕ Close</button>
      </div>
      <pre id="console-output"
           class="bg-gray-900 text-green-400 text-xs rounded-xl p-4 overflow-y-auto"
           style="max-height:320px;font-family:'Courier New',monospace;"></pre>
    </div>

  </div><!-- end main -->

  <!-- ── Generate side panel ── -->
  <aside id="gen-panel"
         class="hidden bg-white border-l border-gray-200 flex flex-col shadow-xl"
         style="width:420px;min-height:calc(100vh - 53px)">

    <div class="px-5 py-4 border-b border-gray-100 bg-gray-50 flex items-center justify-between sticky top-[53px] z-10">
      <div>
        <h2 class="font-bold text-sm">🤖 Generate Image</h2>
        <p class="text-xs text-gray-400 mt-0.5">Gemini · gemini-2.5-flash-image</p>
      </div>
      <button onclick="closePanel()" class="text-gray-400 hover:text-gray-700 text-lg leading-none">✕</button>
    </div>

    <form id="gen-form" class="flex-1 overflow-y-auto p-5 space-y-5">

      <!-- Subject / filename -->
      <div>
        <label class="block text-xs font-semibold text-gray-700 mb-1.5">Subject / page label <span class="text-red-400">*</span></label>
        <input id="f-subject" type="text" required
               class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
               placeholder="e.g. The Shadow Monarch"
               oninput="updateFilename(); updatePreview()"/>
        <p class="text-xs text-gray-400 mt-1">Filename: <code id="filename-preview" class="text-indigo-600">—</code></p>
      </div>

      <!-- Description -->
      <div>
        <label class="block text-xs font-semibold text-gray-700 mb-1.5">Character description <span class="text-red-400">*</span></label>
        <textarea id="f-desc" rows="3" required
                  class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 resize-none"
                  placeholder="Physical traits, outfit, accessories — avoid color words like 'black' or 'dark'"
                  oninput="updatePreview()"></textarea>
        <p class="text-xs text-amber-600 mt-1">⚠ Avoid color names → use texture/pattern instead ("coat with patterns" not "black coat")</p>
      </div>

      <!-- Style tags -->
      <div>
        <label class="block text-xs font-semibold text-gray-700 mb-2">Art style</label>
        <div id="style-tags" class="flex flex-wrap gap-1.5"></div>
      </div>

      <!-- Pose tags -->
      <div>
        <label class="block text-xs font-semibold text-gray-700 mb-2">Pose / ambiance</label>
        <div id="pose-tags" class="flex flex-wrap gap-1.5"></div>
      </div>

      <!-- Element tags -->
      <div>
        <label class="block text-xs font-semibold text-gray-700 mb-2">Additional elements</label>
        <div id="element-tags" class="flex flex-wrap gap-1.5"></div>
      </div>

      <!-- Post-processing toggles -->
      <div class="space-y-2">
        <label class="block text-xs font-semibold text-gray-700">Post-processing</label>
        <label class="flex items-center justify-between bg-gray-50 rounded-lg px-3 py-2.5 cursor-pointer">
          <div>
            <p class="text-sm font-medium">Auto-clean artifacts</p>
            <p class="text-xs text-gray-400">Whiten dark corner blobs automatically</p>
          </div>
          <input id="t-clean" type="checkbox" checked class="w-4 h-4 accent-indigo-600"/>
        </label>
        <label class="flex items-center justify-between bg-gray-50 rounded-lg px-3 py-2.5 cursor-pointer">
          <div>
            <p class="text-sm font-medium">Auto-crop to portrait</p>
            <p class="text-xs text-gray-400">Crop landscape 16:9 images to 8.5×11 ratio</p>
          </div>
          <input id="t-crop" type="checkbox" checked class="w-4 h-4 accent-indigo-600"/>
        </label>
        <label class="flex items-center justify-between bg-gray-50 rounded-lg px-3 py-2.5 cursor-pointer">
          <div>
            <p class="text-sm font-medium">Add to PAGE_SEQUENCE</p>
            <p class="text-xs text-gray-400">Append to config.py automatically after generation</p>
          </div>
          <input id="t-seq" type="checkbox" class="w-4 h-4 accent-indigo-600"/>
        </label>
      </div>

      <!-- Prompt preview -->
      <div>
        <div class="flex items-center justify-between mb-1.5">
          <label class="text-xs font-semibold text-gray-700">Prompt preview</label>
          <button type="button" onclick="updatePreview()" class="text-xs text-indigo-500 hover:text-indigo-700 underline">Refresh</button>
        </div>
        <pre id="prompt-preview"
             class="bg-gray-900 text-green-300 text-xs rounded-lg p-3 whitespace-pre-wrap break-words leading-relaxed"
             style="min-height:72px;max-height:160px;overflow-y:auto;font-family:'Courier New',monospace;">Fill in subject and description above...</pre>
      </div>

    </form>

    <!-- Panel footer -->
    <div class="p-4 border-t border-gray-100 bg-gray-50 space-y-2">
      <button id="gen-btn" onclick="submitGenerate()"
              class="w-full bg-indigo-600 text-white text-sm font-semibold rounded-lg px-4 py-3 hover:bg-indigo-700 transition-colors flex items-center justify-center gap-2">
        🚀 Generate Image
      </button>
      <p class="text-center text-xs text-gray-400">~5-15 sec · ~$0.04 / image via Gemini API</p>
    </div>

  </aside><!-- end panel -->

</div><!-- end flex -->

<script>
  // ── Tag data (fetched from API) ──────────────────────────────────────────────
  let TAGS = { style: [], pose: [], elements: [] };
  const selectedTags = { style: new Set(), pose: new Set(), elements: new Set() };

  async function loadTags() {
    const r = await fetch('/api/tags');
    TAGS = await r.json();
    renderTags('style-tags',   TAGS.style,    'style',    ['thick outlines']);
    renderTags('pose-tags',    TAGS.pose,     'pose',     ['standing portrait']);
    renderTags('element-tags', TAGS.elements, 'elements', []);
  }

  function renderTags(containerId, tags, group, defaultActive) {
    const el = document.getElementById(containerId);
    el.innerHTML = '';
    tags.forEach(tag => {
      const active = defaultActive.includes(tag);
      if (active) selectedTags[group].add(tag);
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'tag-btn' + (active ? ' active' : '');
      btn.textContent = tag;
      btn.onclick = () => {
        btn.classList.toggle('active');
        if (btn.classList.contains('active')) selectedTags[group].add(tag);
        else selectedTags[group].delete(tag);
        updatePreview();
      };
      el.appendChild(btn);
    });
  }

  // ── Filename auto-generation ─────────────────────────────────────────────────
  function updateFilename() {
    const subject = document.getElementById('f-subject').value.trim();
    const slug    = subject.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
    const fname   = slug ? `book_custom_${slug}.png` : '—';
    document.getElementById('filename-preview').textContent = fname;
  }

  function getFilename() {
    const subject = document.getElementById('f-subject').value.trim();
    const slug    = subject.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
    return `book_custom_${slug}.png`;
  }

  // ── Prompt preview ───────────────────────────────────────────────────────────
  function updatePreview() {
    const desc     = document.getElementById('f-desc').value.trim();
    const allTags  = [
      ...selectedTags.style,
      ...selectedTags.pose,
      ...selectedTags.elements,
    ];
    const charPrompt = [desc, ...allTags].filter(Boolean).join(', ');
    const preview = charPrompt
      ? `Provide Professional adult coloring book page of ${charPrompt}, full body centered, pure white background. Thick, bold black vector-style outlines only. CRITICAL: zero black fills, zero solid black areas...`
      : 'Fill in subject and description above...';
    document.getElementById('prompt-preview').textContent = preview;
  }

  // ── Panel open/close ─────────────────────────────────────────────────────────
  function openPanel() {
    document.getElementById('gen-panel').classList.remove('hidden');
  }
  function closePanel() {
    document.getElementById('gen-panel').classList.add('hidden');
  }

  // ── Prefill for regen ────────────────────────────────────────────────────────
  function prefillRegen(filename, label) {
    openPanel();
    if (label) document.getElementById('f-subject').value = label;
    updateFilename();
    updatePreview();
  }

  // ── Submit generate form ─────────────────────────────────────────────────────
  async function submitGenerate() {
    const subject = document.getElementById('f-subject').value.trim();
    const desc    = document.getElementById('f-desc').value.trim();
    if (!subject || !desc) { alert('Subject and description are required.'); return; }

    const btn = document.getElementById('gen-btn');
    btn.disabled  = true;
    btn.textContent = '⏳ Generating...';

    // Show console
    const wrapper = document.getElementById('console-wrapper');
    const output  = document.getElementById('console-output');
    const title   = document.getElementById('console-title');
    wrapper.classList.remove('hidden');
    output.textContent = '';
    title.textContent  = `🤖 Generating: ${subject}`;
    wrapper.scrollIntoView({ behavior: 'smooth' });

    const form = new FormData();
    form.append('subject',        subject);
    form.append('description',    desc);
    form.append('filename',       getFilename());
    form.append('style_tags',     [...selectedTags.style].join(','));
    form.append('pose_tags',      [...selectedTags.pose].join(','));
    form.append('element_tags',   [...selectedTags.elements].join(','));
    form.append('auto_clean',     document.getElementById('t-clean').checked ? 'true' : 'false');
    form.append('auto_crop',      document.getElementById('t-crop').checked  ? 'true' : 'false');
    form.append('add_to_sequence',document.getElementById('t-seq').checked   ? 'true' : 'false');

    const resp = await fetch('/stream/generate-custom/{{ book_name }}', {
      method: 'POST', body: form
    });
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split('\n');
      buf = lines.pop();
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const msg = line.slice(6);
          if (msg === '[DONE]') {
            output.textContent += '\n✅ Done!\n';
            btn.disabled = false;
            btn.textContent = '🚀 Generate Image';
            setTimeout(() => location.reload(), 1800);
          } else {
            output.textContent += msg + '\n';
          }
          output.scrollTop = output.scrollHeight;
        }
      }
    }
  }

  // ── Shared stream runner (for clean/assemble buttons) ────────────────────────
  let activeSource = null;
  function runStream(url, title) {
    const wrapper = document.getElementById('console-wrapper');
    const output  = document.getElementById('console-output');
    const titleEl = document.getElementById('console-title');
    wrapper.classList.remove('hidden');
    output.textContent = '';
    titleEl.textContent = title;
    wrapper.scrollIntoView({ behavior: 'smooth' });
    if (activeSource) activeSource.close();
    activeSource = new EventSource(url);
    activeSource.onmessage = e => {
      if (e.data === '[DONE]') {
        activeSource.close();
        output.textContent += '\n✅ Complete\n';
        setTimeout(() => location.reload(), 1500);
      } else {
        output.textContent += e.data + '\n';
        output.scrollTop = output.scrollHeight;
      }
    };
    activeSource.onerror = () => {
      output.textContent += '\n[Connection error]\n';
      activeSource.close();
    };
  }

  function closeConsole() {
    if (activeSource) { activeSource.close(); activeSource = null; }
    document.getElementById('console-wrapper').classList.add('hidden');
  }

  // ── Init ─────────────────────────────────────────────────────────────────────
  loadTags();
</script>
</body>
</html>
```

- [ ] **Step 2: Verify the page renders**

```bash
curl -s http://localhost:8000/book/book2-modern-anime | grep -o '<title>.*</title>'
```

Expected: `<title>Modern Legends: Coloring Our Stories — KDP Dashboard</title>`

- [ ] **Step 3: Commit**

```bash
git add dashboard/templates/book.html
git commit -m "feat: add generate side panel with tags, toggles, prompt preview"
```

---

### Task 4: Smoke test end-to-end

- [ ] **Step 1: Restart dashboard**

```bash
pkill -f uvicorn
cd /Users/mouadbelghiti/mo-projects/kidp
GEMINI_API_KEY="AIzaSyADnCX801njirLtxBlyBxvUvtF-WhaYlIw" python3 -m uvicorn dashboard.app:app --port 8000
```

- [ ] **Step 2: Open http://localhost:8000/book/book2-modern-anime**

Verify:
- "Clean All" button shows tooltip text "auto-crop · remove artifacts"
- "Assemble PDF" button shows page count
- Clicking "Generate Image" opens the side panel
- Tags load (style / pose / elements)
- Typing in Subject updates the filename preview
- Typing in Description updates the prompt preview
- Clicking a tag updates the prompt preview

- [ ] **Step 3: Test dry generation (no API cost)**

Fill in Subject: "Test Character", Description: "anime warrior with ornate armor". Toggle off "Add to PAGE_SEQUENCE". Click Generate.

Verify: console output appears, streams prompt text, then either saves the image or shows a clear error.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: dashboard generate panel complete — subject, tags, toggles, live preview, streaming"
```
