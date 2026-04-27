# Prompt Builder v2 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter un panneau latéral structuré dans l'onglet Config du dashboard pour assembler des prompts Gemini en mode Solo (un personnage) et Groupe (N personnages ensemble).

**Architecture:** Le panneau latéral vit entièrement côté client (JS pur, Tailwind). Il lit les tags disponibles via un nouvel endpoint `/api/prompt/tags`. L'assemblage du prompt est dupliqué en JS (miroir du Python) pour le live preview temps réel — aucun appel réseau sur chaque keystroke. Le prompt assemblé final est écrit dans le champ `prompt` du personnage dans la table existante.

**Tech Stack:** Python (FastAPI), Jinja2, Tailwind CDN, Vanilla JS (ES2020), `pipeline/prompt.py` existant.

---

## File Map

| Fichier | Action | Responsabilité |
|---|---|---|
| `pipeline/prompt.py` | Modify | + THEME_TAGS, GROUP_DYNAMICS, update build_prompt(), add build_group_prompt() |
| `dashboard/app.py` | Modify | + endpoint GET /api/prompt/tags |
| `dashboard/templates/book.html` | Modify | Layout flex Config tab + panneau JS complet |

---

### Task 1 : Étendre pipeline/prompt.py

**Files:**
- Modify: `pipeline/prompt.py`

- [x] **Step 1 : Ajouter THEME_TAGS et GROUP_DYNAMICS**

Remplacer le contenu de `pipeline/prompt.py` par :

```python
"""
pipeline/prompt.py — Shared prompt assembly for Gemini image generation.

Used by both pipeline/generate.py (CLI) and dashboard/app.py (web).
"""

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

THEME_TAGS = [
    "Art Nouveau",
    "Mandala-infused",
    "Kawaii",
    "Geometric",
    "Baroque",
]

GROUP_DYNAMICS = [
    "back-to-back",
    "facing each other",
    "battle formation",
    "side by side",
    "walking together",
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
    theme_tags: list[str] | None = None,
    extra_notes: str = "",
) -> str:
    parts = [description]
    if extra_notes and extra_notes.strip():
        parts.append(extra_notes.strip())
    for tag_list in (style_tags, pose_tags, element_tags, theme_tags):
        if tag_list:
            parts.extend(tag_list)
    character_prompt = ", ".join(p.strip() for p in parts if p.strip())
    return _BASE_TEMPLATE.format(character_prompt=character_prompt)


def build_group_prompt(
    character_descriptions: list[str],
    style_tags: list[str] | None = None,
    element_tags: list[str] | None = None,
    theme_tags: list[str] | None = None,
    group_dynamic: str = "",
    extra_notes: str = "",
) -> str:
    desc = " alongside ".join(d.strip() for d in character_descriptions if d.strip())
    parts = [desc]
    if extra_notes and extra_notes.strip():
        parts.append(extra_notes.strip())
    if group_dynamic:
        parts.append(group_dynamic)
    for tag_list in (style_tags, element_tags, theme_tags):
        if tag_list:
            parts.extend(tag_list)
    character_prompt = ", ".join(p.strip() for p in parts if p.strip())
    return _BASE_TEMPLATE.format(character_prompt=character_prompt)
```

- [ ] **Step 2 : Vérifier que le CLI existant fonctionne encore**

```bash
python3 -c "from pipeline.prompt import build_prompt, build_group_prompt, THEME_TAGS, GROUP_DYNAMICS; print('OK', THEME_TAGS, GROUP_DYNAMICS)"
```

Expected : `OK ['Art Nouveau', 'Mandala-infused', 'Kawaii', 'Geometric', 'Baroque'] ['back-to-back', ...]`

- [x] **Step 3 : Commit**

```bash
git add pipeline/prompt.py
git commit -m "feat: add THEME_TAGS, GROUP_DYNAMICS, build_group_prompt to prompt.py"
```

---

### Task 2 : Ajouter /api/prompt/tags dans dashboard/app.py

**Files:**
- Modify: `dashboard/app.py:244` (après les Config API routes existantes)

- [x] **Step 1 : Ajouter l'import et l'endpoint**

Ajouter l'import en haut de `dashboard/app.py`, après la ligne `from pipeline.config_io import read_config, write_config` :

