import sys
import re

with open('dashboard/templates/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

toast_html = '  <div id="toast" class="hidden fixed top-4 right-4 bg-gray-900 text-white text-sm px-4 py-2 rounded-lg shadow-lg z-50"></div>\n'
if '<div id="toast"' not in text:
    text = text.replace('<body class="bg-gray-50 flex h-screen text-gray-800">', '<body class="bg-gray-50 flex h-screen text-gray-800">\n' + toast_html)
    text = text.replace('<body class="bg-gray-50 text-gray-800">', '<body class="bg-gray-50 text-gray-800">\n' + toast_html)

toast_js = """    function showToast(msg, type='info') {
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

if 'function showToast' not in text:
    text = text.replace('async function deleteBook', toast_js + '\n    async function deleteBook')

text = text.replace("alert(", "showToast(")

with open('dashboard/templates/index.html', 'w', encoding='utf-8') as f:
    f.write(text)
