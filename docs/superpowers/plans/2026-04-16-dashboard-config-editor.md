# Dashboard Config Editor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter un éditeur de configuration complet au dashboard KDP — modifier metadata, personnages, PAGE_SEQUENCE et créer de nouveaux livres, sans toucher au code.

**Architecture:** Un module `pipeline/config_io.py` expose `read_config()` et `write_config()` ; FastAPI ajoute 3 nouveaux endpoints REST ; le frontend (vanilla JS) charge et sauvegarde la config via `fetch()`. Les sections non-éditables (`TITLE_PAGE_LINES`, etc.) sont préservées verbatim à chaque écriture.

**Tech Stack:** Python 3.11, FastAPI, Pydantic (déjà présent), Jinja2, vanilla JS, Tailwind CDN

---

## Fichiers touchés

| Action | Fichier | Responsabilité |
|---|---|---|
| Créer | `pipeline/config_io.py` | Lire/écrire config.py en JSON |
| Créer | `tests/test_config_io.py` | Tests unitaires config_io |
| Créer | `tests/test_api_config.py` | Tests endpoints API |
| Modifier | `dashboard/app.py` | 3 nouveaux endpoints + route new-book |
| Modifier | `dashboard/templates/book.html` | Onglets Status / Config |
| Créer | `dashboard/templates/new_book.html` | Wizard création livre |
| Modifier | `dashboard/templates/index.html` | Bouton "+ New Book" |

---

## Task 1 — pipeline/config_io.py : read_config()

**Files:**
- Create: `pipeline/config_io.py`
- Create: `tests/test_config_io.py`

- [ ] **Step 1 : Créer le squelette de config_io.py**

```python
# pipeline/config_io.py
"""
pipeline/config_io.py — Sérialisation/désérialisation des configs de livres.

Utilisé par le dashboard pour lire et écrire books/{name}/config.py.
"""

import importlib.util
import json
import pathlib
import pprint

ROOT = pathlib.Path(__file__).parent.parent


def read_config(book_name: str) -> dict:
    """Charge books/{book_name}/config.py et retourne un dict JSON-serializable."""
    config_path = ROOT / "books" / book_name / "config.py"
    if not config_path.exists():
        raise FileNotFoundError(f"config.py introuvable pour {book_name!r}")

    spec = importlib.util.spec_from_file_location(
        f"books.{book_name}.config", config_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    images_dir = getattr(module, "IMAGES_DIR", None)
    images_folder = images_dir.name if images_dir else book_name

    return {
        "title":                getattr(module, "TITLE",    ""),
        "subtitle":             getattr(module, "SUBTITLE", ""),
        "author":               getattr(module, "AUTHOR",   ""),
        "testpen":              getattr(module, "TESTPEN",  ""),
        "images_folder":        images_folder,
        "characters":           getattr(module, "CHARACTERS",   []),
        "page_sequence": [
            {"file": f, "label": lbl}
            for f, lbl in getattr(module, "PAGE_SEQUENCE", [])
        ],
        "title_page_lines":     getattr(module, "TITLE_PAGE_LINES",     []),
        "copyright_page_lines": getattr(module, "COPYRIGHT_PAGE_LINES", []),
        "back_page_lines":      getattr(module, "BACK_PAGE_LINES",      []),
    }
```

- [ ] **Step 2 : Écrire le test de read_config**

```python
# tests/test_config_io.py
import pathlib
import pytest
from pipeline.config_io import read_config

FAKE_CONFIG = '''
import pathlib
TITLE    = "Test Book"
SUBTITLE = "A subtitle"
AUTHOR   = "Marco Belghiti"
TESTPEN  = "book_test_testpen.png"
IMAGES_DIR = pathlib.Path(__file__).parent.parent.parent / "images" / "book-test"
CHARACTERS = [{"id": "hero", "name": "The Hero", "series": "S1", "prompt": "a hero"}]
PAGE_SEQUENCE = [("book_test_hero.png", "The Hero")]
TITLE_PAGE_LINES = [("Test Book", 120, True, (0, 0, 0))]
COPYRIGHT_PAGE_LINES = [("© 2026", 32, True, (40, 40, 40))]
BACK_PAGE_LINES = [("Thank you!", 55, True, (0, 0, 0))]
'''


@pytest.fixture()
def fake_book(tmp_path, monkeypatch):
    """Crée un faux livre dans tmp_path et patche ROOT."""
    book_dir = tmp_path / "books" / "book-test"
    book_dir.mkdir(parents=True)
    (book_dir / "config.py").write_text(FAKE_CONFIG)
    import pipeline.config_io as cio
    monkeypatch.setattr(cio, "ROOT", tmp_path)
    return tmp_path


def test_read_config_returns_dict(fake_book):
    data = read_config("book-test")
    assert data["title"] == "Test Book"
    assert data["author"] == "Marco Belghiti"
    assert data["images_folder"] == "book-test"
    assert data["characters"] == [{"id": "hero", "name": "The Hero", "series": "S1", "prompt": "a hero"}]
    assert data["page_sequence"] == [{"file": "book_test_hero.png", "label": "The Hero"}]
    assert data["title_page_lines"] == [("Test Book", 120, True, (0, 0, 0))]


def test_read_config_missing_book(tmp_path, monkeypatch):
    import pipeline.config_io as cio
    monkeypatch.setattr(cio, "ROOT", tmp_path)
    with pytest.raises(FileNotFoundError):
        read_config("nonexistent")
```

- [ ] **Step 3 : Lancer le test pour vérifier qu'il échoue**

```bash
cd /Users/mouadbelghiti/mo-projects/kidp
python -m pytest tests/test_config_io.py::test_read_config_returns_dict -v
```
Attendu : `FAILED` — `ModuleNotFoundError: No module named 'pipeline.config_io'`

- [ ] **Step 4 : Créer `tests/__init__.py` vide + vérifier que le module est importable**

```bash
touch tests/__init__.py
python -c "from pipeline.config_io import read_config; print('OK')"
```
Attendu : `OK`

- [ ] **Step 5 : Lancer les tests et vérifier qu'ils passent**

```bash
python -m pytest tests/test_config_io.py -v
```
Attendu : `2 passed`

- [ ] **Step 6 : Commit**

```bash
git add pipeline/config_io.py tests/__init__.py tests/test_config_io.py
git commit -m "feat: add config_io.read_config with tests"
```

---

## Task 2 — pipeline/config_io.py : write_config()

**Files:**
- Modify: `pipeline/config_io.py` (ajouter write_config + helpers)
- Modify: `tests/test_config_io.py` (ajouter tests write)

- [ ] **Step 1 : Écrire les tests de write_config**

Ajouter à `tests/test_config_io.py` :

