with open("dashboard/templates/book.html") as f:
    html = f.read()

js_to_add = """
    // --- Import Modal Logic ---
    let allImportImages = {};
    let selectedImportBook = null;

    async function openImportModal() {
      document.getElementById('import-image-modal').classList.remove('hidden');
      try {
        const res = await fetch('/api/images/all');
        allImportImages = await res.json();
        renderImportFolders();
      } catch (err) {
        console.error(err);
      }
    }

    function closeImportModal() {
      document.getElementById('import-image-modal').classList.add('hidden');
    }

    function renderImportFolders() {
      const list = document.getElementById('import-books-list');
      list.innerHTML = '';
      for (const book of Object.keys(allImportImages)) {
        const btn = document.createElement('button');
        btn.className = 'w-full text-left px-3 py-2 text-sm rounded-lg hover:bg-gray-200 focus:bg-indigo-100 focus:text-indigo-700 ' + (selectedImportBook === book ? 'bg-indigo-100 text-indigo-700 font-bold' : 'text-gray-600');
        btn.textContent = book;
        btn.onclick = () => {
          selectedImportBook = book;
          renderImportFolders();
          renderImportImages(book);
        };
        list.appendChild(btn);
      }
    }

    function renderImportImages(book) {
      const grid = document.getElementById('import-images-grid');
      grid.innerHTML = '';
      const imgs = allImportImages[book];
      if (!imgs || imgs.length === 0) {
        grid.innerHTML = '<div class="text-xs text-gray-400 italic">Aucune image dans ce dossier</div>';
        return;
      }
      
      for (const img of imgs) {
        if (!img.endsWith('.png')) continue;
        const div = document.createElement('div');
        div.className = 'cursor-pointer border-2 border-transparent hover:border-indigo-400 rounded overflow-hidden relative group aspect-square bg-gray-50';
        
        div.innerHTML = `
          <img src="/api/book/${book}/open-image?filename=${img}" style="pointer-events: none; width: 100%; height: 100%; object-fit: cover;" onerror="this.src='/images/${book}/${img}'">
          <div class="absolute inset-x-0 bottom-0 bg-black/60 text-white text-[10px] p-1 truncate opacity-0 group-hover:opacity-100 transition-opacity">
            ${img}
          </div>
        `;
        
        div.onclick = () => doImportImage(book, img);
        grid.appendChild(div);
      }
    }

    async function doImportImage(sourceBook, filename) {
      if (!confirm(`Importer l'image ${filename} depuis ${sourceBook} ?\nElle sera copiée dans votre livre.`)) return;
      
      try {
        const res = await fetch(`/api/book/${BOOK_NAME}/add-image`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({source_book: sourceBook, filename: filename})
        });
        const data = await res.json();
        
        if (data.status === 'ok') {
          // Add to state
          configData.characters.push({
            id: data.new_id,
            name: "Importé de " + sourceBook,
            series: "",
            prompt: "Copie de " + filename
          });
          
          await saveConfig(BOOK_NAME);
          renderCharacters(configData.characters);
          closeImportModal();
          showToast(`Image importée avec succès (${data.new_filename})`);
        } else {
          alert('Erreur: ' + data.detail);
        }
      } catch (err) {
        console.error(err);
        alert('Erreur: ' + err.message);
      }
    }

    // ── Drag & drop reorder ──
"""

if "function openImportModal()" not in html:
    html = html.replace("// ── Drag & drop reorder ──", js_to_add)
    with open("dashboard/templates/book.html", "w") as f:
        f.write(html)
        print("Successfully injected JS.")
else:
    print("JS already exists.")
