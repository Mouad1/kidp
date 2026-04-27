# Prompt Builder v2 — Design Spec

**Date:** 2026-04-17  
**Status:** Approved

## Overview

Amélioration du prompt builder dans le dashboard KDP. Le textarea brut de chaque personnage est remplacé par un panneau latéral structuré avec deux modes (Solo / Groupe), live preview, et tag system étendu.

## Layout

L'onglet Config passe en `flex gap-6` :

- **Colonne gauche (40%)** — table des personnages inchangée, chaque ligne cliquable (highlight de la ligne active)
- **Colonne droite (60%)** — panneau Prompt Builder, visible dès qu'un personnage est sélectionné, sinon état vide "← Sélectionne un personnage"

## Mode Solo

Déclenché au clic sur une ligne de la table personnages.

### Champs

| Champ | Type | Notes |
|---|---|---|
| Description physique | `textarea` 3 lignes | Corps principal, sans noms de couleur |
| Style | Tags multi-select | `STYLE_TAGS` existants |
| Pose | Tags multi-select | `POSE_TAGS` existants |
| Éléments | Tags multi-select | `ELEMENT_TAGS` existants |
| Thème | Tags multi-select | Nouveau : "Art Nouveau", "Mandala-infused", "Kawaii", "Geometric", "Baroque" |
| Notes supplémentaires | `textarea` 2 lignes | Ajouté en fin de description |

### UI fixe

- Badge readonly No-Go : `⛔ Zero shading · Zero gray fills · Zero gradients · Zero black fills`
- Live preview : zone `<pre>` fond sombre, mise à jour JS en temps réel (aucun appel réseau)
- Bouton "💾 Apply" — écrit le prompt assemblé dans le champ `prompt` du personnage en mémoire

## Mode Groupe

Déclenché par bouton "+ Créer page de groupe" au-dessus de la table.

### Champs

| Champ | Type | Notes |
|---|---|---|
| Personnages | Multi-select (pills/checkbox) | Parmi les personnages du livre, N sans limite |
| Descriptions | Readonly par personnage | Tirées de la config, non modifiables ici |
| Style | Tags partagés | `STYLE_TAGS` |
| Éléments | Tags partagés | `ELEMENT_TAGS` |
| Thème | Tags partagés | `THEME_TAGS` |
| Dynamique de groupe | Tags (remplace Pose) | "back-to-back", "facing each other", "battle formation", "side by side", "walking together" |
| Notes supplémentaires | `textarea` 2 lignes | |

### Prompt assemblé

```
"[Desc A], alongside [Desc B], alongside [Desc C], [groupe dynamic], [tags partagés]…"
```

### Action

Bouton "💾 Ajouter à PAGE_SEQUENCE" — crée une nouvelle entrée dans `page_sequence` avec un nom de fichier généré (`bookN_group_<ids>.png`) et ajoute le prompt en config.

## Modifications techniques

### `pipeline/prompt.py`

- Ajouter `THEME_TAGS = ["Art Nouveau", "Mandala-infused", "Kawaii", "Geometric", "Baroque"]`
- Ajouter `GROUP_DYNAMICS = ["back-to-back", "facing each other", "battle formation", "side by side", "walking together"]`
- Ajouter `build_group_prompt(characters: list[dict], style_tags, element_tags, theme_tags, group_dynamic, extra_notes)` → retourne le prompt assemblé multi-personnages
- Mettre à jour `build_prompt()` : ajouter param `theme_tags`

### `dashboard/app.py`

- Ajouter `GET /api/prompt/tags` → retourne `{style, pose, elements, theme, group_dynamics}`

### `dashboard/templates/book.html`

- Layout flex dans le panel Config
- Panneau latéral JS pur (Tailwind uniquement, pas de dépendance supplémentaire)
- Logique JS : sélection personnage → mode solo, bouton groupe → mode groupe, live preview temps réel

## Contraintes

- Pas de nouvelle dépendance npm/pip
- Le prompt final stocké dans `characters[i].prompt` reste une string plate (compatible avec le pipeline existant)
- Les pages de groupe apparaissent dans `PAGE_SEQUENCE` comme des entrées normales