```python
from pipeline.config_io import write_config


def test_write_config_creates_valid_python(fake_book, monkeypatch):
    """write_config doit générer un config.py importable par le pipeline."""
    import pipeline.config_io as cio
    monkeypatch.setattr(cio, "ROOT", fake_book)

    data = {
        "title": "New Title",
        "subtitle": "New Subtitle",
        "author": "Marco Belghiti",
        "testpen": "book-test_testpen.png",
        "images_folder": "book-test",
        "characters": [
            {"id": "hero", "name": "The Hero", "series": "S1", "prompt": "a hero prompt"},
        ],
        "page_sequence": [
            {"file": "book-test_hero.png", "label": "The Hero"},
        ],
    }
    write_config("book-test", data)

    # Le fichier doit être importable et avoir les bonnes valeurs
    result = read_config("book-test")
    assert result["title"] == "New Title"
    assert result["author"] == "Marco Belghiti"
    assert result["characters"][0]["id"] == "hero"
    assert result["page_sequence"][0]["file"] == "book-test_hero.png"


def test_write_config_preserves_non_editable_sections(fake_book, monkeypatch):
    """Les sections TITLE_PAGE_LINES etc. doivent être préservées."""
    import pipeline.config_io as cio
    monkeypatch.setattr(cio, "ROOT", fake_book)

    data = {
        "title": "Changed Title",
        "subtitle": "Sub",
        "author": "Marco Belghiti",
        "testpen": "tp.png",
        "images_folder": "book-test",
        "characters": [],
        "page_sequence": [],
    }
    write_config("book-test", data)
    result = read_config("book-test")
    # TITLE_PAGE_LINES doit être identique à ce qui était dans FAKE_CONFIG
    assert result["title_page_lines"] == [("Test Book", 120, True, (0, 0, 0))]


def test_write_config_images_dir_uses_relative_path(fake_book, monkeypatch):
    """IMAGES_DIR doit utiliser pathlib.Path(__file__).parent... (jamais hardcodé)."""
    import pipeline.config_io as cio
    monkeypatch.setattr(cio, "ROOT", fake_book)

    data = {
        "title": "T", "subtitle": "S", "author": "A",
        "testpen": "tp.png", "images_folder": "book-test",
        "characters": [], "page_sequence": [],
    }
    write_config("book-test", data)

    content = (fake_book / "books" / "book-test" / "config.py").read_text()
    assert 'pathlib.Path(__file__).parent.parent.parent' in content
    assert '"book-test"' in content
    # Jamais de chemin absolu hardcodé
    assert '/Users/' not in content
```

- [ ] **Step 2 : Lancer les tests pour vérifier qu'ils échouent**

```bash
python -m pytest tests/test_config_io.py -v -k "write"
```
Attendu : `FAILED` — `ImportError: cannot import name 'write_config'`

- [ ] **Step 3 : Implémenter write_config et les helpers dans config_io.py**

Ajouter à `pipeline/config_io.py` :

```python
def write_config(book_name: str, data: dict) -> None:
    """Régénère books/{book_name}/config.py depuis un dict JSON."""
    config_path = ROOT / "books" / book_name / "config.py"

    # Préserver les sections non-éditables si le fichier existe déjà
    if config_path.exists():
        existing = read_config(book_name)
        title_page_lines     = data.get("title_page_lines",     existing["title_page_lines"])
        copyright_page_lines = data.get("copyright_page_lines", existing["copyright_page_lines"])
        back_page_lines      = data.get("back_page_lines",      existing["back_page_lines"])
    else:
        title_page_lines     = data.get("title_page_lines",     _default_title_page(data.get("title", ""), data.get("subtitle", "")))
        copyright_page_lines = data.get("copyright_page_lines", _default_copyright())
        back_page_lines      = data.get("back_page_lines",      _default_back())

    content = _render_config(
        book_name            = book_name,
        title                = data.get("title", ""),
        subtitle             = data.get("subtitle", ""),
        author               = data.get("author", ""),
        testpen              = data.get("testpen", f"{book_name}_testpen.png"),
        images_folder        = data.get("images_folder", book_name),
        characters           = data.get("characters", []),
        page_sequence        = data.get("page_sequence", []),
        title_page_lines     = title_page_lines,
        copyright_page_lines = copyright_page_lines,
        back_page_lines      = back_page_lines,
    )
    config_path.write_text(content, encoding="utf-8")


def _render_config(
    book_name: str,
    title: str,
    subtitle: str,
    author: str,
    testpen: str,
    images_folder: str,
    characters: list,
    page_sequence: list,
    title_page_lines: list,
    copyright_page_lines: list,
    back_page_lines: list,
) -> str:
    # Formater CHARACTERS
    char_blocks = []
    for c in characters:
        char_blocks.append(
            "    {\n"
            f'        "id":     {json.dumps(c["id"])},\n'
            f'        "name":   {json.dumps(c["name"])},\n'
            f'        "series": {json.dumps(c["series"])},\n'
            f'        "prompt": {json.dumps(c["prompt"])},\n'
            "    }"
        )
    chars_str = "[\n" + ",\n".join(char_blocks) + "\n]" if char_blocks else "[]"

    # Formater PAGE_SEQUENCE
    seq_lines = []
    for p in page_sequence:
        seq_lines.append(f'    ({json.dumps(p["file"])}, {json.dumps(p["label"])})')
    seq_str = "[\n" + ",\n".join(seq_lines) + "\n]" if seq_lines else "[]"

    # Formater sections non-éditables avec pprint
    tpl_str = pprint.pformat(title_page_lines,     width=100)
    cpl_str = pprint.pformat(copyright_page_lines, width=100)
    bpl_str = pprint.pformat(back_page_lines,      width=100)

    return (
        f'"""\n'
        f'books/{book_name}/config.py — Book data manifest\n\n'
        f'Generated by KDP Dashboard.\n'
        f'Identity, CHARACTERS, and PAGE_SEQUENCE are managed via the dashboard.\n'
        f'Edit TITLE_PAGE_LINES, COPYRIGHT_PAGE_LINES, BACK_PAGE_LINES directly if needed.\n'
        f'"""\n\n'
        f'import pathlib\n\n'
        f'# ── Identity ───────────────────────────────────────────────────────────────────\n\n'
        f'TITLE    = {json.dumps(title)}\n'
        f'SUBTITLE = {json.dumps(subtitle)}\n'
        f'AUTHOR   = {json.dumps(author)}\n\n'
        f'# ── Paths ──────────────────────────────────────────────────────────────────────\n\n'
        f'IMAGES_DIR = pathlib.Path(__file__).parent.parent.parent / "images" / {json.dumps(images_folder)}\n'
        f'TESTPEN    = {json.dumps(testpen)}\n\n'
        f'# ── Character roster ──────────────────────────────────────────────────────────\n\n'
        f'CHARACTERS = {chars_str}\n\n'
        f'# ── Page sequence ─────────────────────────────────────────────────────────────\n\n'
        f'PAGE_SEQUENCE = {seq_str}\n\n'
        f'# ── Title-page layout ─────────────────────────────────────────────────────────\n\n'
        f'TITLE_PAGE_LINES = {tpl_str}\n\n'
        f'# ── Copyright-page layout ────────────────────────────────────────────────────\n\n'
        f'COPYRIGHT_PAGE_LINES = {cpl_str}\n\n'
        f'# ── Back-matter layout ───────────────────────────────────────────────────────\n\n'
        f'BACK_PAGE_LINES = {bpl_str}\n'
    )


def _default_title_page(title: str, subtitle: str) -> list:
    return [
        (title, 120, True, (0, 0, 0)),
        ("Coloring Our Stories", 72, True, (0, 0, 0)),
        ("", 36, False, (255, 255, 255)),
        (subtitle, 46, False, (60, 60, 60)),
        ("", 24, False, (255, 255, 255)),
        ("Color with your kids — bring the heroes to life!", 38, False, (110, 110, 110)),
    ]


def _default_copyright() -> list:
    return [
        ("© 2026 All rights reserved.", 32, True, (40, 40, 40)),
        ("", 18, False, (255, 255, 255)),
        ("No part of this publication may be reproduced", 26, False, (80, 80, 80)),
        ("or distributed without prior written permission.", 26, False, (80, 80, 80)),
        ("", 18, False, (255, 255, 255)),
        ("All characters are original fictional archetypes", 26, False, (80, 80, 80)),
        ("inspired by the world of anime.", 26, False, (80, 80, 80)),
        ("", 18, False, (255, 255, 255)),
        ("Printed in the United States of America", 26, False, (80, 80, 80)),
        ("First Edition", 26, False, (80, 80, 80)),
    ]


def _default_back() -> list:
    return [
        ("Thank you for coloring with us!", 55, True, (0, 0, 0)),
        ("", 30, False, (255, 255, 255)),
        ("If you enjoyed this book,", 40, False, (60, 60, 60)),
        ("please leave a review on Amazon.", 40, False, (60, 60, 60)),
        ("", 24, False, (255, 255, 255)),
        ("It means the world to us", 34, False, (110, 110, 110)),
        ("and helps other families discover it.", 34, False, (110, 110, 110)),
    ]
```