```python
from pipeline.prompt import STYLE_TAGS, POSE_TAGS, ELEMENT_TAGS, THEME_TAGS, GROUP_DYNAMICS
```

Puis ajouter l'endpoint dans la section `# ── Config API routes` (après la route `api_new_book`) :

```python
@app.get("/api/prompt/tags")
async def api_prompt_tags():
    return {
        "style": STYLE_TAGS,
        "pose": POSE_TAGS,
        "elements": ELEMENT_TAGS,
        "theme": THEME_TAGS,
        "group_dynamics": GROUP_DYNAMICS,
    }
```

- [x] **Step 2 : Démarrer le serveur et tester l'endpoint**

```bash
python3 dashboard/app.py &
sleep 2
curl http://localhost:8000/api/prompt/tags
```

Expected : JSON avec les 5 clés `style`, `pose`, `elements`, `theme`, `group_dynamics`.

```bash
kill %1
```

- [x] **Step 3 : Commit**

```bash
git add dashboard/app.py
git commit -m "feat: add GET /api/prompt/tags endpoint"
```

---

### Task 3 : Modifier le layout Config dans book.html

**Files:**
- Modify: `dashboard/templates/book.html`

- [ ] **Step 1 : Remplacer la section Config panel par le nouveau layout flex**

Dans `book.html`, localiser le bloc `<div id="panel-config" ...>` (ligne 171). Remplacer tout son contenu par le HTML suivant :

```html
<div id="panel-config" class="hidden">
<main class="max-w-6xl mx-auto px-6 py-8 space-y-8">

  <div id="toast" class="hidden fixed top-4 right-4 bg-gray-900 text-white text-sm px-4 py-2 rounded-lg shadow-lg z-50"></div>

  <!-- Identity -->
  <div class="bg-white border border-gray-200 rounded-xl p-6 space-y-4">
    <h2 class="font-semibold text-sm">Identité</h2>
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div>
        <label class="text-xs text-gray-500 block mb-1">Title</label>
        <input id="cfg-title" type="text" class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
      </div>
      <div>
        <label class="text-xs text-gray-500 block mb-1">Subtitle</label>
        <input id="cfg-subtitle" type="text" class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
      </div>
      <div>
        <label class="text-xs text-gray-500 block mb-1">Author (pen name)</label>
        <input id="cfg-author" type="text" class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
      </div>
    </div>
  </div>

  <!-- Characters + Prompt Builder (flex) -->
  <div class="flex gap-6 items-start">

    <!-- Left: Characters table -->
    <div class="w-2/5 bg-white border border-gray-200 rounded-xl overflow-hidden flex-shrink-0">
      <div class="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
        <h2 class="font-semibold text-sm">Personnages <span id="char-count" class="text-gray-400 font-normal"></span></h2>
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
              <th class="px-3 py-2 text-left">ID</th>
              <th class="px-3 py-2 text-left">Nom</th>
              <th class="px-3 py-2 text-center w-16">Ordre</th>
              <th class="px-3 py-2 text-center w-8"></th>
            </tr>
          </thead>
          <tbody id="characters-tbody" class="divide-y divide-gray-100"></tbody>
        </table>
      </div>
    </div>

    <!-- Right: Prompt Builder Panel -->
    <div class="flex-1 min-w-0">
      <div id="prompt-builder-panel" class="bg-white border border-gray-200 rounded-xl overflow-hidden">
        <div id="pb-empty" class="px-6 py-12 text-center text-sm text-gray-400">
          ← Sélectionne un personnage ou crée une page de groupe
        </div>
        <div id="pb-solo" class="hidden"></div>
        <div id="pb-group" class="hidden"></div>
      </div>
    </div>

  </div>

  <!-- PAGE_SEQUENCE -->
  <div class="bg-white border border-gray-200 rounded-xl overflow-hidden">
    <div class="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
      <h2 class="font-semibold text-sm">PAGE_SEQUENCE <span id="seq-count" class="text-gray-400 font-normal"></span></h2>
      <p class="text-xs text-gray-400">Ordre des pages dans le PDF</p>
    </div>
    <div id="sequence-list" class="divide-y divide-gray-100"></div>
  </div>

  <div class="flex justify-end">
    <button onclick="saveConfig('{{ book_name }}')"
            class="bg-gray-900 text-white text-sm rounded-lg px-6 py-2.5 hover:bg-gray-700 transition-colors">
      💾 Save Config
    </button>
  </div>
</main>
</div>
```

