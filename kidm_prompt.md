# Projet KIDP : Générateur Automatisé de Livres de Coloriage et Contes KDP

Tu es un développeur expert en Python (FastAPI, Pillow) et frontend (HTML, TailwindCSS, Vanilla JS).
Ton but est de recréer de zéro le projet "KIDP", une application permettant de générer, gérer et exporter des livres illustrés et de coloriage compatibles avec Amazon KDP (Kindle Direct Publishing).

## 1. Architecture du Projet

Le projet suit la structure suivante :
```text
kidp/
├── dashboard/                 # Interface Utilisateur et Serveur API
│   ├── app.py                 # Serveur backend FastAPI
│   └── templates/
│       ├── index.html         # Accueil (liste des livres)
│       └── book.html          # Éditeur d'un livre spécifique
├── pipeline/                  # Scripts de traitement
│   ├── assemble.py            # Crée le PDF intérieur sans polices (PIL + img2pdf)
│   ├── config_io.py           # Lit et écrit les configurations (config.py)
│   ├── cover.py               # Génère une preview de couverture
│   ├── draw_utils.py          # Fonctions utilitaires de dessin (Pillow)
│   └── generate.py            # API Gemini/Midjourney pour la génération
├── books/                     # Données des livres (un dossier = un livre)
│   └── my-book/
│       └── config.py          # Fichier de configuration généré dynamiquement
├── images/                    # Images sources (un dossier = un livre)
└── output/                    # Fichiers PDF finaux
```

## 2. Fonctionnalités Clés à Implémenter

### Backend / Pipeline (Python)
- **Génération d'images et texte :** Via le SDK `google.genai` (modèle `gemini-2.5-flash`), le système doit pouvoir générer les morales ("Values Learned"), l'introduction, et réécrire des descriptions de personnages/pages.
- **Assemblage KDP (`assemble.py`) :**
  - Crée les pages sous format Image (Pillow) à **300 DPI**, dimension KDP **11.0" x 8.5"** (Landscape).
  - Convertit la séquence des images PNG en PDF avec `img2pdf`. **Alerte : aucune police ne doit être encapsulée dans le PDF (KDP strict rule)**. Le texte doit être "dessiné" en pixels sur les images.
  - Marges imposées : `Gutter = 0.75"`, Top/Bottom/Outer = `0.5"`.
  - Typographie enfantine : Texte aligné à **gauche** (`align="left"`), taille 14-16pt, police System `Futura`.
  - Logique "Coloring" : Si `STORY_FORMAT == "coloring"`, on intercale systématiquement une page blanche (`_blank_page()`) derrière chaque modèle pour éviter que les feutres ne transpercent.
- **Configurations (`config_io.py`) :** Sauvegarde le livre sous forme de module Python `config.py` (facilement lisible par les scripts) mais géré comme un dictionnaire en mémoire RAM lors des exports depuis l'interface API.
- **Couverture (`cover.py`) :** Construit une composition simple d'image de couverture.

### Frontend / Dashboard (FastAPI + Jinja + JS Vanilla)
- **Tableau de bord UI (`book.html`) :** Construit sur TailwindCSS avec CSS Grid (`min-h-0` pour l'overflow et scrollbar indépendante).
- **Éditeur de Personnages et d'Histoire :**
  - Ajout/Suppression de "Characters" (avec ID, Nom, Série, Prompt).
  - Ajout de "Détails Constats (Global Prompt)" qui se rajoute au prompt de tous les personnages du livre.
  - Système Drag-and-Drop pour changer l'ordre.
- **Remplacement Global :** Une route API qui parcourt `INTRO_TEXT`, `VALUES`, `PAGES` et modifie un terme X en terme Y.
- **Streaming Console :** Les actions lourdes (clean, generate, assemble) s'exécutent en ouvrant un "EventSource" (StreamingResponse) vers l'interface pour afficher la sortie console Python (stdout) en direct.
- **Image Cache-Busting :** Quand générée récemment, l'image se recharge avec `?timestamp=Date.now()`.
- **Sauvegarde Intelligente :** L'UI utilise `fetch` avec un payload JSON global (qui clone `...configData` pour ne pas perdre les tableaux comme `pages` s'ils sont hors UI) pour écrire le `config.py` cible.

## 3. Technologies et Modèles Attendus
- **Python 3.11+**, `FastAPI`, `uvicorn`, `Pillow`, `img2pdf`, `pydantic`.
- Utilisation de **google.genai** Client (et non le vieux `google.generativeai`).

Génère moi les scripts dans l'ordre pour recréer l'architecture de cette application KDP de A à Z.