- [ ] **Step 4 : Lancer les tests write et vérifier qu'ils passent**

```bash
python -m pytest tests/test_config_io.py -v
```
Attendu : `5 passed`

- [ ] **Step 5 : Vérification manuelle — le fichier généré est lisible et importable**

```bash
python -c "
from pipeline.config_io import read_config, write_config
import tempfile, pathlib, sys

# Lire le livre 1 existant
data = read_config('book1-90s-legends')
print('title:', data['title'])
print('author:', data['author'])
print('chars:', len(data['characters']))
print('seq:', len(data['page_sequence']))
"
```
Attendu : affichage sans erreur des valeurs du livre 1.

- [ ] **Step 6 : Commit**

```bash
git add pipeline/config_io.py tests/test_config_io.py
git commit -m "feat: add config_io.write_config with template generation and tests"
```

---

## Task 3 — dashboard/app.py : API endpoints config

**Files:**
- Modify: `dashboard/app.py` (ajouter 3 routes + imports Pydantic)
- Create: `tests/test_api_config.py`

- [ ] **Step 1 : Écrire les tests API**

```python
# tests/test_api_config.py
import pathlib
import pytest
from fastapi.testclient import TestClient

FAKE_CONFIG = '''
import pathlib
TITLE    = "Test Book"
SUBTITLE = "Sub"
AUTHOR   = "Marco Belghiti"
TESTPEN  = "tp.png"
IMAGES_DIR = pathlib.Path(__file__).parent.parent.parent / "images" / "book-test"
CHARACTERS = [{"id": "hero", "name": "The Hero", "series": "S1", "prompt": "a hero"}]
PAGE_SEQUENCE = [("book_test_hero.png", "The Hero")]
TITLE_PAGE_LINES = [("Test Book", 120, True, (0, 0, 0))]
COPYRIGHT_PAGE_LINES = [("© 2026", 32, True, (40, 40, 40))]
BACK_PAGE_LINES = [("Thanks!", 55, True, (0, 0, 0))]
'''


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Patch ROOT dans config_io et app
    import pipeline.config_io as cio
    import dashboard.app as app_module
    monkeypatch.setattr(cio, "ROOT", tmp_path)
    monkeypatch.setattr(app_module, "ROOT", tmp_path)

    # Créer le faux livre
    book_dir = tmp_path / "books" / "book-test"
    book_dir.mkdir(parents=True)
    (book_dir / "config.py").write_text(FAKE_CONFIG)
    (tmp_path / "images" / "book-test").mkdir(parents=True)

    from dashboard.app import app
    return TestClient(app)


def test_get_config(client):
    res = client.get("/api/book/book-test/config")
    assert res.status_code == 200
    data = res.json()
    assert data["title"] == "Test Book"
    assert data["author"] == "Marco Belghiti"
    assert len(data["characters"]) == 1


def test_get_config_not_found(client):
    res = client.get("/api/book/nonexistent/config")
    assert res.status_code == 404


def test_put_config(client, tmp_path, monkeypatch):
    import pipeline.config_io as cio
    monkeypatch.setattr(cio, "ROOT", tmp_path)

    payload = {
        "title": "Updated Title",
        "subtitle": "Updated Sub",
        "author": "Marco Belghiti",
        "testpen": "tp.png",
        "images_folder": "book-test",
        "characters": [{"id": "hero", "name": "The Hero", "series": "S1", "prompt": "prompt"}],
        "page_sequence": [{"file": "book_test_hero.png", "label": "The Hero"}],
    }
    res = client.put("/api/book/book-test/config", json=payload)
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    # Vérifier que le fichier a été mis à jour
    verify = client.get("/api/book/book-test/config")
    assert verify.json()["title"] == "Updated Title"


def test_post_new_book(client, tmp_path, monkeypatch):
    import pipeline.config_io as cio
    monkeypatch.setattr(cio, "ROOT", tmp_path)

    payload = {
        "slug": "book3-test",
        "title": "New Book",
        "subtitle": "A new book",
        "author": "Marco Belghiti",
        "characters": [],
    }
    res = client.post("/api/books/new", json=payload)
    assert res.status_code == 200
    assert res.json()["slug"] == "book3-test"
    assert (tmp_path / "books" / "book3-test" / "config.py").exists()
    assert (tmp_path / "images" / "book3-test").exists()


def test_post_new_book_invalid_slug(client):
    payload = {"slug": "INVALID SLUG!", "title": "T", "subtitle": "S", "author": "A", "characters": []}
    res = client.post("/api/books/new", json=payload)
    assert res.status_code == 400


def test_post_new_book_duplicate(client, tmp_path, monkeypatch):
    import pipeline.config_io as cio
    monkeypatch.setattr(cio, "ROOT", tmp_path)
    payload = {"slug": "book-test", "title": "T", "subtitle": "S", "author": "A", "characters": []}
    res = client.post("/api/books/new", json=payload)
    assert res.status_code == 409
```

