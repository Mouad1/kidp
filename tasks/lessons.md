# Lessons — KDP Pipeline

## Image generation

- **1 personnage = 1 prompt** — la génération en grille (4×2, 4×6) produit des personnages mal alignés et de mauvaise qualité. Toujours générer un seul personnage par prompt.
- **Zones noires non coloriables** — si le prompt mentionne des couleurs sombres ("black coat", "dark armor", "shadow"), Gemini remplit ces zones en noir solide. Le résultat est impossible à colorier. Règle : ne jamais mentionner de couleurs dans les prompts de personnages — décrire la forme/texture uniquement (ex: "long coat with detailed patterns" au lieu de "black coat"). Le template dans `pipeline/generate.py` contient déjà "CRITICAL: zero black fills" mais le prompt individuel du personnage doit aussi éviter tout mot de couleur sombre.
- **Format paysage** — Gemini génère souvent en 2816×1536 (paysage). Utiliser `pipeline/clean.py --crop-portrait` pour recadrer. L'algo centre le crop sur le centroïde horizontal des pixels sombres.
- **Artefacts courants** — tête flottante top-left, logo Gemini (étoile 4 branches), texte bas de page. Utiliser `--auto` pour les coins ou `--zones "x1,y1,x2,y2"` pour des zones précises.
- **Cohérence de style** — commencer les prompts avec "Same art style as previous image:" pour enchaîner les personnages avec un style uniforme.

## PDF / KDP

- **Jamais reportlab pour l'intérieur KDP** — reportlab injecte une référence Helvetica en boilerplate PDF même sans aucun texte. img2pdf + PIL (texte rendu en pixels) = 0 font ref = 0 erreur KDP.
- **img2pdf produit des PDFs lourds** — 83 MB pour 59 pages est normal (images full res non compressées). La limite KDP est 650 MB, pas de problème.
- **Tester le PDF** — après chaque assemblage, vérifier `Font refs in PDF: 0 [clean]` dans la sortie du script.

## Catégories KDP

- **Ne jamais utiliser "Juvenile Nonfiction"** — ces livres ciblent des adultes millennials. Utiliser : Arts & Photography > Drawing > Manga + Adult Coloring Books.

## Architecture

- **config.py par livre** — chaque livre est autonome. Le pipeline lit n'importe quel config.py sans modification. Ajouter un livre = copier le dossier + éditer config.py.
- **IMAGES_DIR relatif** — utiliser `pathlib.Path(__file__).parent.parent.parent / "images" / "<dossier>"` pour que le projet soit portable.
- **PAGE_SEQUENCE = source de vérité** — l'ordre des pages, les labels, les noms de fichiers. Tout part de là.
- **Story Images vs Coloring Pages**: `pipeline/generate.py` applies a forced B&W lineart conversion and contamination check (`cross_color_contamination` > `strip_colors`). For a `story` category, it is critical to **bypass** these cleanups so the final AI-generated children's book illustrations remain fully colored.
- **Dynamic Prompts**: `pipeline/prompt.py` has a rigid global `_BASE_TEMPLATE` enforcing "PURE BLACK AND WHITE". A separate `build_story_prompt` template must be used for stories to ensure artistic harmony and proper colors.
- **Lost Generations (Only 1st Page)**: This occurs when the `config.py` did not successfully synchronize the `PAGES` array from the dashboard before `generate.py` ran. A resilient dashboard saves (`PUT` vs `POST` routing fix) ensures all pages are written, so the backend loop sees everything.
- **UI Overflow**: Wrapping HTML structures that employ Tailwind's `overflow-y-auto flex-1` must be meticulously checked for rogue `</div>` closures, which can break scrolling and truncate the bottom contents of a layout.
- **Granular Generation**: Passed specific IDs (page numbers) straight to generative endpoints (`generate.py --id <item>`) to provide item-level regeneration instead of batch-ony runs.
- **PDF Layout Modification**: Text logic was extracted to `pipeline/draw_utils.py` handling exact font width checking so lines break correctly (`draw_text_wrapped`) across varying font lengths when dealing with multilingual text on storybook images.
- **Introduction and Outro Pages**: New functions `make_intro_page` and `make_values_page` assemble fully autonomous custom pages using `img2pdf` compatibility formatting while strictly abiding by the 0-font insertion rule by utilizing PIL directly on blank canvas masks.
- **CSS Grid/Flex Heights**: When combining `h-full` and `flex-col`, make sure parent containers explicitly use `overflow-hidden` otherwise inner elements with `flex-1 overflow-y-auto` will expand the parent layout rather than scroll, causing half-visibility or cut-off interfaces.
- **Story Layout Varieties**: Introduced discrete rendering loops (`make_text_only_page`, `make_overlay_story_page`, `make_story_page`) to support multiple presentation forms while preserving KDP formatting rules.
- **Language Iteration Output**: Instead of returning a single `FINAL.pdf`, iteration loops wrap the PDF assembly process producing `<book>_<lang>_interior_FINAL.pdf` output matrices corresponding to configured UI checkboxes.
