with open("dashboard/templates/book.html", "r") as f:
    text = f.read()

# Fix saveConfig payload to preserve other fields
bad_js = """    async function saveConfig(bookName) {
      const payload = {"""
good_js = """    async function saveConfig(bookName) {
      const payload = {
        ...configData,"""

text = text.replace(bad_js, good_js)

with open("dashboard/templates/book.html", "w") as f:
    f.write(text)