- [ ] **Step 2 : Lancer les tests pour vérifier qu'ils échouent**

```bash
python -m pytest tests/test_api_config.py -v
```
Attendu : `FAILED` — endpoints inexistants (404 ou ImportError)

- [ ] **Step 3 : Ajouter les imports et les modèles Pydantic dans app.py**

En haut de `dashboard/app.py`, après les imports existants, ajouter :

```python
import re
from pydantic import BaseModel
from fastapi import HTTPException
from pipeline.config_io import read_config, write_config


class CharacterModel(BaseModel):
    id: str
    name: str
    series: str
    prompt: str


class PageEntryModel(BaseModel):
    file: str
    label: str


class BookConfigModel(BaseModel):
    title: str
    subtitle: str
    author: str
    testpen: str = ""
    images_folder: str = ""
    characters: list[CharacterModel] = []
    page_sequence: list[PageEntryModel] = []


class NewBookModel(BaseModel):
    slug: str
    title: str
    subtitle: str
    author: str
    characters: list[CharacterModel] = []
```

- [ ] **Step 4 : Ajouter les 3 endpoints dans app.py**

Ajouter après les routes existantes (avant `if __name__ == "__main__":`) :

```python
@app.get("/api/book/{book_name}/config")
async def api_get_book_config(book_name: str):
    try:
        return read_config(book_name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Livre {book_name!r} introuvable")


@app.put("/api/book/{book_name}/config")
async def api_put_book_config(book_name: str, data: BookConfigModel):
    try:
        write_config(book_name, data.model_dump())
        return {"status": "ok"}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Livre {book_name!r} introuvable")


@app.post("/api/books/new")
async def api_new_book(data: NewBookModel):
    if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$', data.slug):
        raise HTTPException(status_code=400, detail="Slug invalide (alphanumérique + tirets)")
    book_dir = ROOT / "books" / data.slug
    if book_dir.exists():
        raise HTTPException(status_code=409, detail=f"Le livre {data.slug!r} existe déjà")
    book_dir.mkdir(parents=True)
    (ROOT / "images" / data.slug).mkdir(parents=True, exist_ok=True)
    write_config(data.slug, {
        "title":         data.title,
        "subtitle":      data.subtitle,
        "author":        data.author,
        "images_folder": data.slug,
        "characters":    [c.model_dump() for c in data.characters],
        "page_sequence": [],
    })
    return {"status": "ok", "slug": data.slug}


@app.get("/new-book", response_class=HTMLResponse)
async def new_book_page(request: Request):
    return templates.TemplateResponse(request=request, name="new_book.html", context={})
```

- [ ] **Step 5 : Lancer les tests API**

```bash
python -m pytest tests/test_api_config.py -v
```
Attendu : `6 passed`

- [ ] **Step 6 : Lancer tous les tests**

```bash
python -m pytest tests/ -v
```
Attendu : tous verts

- [ ] **Step 7 : Commit**

```bash
git add dashboard/app.py tests/test_api_config.py
git commit -m "feat: add config API endpoints (GET/PUT /config, POST /books/new)"
```

---

## Task 4 — book.html : onglet Config avec éditeur complet

**Files:**
- Modify: `dashboard/templates/book.html`

L'onglet Config a 3 sections : Identité, Personnages, PAGE_SEQUENCE. Tout est géré par un bloc `<script>` vanilla JS qui appelle l'API.

- [ ] **Step 1 : Remplacer book.html par la version avec onglets**

