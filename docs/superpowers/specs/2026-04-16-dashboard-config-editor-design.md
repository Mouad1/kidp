# Design Spec — Dashboard Config Editor

**Date:** 2026-04-16  
**Author:** Marco Belghiti  
**Status:** Approved

---

## Objectif

Transformer le dashboard KDP en panneau de contrôle complet : éditer les configs de livres (metadata, personnages, PAGE_SEQUENCE), créer de nouveaux livres, sans jamais toucher au code.

---

## Architecture générale

### Nouveaux endpoints FastAPI

| Méthode | Route | Description |
|---|---|---|
| `GET` | `/api/book/{name}/config` | Lit config.py → JSON |
| `PUT` | `/api/book/{name}/config` | JSON → écrit config.py |
| `POST` | `/api/books/new` | Crée un nouveau livre depuis template |

### Nouveau module

`pipeline/config_io.py` — sérialisation / désérialisation des configs :
- `read_config(book_name) → dict` : utilise `importlib` (déjà présent dans `app.py`)
- `write_config(book_name, data: dict)` : régénère `config.py` depuis un template string Python

### Templates Jinja2 modifiés

- `dashboard/templates/index.html` — ajout bouton **"+ New Book"**
- `dashboard/templates/book.html` — ajout onglet **"Config"**
- `dashboard/templates/book_config.html` — contenu de l'onglet config (ou inline)
- `dashboard/templates/new_book.html` — wizard création livre

---

## Détail des fonctionnalités

### 1. Éditeur identité du livre

Champs simples dans l'onglet Config :
- `TITLE` (text input)
- `SUBTITLE` (text input)
- `AUTHOR` (text input, pen name)

Bouton **Save Identity** → `PUT /api/book/{name}/config` avec payload partiel.

### 2. Gestionnaire de personnages

Tableau HTML avec une ligne par personnage :

| id | name | series | prompt | Actions |
|---|---|---|---|---|
| `gojo` | The Boundless... | Jujutsu Kaisen | *(textarea)* | ↑ ↓ 🗑 |

- **Ajouter** : bouton "+ Add Character" → nouvelle ligne vide
- **Supprimer** : bouton 🗑 par ligne
- **Réordonner** : boutons ↑↓ par ligne
- Le champ `prompt` est un `<textarea>` extensible (champ le plus critique)

Bouton **Save Characters** → `PUT /api/book/{name}/config`.

### 3. Gestionnaire PAGE_SEQUENCE

Liste ordonnée des images du livre :
- Checkbox par image (inclus/exclu)
- Champ `label` éditable (texte affiché dans le PDF)
- Aperçu du statut fichier : `book2_gojo.png ✅` ou `❌ manquant`
- Boutons ↑↓ pour réordonner

Bouton **Save Sequence** → `PUT /api/book/{name}/config`.

### 4. Wizard "New Book"

**Étape 1 — Identité**
- slug (ex: `book3-shonen`) → validé: alphanumérique + tirets
- title, subtitle, author

**Étape 2 — Personnages**
- Tableau vide avec bouton "+ Add Character"
- Même interface que le gestionnaire de personnages existant

**Submit** → `POST /api/books/new` :
- Crée `books/{slug}/config.py` depuis template
- Crée `images/{slug}/` (dossier vide)
- Redirige vers `/book/{slug}`

---

## Ce qui n'est PAS inclus

- Édition de `TITLE_PAGE_LINES`, `COPYRIGHT_PAGE_LINES`, `BACK_PAGE_LINES` (trop complexe, faible valeur)
- Aucune nouvelle dépendance Python
- Le pipeline generate/clean/assemble reste inchangé

---

## Écriture de config.py

`config_io.write_config()` régénère le fichier complet depuis un template f-string. Avantages :
- Pas de manipulation d'AST
- Format toujours propre et lisible
- Les sections TITLE_PAGE_LINES / COPYRIGHT / BACK sont préservées telles quelles (lues et réécrites verbatim)

---

## Diagrammes

Voir `docs/diagrams/` pour les diagrammes Mermaid détaillés.
