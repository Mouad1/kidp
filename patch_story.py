import sys
import re

with open('dashboard/templates/story.html', 'r', encoding='utf-8') as f:
    text = f.read()

# Fix the broken showToast
pattern = r"// ── Utilities ─────────────────────────────────────────────────────────────\n\s*function showToast.*?\}\n\n"
text = re.sub(pattern, "", text, flags=re.DOTALL)

toast_js = """    // ── Utilities ─────────────────────────────────────────────────────────────
    function showToast(msg, type='info') {
      const t = document.getElementById('toast');
      if (!t) return;
      t.textContent = msg;
      t.className = `fixed top-4 right-4 text-sm px-4 py-2 rounded-lg shadow-lg z-50 transition-opacity duration-300 ${type === 'error' ? 'bg-red-500 text-white' : 'bg-gray-900 text-white'}`;
      t.classList.remove('opacity-0');
      setTimeout(() => {
        t.classList.add('opacity-0');
        setTimeout(() => t.className = 'hidden', 300);
      }, 3000);
    }

"""

text = text.replace("async function loadConfig()", toast_js + "    async function loadConfig()")

# Replace all alert(...) with showToast(..., 'error')
text = re.sub(r'alert\("Erreur: "\s*\+\s*([a-zA-Z0-9_.]+(?:\.message|\.detail|JSON\.stringify\([a-zA-Z0-9_.]+\))?)\);', r"showToast('Erreur: ' + \1, 'error');", text)
text = re.sub(r'alert\((['"'"'"].*?['"'"'"](?:\s*\+\s*[a-zA-Z0-9_.]+)?)\);', r"showToast(\1, 'error');", text)
text = re.sub(r"alert\('Erreur: '\s*\+\s*([a-zA-Z0-9_.]+)\);", r"showToast('Erreur: ' + \1, 'error');", text)

# Special cases
text = text.replace("showToast('✅ Traductions générées avec succès', 'error')", "showToast('✅ Traductions générées avec succès', 'info')")
text = text.replace("return alert(", "return showToast(")

# Any remaining alert(
text = text.replace("alert(", "showToast(")

with open('dashboard/templates/story.html', 'w', encoding='utf-8') as f:
    f.write(text)
