with open("dashboard/templates/story.html") as f:
    html = f.read()

# remove all injected btn_html parts
btn_html = """
          <div class="flex items-center justify-between mb-2">
            <label class="text-xs font-bold text-gray-500 uppercase">Traductions</label>
            <button type="button" onclick="translateCurrentPage(event)" class="text-indigo-600 hover:text-indigo-800 text-xs px-2 py-1 rounded bg-indigo-50 hover:bg-indigo-100 flex items-center gap-1">
              🔄 Auto-Traduire (depuis FR)
            </button>
          </div>
          <div class="grid grid-cols-2 gap-4">
"""

# restore original structure
import re
html = re.sub(r'<div class="flex items-center justify-between mb-2">\s*<label class="text-xs font-bold text-gray-500 uppercase">Traductions</label>\s*<button type="button" onclick="translateCurrentPage[^"]*" class="[^"]*">\s*🔄 Auto-Traduire \(depuis FR\)\s*</button>\s*</div>\s*<div class="grid grid-cols-2 gap-4">', '<div class="grid grid-cols-2 gap-4">', html)

# Now, we only inject before the "Texte (FR)" area.
split_str = '<div>\n              <label class="block text-xs font-bold text-gray-500 uppercase mb-2">Texte (FR)</label>'
if split_str in html:
    parts = html.split(split_str)
    # The first instance of <div class="grid grid-cols-2 gap-4"> before this string needs to be replaced.
    idx = parts[0].rfind('<div class="grid grid-cols-2 gap-4">')
    if idx != -1:
        parts[0] = parts[0][:idx] + btn_html + parts[0][idx + len('<div class="grid grid-cols-2 gap-4">'):]
    html = split_str.join(parts)
else:
    print("Could not find Texte (FR)")

with open("dashboard/templates/story.html", "w") as f:
    f.write(html)
