import sys

with open('dashboard/templates/book.html', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. State Variables
state_vars = """    // ── Prompt Builder state ────────────────────────────────────────────────────
    let allTags = null;
    let builderMode = 'none'; // 'none' | 'solo' | 'group'
    window.activeSoloIndex = null;

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
      charDescs: {},   // { charId: description string }
      charIds: [],     // IDs sélectionnés, dans l'ordre
      styleTags: [], elementTags: [], themeTags: [],
      groupDynamic: '',
      extraNotes: ''
    };
"""
text = text.replace("let configData = null;", "let configData = null;\n" + state_vars)

# 2. Add API fetch to loadConfig
tag_loader = """      renderSequence(configData.page_sequence);
      if (!allTags) {
        const tagRes = await fetch('/api/prompt/tags');
        allTags = await tagRes.json();
      }"""
text = text.replace("renderSequence(configData.page_sequence);", tag_loader)

# 3. Add all new functions before // ── Startup 
# In this file, // ── Startup doesn't seem to exist. Let's find loadConfig and insert there.
fns = """    // ── Prompt Builder System ────────────────────────────────────────────────────

    function selectCharacter(i) {
      window.activeSoloIndex = i;
      builderMode = 'solo';
      const chars = collectCharacters();
      const c = chars[i];
      soloState = {
        description: c.prompt || '',
        styleTags: [], poseTags: [], elementTags: [], themeTags: [],
        extraNotes: ''
      };
      renderCharacters(chars); // rafraîchit le highlight
      renderSoloPanel(c);
    }

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
            renderSoloPanel(collectCharacters()[window.activeSoloIndex]);
          } else {
            const idx = groupState[key].indexOf(tag);
            if (idx === -1) groupState[key].push(tag);
            else groupState[key].splice(idx, 1);
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
      const cp = parts.filter(Boolean).join(', ');
      return PROMPT_TEMPLATE.replace('{cp}', cp);
    }

    function updateSoloPreview() {
      const el = document.getElementById('pb-preview');
      if (el) el.textContent = buildSoloPromptText();
    }

    function applySoloPrompt() {
      if (window.activeSoloIndex === null) return;
      const prompt = buildSoloPromptText();
      const rows = document.querySelectorAll('#characters-tbody tr');
      const row = rows[window.activeSoloIndex];
      if (row) {
        row.querySelector('[data-field="prompt"]').value = prompt;
      }
      showToast('✅ Prompt appliqué au personnage');
    }

    function openGroupBuilder() {
      builderMode = 'group';
      window.activeSoloIndex = null;
      groupState = { charDescs: {}, charIds: [], styleTags: [], elementTags: [], themeTags: [], groupDynamic: '', extraNotes: '' };
      const chars = collectCharacters();
      renderCharacters(chars);
      renderGroupPanel();
    }

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
      let sanitizedBookName = BOOK_NAME;
      if (typeof sanitizedBookName === 'string') {
          sanitizedBookName = sanitizedBookName.replace(/-/g, '');
      }
      const filename = `${sanitizedBookName}_${groupId}.png`;

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

"""
text = text.replace("async function loadConfig()", fns + "\n    async function loadConfig()")


with open('dashboard/templates/book.html', 'w', encoding='utf-8') as f:
    f.write(text)

print("JS Patched")
