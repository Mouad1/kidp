import urllib.request
import json
import os

html_content = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{{ book.title }} — Story Editor</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    .page-item { transition: all 0.2s; cursor: pointer; }
    .page-item.active { border-left-color: #6366f1; background: #eef2ff; }
    .col-scroll { overflow-y: auto; max-height: calc(100vh - 180px); }
  </style>
</head>
<body class="bg-gray-50 text-gray-900 min-h-screen flex flex-col h-screen">

  <!-- Header -->
  <header class="bg-white border-b border-gray-200 px-6 py-3 shrink-0">
    <div class="max-w-screen-2xl mx-auto flex items-center justify-between">
      <div class="flex items-center gap-4">
        <a href="/" class="text-gray-400 hover:text-gray-700 text-sm font-medium">← Dashboard</a>
        <div>
          <h1 class="text-base font-bold">{{ book.title }} <span class="bg-blue-100 text-blue-800 text-[10px] uppercase px-2 py-0.5 rounded-full ml-2">Story Edition</span></h1>
          <p class="text-xs text-gray-400">Book: {{ book_name }}</p>
        </div>
      </div>
      <div class="flex gap-2">
        <button onclick="runAssemble()" class="px-4 py-2 text-sm font-semibold text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50">
          ⚙️ Assembler PDF
        </button>
        <button onclick="runGenerate()" class="px-4 py-2 text-sm font-semibold text-white bg-indigo-600 rounded-lg outline-none hover:bg-indigo-700">
          🎨 Générer les images ({{ book.in_sequence }} pages)
        </button>
      </div>
    </div>
  </header>

  <!-- Main Workspace -->
  <main class="flex-1 max-w-screen-2xl mx-auto w-full p-6 grid md:grid-cols-[280px_1fr_400px] gap-6 items-start overflow-hidden">
    
    <!-- COL 1: Pages & Global Config -->
    <div class="flex flex-col gap-4 h-full">
      <div class="bg-white border border-gray-200 rounded-xl overflow-hidden flex flex-col h-full shadow-sm">
        
        <div class="p-4 border-b border-gray-100 shrink-0">
           <h2 class="font-semibold text-sm">Sommaire & Pages</h2>
        </div>

        <div id="pages-list" class="flex-1 col-scroll divide-y divide-gray-100 bg-gray-50">
          <!-- Populated by JS -->
        </div>
        
        <div class="p-4 border-t border-gray-200 shrink-0">
           <button onclick="addPage()" class="w-full text-xs font-semibold text-indigo-700 bg-indigo-50 py-2 rounded-lg hover:bg-indigo-100">
             + Ajouter une Page
           </button>
        </div>
      </div>
    </div>

    <!-- COL 2: Page Editor -->
    <div class="bg-white border border-gray-200 rounded-xl shadow-sm h-full flex flex-col overflow-hidden">
      
      <!-- Idle State -->
      <div id="editor-idle" class="flex-1 flex flex-col items-center justify-center text-gray-400 p-8">
        <span class="text-4xl mb-4">📖</span>
        <p class="text-sm">Sélectionnez une page à gauche ou éditez les infos globales à droite.</p>
      </div>

      <!-- Edit Page -->
      <div id="editor-active" class="hidden flex flex-col h-full">
        <div class="px-6 py-4 border-b border-gray-200 flex justify-between items-center shrink-0 bg-gray-50">
          <h3 class="font-bold text-gray-800" id="editor-title">Page X</h3>
          <button onclick="deleteCurrentPage()" class="text-red-500 hover:text-red-700 text-xs font-semibold bg-red-50 px-3 py-1.5 rounded-lg">Supprimer</button>
        </div>

        <div class="p-6 overflow-y-auto flex-1 space-y-6">
           <div>
             <label class="block text-xs font-bold text-gray-500 uppercase mb-2">Prompt Image (Gemini -> Imagen)</label>
             <textarea id="page-image-prompt" rows="3" class="w-full text-sm border-gray-300 rounded-lg p-3 border focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 shadow-sm" placeholder="A cozy cabin in the woods..."></textarea>
           </div>
           
           <div>
             <label class="block text-xs font-bold text-gray-500 uppercase mb-2">Morale / Valeur</label>
             <input type="text" id="page-moral" class="w-full border-gray-300 border text-sm rounded-lg p-3 shadow-sm focus:ring-indigo-500 focus:border-indigo-500" />
           </div>

           <div class="grid grid-cols-2 gap-4">
             <div>
               <label class="block text-xs font-bold text-gray-500 uppercase mb-2">Texte (FR)</label>
               <textarea id="page-text-fr" rows="4" class="w-full text-sm border-gray-300 border rounded-lg p-3 shadow-sm focus:ring-indigo-500 focus:border-indigo-500"></textarea>
             </div>
             <div>
               <label class="block text-xs font-bold text-gray-500 uppercase mb-2">Text (EN)</label>
               <textarea id="page-text-en" rows="4" class="w-full text-sm border-gray-300 border rounded-lg p-3 shadow-sm focus:ring-indigo-500 focus:border-indigo-500"></textarea>
             </div>
             <div>
               <label class="block text-xs font-bold text-gray-500 uppercase mb-2">Texto (ES)</label>
               <textarea id="page-text-es" rows="4" class="w-full text-sm border-gray-300 border rounded-lg p-3 shadow-sm focus:ring-indigo-500 focus:border-indigo-500"></textarea>
             </div>
             <div>
               <label class="block text-xs font-bold text-gray-500 uppercase mb-2">Text (AR)</label>
               <textarea id="page-text-ar" rows="4" class="w-full text-sm border-gray-300 border rounded-lg p-3 shadow-sm focus:ring-indigo-500 focus:border-indigo-500" dir="rtl"></textarea>
             </div>
           </div>
        </div>
      </div>

    </div>

    <!-- COL 3: Global Book Config -->
    <div class="bg-white border border-gray-200 rounded-xl shadow-sm col-scroll p-5 space-y-6">
      
      <div>
         <h3 class="font-bold text-sm border-b pb-2 mb-4">Informations du Livre</h3>
         <div class="space-y-4">
            <div>
              <label class="text-xs text-gray-500 block mb-1">Titre</label>
              <input type="text" id="cfg-title" class="w-full border rounded-lg px-3 py-2 text-sm focus:border-indigo-500 focus:ring-indigo-500" />
            </div>
            <div>
              <label class="text-xs text-gray-500 block mb-1">Sous-Titre</label>
              <input type="text" id="cfg-subtitle" class="w-full border rounded-lg px-3 py-2 text-sm focus:border-indigo-500 focus:ring-indigo-500" />
            </div>
            <div>
              <label class="text-xs text-gray-500 block mb-1">Auteur</label>
              <input type="text" id="cfg-author" class="w-full border rounded-lg px-3 py-2 text-sm focus:border-indigo-500 focus:ring-indigo-500" />
            </div>
         </div>
      </div>

      <div>
         <h3 class="font-bold text-sm border-b pb-2 mb-4">Charte Graphique (Story Base Prompt)</h3>
         <p class="text-[10px] text-gray-400 mb-2 leading-tight">Ce prompt est prefixé à chaque génération d'image pour assurer la cohérence de l'histoire.</p>
         <textarea id="cfg-base-prompt" rows="8" class="w-full text-xs font-mono text-indigo-900 bg-indigo-50 border border-indigo-100 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-indigo-500"></textarea>
      </div>

      <button id="btn-save" onclick="saveConfig()" class="w-full bg-gray-900 text-white font-medium rounded-lg py-3 hover:bg-gray-800 transition shadow-sm">
        💾 Sauvegarder Complet
      </button>

    </div>

  </main>

  <!-- Output Modal -->
  <div id="output-modal" class="hidden fixed inset-0 bg-gray-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-6">
    <div class="bg-gray-900 text-green-400 w-full max-w-4xl max-h-full rounded-2xl shadow-2xl flex flex-col border border-gray-700">
      <div class="p-4 border-b border-gray-700 flex justify-between items-center text-white shrink-0">
        <h2 id="modal-title" class="font-bold">🖥️ Terminal Console</h2>
        <button onclick="document.getElementById('output-modal').classList.add('hidden')" class="text-gray-400 hover:text-white font-bold px-2 py-1 bg-gray-800 rounded">Fermer</button>
      </div>
      <div class="p-4 overflow-auto flex-1 font-mono text-xs whitespace-pre-wrap" id="modal-content"></div>
    </div>
  </div>

  <script>
    const BOOK_NAME = '{{ book_name }}';
    let configData = null;
    let selectedPageIndex = null;

    async function loadConfig() {
      const res = await fetch(`/api/book/${BOOK_NAME}/config`);
      configData = await res.json();
      
      // Init missing story fields if any
      if (!configData.pages) configData.pages = [];
      if (!configData.story_base_prompt) configData.story_base_prompt = "";
      
      // Populate global fields
      document.getElementById('cfg-title').value = configData.title || "";
      document.getElementById('cfg-subtitle').value = configData.subtitle || "";
      document.getElementById('cfg-author').value = configData.author || "";
      document.getElementById('cfg-base-prompt').value = configData.story_base_prompt;

      renderPagesList();
    }

    function renderPagesList() {
      const list = document.getElementById('pages-list');
      list.innerHTML = "";
      
      configData.pages.forEach((p, idx) => {
        const div = document.createElement('div');
        div.className = `page-item border-l-4 border-transparent p-4 hover:bg-gray-100 ${idx === selectedPageIndex ? 'active' : 'bg-white'}`;
        
        const shortText = (p.text && p.text.fr) ? p.text.fr.substring(0, 30) + "..." : "Aucun texte FR";
        
        div.innerHTML = `
          <div class="flex justify-between items-start">
             <span class="text-sm font-bold text-gray-800">Page ${p.page_number}</span>
             ${p.moral ? '<span class="bg-indigo-100 text-indigo-800 text-[10px] px-1.5 rounded uppercase">Morale</span>' : ''}
          </div>
          <p class="text-xs text-gray-500 mt-1 line-clamp-1 italic">"${shortText}"</p>
        `;
        div.onclick = () => selectPage(idx);
        list.appendChild(div);
      });
      
      if (selectedPageIndex !== null && configData.pages[selectedPageIndex]) {
         document.getElementById('editor-idle').classList.add('hidden');
         document.getElementById('editor-active').classList.remove('hidden');
         populateEditor(selectedPageIndex);
      } else {
         document.getElementById('editor-idle').classList.remove('hidden');
         document.getElementById('editor-active').classList.add('hidden');
      }
    }

    function selectPage(idx) {
      // Save current page info before switching
      saveCurrentPageToState();
      
      selectedPageIndex = idx;
      renderPagesList();
    }

    function populateEditor(idx) {
      const p = configData.pages[idx];
      document.getElementById('editor-title').innerText = `Edition de la Page ${p.page_number}`;
      
      document.getElementById('page-image-prompt').value = p.image_prompt || "";
      document.getElementById('page-moral').value = p.moral || "";
      
      if (!p.text) p.text = {fr:"", en:"", es:"", ar:""};
      document.getElementById('page-text-fr').value = p.text.fr || "";
      document.getElementById('page-text-en').value = p.text.en || "";
      document.getElementById('page-text-es').value = p.text.es || "";
      document.getElementById('page-text-ar').value = p.text.ar || "";
    }

    function saveCurrentPageToState() {
      if (selectedPageIndex === null) return;
      const p = configData.pages[selectedPageIndex];
      if (!p) return;
      
      p.image_prompt = document.getElementById('page-image-prompt').value;
      p.moral = document.getElementById('page-moral').value;
      
      if (!p.text) p.text = {};
      p.text.fr = document.getElementById('page-text-fr').value;
      p.text.en = document.getElementById('page-text-en').value;
      p.text.es = document.getElementById('page-text-es').value;
      p.text.ar = document.getElementById('page-text-ar').value;
    }

    function addPage() {
      saveCurrentPageToState();
      const maxNum = configData.pages.length > 0 ? Math.max(...configData.pages.map(x => x.page_number)) : 0;
      configData.pages.push({
         page_number: maxNum + 1,
         image_prompt: "",
         moral: "",
         text: {fr:"", en:"", es:"", ar:""}
      });
      selectedPageIndex = configData.pages.length - 1;
      renderPagesList();
    }

    function deleteCurrentPage() {
      if (selectedPageIndex === null) return;
      if (!confirm("Supprimer cette page ?")) return;
      
      configData.pages.splice(selectedPageIndex, 1);
      
      // Auto-renumber
      configData.pages.forEach((p, i) => p.page_number = i + 1);
      
      selectedPageIndex = null;
      renderPagesList();
    }

    async function saveConfig() {
      const btn = document.getElementById('btn-save');
      btn.innerText = "⏳ Sauvegarde...";
      btn.disabled = true;
      
      saveCurrentPageToState(); // commit editor values to configData
      
      // Commit global fields
      configData.title = document.getElementById('cfg-title').value;
      configData.subtitle = document.getElementById('cfg-subtitle').value;
      configData.author = document.getElementById('cfg-author').value;
      configData.story_base_prompt = document.getElementById('cfg-base-prompt').value;

      try {
        const res = await fetch(`/api/book/${BOOK_NAME}/config`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(configData)
        });
        if (res.ok) {
           btn.innerText = "✅ Config Sauvegardée !";
           setTimeout(() => { btn.innerText = "💾 Sauvegarder Complet"; btn.disabled = false; }, 2000);
           // reload just in case
           console.log("Config updated successfully.");
        } else {
           const err = await res.json();
           alert('Erreur: ' + err.detail);
           btn.innerText = "❌ Echec";
           setTimeout(() => { btn.innerText = "💾 Sauvegarder Complet"; btn.disabled = false; }, 2000);
        }
      } catch (e) {
        alert('Network error');
        btn.innerText = "💾 Sauvegarder Complet"; 
        btn.disabled = false;
      }
    }

    /* -- Terminal Output Management -- */
    const modal = document.getElementById('output-modal');
    const modalContent = document.getElementById('modal-content');
    const modalTitle = document.getElementById('modal-title');

    function openModal(title) {
      modalTitle.innerText = title;
      modalContent.innerText = "Initialisation...";
      modal.classList.remove('hidden');
    }

    async function runStreamCommand(url, title) {
      openModal("🖥️ " + title);
      try {
        const response = await fetch(url);
        if (!response.ok) { throw new Error(`HTTP error! status: ${response.status}`); }
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value);
          const lines = chunk.split('\\n\\n').filter(l => l.trim());
          for (let line of lines) {
            if (line.startsWith('data: ')) {
              const content = line.substring(6);
              if (content === '[DONE]') {
                modalContent.innerHTML += "\\n\\n<span class='text-blue-400 font-bold'>[Process Terminé avec succès]</span>\\n";
                // Optionally reload after a few seconds
                setTimeout(() => window.location.reload(), 2000);
                return;
              } else if (content.startsWith('ERROR:')) {
                 modalContent.innerHTML += "\\n<span class='text-red-500 font-bold'>" + content + "</span>\\n";
              } else {
                 modalContent.innerText += content + "\\n";
              }
              modalContent.scrollTop = modalContent.scrollHeight;
            }
          }
        }
      } catch (err) {
        modalContent.innerHTML += `\\n<span class="text-red-500 font-bold">Fetch Error: ${err.message}</span>`;
      }
    }

    function runGenerate() {
      if(!confirm("Générer les images pour cette Story ?")) return;
      saveConfig().then(() => runStreamCommand(`/stream/generate/${BOOK_NAME}`, `Generate Images: ${BOOK_NAME}`));
    }
    function runAssemble() {
      runStreamCommand(`/stream/assemble/${BOOK_NAME}`, `Assemble PDF: ${BOOK_NAME}`);
    }

    // Init
    loadConfig();
  </script>
</body>
</html>
"""

with open("dashboard/templates/story.html", "w") as f:
    f.write(html_content)

