with open("dashboard/templates/new_book.html", "r") as f:
    html = f.read()

# 1. Add Category selector right after "Étape 1" header
html = html.replace(
'''    <div class="bg-white border border-gray-200 rounded-xl p-6 space-y-4">
      <h2 class="font-semibold text-sm">Étape 1 — Identité</h2>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">''',
'''    <div class="bg-white border border-gray-200 rounded-xl p-6 space-y-6">
      <div>
        <h2 class="font-semibold text-sm mb-3">Catégorie du Livre</h2>
        <div class="flex gap-4">
          <label class="flex items-center gap-2 cursor-pointer">
            <input type="radio" name="category" value="coloring" checked onchange="toggleCategory()" class="text-indigo-600 focus:ring-indigo-500" />
            <span class="text-sm">Coloring Book (Tableau de personnages)</span>
          </label>
          <label class="flex items-center gap-2 cursor-pointer">
            <input type="radio" name="category" value="story" onchange="toggleCategory()" class="text-indigo-600 focus:ring-indigo-500" />
            <span class="text-sm">Story Book (Script / Histoire)</span>
          </label>
        </div>
      </div>

      <div class="border-t border-gray-100"></div>

      <h2 class="font-semibold text-sm mt-4">Étape 1 — Identité</h2>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">'''
)

# 2. Add Story script mode UI, hide Characters table if Story is selected
html = html.replace(
'''    <div class="bg-white border border-gray-200 rounded-xl overflow-hidden">
      <div class="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
        <h2 class="font-semibold text-sm">Étape 2 — Personnages <span id="new-char-count" class="text-gray-400 font-normal">(0)</span></h2>''',
'''    <div id="coloring-mode" class="bg-white border border-gray-200 rounded-xl overflow-hidden">
      <div class="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
        <h2 class="font-semibold text-sm">Étape 2 — Personnages <span id="new-char-count" class="text-gray-400 font-normal">(0)</span></h2>'''
)

html = html.replace(
'''      <button onclick="createBook()"
              class="bg-gray-900 text-white text-sm rounded-lg px-6 py-2.5 hover:bg-gray-700 transition-colors">
        ✅ Create Book
      </button>
    </div>

  </main>''',
'''    <div id="story-mode" class="bg-white border border-gray-200 rounded-xl p-6 hidden">
      <h2 class="font-semibold text-sm mb-2">Étape 2 — Quick Mode : Script ("Stories")</h2>
      <p class="text-xs text-gray-500 mb-4">
        Collez ici votre script brut. L'IA va créer la "Charte Graphique" globale et diviser l'histoire page par page
        avec des prompts de génération d'images, puis traduire vos textes en FR/AR/EN/ES.
      </p>
      <textarea id="story-script" rows="15" placeholder="Collez le texte brut de l'histoire ici... (Exemple Joudia)" 
                class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-y"></textarea>
    </div>

    <div class="flex justify-end gap-3">
      <a href="/" class="border border-gray-200 text-sm rounded-lg px-4 py-2 hover:bg-gray-50 transition-colors">
        Annuler
      </a>
      <button id="btn-create" onclick="createBook()"
              class="bg-gray-900 text-white text-sm rounded-lg px-6 py-2.5 hover:bg-gray-700 transition-colors flex items-center justify-center min-w-[140px]">
        <span>✅ Create Book</span>
      </button>
    </div>

  </main>'''
)

# 3. Update JS Logic
html = html.replace(
'''    async function createBook() {
      const slug     = document.getElementById('new-slug').value.trim();
      const title    = document.getElementById('new-title').value.trim();
      const subtitle = document.getElementById('new-subtitle').value.trim();
      const author   = document.getElementById('new-author').value.trim();''',
'''    function toggleCategory() {
      const mode = document.querySelector('input[name="category"]:checked').value;
      if (mode === "coloring") {
        document.getElementById("coloring-mode").classList.remove("hidden");
        document.getElementById("story-mode").classList.add("hidden");
      } else {
        document.getElementById("coloring-mode").classList.add("hidden");
        document.getElementById("story-mode").classList.remove("hidden");
      }
    }

    async function createBook() {
      const btn = document.getElementById('btn-create');
      const category = document.querySelector('input[name="category"]:checked').value;
      const slug     = document.getElementById('new-slug').value.trim();
      const title    = document.getElementById('new-title').value.trim();
      const subtitle = document.getElementById('new-subtitle').value.trim();
      const author   = document.getElementById('new-author').value.trim();
      const story_script = document.getElementById('story-script').value.trim();'''
)

html = html.replace(
'''      const res = await fetch('/api/books/new', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ slug, title, subtitle, author, characters: newChars }),
      });''',
'''      
      btn.innerHTML = `<svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> Génération (10s)...`;
      btn.disabled = true;
      btn.classList.add("opacity-75", "cursor-not-allowed");

      try {
          const res = await fetch('/api/books/new', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ category, slug, title, subtitle, author, characters: newChars, story_script }),
          });'''
)

html = html.replace(
'''      if (res.ok) {
        const data = await res.json();
        window.location.href = `/book/${data.slug}`;
      } else {
        const err = await res.json();
        showToast(`❌ ${err.detail || 'Erreur lors de la création'}`);
      }
    }''',
'''      if (res.ok) {
        const data = await res.json();
        window.location.href = `/book/${data.slug}`;
      } else {
        const err = await res.json();
        showToast(`❌ ${err.detail || 'Erreur lors de la création'}`);
      }
      } finally {
        btn.innerHTML = "<span>✅ Create Book</span>";
        btn.disabled = false;
        btn.classList.remove("opacity-75", "cursor-not-allowed");
      }
    }'''
)

with open("dashboard/templates/new_book.html", "w") as f:
    f.write(html)
