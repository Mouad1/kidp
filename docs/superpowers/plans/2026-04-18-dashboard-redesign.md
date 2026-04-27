# Dashboard Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refondre la page livre en vue unique sans onglets : table personnages à gauche, panneau contextuel (image preview + prompt builder) à droite, PAGE_SEQUENCE auto-générée, labels d'action clarifiés.

**Architecture:** La page `/book/<slug>` charge config + tags au démarrage, rend une table avec badges status calculés depuis `BOOK_DATA` (injecté en JSON par Jinja2), et un panneau droit contextuel géré entièrement en JS. `config_io.py` auto-génère `PAGE_SEQUENCE` depuis `CHARACTERS` quand le frontend ne l'envoie pas. Un endpoint `/images/<book>/<file>` sert les PNG pour le preview inline.

**Tech Stack:** Python (FastAPI), Jinja2, Tailwind CDN, Vanilla JS ES2020, FileResponse.

---

## File Map

| Fichier | Action | Responsabilité |
|---|---|---|
| `pipeline/config_io.py` | Modify | Auto-génère PAGE_SEQUENCE depuis CHARACTERS quand non fournie |
| `dashboard/app.py` | Modify | + `Optional` import, `page_sequence: Optional` dans BookConfigModel, + endpoint `/images/<book>/<file>` |
| `dashboard/templates/book.html` | Rewrite | Page unique, table + panneau, tout le JS |

---

### Task 1 : Backend — auto-génération PAGE_SEQUENCE + endpoint images

**Files:**
- Modify: `pipeline/config_io.py`
- Modify: `dashboard/app.py`

- [ ] **Step 1 : Rendre page_sequence Optional dans BookConfigModel**

Dans `dashboard/app.py`, ajouter `Optional` à l'import typing et modifier le modèle :

```python
from typing import Optional
```

Remplacer dans `BookConfigModel` :
```python
# AVANT
page_sequence: list[PageEntryModel] = []

# APRÈS
page_sequence: Optional[list[PageEntryModel]] = None
```

- [ ] **Step 2 : Auto-générer PAGE_SEQUENCE dans write_config()**

Dans `pipeline/config_io.py`, modifier `write_config()`. Remplacer la ligne :
```python
page_sequence = data.get("page_sequence", [])
```
par :
```python
if data.get("page_sequence") is None:
    book_prefix = book_name.split("-")[0]  # "book2-modern-anime" → "book2"
    page_sequence = [
        {"file": f"{book_prefix}_{c['id']}.png", "label": c["name"]}
        for c in data.get("characters", [])
    ]
else:
    page_sequence = data.get("page_sequence", [])
```

- [ ] **Step 3 : Ajouter l'endpoint /images/<book>/<file>**

Dans `dashboard/app.py`, ajouter l'import en haut :
```python
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
```
(remplace la ligne `from fastapi.responses import HTMLResponse, StreamingResponse`)

Ajouter l'endpoint après la route `api_prompt_tags` :
```python
@app.get("/images/{book_name}/{filename}")
async def serve_image(book_name: str, filename: str):
    cfg = _load_config(book_name)
    if not cfg:
        raise HTTPException(status_code=404, detail="Book not found")
    image_path = pathlib.Path(cfg.IMAGES_DIR) / filename
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(str(image_path), media_type="image/png")
```

- [ ] **Step 4 : Vérifier les endpoints**

```bash
python3 dashboard/app.py &
sleep 2
# Tester l'auto-génération (sauvegarder un livre existant)
curl -X PUT http://localhost:8000/api/book/book1-90s-legends/config \
  -H "Content-Type: application/json" \
  -d '{"title":"Test","subtitle":"","author":"Marco Belghiti","testpen":"","images_folder":"book1-90s-legends","characters":[{"id":"test","name":"Test Char","series":"","prompt":"test prompt"}]}'
# Vérifier que PAGE_SEQUENCE est généré dans books/book1-90s-legends/config.py
grep PAGE_SEQUENCE books/book1-90s-legends/config.py
kill %1
```

Expected : `PAGE_SEQUENCE = [\n    ('book1_test.png', 'Test Char')\n]`

- [ ] **Step 5 : Commit**

```bash
git add pipeline/config_io.py dashboard/app.py
git commit -m "feat: auto-generate PAGE_SEQUENCE from CHARACTERS, add /images endpoint"
```

