# KDP Pipeline — Backlog

> Toutes les idées, features, et bugs capturés ici. Statuts : `[ ]` à faire · `[~]` en cours · `[x]` fait.
> Ajouter une idée → une ligne avec `[ ]` dans la section qui correspond.

---

## 🚀 En cours

_(rien pour l'instant)_

---

## 📋 À faire — Dashboard

- [ ] **Batch regen** — sélectionner plusieurs images suspectes et les régénérer en une fois
- [ ] **Diff avant/après** — afficher l'ancienne image vs la nouvelle après regen
- [ ] **Historique des générations** — log des prompts utilisés avec date/coût estimé
- [x] **Bouton "Open PDF"** — ouvrir le PDF final directement depuis le dashboard
- [ ] **Iteration sur le prompt builder** — tester les cas d'usage réels et affiner les tags/thèmes

---

## 📋 À faire — Pipeline

- [ ] **pipeline/generate_scenes.py** — générer les 6 pages de scènes de groupe automatiquement
- [ ] **pipeline/clean_all.py** — clean batch pour tout un livre (wrap de clean.py)
- [ ] **Validation qualité** — détection automatique des fills noirs (analyse pixels, pas juste taille fichier)
- [ ] **pipeline/publish.py** — upload KDP via Selenium (Phase 2 post-traction)
- [ ] **pipeline/clean_all.py** — clean batch amélioré avec reporting

---

## 📋 À faire — Couverture & Contenu éditorial

- [ ] **Cover generator (IA)** — générer la couverture colorée via Gemini (personnage principal + titre) puis export PNG 300 DPI pour Canva full-wrap ; intégrer un bouton "🎨 Generate Cover" dans le dashboard
- [ ] **Back cover content** — pour chaque livre, générer automatiquement : accroche marketing (2–3 lignes), description Amazon (150–200 mots), 5 bullet points, et le texte à imprimer au dos ; stocker dans `books/*/back_cover.md`
- [ ] **Cover pipeline** — `pipeline/cover.py` : prend un personnage, génère l'image de couverture (full body, vibrant colors, bold background), applique le titre en overlay, export PDF KDP-ready (full-wrap = recto + dos + tranche)
- [ ] **Dashboard — onglet Éditorial** — UI pour éditer/générer le contenu back cover et preview de la couverture avant export

---

## 📋 À faire — KDP / Business

- [ ] **Pen name** — choisir + mettre dans les deux config.py → AUTHOR
- [ ] **Cover Book 1** — Canva full-wrap (59 pages) → output/book1-90s-legends_cover_FULLWRAP.pdf
- [ ] **Cover Book 2** — Canva full-wrap (51 pages) → output/book2-modern-anime_cover_FULLWRAP.pdf
- [ ] **KDP upload Book 1** — manuscript + cover + metadata complets (titre, sous-titre, description, keywords x7, catégories x2, prix)
- [ ] **KDP upload Book 2** — idem
- [ ] **Book 3** — niche research + nouvelle config.py

---

## 📋 À faire — Publication KDP automatisée

- [ ] **Étude faisabilité KDP automation** — cartographier le flow de publication KDP (login → New Title → upload manuscript → upload cover → metadata → pricing → publish) ; identifier les étapes bloquantes (CAPTCHA, 2FA, anti-bot)
- [ ] **pipeline/publish.py (Playwright)** — automatiser la publication KDP : login, création titre, upload PDF manuscript + cover, saisie metadata depuis `books/*/config.py`, soumission ; stocker les credentials dans `.env.local`
- [x] **KDP metadata store** — ajouter dans `config.py` les champs : `description`, `keywords` (liste 7), `categories` (liste 2 BISAC), `price_usd`, `amazon_asin` ; exposés dans le dashboard pour édition (panel idle)
- [ ] **Dashboard — bouton "🚀 Publish to KDP"** — déclenche `pipeline/publish.py` avec streaming du log ; affiche le lien ASIN après publication réussie

---

## 📋 À faire — BookBolt / Outils KDP tiers

- [ ] **Étude faisabilité BookBolt** — analyser si BookBolt expose une API ou si l'accès passe uniquement par l'UI web ; tester si Playwright peut se connecter au dashboard BookBolt (login + navigation) sans être bloqué par anti-bot
- [ ] **BookBolt via Playwright** — si faisable : automatiser la recherche de niches (keyword research, BSR tracker, competition score) depuis BookBolt ; parser les résultats et les stocker dans `data/niche_research.json`
- [ ] **BookBolt via extension Claude** — explorer l'option Claude + MCP Browser pour piloter BookBolt via Chrome extension plutôt que Playwright ; avantage : session déjà authentifiée du navigateur utilisateur, pas de détection bot
- [ ] **Niche tracker dashboard** — onglet dans le dashboard affichant les résultats BookBolt (BSR, competition, monthly sales estimate) pour les niches ciblées ; mettre à jour manuellement ou automatiquement

---

## 💡 Idées / Brainstorm

- [ ] **Multi-style preview** — générer 3 variantes du même personnage avec styles différents pour choisir
- [ ] **Niche tracker intégré** — onglet dashboard pour suivre les BSR Amazon par livre
- [ ] **Auto-keywords** — suggérer les 7 keywords KDP basé sur le titre et les personnages
- [ ] **Scene builder** — UI pour composer les pages de groupe (choisir N personnages → générer scene)
- [ ] **Export ZIP** — télécharger toutes les images d'un livre en un clic

---

## ✅ Fait

- [x] Pipeline Karpathy restructuré (pipeline/assemble.py + clean.py + books/*/config.py)
- [x] Interior PDF Book 1 — 59p, 0 fonts, 83.8 MB
- [x] Interior PDF Book 2 — 51p, 0 fonts, 32.8 MB
- [x] Génération automatique via API Gemini (pipeline/generate.py)
- [x] Dashboard v1 — overview + streaming terminal + stats par livre
- [x] Skills installés — superpowers + frontend-design + web-design-guidelines + memory
- [x] CLAUDE.md projet avec règles critiques
- [x] Prompt Builder v2 — panneau latéral solo/groupe, tags (style/pose/éléments/thème/dynamique), live preview
- [x] Dashboard redesign — page unique sans onglets, flex table+panneau, image preview inline, status badges
- [x] PAGE_SEQUENCE auto-générée depuis CHARACTERS (plus de gestion manuelle)
- [x] Endpoint `/images/<book>/<file>` avec protection path traversal
- [x] GEMINI_API_KEY via `.env.local` + `make dashboard` + `run.sh`
- [x] Bouton "🤖 Save & Generate" — sauvegarde + génération en un clic