Remplacer le contenu complet de `dashboard/templates/book.html` :

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{{ book.title }} — KDP Dashboard</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50 text-gray-900 min-h-screen">

  <!-- Header -->
  <header class="bg-white border-b border-gray-200 px-6 py-4 flex items-center gap-4">
    <a href="/" class="text-gray-400 hover:text-gray-700 text-sm">← Dashboard</a>
    <div>
      <h1 class="text-lg font-bold">{{ book.title }}</h1>
      <p class="text-xs text-gray-400">{{ book_name }} · {{ book.author }}</p>
    </div>
  </header>

  <!-- Tabs -->
  <div class="bg-white border-b border-gray-200 px-6">
    <nav class="flex gap-6 text-sm">
      <button onclick="switchTab('status')" id="tab-status"
              class="py-3 border-b-2 border-gray-900 font-medium text-gray-900">
        Status
      </button>
      <button onclick="switchTab('config')" id="tab-config"
              class="py-3 border-b-2 border-transparent text-gray-400 hover:text-gray-700">
        ⚙️ Config
      </button>
    </nav>
  </div>

  <!-- ── TAB: STATUS ─────────────────────────────────────────────────────────── -->
  <div id="panel-status">
  <main class="max-w-5xl mx-auto px-6 py-8 space-y-8">

    <!-- Action bar -->
    <div class="flex flex-wrap gap-3">
      <button onclick="runAction('generate', '{{ book_name }}')"
              class="flex items-center gap-2 bg-indigo-600 text-white text-sm rounded-lg px-4 py-2 hover:bg-indigo-700 transition-colors">
        🤖 Generate All Images
      </button>
      <button onclick="runAction('clean', '{{ book_name }}')"
              class="flex items-center gap-2 bg-gray-700 text-white text-sm rounded-lg px-4 py-2 hover:bg-gray-600 transition-colors">
        🧹 Clean All Images
      </button>
      <button onclick="runAction('assemble', '{{ book_name }}')"
              class="flex items-center gap-2 bg-green-600 text-white text-sm rounded-lg px-4 py-2 hover:bg-green-700 transition-colors">
        ⚙️ Assemble PDF
      </button>
    </div>

    <!-- Stats -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
      <div class="bg-white border border-gray-200 rounded-xl p-4 text-center">
        <p class="text-3xl font-bold">{{ book.present }}</p>
        <p class="text-xs text-gray-500 mt-1">Images in sequence</p>
      </div>
      <div class="bg-white border border-gray-200 rounded-xl p-4 text-center">
        <p class="text-3xl font-bold {% if book.missing %}text-red-600{% endif %}">{{ book.missing | length }}</p>
        <p class="text-xs text-gray-500 mt-1">Missing</p>
      </div>
      <div class="bg-white border border-gray-200 rounded-xl p-4 text-center">
        <p class="text-3xl font-bold {% if book.suspicious %}text-yellow-600{% endif %}">{{ book.suspicious | length }}</p>
        <p class="text-xs text-gray-500 mt-1">⚠ Suspicious</p>
      </div>
      <div class="bg-white border border-gray-200 rounded-xl p-4 text-center">
        {% if book.pdf %}
          <p class="text-3xl font-bold text-green-600">✓</p>
          <p class="text-xs text-gray-500 mt-1">PDF {{ book.pdf.size_mb }} MB</p>
        {% else %}
          <p class="text-3xl font-bold text-gray-300">–</p>
          <p class="text-xs text-gray-500 mt-1">No PDF yet</p>
        {% endif %}
      </div>
    </div>

    {% if book.suspicious %}
    <div class="bg-yellow-50 border border-yellow-200 rounded-xl p-4 text-sm text-yellow-900">
      <p class="font-semibold mb-2">⚠ Possibly uncolorable (solid black fill detected)</p>
      <p class="text-xs text-yellow-700 mb-3">Small file size (&lt;150 KB) may indicate solid black fills.</p>
      <div class="flex flex-wrap gap-2">
        {% for fname in book.suspicious %}
        <button onclick="regenerate('{{ book_name }}', '{{ fname }}')"
                class="text-xs bg-yellow-200 text-yellow-900 rounded px-2 py-1 hover:bg-yellow-300">
          🔄 Regen {{ fname }}
        </button>
        {% endfor %}
      </div>
    </div>
    {% endif %}

    {% if book.missing %}
    <div class="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-900">
      <p class="font-semibold mb-2">❌ Missing images</p>
      <ul class="text-xs space-y-1">{% for f in book.missing %}<li class="font-mono">{{ f }}</li>{% endfor %}</ul>
    </div>
    {% endif %}

    <!-- Images table -->
    <div class="bg-white border border-gray-200 rounded-xl overflow-hidden">
      <div class="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
        <h2 class="font-semibold text-sm">Images in PAGE_SEQUENCE</h2>
        <span class="text-xs text-gray-400">{{ book.images_detail | length }} pages</span>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="bg-gray-50 text-xs text-gray-500 uppercase tracking-wide">
            <tr>
              <th class="px-4 py-2 text-left">#</th>
              <th class="px-4 py-2 text-left">File</th>
              <th class="px-4 py-2 text-left">Label</th>
              <th class="px-4 py-2 text-right">Size</th>
              <th class="px-4 py-2 text-center">Status</th>
              <th class="px-4 py-2 text-center">Actions</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100">
            {% for img in book.images_detail %}
            <tr class="hover:bg-gray-50 {% if img.file in book.suspicious %}bg-yellow-50{% endif %}">
              <td class="px-4 py-2 text-gray-400 text-xs">{{ loop.index }}</td>
              <td class="px-4 py-2 font-mono text-xs">{{ img.file }}</td>
              <td class="px-4 py-2 text-gray-700">{{ img.label }}</td>
              <td class="px-4 py-2 text-right text-xs {% if img.size_kb < 150 %}text-yellow-600 font-medium{% else %}text-gray-500{% endif %}">{{ img.size_kb }} KB</td>
              <td class="px-4 py-2 text-center">
                {% if img.file in book.suspicious %}
                  <span class="bg-yellow-100 text-yellow-800 text-xs px-2 py-0.5 rounded-full">⚠ Check</span>
                {% else %}
                  <span class="bg-green-100 text-green-800 text-xs px-2 py-0.5 rounded-full">✓ OK</span>
                {% endif %}
              </td>
              <td class="px-4 py-2 text-center">
                <button onclick="cleanFile('{{ book_name }}', '{{ img.file }}')"
                        class="text-xs text-gray-400 hover:text-gray-700 underline">clean</button>
              </td>
            </tr>
            {% endfor %}
            {% for f in book.missing %}
            <tr class="bg-red-50">
              <td class="px-4 py-2 text-gray-400 text-xs">–</td>
              <td class="px-4 py-2 font-mono text-xs text-red-600">{{ f }}</td>
              <td class="px-4 py-2 text-red-400">Missing</td>
              <td class="px-4 py-2 text-right text-xs text-red-400">–</td>
              <td class="px-4 py-2 text-center"><span class="bg-red-100 text-red-800 text-xs px-2 py-0.5 rounded-full">Missing</span></td>
              <td class="px-4 py-2 text-center">–</td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>

    {% if book.extra_images %}
    <div class="bg-white border border-gray-200 rounded-xl p-5">
      <h2 class="font-semibold text-sm mb-3">Generated but not in PAGE_SEQUENCE</h2>
      <div class="flex flex-wrap gap-2">
        {% for fname in book.extra_images %}
        <span class="bg-gray-100 text-gray-700 text-xs px-2 py-1 rounded font-mono">{{ fname }}</span>
        {% endfor %}
      </div>
      <p class="text-xs text-gray-400 mt-3">Add these to <code>books/{{ book_name }}/config.py → PAGE_SEQUENCE</code> to include them.</p>
    </div>
    {% endif %}

    <!-- Console -->
    <div id="console-wrapper" class="hidden">
      <div class="flex items-center justify-between mb-2">
        <h3 class="font-semibold text-sm" id="console-title">Output</h3>
        <button onclick="closeConsole()" class="text-xs text-gray-400 hover:text-gray-600">✕ Close</button>
      </div>
      <pre id="console-output"
           class="bg-gray-900 text-green-400 text-xs rounded-xl p-4 overflow-y-auto"
           style="max-height: 400px; min-height: 100px; font-family: 'Courier New', monospace;"></pre>
    </div>

  </main>
  </div>

  <!-- ── TAB: CONFIG ─────────────────────────────────────────────────────────── -->
  <div id="panel-config" class="hidden">
  <main class="max-w-4xl mx-auto px-6 py-8 space-y-8">

    <!-- Toast -->
    <div id="toast" class="hidden fixed top-4 right-4 bg-gray-900 text-white text-sm px-4 py-2 rounded-lg shadow-lg z-50"></div>

    <!-- Section A : Identité -->
    <div class="bg-white border border-gray-200 rounded-xl p-6 space-y-4">
      <h2 class="font-semibold text-sm">Identité</h2>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <label class="text-xs text-gray-500 block mb-1">Title</label>
          <input id="cfg-title" type="text" class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
        </div>
        <div>
          <label class="text-xs text-gray-500 block mb-1">Subtitle</label>
          <input id="cfg-subtitle" type="text" class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
        </div>
        <div>
          <label class="text-xs text-gray-500 block mb-1">Author (pen name)</label>
          <input id="cfg-author" type="text" class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
        </div>
      </div>
    </div>

    <!-- Section B : Personnages -->
    <div class="bg-white border border-gray-200 rounded-xl overflow-hidden">
      <div class="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
        <h2 class="font-semibold text-sm">Personnages <span id="char-count" class="text-gray-400 font-normal"></span></h2>
        <button onclick="addCharacterRow()"
                class="text-xs bg-indigo-600 text-white rounded-lg px-3 py-1.5 hover:bg-indigo-700">
          + Add Character
        </button>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="bg-gray-50 text-xs text-gray-500 uppercase tracking-wide">
            <tr>
              <th class="px-3 py-2 text-left w-24">ID</th>
              <th class="px-3 py-2 text-left w-36">Name</th>
              <th class="px-3 py-2 text-left w-36">Series</th>
              <th class="px-3 py-2 text-left">Prompt</th>
              <th class="px-3 py-2 text-center w-20">Order</th>
              <th class="px-3 py-2 text-center w-12"></th>
            </tr>
          </thead>
          <tbody id="characters-tbody" class="divide-y divide-gray-100"></tbody>
        </table>
      </div>
    </div>

    <!-- Section C : PAGE_SEQUENCE -->
    <div class="bg-white border border-gray-200 rounded-xl overflow-hidden">
      <div class="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
        <h2 class="font-semibold text-sm">PAGE_SEQUENCE <span id="seq-count" class="text-gray-400 font-normal"></span></h2>
        <p class="text-xs text-gray-400">Ordre des pages dans le PDF</p>
      </div>
      <div id="sequence-list" class="divide-y divide-gray-100"></div>
    </div>

    <!-- Save button -->
    <div class="flex justify-end">
      <button onclick="saveConfig('{{ book_name }}')"
              class="bg-gray-900 text-white text-sm rounded-lg px-6 py-2.5 hover:bg-gray-700 transition-colors">
        💾 Save Config
      </button>
    </div>

  </main>
  </div>

  <script>
    const BOOK_NAME = '{{ book_name }}';
    let configData = null;

    // ── Tabs ─────────────────────────────────────────────────────────────────
    function switchTab(tab) {
      document.getElementById('panel-status').classList.toggle('hidden', tab !== 'status');
      document.getElementById('panel-config').classList.toggle('hidden', tab !== 'config');
      document.getElementById('tab-status').className =
        tab === 'status'
          ? 'py-3 border-b-2 border-gray-900 font-medium text-gray-900'
          : 'py-3 border-b-2 border-transparent text-gray-400 hover:text-gray-700';
      document.getElementById('tab-config').className =
        tab === 'config'
          ? 'py-3 border-b-2 border-gray-900 font-medium text-gray-900'
          : 'py-3 border-b-2 border-transparent text-gray-400 hover:text-gray-700';
      if (tab === 'config' && !configData) loadConfig();
    }

    // ── Load config ──────────────────────────────────────────────────────────
    async function loadConfig() {
      const res = await fetch(`/api/book/${BOOK_NAME}/config`);
      configData = await res.json();
      document.getElementById('cfg-title').value    = configData.title;
      document.getElementById('cfg-subtitle').value = configData.subtitle;
      document.getElementById('cfg-author').value   = configData.author;
      renderCharacters(configData.characters);
      renderSequence(configData.page_sequence, configData.characters);
    }

    // ── Characters table ─────────────────────────────────────────────────────
    function renderCharacters(characters) {
      const tbody = document.getElementById('characters-tbody');
      tbody.innerHTML = '';
      characters.forEach((c, i) => tbody.appendChild(makeCharRow(c, i)));
      document.getElementById('char-count').textContent = `(${characters.length})`;
    }

    function makeCharRow(c, i) {
      const tr = document.createElement('tr');
      tr.className = 'hover:bg-gray-50';
      tr.dataset.index = i;
      tr.innerHTML = `
        <td class="px-3 py-2">
          <input type="text" value="${esc(c.id)}" placeholder="gojo"
                 class="w-full border border-gray-200 rounded px-2 py-1 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-indigo-400" data-field="id" />
        </td>
        <td class="px-3 py-2">
          <input type="text" value="${esc(c.name)}" placeholder="The Hero"
                 class="w-full border border-gray-200 rounded px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-400" data-field="name" />
        </td>
        <td class="px-3 py-2">
          <input type="text" value="${esc(c.series)}" placeholder="Series"
                 class="w-full border border-gray-200 rounded px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-400" data-field="series" />
        </td>
        <td class="px-3 py-2">
          <textarea rows="2" placeholder="Prompt Gemini..."
                    class="w-full border border-gray-200 rounded px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-400 resize-y" data-field="prompt">${esc(c.prompt)}</textarea>
        </td>
        <td class="px-3 py-2 text-center whitespace-nowrap">
          <button onclick="moveChar(${i}, -1)" class="text-gray-400 hover:text-gray-700 px-1">↑</button>
          <button onclick="moveChar(${i},  1)" class="text-gray-400 hover:text-gray-700 px-1">↓</button>
        </td>
        <td class="px-3 py-2 text-center">
          <button onclick="deleteChar(${i})" class="text-red-400 hover:text-red-600 text-xs">🗑</button>
        </td>`;
      return tr;
    }

    function collectCharacters() {
      const rows = document.querySelectorAll('#characters-tbody tr');
      return Array.from(rows).map(tr => ({
        id:     tr.querySelector('[data-field="id"]').value.trim(),
        name:   tr.querySelector('[data-field="name"]').value.trim(),
        series: tr.querySelector('[data-field="series"]').value.trim(),
        prompt: tr.querySelector('[data-field="prompt"]').value.trim(),
      }));
    }

    function addCharacterRow() {
      const chars = collectCharacters();
      chars.push({ id: '', name: '', series: '', prompt: '' });
      renderCharacters(chars);
    }

    function deleteChar(i) {
      const chars = collectCharacters();
      chars.splice(i, 1);
      renderCharacters(chars);
    }

    function moveChar(i, dir) {
      const chars = collectCharacters();
      const j = i + dir;
      if (j < 0 || j >= chars.length) return;
      [chars[i], chars[j]] = [chars[j], chars[i]];
      renderCharacters(chars);
    }

    // ── PAGE_SEQUENCE ────────────────────────────────────────────────────────
    function renderSequence(sequence, characters) {
      const list = document.getElementById('sequence-list');
      list.innerHTML = '';
      sequence.forEach((entry, i) => {
        const div = document.createElement('div');
        div.className = 'flex items-center gap-3 px-4 py-2 hover:bg-gray-50';
        div.dataset.index = i;
        div.innerHTML = `
          <span class="text-xs text-gray-400 w-5">${i + 1}</span>
          <span class="font-mono text-xs text-gray-600 w-48 truncate">${esc(entry.file)}</span>
          <input type="text" value="${esc(entry.label)}"
                 class="flex-1 border border-gray-200 rounded px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-400"
                 data-seq-label />
          <div class="flex gap-1">
            <button onclick="moveSeq(${i}, -1)" class="text-gray-400 hover:text-gray-700 text-xs px-1">↑</button>
            <button onclick="moveSeq(${i},  1)" class="text-gray-400 hover:text-gray-700 text-xs px-1">↓</button>
            <button onclick="deleteSeq(${i})" class="text-red-400 hover:text-red-600 text-xs px-1">🗑</button>
          </div>`;
        list.appendChild(div);
      });
      document.getElementById('seq-count').textContent = `(${sequence.length} pages)`;
    }

    function collectSequence() {
      const rows = document.querySelectorAll('#sequence-list [data-index]');
      const files = Array.from(document.querySelectorAll('#sequence-list .font-mono')).map(el => el.textContent.trim());
      const labels = Array.from(document.querySelectorAll('#sequence-list [data-seq-label]')).map(el => el.value.trim());
      return files.map((file, i) => ({ file, label: labels[i] }));
    }

    function moveSeq(i, dir) {
      const seq = collectSequence();
      const j = i + dir;
      if (j < 0 || j >= seq.length) return;
      [seq[i], seq[j]] = [seq[j], seq[i]];
      renderSequence(seq, []);
    }

    function deleteSeq(i) {
      const seq = collectSequence();
      seq.splice(i, 1);
      renderSequence(seq, []);
    }

    // ── Save ─────────────────────────────────────────────────────────────────
    async function saveConfig(bookName) {
      const payload = {
        title:         document.getElementById('cfg-title').value.trim(),
        subtitle:      document.getElementById('cfg-subtitle').value.trim(),
        author:        document.getElementById('cfg-author').value.trim(),
        testpen:       configData.testpen,
        images_folder: configData.images_folder,
        characters:    collectCharacters(),
        page_sequence: collectSequence(),
      };
      const res = await fetch(`/api/book/${bookName}/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        configData = null;  // force reload au prochain switch
        showToast('✅ Config sauvegardée');
      } else {
        showToast('❌ Erreur lors de la sauvegarde');
      }
    }

    // ── Toast ────────────────────────────────────────────────────────────────
    function showToast(msg) {
      const t = document.getElementById('toast');
      t.textContent = msg;
      t.classList.remove('hidden');
      setTimeout(() => t.classList.add('hidden'), 3000);
    }

    // ── Pipeline actions (onglet Status) ─────────────────────────────────────
    let activeSource = null;

    function runAction(action, bookName) {
      const urls = {
        generate: `/stream/generate/${bookName}`,
        clean:    `/stream/clean/${bookName}`,
        assemble: `/stream/assemble/${bookName}`,
      };
      const titles = {
        generate: `🤖 Generating images — ${bookName}`,
        clean:    `🧹 Cleaning images — ${bookName}`,
        assemble: `⚙️ Assembling PDF — ${bookName}`,
      };
      startStream(urls[action], titles[action]);
    }

    function cleanFile(bookName, filename) {
      startStream(`/stream/clean/${bookName}?filename=${encodeURIComponent(filename)}`,
                  `🧹 Cleaning ${filename}`);
    }

    function regenerate(bookName, filename) {
      const charId = filename.replace(/^book\d+_/, '').replace('.png', '');
      startStream(`/stream/generate/${bookName}?char_id=${charId}`,
                  `🔄 Regenerating ${filename}`);
    }

    function startStream(url, title) {
      const wrapper = document.getElementById('console-wrapper');
      const output  = document.getElementById('console-output');
      const titleEl = document.getElementById('console-title');
      wrapper.classList.remove('hidden');
      output.textContent = '';
      titleEl.textContent = title;
      wrapper.scrollIntoView({ behavior: 'smooth' });
      if (activeSource) activeSource.close();
      activeSource = new EventSource(url);
      activeSource.onmessage = (e) => {
        if (e.data === '[DONE]') {
          activeSource.close();
          output.textContent += '\n✅ Complete\n';
          setTimeout(() => location.reload(), 1500);
        } else {
          output.textContent += e.data + '\n';
        }
        output.scrollTop = output.scrollHeight;
      };
      activeSource.onerror = () => {
        output.textContent += '\n[Connection error]\n';
        activeSource.close();
      };
    }

    function closeConsole() {
      if (activeSource) { activeSource.close(); activeSource = null; }
      document.getElementById('console-wrapper').classList.add('hidden');
    }

    function esc(s) {
      return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }
  </script>
</body>
</html>
```

- [ ] **Step 2 : Vérifier que le dashboard se lance sans erreur**

```bash
cd /Users/mouadbelghiti/mo-projects/kidp
python3 dashboard/app.py
```
Attendu : `KDP Dashboard running at http://localhost:8000` sans traceback.

- [ ] **Step 3 : Tester manuellement dans le navigateur**

Ouvrir `http://localhost:8000/book/book1-90s-legends` :
- Vérifier que l'onglet "Status" affiche les données existantes
- Cliquer sur "⚙️ Config" → le formulaire se charge avec Title, Author etc.
- Modifier le champ Author, cliquer "Save Config" → toast "✅ Config sauvegardée"
- Vérifier que `books/book1-90s-legends/config.py` contient la nouvelle valeur

- [ ] **Step 4 : Commit**

```bash
git add dashboard/templates/book.html
git commit -m "feat: add Config tab to book detail page with identity/characters/sequence editor"
```

---

## Task 5 — index.html + new_book.html : wizard création livre

**Files:**
- Modify: `dashboard/templates/index.html` (bouton + New Book)
- Create: `dashboard/templates/new_book.html`

- [ ] **Step 1 : Ajouter le bouton "+ New Book" dans index.html**

Dans `dashboard/templates/index.html`, modifier le header pour ajouter le bouton :

```html
<!-- Remplacer la div de droite dans le header -->
<div class="flex items-center gap-4 text-sm text-gray-500">
  <span>{{ books | length }} book(s)</span>
  <a href="/new-book"
     class="bg-gray-900 text-white text-sm rounded-lg px-4 py-2 hover:bg-gray-700 transition-colors">
    + New Book
  </a>
</div>
```

- [ ] **Step 2 : Créer new_book.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>New Book — KDP Dashboard</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50 text-gray-900 min-h-screen">

  <header class="bg-white border-b border-gray-200 px-6 py-4 flex items-center gap-4">
    <a href="/" class="text-gray-400 hover:text-gray-700 text-sm">← Dashboard</a>
    <h1 class="text-lg font-bold">New Book</h1>
  </header>

  <main class="max-w-3xl mx-auto px-6 py-8 space-y-8">

    <!-- Toast -->
    <div id="toast" class="hidden fixed top-4 right-4 bg-gray-900 text-white text-sm px-4 py-2 rounded-lg shadow-lg z-50"></div>

    <!-- Étape 1 : Identité -->
    <div class="bg-white border border-gray-200 rounded-xl p-6 space-y-4">
      <h2 class="font-semibold text-sm">Étape 1 — Identité</h2>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label class="text-xs text-gray-500 block mb-1">Slug <span class="text-red-400">*</span></label>
          <input id="new-slug" type="text" placeholder="book3-shonen"
                 class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500" />
          <p class="text-xs text-gray-400 mt-1">Minuscules, chiffres, tirets. Ex: book3-shonen</p>
        </div>
        <div>
          <label class="text-xs text-gray-500 block mb-1">Author <span class="text-red-400">*</span></label>
          <input id="new-author" type="text" value="Marco Belghiti"
                 class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
        </div>
        <div class="md:col-span-2">
          <label class="text-xs text-gray-500 block mb-1">Title <span class="text-red-400">*</span></label>
          <input id="new-title" type="text" placeholder="Shonen Legends: Coloring Our Stories"
                 class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
        </div>
        <div class="md:col-span-2">
          <label class="text-xs text-gray-500 block mb-1">Subtitle</label>
          <input id="new-subtitle" type="text" placeholder="A coloring book for dads who never grew up"
                 class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
        </div>
      </div>
    </div>

    <!-- Étape 2 : Personnages -->
    <div class="bg-white border border-gray-200 rounded-xl overflow-hidden">
      <div class="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
        <h2 class="font-semibold text-sm">Étape 2 — Personnages <span id="new-char-count" class="text-gray-400 font-normal">(0)</span></h2>
        <button onclick="addNewCharRow()"
                class="text-xs bg-indigo-600 text-white rounded-lg px-3 py-1.5 hover:bg-indigo-700">
          + Add Character
        </button>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="bg-gray-50 text-xs text-gray-500 uppercase tracking-wide">
            <tr>
              <th class="px-3 py-2 text-left w-24">ID</th>
              <th class="px-3 py-2 text-left w-36">Name</th>
              <th class="px-3 py-2 text-left w-36">Series</th>
              <th class="px-3 py-2 text-left">Prompt</th>
              <th class="px-3 py-2 text-center w-12"></th>
            </tr>
          </thead>
          <tbody id="new-characters-tbody" class="divide-y divide-gray-100">
            <tr id="empty-row">
              <td colspan="5" class="px-4 py-8 text-center text-xs text-gray-400">
                Aucun personnage — cliquez "+ Add Character" pour commencer
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Submit -->
    <div class="flex justify-end gap-3">
      <a href="/" class="border border-gray-200 text-sm rounded-lg px-4 py-2 hover:bg-gray-50 transition-colors">
        Annuler
      </a>
      <button onclick="createBook()"
              class="bg-gray-900 text-white text-sm rounded-lg px-6 py-2.5 hover:bg-gray-700 transition-colors">
        ✅ Create Book
      </button>
    </div>

  </main>

  <script>
    let newChars = [];

    function addNewCharRow() {
      newChars.push({ id: '', name: '', series: '', prompt: '' });
      renderNewChars();
    }

    function deleteNewChar(i) {
      newChars.splice(i, 1);
      renderNewChars();
    }

    function renderNewChars() {
      const tbody = document.getElementById('new-characters-tbody');
      document.getElementById('empty-row')?.remove();
      tbody.innerHTML = '';
      if (newChars.length === 0) {
        tbody.innerHTML = '<tr id="empty-row"><td colspan="5" class="px-4 py-8 text-center text-xs text-gray-400">Aucun personnage — cliquez "+ Add Character" pour commencer</td></tr>';
      } else {
        newChars.forEach((c, i) => {
          const tr = document.createElement('tr');
          tr.className = 'hover:bg-gray-50';
          tr.innerHTML = `
            <td class="px-3 py-2"><input type="text" value="${esc(c.id)}" placeholder="gojo"
              oninput="newChars[${i}].id=this.value"
              class="w-full border border-gray-200 rounded px-2 py-1 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-indigo-400" /></td>
            <td class="px-3 py-2"><input type="text" value="${esc(c.name)}" placeholder="The Hero"
              oninput="newChars[${i}].name=this.value"
              class="w-full border border-gray-200 rounded px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-400" /></td>
            <td class="px-3 py-2"><input type="text" value="${esc(c.series)}" placeholder="Series"
              oninput="newChars[${i}].series=this.value"
              class="w-full border border-gray-200 rounded px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-400" /></td>
            <td class="px-3 py-2"><textarea rows="2" placeholder="Prompt Gemini..."
              oninput="newChars[${i}].prompt=this.value"
              class="w-full border border-gray-200 rounded px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-400 resize-y">${esc(c.prompt)}</textarea></td>
            <td class="px-3 py-2 text-center">
              <button onclick="deleteNewChar(${i})" class="text-red-400 hover:text-red-600 text-xs">🗑</button>
            </td>`;
          tbody.appendChild(tr);
        });
      }
      document.getElementById('new-char-count').textContent = `(${newChars.length})`;
    }

    async function createBook() {
      const slug     = document.getElementById('new-slug').value.trim();
      const title    = document.getElementById('new-title').value.trim();
      const subtitle = document.getElementById('new-subtitle').value.trim();
      const author   = document.getElementById('new-author').value.trim();

      if (!slug || !title || !author) {
        showToast('❌ Slug, Title et Author sont obligatoires');
        return;
      }
      if (!/^[a-z0-9][a-z0-9-]*[a-z0-9]$/.test(slug)) {
        showToast('❌ Slug invalide — minuscules, chiffres et tirets uniquement');
        return;
      }

      const res = await fetch('/api/books/new', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ slug, title, subtitle, author, characters: newChars }),
      });

      if (res.ok) {
        const data = await res.json();
        window.location.href = `/book/${data.slug}`;
      } else {
        const err = await res.json();
        showToast(`❌ ${err.detail || 'Erreur lors de la création'}`);
      }
    }

    function showToast(msg) {
      const t = document.getElementById('toast');
      t.textContent = msg;
      t.classList.remove('hidden');
      setTimeout(() => t.classList.add('hidden'), 3500);
    }

    function esc(s) {
      return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }
  </script>