- [ ] **Step 2 : Mettre à jour makeCharRow() pour le nouveau format simplifié**

La table n'affiche plus le textarea prompt. Remplacer la fonction `makeCharRow` dans le `<script>` par :

```javascript
function makeCharRow(c, i) {
  const tr = document.createElement('tr');
  tr.className = 'hover:bg-gray-50 cursor-pointer' + (activeSoloIndex === i ? ' bg-indigo-50' : '');
  tr.dataset.index = i;
  tr.onclick = () => selectCharacter(i);
  tr.innerHTML = `
    <td class="px-3 py-2">
      <input type="text" value="${esc(c.id)}" placeholder="gojo"
             class="w-full border border-gray-200 rounded px-2 py-1 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-indigo-400"
             data-field="id" onclick="event.stopPropagation()" />
    </td>
    <td class="px-3 py-2">
      <input type="text" value="${esc(c.name)}" placeholder="The Hero"
             class="w-full border border-gray-200 rounded px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-400"
             data-field="name" onclick="event.stopPropagation()" />
      <input type="hidden" value="${esc(c.series)}" data-field="series" />
      <input type="hidden" value="${esc(c.prompt)}" data-field="prompt" />
    </td>
    <td class="px-3 py-2 text-center whitespace-nowrap">
      <button onclick="event.stopPropagation(); moveChar(${i}, -1)" class="text-gray-400 hover:text-gray-700 px-1">↑</button>
      <button onclick="event.stopPropagation(); moveChar(${i},  1)" class="text-gray-400 hover:text-gray-700 px-1">↓</button>
    </td>
    <td class="px-3 py-2 text-center">
      <button onclick="event.stopPropagation(); deleteChar(${i})" class="text-red-400 hover:text-red-600 text-xs">🗑</button>
    </td>`;
  return tr;
}
```

Note : `series` et `prompt` sont des `input[type=hidden]` pour être collectés par `collectCharacters()` sans être visibles.

- [ ] **Step 3 : Mettre à jour collectCharacters() pour lire les champs cachés**

```javascript
function collectCharacters() {
  const rows = document.querySelectorAll('#characters-tbody tr');
  return Array.from(rows).map(tr => ({
    id:     tr.querySelector('[data-field="id"]').value.trim(),
    name:   tr.querySelector('[data-field="name"]').value.trim(),
    series: tr.querySelector('[data-field="series"]').value.trim(),
    prompt: tr.querySelector('[data-field="prompt"]').value.trim(),
  }));
}
```

- [ ] **Step 4 : Démarrer le serveur, ouvrir http://localhost:8000, naviguer vers un livre, onglet Config**

Vérifier :
- Layout flex visible : table à gauche, panneau vide "← Sélectionne un personnage" à droite
- Les personnages sont listés dans la table (ID + Nom)
- Le bouton "+ Perso" fonctionne
- Le bouton "+ Groupe" est présent

- [ ] **Step 5 : Commit**

```bash
git add dashboard/templates/book.html
git commit -m "feat: restructure Config tab with flex layout and prompt builder panel placeholder"
```

---

### Task 4 : Implémenter le Mode Solo dans le panneau

**Files:**
- Modify: `dashboard/templates/book.html` (section `<script>`)

- [ ] **Step 1 : Ajouter les variables d'état et le template prompt en JS**

Ajouter en haut du bloc `<script>` (après `const BOOK_NAME = ...`) :

```javascript
// ── Prompt Builder state ────────────────────────────────────────────────────
let allTags = null;
let builderMode = 'none'; // 'none' | 'solo' | 'group'
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
```

- [ ] **Step 2 : Charger les tags au loadConfig()**

Dans la fonction `loadConfig()` existante, ajouter à la fin :

```javascript
if (!allTags) {
  const tagRes = await fetch('/api/prompt/tags');
  allTags = await tagRes.json();
}
```

- [ ] **Step 3 : Ajouter la fonction selectCharacter()**

```javascript
function selectCharacter(i) {
  activeSoloIndex = i;
  builderMode = 'solo';
  const chars = collectCharacters();
  const c = chars[i];
  soloState = {
    description: '',
    styleTags: [], poseTags: [], elementTags: [], themeTags: [],
    extraNotes: ''
  };
  renderCharacters(chars); // rafraîchit le highlight
  renderSoloPanel(c);
}
```