---

### Task 2 : book.html — Structure HTML complète

**Files:**
- Rewrite: `dashboard/templates/book.html`

- [ ] **Step 1 : Remplacer book.html par la nouvelle structure**

Remplacer le contenu intégral de `dashboard/templates/book.html` par :

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{{ book.title }} — KDP Dashboard</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50 text-gray-900 min-h-screen">

  <!-- Toast -->
  <div id="toast" class="hidden fixed top-4 right-4 bg-gray-900 text-white text-sm px-4 py-2 rounded-lg shadow-lg z-50"></div>

  <!-- Header -->
  <header class="bg-white border-b border-gray-200 px-6 py-4">
    <div class="max-w-7xl mx-auto">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-4">
          <a href="/" class="text-gray-400 hover:text-gray-700 text-sm">← Dashboard</a>
          <div>
            <h1 class="text-lg font-bold">{{ book.title }}</h1>
            <p class="text-xs text-gray-400">{{ book_name }} · {{ book.author }}</p>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <button onclick="runAction('generate', '{{ book_name }}')"
                  class="flex items-center gap-1.5 bg-indigo-600 text-white text-sm rounded-lg px-4 py-2 hover:bg-indigo-700">
            🤖 Generate All
          </button>
          <button onclick="runAction('clean', '{{ book_name }}')"
                  class="flex items-center gap-1.5 bg-gray-700 text-white text-sm rounded-lg px-4 py-2 hover:bg-gray-600">
            🔧 Fix Images
          </button>
          <button onclick="runAction('assemble', '{{ book_name }}')"
                  class="flex items-center gap-1.5 bg-green-600 text-white text-sm rounded-lg px-4 py-2 hover:bg-green-700">
            📄 Build PDF
          </button>
        </div>
      </div>
      <!-- Stats line -->
      <p class="mt-2 text-xs text-gray-500">
        {{ book.present }} images
        {% if book.missing %} · <span class="text-red-500">{{ book.missing | length }} missing</span>{% endif %}
        {% if book.suspicious %} · <span class="text-yellow-600">{{ book.suspicious | length }} ⚠ suspicious</span>{% endif %}
        {% if book.pdf %} · <span class="text-green-600">PDF ✓ {{ book.pdf.size_mb }} MB</span>
        {% else %} · <span class="text-gray-400">No PDF yet</span>{% endif %}
      </p>
    </div>
  </header>

  <!-- Main flex -->
  <main class="max-w-7xl mx-auto px-6 py-6 flex gap-6 items-start">

    <!-- LEFT: Characters table -->
    <div class="w-5/12 flex-shrink-0 space-y-4">
      <div class="bg-white border border-gray-200 rounded-xl overflow-hidden">
        <div class="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
          <h2 class="font-semibold text-sm">Personnages
            <span id="char-count" class="text-gray-400 font-normal"></span>
          </h2>
          <div class="flex gap-2">
            <button onclick="openGroupBuilder()"
                    class="text-xs bg-gray-100 text-gray-700 rounded-lg px-3 py-1.5 hover:bg-gray-200">
              + Groupe
            </button>
            <button onclick="addCharacterRow()"
                    class="text-xs bg-indigo-600 text-white rounded-lg px-3 py-1.5 hover:bg-indigo-700">
              + Perso
            </button>
          </div>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead class="bg-gray-50 text-xs text-gray-500 uppercase tracking-wide">
              <tr>
                <th class="px-3 py-2 text-left w-8">#</th>
                <th class="px-3 py-2 text-left w-20">ID</th>
                <th class="px-3 py-2 text-left">Nom</th>
                <th class="px-3 py-2 text-center w-28">Status</th>
                <th class="px-3 py-2 text-center w-12">↑↓</th>
              </tr>
            </thead>
            <tbody id="characters-tbody" class="divide-y divide-gray-100"></tbody>
          </table>
        </div>
      </div>
      <div class="flex justify-end">
        <button onclick="saveConfig('{{ book_name }}')"
                class="bg-gray-900 text-white text-sm rounded-lg px-6 py-2.5 hover:bg-gray-700">
          💾 Save Config
        </button>
      </div>
    </div>

    <!-- RIGHT: Contextual panel -->
    <div class="flex-1 min-w-0">
      <div id="right-panel" class="bg-white border border-gray-200 rounded-xl overflow-hidden">

        <!-- Idle -->
        <div id="panel-idle">
          <div class="px-5 py-4 border-b border-gray-100">
            <p class="font-semibold text-sm">Identité du livre</p>
          </div>
          <div class="p-5 space-y-4">
            <div>
              <label class="text-xs text-gray-500 block mb-1">Title</label>
              <input id="cfg-title" type="text"
                     class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
            </div>
            <div>
              <label class="text-xs text-gray-500 block mb-1">Subtitle</label>
              <input id="cfg-subtitle" type="text"
                     class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
            </div>
            <div>
              <label class="text-xs text-gray-500 block mb-1">Author</label>
              <input id="cfg-author" type="text"
                     class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
            </div>
            <p class="text-xs text-gray-400 pt-2">
              ← Sélectionne un personnage pour éditer son prompt et voir l'image générée
            </p>
          </div>
        </div>

        <!-- Solo -->
        <div id="panel-solo" class="hidden"></div>

        <!-- Group -->
        <div id="panel-group" class="hidden"></div>

      </div>
    </div>

  </main>

  <!-- Console streaming -->
  <div class="max-w-7xl mx-auto px-6 pb-8">
    <div id="console-wrapper" class="hidden">
      <div class="flex items-center justify-between mb-2">
        <h3 class="font-semibold text-sm" id="console-title">Output</h3>
        <button onclick="closeConsole()" class="text-xs text-gray-400 hover:text-gray-600">✕ Close</button>
      </div>
      <pre id="console-output"
           class="bg-gray-900 text-green-400 text-xs rounded-xl p-4 overflow-y-auto"
           style="max-height:400px;min-height:100px;font-family:'Courier New',monospace;"></pre>
    </div>
  </div>

  <script>
    const BOOK_NAME = '{{ book_name }}';
    const BOOK_DATA = {{ book | tojson }};
    let configData  = null;

    // ── Prompt builder state ──────────────────────────────────────────────────
    let allTags         = null;
    let builderMode     = 'none'; // 'none' | 'solo' | 'group'
    let activeSoloIndex = null;

    const PROMPT_TEMPLATE = (
      "Provide Professional adult coloring book page of {cp}, " +
      "full body centered, pure white background. " +
      "Thick, bold black vector-style outlines only. " +
      "CRITICAL: zero black fills, zero solid black areas anywhere on the body or clothing — " +
      "all interior areas must be pure white and left empty for coloring. " +
      "Zero shading, zero gray fills, zero gradients, zero color fills of any kind. " +
      "High contrast, clean line art, 300 DPI quality, minimalist style ready for coloring."
    );

    let soloState = {
      description: '', styleTags: [], poseTags: [],
      elementTags: [], themeTags: [], extraNotes: ''
    };

    let groupState = {
      charDescs: {}, charIds: [],
      styleTags: [], elementTags: [], themeTags: [],
      groupDynamic: '', extraNotes: ''
    };

    // ── Init ──────────────────────────────────────────────────────────────────
    async function init() {
      const res   = await fetch(`/api/book/${BOOK_NAME}/config`);
      configData  = await res.json();
      document.getElementById('cfg-title').value    = configData.title;
      document.getElementById('cfg-subtitle').value = configData.subtitle;
      document.getElementById('cfg-author').value   = configData.author;
      if (!allTags) {
        const tagRes = await fetch('/api/prompt/tags');
        allTags = await tagRes.json();
      }
      renderCharacters(configData.characters);
    }

    // ── Status helpers ────────────────────────────────────────────────────────
    function getCharStatus(charId) {
      const prefix   = BOOK_NAME.split('-')[0];
      const filename = `${prefix}_${charId}.png`;
      if ((BOOK_DATA.suspicious || []).includes(filename)) {
        const detail = (BOOK_DATA.images_detail || []).find(d => d.file === filename);
        return { type: 'suspicious', label: `⚠ ${detail ? detail.size_kb : '?'} KB`, filename };
      }
      if ((BOOK_DATA.missing || []).includes(filename)) {
        return { type: 'missing', label: '❌ Missing', filename };
      }
      const detail = (BOOK_DATA.images_detail || []).find(d => d.file === filename);
      if (detail) return { type: 'ok', label: '✓ OK', filename };
      return { type: 'missing', label: '❌ Missing', filename };
    }

    function statusBadge(status) {
      const cls = {
        ok:         'bg-green-100 text-green-800',
        suspicious: 'bg-yellow-100 text-yellow-800',
        missing:    'bg-red-100 text-red-800',
      }[status.type] || 'bg-gray-100 text-gray-600';
      return `<span class="text-xs px-2 py-0.5 rounded-full ${cls}">${status.label}</span>`;
    }

    // ── Characters table ──────────────────────────────────────────────────────
    function renderCharacters(characters) {
      const tbody = document.getElementById('characters-tbody');
      tbody.innerHTML = '';
      characters.forEach((c, i) => tbody.appendChild(makeCharRow(c, i)));
      document.getElementById('char-count').textContent = `(${characters.length})`;
    }

    function makeCharRow(c, i) {
      const status   = getCharStatus(c.id);
      const isActive = activeSoloIndex === i && builderMode === 'solo';
      const tr       = document.createElement('tr');
      tr.className   = `hover:bg-gray-50 cursor-pointer${isActive ? ' bg-indigo-50 border-l-2 border-l-indigo-500' : ''}`;
      tr.onclick     = () => selectCharacter(i);
      tr.innerHTML   = `
        <td class="px-3 py-2 text-xs text-gray-400">${i + 1}</td>
        <td class="px-3 py-2">
          <input type="text" value="${esc(c.id)}" placeholder="id"
                 data-field="id" onclick="event.stopPropagation()"
                 class="w-full border border-gray-200 rounded px-1 py-0.5 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-indigo-400" />
        </td>
        <td class="px-3 py-2">
          <input type="text" value="${esc(c.name)}" placeholder="Nom"
                 data-field="name" onclick="event.stopPropagation()"
                 class="w-full border border-gray-200 rounded px-1 py-0.5 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-400" />
          <input type="hidden" value="${esc(c.series)}" data-field="series" />
          <input type="hidden" value="${esc(c.prompt)}" data-field="prompt" />
        </td>
        <td class="px-3 py-2 text-center">${statusBadge(status)}</td>
        <td class="px-3 py-2 text-center whitespace-nowrap">
          <button onclick="event.stopPropagation(); moveChar(${i}, -1)"
                  class="text-gray-400 hover:text-gray-700 px-0.5 text-xs">↑</button>
          <button onclick="event.stopPropagation(); moveChar(${i},  1)"
                  class="text-gray-400 hover:text-gray-700 px-0.5 text-xs">↓</button>
        </td>`;
      return tr;
    }

    function collectCharacters() {
      return Array.from(document.querySelectorAll('#characters-tbody tr')).map(tr => ({
        id:     tr.querySelector('[data-field="id"]').value.trim(),
        name:   tr.querySelector('[data-field="name"]').value.trim(),
        series: tr.querySelector('[data-field="series"]').value.trim(),
        prompt: tr.querySelector('[data-field="prompt"]').value.trim(),
      }));
    }

    function addCharacterRow() {
      const chars = collectCharacters();
      chars.push({ id: '', name: '', series: '', prompt: '' });
      renderCharacters(chars);
    }

    function deleteChar(i) {
      const chars = collectCharacters();
      chars.splice(i, 1);
      if (activeSoloIndex === i) {
        activeSoloIndex = null; builderMode = 'none'; showPanel('idle');
      } else if (activeSoloIndex !== null && activeSoloIndex > i) {
        activeSoloIndex--;
      }
      renderCharacters(chars);
    }

    function moveChar(i, dir) {
      const chars = collectCharacters();
      const j = i + dir;
      if (j < 0 || j >= chars.length) return;
      [chars[i], chars[j]] = [chars[j], chars[i]];
      if (activeSoloIndex === i) activeSoloIndex = j;
      else if (activeSoloIndex === j) activeSoloIndex = i;
      renderCharacters(chars);
    }

    // ── Panel management ──────────────────────────────────────────────────────
    function showPanel(mode) {
      document.getElementById('panel-idle').classList.toggle('hidden',  mode !== 'idle');
      document.getElementById('panel-solo').classList.toggle('hidden',  mode !== 'solo');
      document.getElementById('panel-group').classList.toggle('hidden', mode !== 'group');
    }

    // ── Solo panel ────────────────────────────────────────────────────────────
    function selectCharacter(i) {
      activeSoloIndex = i;
      builderMode     = 'solo';
      soloState       = { description: '', styleTags: [], poseTags: [], elementTags: [], themeTags: [], extraNotes: '' };
      renderCharacters(collectCharacters());
      renderSoloPanel(collectCharacters()[i]);
    }

    function renderSoloPanel(character) {
      showPanel('solo');
      const status   = getCharStatus(character.id);
      const prefix   = BOOK_NAME.split('-')[0];
      const filename = `${prefix}_${character.id}.png`;
      const imgHtml  = status.type !== 'missing'
        ? `<img src="/images/${BOOK_NAME}/${filename}" alt="${esc(character.name)}"
               class="w-full object-contain rounded-lg border border-gray-100"
               style="max-height:240px" />`
        : `<div class="flex items-center justify-center bg-gray-100 rounded-lg text-gray-400 text-sm"
               style="height:120px">❌ Image non générée</div>`;

      document.getElementById('panel-solo').innerHTML = `
        <div class="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <div>
            <p class="font-semibold text-sm">${esc(character.name || character.id)}</p>
            <p class="text-xs text-gray-400 font-mono">${esc(character.id)}</p>
          </div>
          <div class="flex gap-2">
            <button onclick="regenChar('${esc(character.id)}')"
                    class="text-xs bg-gray-100 text-gray-700 rounded-lg px-3 py-1.5 hover:bg-gray-200">
              🔄 Regen
            </button>
            <button onclick="deleteChar(${activeSoloIndex})"
                    class="text-xs bg-red-50 text-red-600 rounded-lg px-3 py-1.5 hover:bg-red-100">
              🗑 Delete
            </button>
          </div>
        </div>
        <div class="p-5 space-y-4">
          <div>${imgHtml}</div>
          <div>
            <label class="text-xs text-gray-500 block mb-1">Description physique <span class="text-gray-400">(sans noms de couleur)</span></label>
            <textarea id="pb-description" rows="3"
              placeholder="Ex: warrior with spiky hair, detailed armor with ornate patterns..."
              class="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs resize-y focus:outline-none focus:ring-2 focus:ring-indigo-500"
              oninput="soloState.description=this.value; updateSoloPreview()">${esc(soloState.description)}</textarea>
          </div>
          ${renderTagSection('Style', 'style', soloState.styleTags, 'styleTags')}
          ${renderTagSection('Pose', 'pose', soloState.poseTags, 'poseTags')}
          ${renderTagSection('Éléments', 'elements', soloState.elementTags, 'elementTags')}
          ${renderTagSection('Thème', 'theme', soloState.themeTags, 'themeTags')}
          <div>
            <label class="text-xs text-gray-500 block mb-1">Notes supplémentaires</label>
            <textarea id="pb-extra" rows="2" placeholder="Info additionnelle..."
              class="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs resize-y focus:outline-none focus:ring-2 focus:ring-indigo-500"
              oninput="soloState.extraNotes=this.value; updateSoloPreview()"></textarea>
          </div>
          <div class="bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-xs text-gray-500 flex gap-2">
            ⛔ <span>Zero shading · Zero gray fills · Zero gradients · Zero black fills</span>
          </div>
          <div>
            <label class="text-xs text-gray-500 block mb-1">Aperçu du prompt</label>
            <pre id="pb-preview" class="bg-gray-900 text-green-400 text-xs rounded-lg p-3 whitespace-pre-wrap break-words"
                 style="max-height:120px;overflow-y:auto;font-family:'Courier New',monospace;"></pre>
          </div>
          <button onclick="applySoloPrompt()"
                  class="w-full text-xs bg-indigo-600 text-white rounded-lg py-2 hover:bg-indigo-700">
            💾 Apply prompt
          </button>
        </div>`;

      attachTagListeners('solo');
      updateSoloPreview();
    }

    function regenChar(charId) {
      startStream(`/stream/generate/${BOOK_NAME}?char_id=${charId}`, `🔄 Regenerating ${charId}`);
    }

    // ── Tag helpers ───────────────────────────────────────────────────────────
    function renderTagSection(label, key, selectedTags, stateKey) {
      if (!allTags) return '';
      const pills = (allTags[key] || []).map(tag => {
        const active = selectedTags.includes(tag);
        return `<button type="button" data-tag="${esc(tag)}" data-key="${stateKey}"
          class="tag-pill px-2 py-1 text-xs rounded-full border transition-colors ${active
            ? 'bg-indigo-600 text-white border-indigo-600'
            : 'bg-white text-gray-600 border-gray-200 hover:border-indigo-400'}"
        >${esc(tag)}</button>`;
      }).join('');
      return `<div><label class="text-xs text-gray-500 block mb-1">${label}</label><div class="flex flex-wrap gap-1.5">${pills}</div></div>`;
    }

    function attachTagListeners(mode) {
      document.querySelectorAll('.tag-pill').forEach(btn => {
        btn.addEventListener('click', () => {
          const tag = btn.dataset.tag;
          const key = btn.dataset.key;
          if (mode === 'solo') {
            const idx = soloState[key].indexOf(tag);
            if (idx === -1) soloState[key].push(tag); else soloState[key].splice(idx, 1);
            renderSoloPanel(collectCharacters()[activeSoloIndex]);
          } else {
            const idx = groupState[key].indexOf(tag);
            if (idx === -1) groupState[key].push(tag); else groupState[key].splice(idx, 1);
            renderGroupPanel();
          }
        });
      });
    }

    function buildSoloPromptText() {
      const parts = [soloState.description.trim()];
      if (soloState.extraNotes.trim()) parts.push(soloState.extraNotes.trim());
      [...soloState.styleTags, ...soloState.poseTags,
       ...soloState.elementTags, ...soloState.themeTags].forEach(t => parts.push(t));
      return PROMPT_TEMPLATE.replace('{cp}', parts.filter(Boolean).join(', '));
    }

    function updateSoloPreview() {
      const el = document.getElementById('pb-preview');
      if (el) el.textContent = buildSoloPromptText();
    }

    function applySoloPrompt() {
      if (activeSoloIndex === null) return;
      const prompt = buildSoloPromptText();
      const row = document.querySelectorAll('#characters-tbody tr')[activeSoloIndex];
      if (row) row.querySelector('[data-field="prompt"]').value = prompt;
      showToast('✅ Prompt appliqué');
    }

    // ── Group panel ───────────────────────────────────────────────────────────
    function openGroupBuilder() {
      builderMode     = 'group';
      activeSoloIndex = null;
      groupState      = { charDescs: {}, charIds: [], styleTags: [], elementTags: [], themeTags: [], groupDynamic: '', extraNotes: '' };
      renderCharacters(collectCharacters());
      renderGroupPanel();
    }

    function renderGroupPanel() {
      showPanel('group');
      const chars = collectCharacters();

      const charCheckboxes = chars.map(c => {
        const checked  = groupState.charIds.includes(c.id);
        const descVal  = groupState.charDescs[c.id] || '';
        return `
          <div class="border border-gray-100 rounded-lg p-3 space-y-2">
            <label class="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" value="${esc(c.id)}" ${checked ? 'checked' : ''}
                onchange="toggleGroupChar('${esc(c.id)}', this.checked)"
                class="rounded text-indigo-600" />
              <span class="text-xs font-medium">${esc(c.name || c.id)}</span>
              <span class="text-xs text-gray-400 font-mono">${esc(c.id)}</span>
            </label>
            ${checked ? `<textarea rows="2" placeholder="Description physique pour cette page..."
              class="w-full border border-gray-200 rounded px-2 py-1 text-xs resize-none focus:outline-none focus:ring-1 focus:ring-indigo-400"
              oninput="groupState.charDescs['${esc(c.id)}']=this.value; updateGroupPreview()"
            >${esc(descVal)}</textarea>` : ''}
          </div>`;
      }).join('');

      const dynamicPills = (allTags?.group_dynamics || []).map(d => {
        const active = groupState.groupDynamic === d;
        return `<button type="button"
          onclick="groupState.groupDynamic = groupState.groupDynamic === '${esc(d)}' ? '' : '${esc(d)}'; renderGroupPanel()"
          class="px-2 py-1 text-xs rounded-full border transition-colors ${active
            ? 'bg-indigo-600 text-white border-indigo-600'
            : 'bg-white text-gray-600 border-gray-200 hover:border-indigo-400'}"
        >${esc(d)}</button>`;
      }).join('');

      document.getElementById('panel-group').innerHTML = `
        <div class="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <p class="font-semibold text-sm">Page de groupe</p>
          <button onclick="addGroupToSequence()"
            class="text-xs bg-green-600 text-white rounded-lg px-4 py-2 hover:bg-green-700">
            ➕ Ajouter à la liste
          </button>
        </div>
        <div class="p-5 space-y-4">
          <div>
            <label class="text-xs text-gray-500 block mb-2">Personnages <span class="text-gray-400">(2+)</span></label>
            <div class="space-y-2">${charCheckboxes}</div>
          </div>
          <div>
            <label class="text-xs text-gray-500 block mb-1">Dynamique de groupe</label>
            <div class="flex flex-wrap gap-1.5">${dynamicPills}</div>
          </div>
          ${renderTagSection('Style', 'style', groupState.styleTags, 'styleTags')}
          ${renderTagSection('Éléments', 'elements', groupState.elementTags, 'elementTags')}
          ${renderTagSection('Thème', 'theme', groupState.themeTags, 'themeTags')}
          <div>
            <label class="text-xs text-gray-500 block mb-1">Notes supplémentaires</label>
            <textarea rows="2" placeholder="Info additionnelle..."
              class="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs resize-y focus:outline-none focus:ring-2 focus:ring-indigo-500"
              oninput="groupState.extraNotes=this.value; updateGroupPreview()"></textarea>
          </div>
          <div class="bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-xs text-gray-500 flex gap-2">
            ⛔ <span>Zero shading · Zero gray fills · Zero gradients · Zero black fills</span>
          </div>
          <div>
            <label class="text-xs text-gray-500 block mb-1">Aperçu du prompt</label>
            <pre id="pb-group-preview" class="bg-gray-900 text-green-400 text-xs rounded-lg p-3 whitespace-pre-wrap break-words"
                 style="max-height:120px;overflow-y:auto;font-family:'Courier New',monospace;"></pre>
          </div>
        </div>`;

      attachTagListeners('group');
      updateGroupPreview();
    }

    function toggleGroupChar(id, checked) {
      if (checked) { if (!groupState.charIds.includes(id)) groupState.charIds.push(id); }
      else { groupState.charIds = groupState.charIds.filter(i => i !== id); delete groupState.charDescs[id]; }
      renderGroupPanel();
    }

    function buildGroupPromptText() {
      const descs = groupState.charIds.map(id => (groupState.charDescs[id] || '').trim()).filter(Boolean);
      if (!descs.length) return '(sélectionne des personnages avec descriptions)';
      const parts = [descs.join(' alongside ')];
      if (groupState.extraNotes.trim()) parts.push(groupState.extraNotes.trim());
      if (groupState.groupDynamic) parts.push(groupState.groupDynamic);
      [...groupState.styleTags, ...groupState.elementTags, ...groupState.themeTags].forEach(t => parts.push(t));
      return PROMPT_TEMPLATE.replace('{cp}', parts.filter(Boolean).join(', '));
    }

    function updateGroupPreview() {
      const el = document.getElementById('pb-group-preview');
      if (el) el.textContent = buildGroupPromptText();
    }

    function addGroupToSequence() {
      if (groupState.charIds.length < 2) { showToast('❌ Sélectionne au moins 2 personnages'); return; }
      const prompt = buildGroupPromptText();
      if (prompt.startsWith('(sélectionne')) { showToast('❌ Ajoute une description pour chaque personnage'); return; }
      const chars   = collectCharacters();
      const ids     = groupState.charIds.join('_');
      const groupId = `group_${ids}`;
      const names   = groupState.charIds.map(id => {
        const c = chars.find(ch => ch.id === id);
        return c ? (c.name || c.id) : id;
      });
      chars.push({ id: groupId, name: `Groupe: ${names.join(' + ')}`, series: '', prompt });
      renderCharacters(chars);
      showToast(`✅ Page de groupe ajoutée`);
      openGroupBuilder();
    }

    // ── Save config ───────────────────────────────────────────────────────────
    async function saveConfig(bookName) {
      const payload = {
        title:         document.getElementById('cfg-title').value.trim(),
        subtitle:      document.getElementById('cfg-subtitle').value.trim(),
        author:        document.getElementById('cfg-author').value.trim(),
        testpen:       configData.testpen,
        images_folder: configData.images_folder,
        characters:    collectCharacters(),
        // page_sequence intentionally omitted — auto-generated by backend
      };
      const res = await fetch(`/api/book/${bookName}/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (res.ok) { configData = null; showToast('✅ Config sauvegardée'); }
      else         { showToast('❌ Erreur lors de la sauvegarde'); }
    }

    // ── Streaming ─────────────────────────────────────────────────────────────
    let activeSource = null;

    function runAction(action, bookName) {
      const urls   = { generate: `/stream/generate/${bookName}`, clean: `/stream/clean/${bookName}`, assemble: `/stream/assemble/${bookName}` };
      const titles = { generate: `🤖 Generating — ${bookName}`, clean: `🔧 Fixing images — ${bookName}`, assemble: `📄 Building PDF — ${bookName}` };
      startStream(urls[action], titles[action]);
    }

    function startStream(url, title) {
      const wrapper = document.getElementById('console-wrapper');
      const output  = document.getElementById('console-output');
      const titleEl = document.getElementById('console-title');
      wrapper.classList.remove('hidden');
      output.textContent  = '';
      titleEl.textContent = title;
      wrapper.scrollIntoView({ behavior: 'smooth' });
      if (activeSource) activeSource.close();
      activeSource = new EventSource(url);
      activeSource.onmessage = (e) => {
        if (e.data === '[DONE]') {
          activeSource.close();
          output.textContent += '\n✅ Complete\n';
          setTimeout(() => location.reload(), 1500);
        } else {
          output.textContent += e.data + '\n';
        }
        output.scrollTop = output.scrollHeight;
      };
      activeSource.onerror = () => { output.textContent += '\n[Connection error]\n'; activeSource.close(); };
    }

    function closeConsole() {
      if (activeSource) { activeSource.close(); activeSource = null; }
      document.getElementById('console-wrapper').classList.add('hidden');
    }

    // ── Utilities ─────────────────────────────────────────────────────────────
    function showToast(msg) {
      const t = document.getElementById('toast');
      t.textContent = msg;
      t.classList.remove('hidden');
      setTimeout(() => t.classList.add('hidden'), 3000);
    }

    function esc(s) {
      return String(s)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    init();
  </script>
</body>
</html>
```

- [ ] **Step 2 : Démarrer le serveur et vérifier le rendu de base**

```bash
python3 dashboard/app.py &
sleep 2
```

Ouvrir `http://localhost:8000/book/book1-90s-legends` (ou tout livre existant).

Vérifier :
- Page unique sans onglets
- Header avec titre, auteur, 3 boutons (Generate All / Fix Images / Build PDF)
- Stats line avec compteurs
- Table à gauche avec personnages et badges status
- Panneau droit "Identité du livre" (idle)
- Console absent (hidden)

```bash
kill %1
```

- [ ] **Step 3 : Tester les interactions clés**

```bash
python3 dashboard/app.py &
sleep 2
```

1. Cliquer sur un personnage → panneau Solo s'ouvre avec image preview (ou placeholder ❌)
2. Taper une description → live preview se met à jour
3. Sélectionner des tags → pills actives + live preview mis à jour
4. "💾 Apply prompt" → toast "✅ Prompt appliqué"
5. "💾 Save Config" → toast "✅ Config sauvegardée"
6. "+ Groupe" → panneau Groupe s'ouvre
7. Cocher 2 personnages + descriptions → preview groupe mis à jour
8. "➕ Ajouter à la liste" → entrée groupe apparaît dans la table
9. "🤖 Generate All" → console de streaming s'ouvre en bas

```bash
kill %1
```

- [ ] **Step 4 : Vérifier que /images sert bien les PNG**

```bash
python3 dashboard/app.py &
sleep 2
# Remplacer book1_gojo par un fichier PNG existant dans images/
ls images/book1-90s-legends/ | head -3
curl -I http://localhost:8000/images/book1-90s-legends/<premier_fichier.png>
kill %1
```

Expected : `HTTP/1.1 200 OK` avec `content-type: image/png`

- [ ] **Step 5 : Commit**

```bash
git add dashboard/templates/book.html
git commit -m "feat: redesign book page — single view, image preview, prompt builder panel"
```
