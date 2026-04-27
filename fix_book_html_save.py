import re

with open("dashboard/templates/book.html") as f:
    html = f.read()

# Let's see if onCharDrop calls saveConfig!
# It doesn't! It just calls renderCharacters(chars) but renderCharacters(chars) might not call saveConfig.
# Wait, let's check renderCharacters(chars) logic.

# In onCharDrop, after renderCharacters(chars), we need to call saveConfig(BOOK_NAME)

js_patch = """      renderCharacters(chars);
      saveConfig(BOOK_NAME);
    }"""

html = html.replace("      renderCharacters(chars);\n    }", js_patch)

with open("dashboard/templates/book.html", "w") as f:
    f.write(html)
