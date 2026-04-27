# Dashboard Redesign — Design Spec

**Date:** 2026-04-18  
**Status:** Approved

## Objectif

Refondre la page livre `/book/<slug>` en une vue unique sans onglets : table de personnages à gauche, panneau contextuel à droite. Éliminer la redondance Status/Config, ajouter la preview image inline, clarifier les labels d'action.

## Structure générale

Page unique, pas d'onglets. Layout :

```
┌─── Header ────────────────────────────────────────────────────┐
│  Titre · Auteur                                               │
│  [🤖 Generate All] [🔧 Fix Images] [📄 Build PDF]            │
│  24 images · 2 missing · 1 ⚠ suspicious · PDF ✓ 12.3 MB     │
├───────────────────────────────────────────────────────────────┤
│  LEFT TABLE (45%)        │  RIGHT PANEL (55%)                 │
│  Characters              │  Idle: Identity fields             │
│  # / ID / Nom / Status   │  Click char: preview + builder     │
│  ↑↓ par ligne            │  "+ Groupe": group builder         │
│  [+ Perso] [+ Groupe]    │                                    │
├───────────────────────────────────────────────────────────────┤
│  [💾 Save Config]                                             │
│  Console streaming (hidden until action)                      │
└───────────────────────────────────────────────────────────────┘
```

## Table des personnages (gauche, 45%)

### Colonnes

| Col | Contenu |
|---|---|
| # | Numéro de page PDF (position dans la liste) |
| ID | Identifiant court (font-mono) |
| Nom | Nom du personnage |
| Status | Badge calculé depuis le fichier image sur disque |
| ↑↓ | Boutons de réordonnancement |

### Badges Status

- `✓ OK` (vert) — fichier existe et taille ≥ 150 KB
- `⚠ 142 KB` (jaune) — fichier existe mais taille < 150 KB (possible black fill)
- `❌ Missing` (rouge) — fichier absent

### Comportement

- Clic sur une ligne → ouvre le panneau Solo à droite + highlight de la ligne
- Ligne active : fond `bg-indigo-50`, bordure gauche indigo
- Boutons `+ Perso` et `+ Groupe` en en-tête de la table

### PAGE_SEQUENCE

Supprimée en tant que section UI. L'ordre des `CHARACTERS` dans la table **est** l'ordre PDF. Au Save, `write_config()` génère automatiquement `PAGE_SEQUENCE` depuis `CHARACTERS` (filename = `{book_name}_{char_id}.png`, label = `char.name`).

## Panneau droit (55%)

### État Idle (rien de sélectionné)

Affiche les champs Identity directement éditables :
- Title, Subtitle, Author (inputs)
- Message hint : "Sélectionne un personnage pour éditer son prompt et voir l'image"

### Mode Solo (clic sur un personnage)

```
┌─ Nom · ID ──────────────── [🔄 Regen] [🗑 Delete] ─┐
│                                                      │
│  Image preview (si fichier existe) :                 │
│    <img src="/images/<book>/<file>"> max-h-64        │
│    Badge status + taille KB                          │
│  Placeholder gris (si missing) :                     │
│    "❌ Image non générée"                            │
│                                                      │
│  ── Prompt Builder ─────────────────────────────── │
│  Description physique (textarea)                    │
│  Style · Pose · Éléments · Thème (tags pills)       │
│  Notes supplémentaires (textarea)                   │
│  ⛔ Zero shading · Zero gray fills · ...            │
│  Live preview (pre fond sombre)                     │
│  [💾 Apply prompt]                                  │
└──────────────────────────────────────────────────────┘
```

Actions dans l'en-tête du panneau :
- **🔄 Regen** → lance `/stream/generate/<book>?char_id=<id>` (console s'ouvre)
- **🗑 Delete** → confirmation inline, supprime la ligne de la table

### Mode Groupe (clic sur "+ Groupe")

Inchangé par rapport au spec prompt-builder-v2 :
- Multi-select personnages avec description par personnage
- Tags partagés (Style, Éléments, Thème)
- Dynamique de groupe
- Notes + No-Go badge + Live preview
- Bouton "➕ Ajouter à la liste"

## Actions globales

| Bouton | Label | Action |
|---|---|---|
| 🤖 Generate All | Generate All | `/stream/generate/<book>` |
| 🔧 Fix Images | Fix Images | `/stream/clean/<book>` |
| 📄 Build PDF | Build PDF | `/stream/assemble/<book>` |

Labels remplacent "Clean All" et "Assemble PDF" pour plus de clarté.

## Ligne de stats

Remplace les 4 cards actuelles. Format inline compact :
```
24 images · 2 missing · 1 ⚠ suspicious · PDF ✓ 12.3 MB
```
ou si pas de PDF :
```
24 images · 2 missing · 1 ⚠ suspicious · No PDF yet
```

## Serving des images

Nouveau endpoint FastAPI pour servir les images PNG du livre :
```
GET /images/<book_name>/<filename>
```
Retourne le fichier PNG depuis `IMAGES_DIR`. Utilisé par le `<img>` du panneau Solo.

## Backend — write_config() adaptation

Dans `pipeline/config_io.py`, `write_config()` génère `PAGE_SEQUENCE` automatiquement :

```python
page_sequence = [
    {"file": f"{book_name}_{c['id']}.png", "label": c["name"]}
    for c in characters
]
```

Si un `id` commence par `group_`, le filename est `{book_name}_{id}.png` (déjà correct).

## Fichiers modifiés

| Fichier | Changement |
|---|---|
| `dashboard/templates/book.html` | Refonte complète — page unique, table + panneau |
| `dashboard/app.py` | + endpoint `/images/<book>/<file>`, labels actions inchangés côté API |
| `pipeline/config_io.py` | `write_config()` auto-génère PAGE_SEQUENCE depuis CHARACTERS |