- [ ] **Step 4 : Ajouter renderSoloPanel()**

```javascript
function renderSoloPanel(character) {
  document.getElementById('pb-empty').classList.add('hidden');
  document.getElementById('pb-group').classList.add('hidden');
  const panel = document.getElementById('pb-solo');
  panel.classList.remove('hidden');

  panel.innerHTML = `
    <div class="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
      <div>
        <p class="font-semibold text-sm">${esc(character.name || character.id)}</p>
        <p class="text-xs text-gray-400">${esc(character.id)}</p>
      </div>
      <button onclick="applySoloPrompt()" class="text-xs bg-indigo-600 text-white rounded-lg px-4 py-2 hover:bg-indigo-700">
        💾 Apply
      </button>
    </div>

    <div class="p-5 space-y-4">

      <div>
        <label class="text-xs text-gray-500 block mb-1">Description physique <span class="text-gray-400">(sans noms de couleur)</span></label>
        <textarea id="pb-description" rows="3" placeholder="Ex: warrior with spiky hair, detailed armor, long cape with ornate patterns..."
          class="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs resize-y focus:outline-none focus:ring-2 focus:ring-indigo-500"
          oninput="soloState.description=this.value; updateSoloPreview()">${esc(soloState.description)}</textarea>
      </div>

      ${renderTagSection('Style', 'style', soloState.styleTags, 'styleTags')}
      ${renderTagSection('Pose', 'pose', soloState.poseTags, 'poseTags')}
      ${renderTagSection('Éléments', 'elements', soloState.elementTags, 'elementTags')}
      ${renderTagSection('Thème', 'theme', soloState.themeTags, 'themeTags')}

      <div>
        <label class="text-xs text-gray-500 block mb-1">Notes supplémentaires</label>
        <textarea id="pb-extra" rows="2" placeholder="Toute info additionnelle..."
          class="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs resize-y focus:outline-none focus:ring-2 focus:ring-indigo-500"
          oninput="soloState.extraNotes=this.value; updateSoloPreview()"></textarea>
      </div>

      <div class="bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-xs text-gray-500 flex items-center gap-2">
        ⛔ <span>Zero shading · Zero gray fills · Zero gradients · Zero black fills</span>
      </div>

      <div>
        <label class="text-xs text-gray-500 block mb-1">Aperçu du prompt</label>
        <pre id="pb-preview" class="bg-gray-900 text-green-400 text-xs rounded-lg p-3 whitespace-pre-wrap break-words" style="max-height:160px;overflow-y:auto;font-family:'Courier New',monospace;"></pre>
      </div>

    </div>`;

  attachTagListeners('solo');
  updateSoloPreview();
}
```

- [ ] **Step 5 : Ajouter renderTagSection() et attachTagListeners()**

```javascript
function renderTagSection(label, key, selectedTags, stateKey) {
  if (!allTags) return '';
  const tags = allTags[key] || [];
  const pills = tags.map(tag => {
    const active = selectedTags.includes(tag);
    return `<button type="button"
      data-tag="${esc(tag)}" data-key="${stateKey}"
      class="tag-pill px-2 py-1 text-xs rounded-full border transition-colors ${active
        ? 'bg-indigo-600 text-white border-indigo-600'
        : 'bg-white text-gray-600 border-gray-200 hover:border-indigo-400'}"
    >${esc(tag)}</button>`;
  }).join('');
  return `
    <div>
      <label class="text-xs text-gray-500 block mb-1">${label}</label>
      <div class="flex flex-wrap gap-1.5">${pills}</div>
    </div>`;
}

function attachTagListeners(mode) {
  document.querySelectorAll('.tag-pill').forEach(btn => {
    btn.addEventListener('click', () => {
      const tag = btn.dataset.tag;
      const key = btn.dataset.key; // 'styleTags', 'poseTags', etc.
      if (mode === 'solo') {
        const idx = soloState[key].indexOf(tag);
        if (idx === -1) soloState[key].push(tag);
        else soloState[key].splice(idx, 1);
        renderSoloPanel(collectCharacters()[activeSoloIndex]);
      } else {
        const idx = groupState[key].indexOf(tag);
        if (idx === -1) groupState[key].push(tag);
        else groupState[key].splice(idx, 1);
        renderGroupPanel();
      }
    });
  });
}
```

