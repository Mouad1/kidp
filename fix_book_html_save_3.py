with open("dashboard/templates/book.html") as f:
    html = f.read()

# Looks like it's `<button onclick="addCharacterRow()">` not `addCharacter()`
import re

btn = """      <button onclick="openImportModal()" class="bg-teal-500 hover:bg-teal-600 text-white px-3 py-1.5 rounded-lg text-sm font-bold shadow transition-colors flex items-center gap-1">
        ➕ Importer
      </button>
      <button onclick="addCharacterRow()" """

html = re.sub(r'<button onclick="addCharacterRow\(\)".*?>\s*➕ Ajouter\s*</button>', btn.replace('<button onclick="addCharacterRow()"', '<button onclick="addCharacterRow()" class="bg-indigo-600 hover:bg-indigo-700 text-white px-3 py-1.5 rounded-lg text-sm font-bold shadow transition-colors flex items-center gap-1">\n        ➕ Ajouter\n      </button>'), html, flags=re.DOTALL)

with open("dashboard/templates/book.html", "w") as f:
    f.write(html)