</body>
</html>
```

- [ ] **Step 3 : Vérifier le wizard dans le navigateur**

Ouvrir `http://localhost:8000` → cliquer "+ New Book" :
- Remplir slug `book3-test`, title, author
- Ajouter 1 personnage
- Cliquer "Create Book" → redirect vers `/book/book3-test`
- Vérifier que `books/book3-test/config.py` et `images/book3-test/` existent

```bash
ls /Users/mouadbelghiti/mo-projects/kidp/books/book3-test/
ls /Users/mouadbelghiti/mo-projects/kidp/images/book3-test/
python3 -c "from pipeline.config_io import read_config; print(read_config('book3-test')['title'])"
```
Attendu : dossiers créés, title correct.

Supprimer le livre de test :
```bash
rm -rf /Users/mouadbelghiti/mo-projects/kidp/books/book3-test
rm -rf /Users/mouadbelghiti/mo-projects/kidp/images/book3-test
```

- [ ] **Step 4 : Lancer la suite de tests complète**

```bash
python -m pytest tests/ -v
```
Attendu : tous verts.

- [ ] **Step 5 : Commit final**

```bash
git add dashboard/templates/index.html dashboard/templates/new_book.html
git commit -m "feat: add New Book wizard with slug/identity/characters form"
```

---

## Récapitulatif des fichiers

| Fichier | Action | Contenu |
|---|---|---|
| `pipeline/config_io.py` | Créé | read_config, write_config, _render_config, defaults |
| `tests/__init__.py` | Créé | vide |
| `tests/test_config_io.py` | Créé | 5 tests unitaires |
| `tests/test_api_config.py` | Créé | 6 tests API |
| `dashboard/app.py` | Modifié | +3 endpoints REST + route /new-book |
| `dashboard/templates/book.html` | Modifié | Onglets Status/Config + éditeur complet |
| `dashboard/templates/index.html` | Modifié | Bouton "+ New Book" |
| `dashboard/templates/new_book.html` | Créé | Wizard création livre |