- [ ] **Step 6 : Ajouter updateSoloPreview() et applySoloPrompt()**

```javascript
function buildSoloPromptText() {
  const parts = [soloState.description.trim()];
  if (soloState.extraNotes.trim()) parts.push(soloState.extraNotes.trim());
  [...soloState.styleTags, ...soloState.poseTags,
   ...soloState.elementTags, ...soloState.themeTags].forEach(t => parts.push(t));
  const cp = parts.filter(Boolean).join(', ');
  return PROMPT_TEMPLATE.replace('{cp}', cp);
}

function updateSoloPreview() {
  const el = document.getElementById('pb-preview');
  if (el) el.textContent = buildSoloPromptText();
}

function applySoloPrompt() {
  if (activeSoloIndex === null) return;
  const prompt = buildSoloPromptText();
  const rows = document.querySelectorAll('#characters-tbody tr');
  const row = rows[activeSoloIndex];
  if (row) {
    row.querySelector('[data-field="prompt"]').value = prompt;
  }
  showToast('✅ Prompt appliqué au personnage');
}
```

- [ ] **Step 7 : Tester en navigateur**

1. Démarrer : `python3 dashboard/app.py`
2. Ouvrir `http://localhost:8000/book/<slug>` → onglet Config
3. Cliquer sur un personnage → panneau Solo s'ouvre à droite
4. Taper une description → live preview se met à jour
5. Sélectionner des tags → live preview se met à jour
6. Cliquer "Apply" → toast "✅ Prompt appliqué"
7. Cliquer "Save Config" → vérifier que le config.py est mis à jour avec le nouveau prompt

- [ ] **Step 8 : Commit**

```bash
git add dashboard/templates/book.html
git commit -m "feat: implement solo prompt builder panel with live preview"
```

---

### Task 5 : Implémenter le Mode Groupe dans le panneau

**Files:**
- Modify: `dashboard/templates/book.html` (section `<script>`)

- [ ] **Step 1 : Ajouter l'état groupe**

Ajouter après `soloState = { ... }` :

```javascript
let groupState = {
  charDescs: {},   // { charId: description string }
  charIds: [],     // IDs sélectionnés, dans l'ordre
  styleTags: [], elementTags: [], themeTags: [],
  groupDynamic: '',
  extraNotes: ''
};
```

- [ ] **Step 2 : Ajouter openGroupBuilder()**

```javascript
function openGroupBuilder() {
  builderMode = 'group';
  activeSoloIndex = null;
  groupState = { charDescs: {}, charIds: [], styleTags: [], elementTags: [], themeTags: [], groupDynamic: '', extraNotes: '' };
  const chars = collectCharacters();
  renderCharacters(chars);
  renderGroupPanel();
}
```

- [ ] **Step 3 : Ajouter renderGroupPanel()**

```javascript
function renderGroupPanel() {
  document.getElementById('pb-empty').classList.add('hidden');
  document.getElementById('pb-solo').classList.add('hidden');
  const panel = document.getElementById('pb-group');
  panel.classList.remove('hidden');

  const chars = collectCharacters();

  const charCheckboxes = chars.map(c => {
    const checked = groupState.charIds.includes(c.id);
    const descVal = groupState.charDescs[c.id] || '';
    return `
      <div class="border border-gray-100 rounded-lg p-3 space-y-2">
        <label class="flex items-center gap-2 cursor-pointer">
          <input type="checkbox" value="${esc(c.id)}" ${checked ? 'checked' : ''}
            onchange="toggleGroupChar('${esc(c.id)}', this.checked)"
            class="rounded text-indigo-600" />
          <span class="text-xs font-medium">${esc(c.name || c.id)}</span>
          <span class="text-xs text-gray-400">${esc(c.id)}</span>
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

  panel.innerHTML = `
    <div class="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
      <p class="font-semibold text-sm">Page de groupe</p>
      <button onclick="addGroupToSequence()"
        class="text-xs bg-green-600 text-white rounded-lg px-4 py-2 hover:bg-green-700">
        + Ajouter à PAGE_SEQUENCE
      </button>
    </div>

    <div class="p-5 space-y-4">

      <div>
        <label class="text-xs text-gray-500 block mb-2">Personnages <span class="text-gray-400">(sélectionner 2+)</span></label>
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
        <textarea id="pb-group-extra" rows="2" placeholder="Toute info additionnelle..."
          class="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs resize-y focus:outline-none focus:ring-2 focus:ring-indigo-500"
          oninput="groupState.extraNotes=this.value; updateGroupPreview()">${esc(groupState.extraNotes)}</textarea>
      </div>

      <div class="bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-xs text-gray-500 flex items-center gap-2">
        ⛔ <span>Zero shading · Zero gray fills · Zero gradients · Zero black fills</span>
      </div>

      <div>
        <label class="text-xs text-gray-500 block mb-1">Aperçu du prompt</label>
        <pre id="pb-group-preview" class="bg-gray-900 text-green-400 text-xs rounded-lg p-3 whitespace-pre-wrap break-words" style="max-height:160px;overflow-y:auto;font-family:'Courier New',monospace;"></pre>
      </div>

    </div>`;

  attachTagListeners('group');
  updateGroupPreview();
}
```

- [ ] **Step 4 : Ajouter toggleGroupChar(), buildGroupPromptText(), updateGroupPreview(), addGroupToSequence()**

```javascript
function toggleGroupChar(id, checked) {
  if (checked) {
    if (!groupState.charIds.includes(id)) groupState.charIds.push(id);
  } else {
    groupState.charIds = groupState.charIds.filter(i => i !== id);
    delete groupState.charDescs[id];
  }
  renderGroupPanel();
}

