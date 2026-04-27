import re

with open("dashboard/templates/book.html") as f:
    html = f.read()

btn = """
      <button onclick="openImportModal()" class="bg-teal-500 hover:bg-teal-600 text-white px-3 py-1.5 rounded-lg text-sm font-bold shadow transition-colors flex items-center gap-1">
        ➕ Importer
      </button>
      <button onclick="addCharacter()"
"""

html = re.sub(r'<button onclick="addCharacter\(\)".*?>\s*➕ Nouveau Personnage\s*</button>', btn.replace('<button onclick="addCharacter()"', '<button onclick="addCharacter()" class="bg-indigo-600 hover:bg-indigo-700 text-white px-3 py-1.5 rounded-lg text-sm font-bold shadow transition-colors flex items-center gap-1">\n        ➕ Nouveau Personnage\n      </button>'), html, flags=re.DOTALL)

with open("dashboard/templates/book.html", "w") as f:
    f.write(html)
