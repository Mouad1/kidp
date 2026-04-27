with open("dashboard/templates/book.html") as f:
    html = f.read()

# Let's see if openImportModal() is there actually.
if "openImportModal()" not in html or "function renderImportFolders" not in html:
    print("JS not fully injected!")
else:
    print("JS is there!")
