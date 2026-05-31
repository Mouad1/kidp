# KDP — Roadmap

## Book 1: 90s Legends (En cours)

- [x] Niche research — anime coloring book for dads (millennial)
- [x] 27 images générées + nettoyées (Gemini, 1 personnage/prompt)
- [x] Pipeline Karpathy restructuré (pipeline/assemble.py + clean.py + books/*/config.py)
- [x] Interior PDF — `output/book1-90s-legends_interior_FINAL.pdf` (59p, 0 fonts)
- [ ] Pen name — choisir + mettre dans `books/book1-90s-legends/config.py → AUTHOR`
- [ ] Cover full-wrap PDF — Canva ou KDP Cover Creator (voir BOOK_PROCESS.md Step 3)
- [ ] KDP upload — manuscript + cover + metadata
- [ ] Publier sur Amazon US + UK

## Book 2: Modern Anime 2020s

- [x] Config + character roster défini (`books/book2-modern-anime/config.py`)
- [x] 2 images générées (flame_pillar, water_breather)
- [ ] Générer les 13 images restantes dans Gemini (prompts dans config.py)
- [ ] Générer 5-6 scene pages (groupes de personnages)
- [ ] Générer book2_testpen.png
- [ ] Nettoyer artifacts + crop portrait si nécessaire
- [ ] Assembler le PDF
- [ ] Cover + KDP upload

## Pipeline automation (Phase 2 — après 5 ventes)

- [ ] `pipeline/generate.py` — appel API Gemini (actuellement manuel)
- [ ] `pipeline/clean_all.py` — clean batch pour un livre entier
- [ ] `pipeline/publish.py` — upload KDP via Selenium

## StoryForge — livres persos depuis photos réelles

Module communautaire réutilisable. Voir `README.storyforge.md`.

### Fait

- [x] `storyforge/` — types, templates (JSON + variables + tokens réservés HERO/HERO_NAME)
- [x] Engine pur `resolve(template, variables, hero)` → `list[PageSpec]`
- [x] Identity — `build_hero` depuis 1–3 photos + portrait canonique de référence (consistance)
- [x] `generate_page` + `build_book` → `books/<name>/config.py` réutilisé par la pipeline
- [x] DI via `ImageGenerator` Protocol + `FakeImageGenerator` (tests 100% offline)
- [x] `GeminiBackend` — génération image + analyse photo
- [x] Endpoints dashboard (`/api/storyforge/*`, SSE `/stream/storyforge/*`)
- [x] UI `/storybook` — flow 3 étapes, drag-drop photos, SSE, zéro refresh
- [x] Template exemple `brave-little-explorer` + guide communauté `README.storyforge.md`
- [x] 31 tests (types, templates, engine, identity, generator, builder, backend, API, public API)

### À faire

- [ ] Templates supplémentaires (anniversaire, dodo, première rentrée, etc.)
- [ ] Mode `lineart` testé bout-en-bout (livre de coloriage perso)
- [ ] Packaging pip installable (`pip install storyforge`) pour partage communautaire
- [ ] Galerie de previews des pages dans l'UI avant build final
- [ ] Régénération d'une page seule depuis l'UI