function buildGroupPromptText() {
  const descs = groupState.charIds
    .map(id => (groupState.charDescs[id] || '').trim())
    .filter(Boolean);
  if (descs.length === 0) return '(sélectionne des personnages avec descriptions)';
  const desc = descs.join(' alongside ');
  const parts = [desc];
  if (groupState.extraNotes.trim()) parts.push(groupState.extraNotes.trim());
  if (groupState.groupDynamic) parts.push(groupState.groupDynamic);
  [...groupState.styleTags, ...groupState.elementTags, ...groupState.themeTags].forEach(t => parts.push(t));
  const cp = parts.filter(Boolean).join(', ');
  return PROMPT_TEMPLATE.replace('{cp}', cp);
}

function updateGroupPreview() {
  const el = document.getElementById('pb-group-preview');
  if (el) el.textContent = buildGroupPromptText();
}

function addGroupToSequence() {
  if (groupState.charIds.length < 2) {
    showToast('❌ Sélectionne au moins 2 personnages');
    return;
  }
  const prompt = buildGroupPromptText();
  if (prompt.startsWith('(sélectionne')) {
    showToast('❌ Ajoute une description pour chaque personnage sélectionné');
    return;
  }
  const ids = groupState.charIds.join('_');
  const groupId = `group_${ids}`;
  const chars = collectCharacters();
  const names = groupState.charIds.map(id => {
    const c = chars.find(ch => ch.id === id);
    return c ? (c.name || c.id) : id;
  });
  const label = names.join(' + ');
  const filename = `${BOOK_NAME.replace(/-/g, '')}_${groupId}.png`;

  // Ajouter dans CHARACTERS (entrée groupe)
  chars.push({ id: groupId, name: `Groupe: ${label}`, series: '', prompt });
  renderCharacters(chars);

  // Ajouter dans PAGE_SEQUENCE
  const seq = collectSequence();
  seq.push({ file: filename, label });
  renderSequence(seq);

  showToast(`✅ Page de groupe "${label}" ajoutée`);
  openGroupBuilder(); // reset
}
```

- [ ] **Step 5 : Tester en navigateur**

1. Démarrer : `python3 dashboard/app.py`
2. Ouvrir un livre → onglet Config
3. Cliquer "+ Groupe" → panneau Groupe s'ouvre
4. Cocher 2+ personnages → textarea de description s'affiche pour chacun
5. Taper des descriptions, sélectionner "back-to-back", des tags
6. Live preview se met à jour correctement
7. Cliquer "+ Ajouter à PAGE_SEQUENCE" → entrée groupe apparaît dans la table Characters ET dans PAGE_SEQUENCE
8. "Save Config" → vérifier dans `books/<slug>/config.py` que le CHARACTERS et PAGE_SEQUENCE sont mis à jour

- [ ] **Step 6 : Commit**

```bash
git add dashboard/templates/book.html
git commit -m "feat: implement group prompt builder panel with multi-character support"
```
