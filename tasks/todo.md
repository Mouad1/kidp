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
