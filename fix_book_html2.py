import re

with open("dashboard/templates/book.html") as f:
    html = f.read()

# When we drag and drop we need the ID to not only exist as values in the DOM but as part of configData.
# Drag and drop uses specific functionality:
# function onCharDrop(e) { ... configData.characters = Array.from(container.children).map ... }
# Then immediately calls saveConfig(BOOK_NAME)

js_to_add = """
    function onCharDrop(e) {
      e.preventDefault();
      const draggedId = e.dataTransfer.getData('text/plain');
      const container = document.getElementById('sortable-characters');
      const target = e.target.closest('.char-card');
      
      const draggedEl = document.querySelector(`[data-char-id="${draggedId}"]`);
      if (!draggedEl || !target || draggedEl === target) return;

      const rect = target.getBoundingClientRect();
      const y = e.clientY - rect.top;
      
      if (y > rect.height / 2) {
        target.parentNode.insertBefore(draggedEl, target.nextSibling);
      } else {
        target.parentNode.insertBefore(draggedEl, target);
      }

      // Re-synchronize configData.characters order
      const newIds = Array.from(container.children).map(c => c.getAttribute('data-char-id'));
      const oldChars = [...configData.characters];
      const newChars = newIds.map(id => oldChars.find(c => c.id === id));
      
      // Update configData and save
      configData.characters = newChars;
      saveConfig(BOOK_NAME);
    }
"""

if "function onCharDrop" not in html:
    html = html.replace("function enableDragDrop() {", js_to_add + "\n    function enableDragDrop() {")
else:
    # already exists, we need to inspect the existing logic for bugs.
    pass

with open("dashboard/templates/book.html", "w") as f:
    f.write(html)
