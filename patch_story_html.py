with open("dashboard/templates/story.html") as f:
    html = f.read()

btn_html = """
          <div class="flex items-center justify-between mb-2">
            <label class="text-xs font-bold text-gray-500 uppercase">Traductions</label>
            <button type="button" onclick="translateCurrentPage()" class="text-indigo-600 hover:text-indigo-800 text-xs px-2 py-1 rounded bg-indigo-50 hover:bg-indigo-100 flex items-center gap-1">
              🔄 Auto-Traduire (depuis FR)
            </button>
          </div>
          <div class="grid grid-cols-2 gap-4">
"""

html = html.replace('<div class="grid grid-cols-2 gap-4">', btn_html)

js_translate = """
    async function translateCurrentPage() {
      if (selectedPageIndex === null) return;
      const textFr = document.getElementById('page-text-fr').value.trim();
      if (!textFr) return alert("Le texte FR est vide !");
      
      const btn = event.currentTarget;
      const oldHtml = btn.innerHTML;
      btn.innerHTML = '⏳ Traduction...';
      btn.disabled = true;
      
      const targetLangs = [];
      if (!document.getElementById('page-text-en').value.trim()) targetLangs.push('en');
      if (!document.getElementById('page-text-es').value.trim()) targetLangs.push('es');
      if (!document.getElementById('page-text-ar').value.trim()) targetLangs.push('ar');
      
      if (targetLangs.length === 0) {
        if (!confirm("Toutes les langues sont renseignées. Forcer la recréation ?")) {
          btn.innerHTML = oldHtml;
          btn.disabled = false;
          return;
        }
        targetLangs.push('en', 'es', 'ar');
      }

      try {
        const res = await fetch("/api/translate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: textFr, langs: targetLangs })
        });
        if (!res.ok) throw new Error("Erreur de traduction");
        const json = await res.json();
        
        if (json.en) document.getElementById('page-text-en').value = json.en;
        if (json.es) document.getElementById('page-text-es').value = json.es;
        if (json.ar) document.getElementById('page-text-ar').value = json.ar;
        
        saveCurrentPageToState();
        saveConfig();
        showToast("✅ Traductions générées avec succès");
      } catch (err) {
        showToast("❌ Erreur: " + err.message);
      } finally {
        btn.innerHTML = oldHtml;
        btn.disabled = false;
      }
    }
"""
html = html.replace('function addPage() {', js_translate + '\n    function addPage() {')

with open("dashboard/templates/story.html", "w") as f:
    f.write(html)
