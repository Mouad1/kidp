# Méthode de Recherche — Semaine 1 (Outils Gratuits Uniquement)

## Hypothèses challengées avant de commencer

### ✗ "Kids coloring books" comme point de départ
La catégorie large est saturée — top 10 avec 500–2000 reviews et BSR < 5k.
**Le jeu est dans la précision : âge + thème + style + occasion.**
"Kids coloring book" = mort. "Kawaii food coloring book for girls ages 4–8" = fenêtre possible.

### ✗ "Même fichier pour US, UK, France"
- US → UK : OK, même fichier, même langue.
- US → France : **problème**. Les livres d'activités avec du texte nécessitent une localisation en français. Les coloring books sans texte passent, mais toute activité (puzzles, mots croisés, journaux) nécessite adaptation.
- **Recommandation v0 : US uniquement. UK ensuite (même fichier). France = phase 2 avec version FR.**

### ✗ "€500/mois avec un livre"
- Possible mais improbable en mois 1. Calcul réaliste :
  - Livre à $8.99, 60 pages B&W : royalty ≈ $3.83/vente
  - Pour €500/mois (≈ $550) avec 1 livre : il faut ~144 ventes/mois = ~5/jour
  - Un livre dans une micro-niche validée atteint 1–3 ventes/jour en régime de croisière (mois 2–3)
  - **Cible réaliste : 5–8 livres × 20–40 ventes/mois = €400–700/mois en mois 3–4**

### ✓ Japan comme signal de tendance (pas comme marché)
Bon signal d'arbitrage. Chercher : populaire sur amazon.co.jp / Daiso / Rakuten → absent ou sous-représenté sur amazon.com EN.
Attention : les préférences japonaises ne se traduisent pas toujours 1:1 en US. Valider TOUJOURS sur amazon.com.

### ⚠ Timing saisonnier — insight critique
On est en **avril 2026**. KDP indexe en 24–72h mais le trafic saisonnier se construit 3–6 semaines avant.
- **Fenêtre immédiate** : livres d'été (beach, pool, outdoor) → publier maintenant pour juin–juillet
- Back-to-school : publier en juin pour août
- Halloween : publier juillet–août pour septembre–octobre
- Noël : publier septembre–octobre
**→ Prioriser les niches saisonnières été dans la shortlist.**

---

## Étape 1 : Brainstorming des seed keywords (30 min)

### Outil : Amazon US autocomplete
Aller sur amazon.com, taper dans la barre de recherche chaque combinaison ci-dessous,
noter toutes les suggestions.

**Seeds de départ :**
```
kids coloring book [a–z]
toddler coloring book [a–z] (juste a, b, c, d, e, f)
kawaii coloring book
activity book for kids ages [3-5] [4-8] [6-10]
summer coloring book kids
mindfulness coloring book kids
simple mandala coloring book
dinosaur coloring book toddler
```

**Ce qu'on cherche :**
- Suggestions avec modificateurs précis (âge, thème, style, saison)
- Variations inattendues (ex: "cactus coloring book for kids" = niche possible)
- Absences : si "kawaii ramen coloring book" n'apparaît pas en autocomplete, c'est soit trop petit, soit une opportunité vierge → vérifier BSR avant de conclure

---

## Étape 2 : Japan Signal (20 min)

### Outil : amazon.co.jp + Google Translate

**Recherches sur amazon.co.jp :**
```
塗り絵 子供 (nurie kodomo = coloring book kids)
かわいい 塗り絵 (kawaii nurie)
ぬりえ 幼児 (nurie yoji = coloring toddler)
知育ドリル (chiku doriru = educational workbook)
```

**Signal positif :**
- BSR amazon.co.jp < 500 dans la catégorie livres
- Format, thème, ou style absent de amazon.com (ou avec < 50 reviews côté US)

**Signaux kawaii exportables vers US :**
- Food kawaii : ramen, boba tea, sushi, onigiri
- Animal kawaii : capybara, axolotl, shiba inu
- Nature kawaii : champignons, fleurs, nuages avec yeux
- Formats fonctionnels : techo/planner style pour ados (journal + coloring hybride)

---

## Étape 3 : BSR Analysis (45 min — cœur de la méthode)

### Outil : Amazon US search + DS Amazon Quick View (extension Chrome gratuite)

**Pour chaque terme retenu à l'étape 1 :**

1. Rechercher le terme exact sur amazon.com
2. Regarder les 10 premiers résultats organiques (ignorer les sponsored)
3. Pour chaque résultat, noter dans le tracker :
   - BSR (Best Seller Rank) dans sa catégorie principale
   - Nombre de reviews
   - Note de qualité de couverture (1–5)
   - Prix

**Conversion BSR → ventes/mois (Amazon US, catégorie Books) :**
```
BSR < 10,000    → ~300–500 ventes/mois
BSR 10–50k      → ~50–150 ventes/mois
BSR 50–100k     → ~15–50 ventes/mois
BSR 100–200k    → ~5–15 ventes/mois
BSR > 300k      → < 5 ventes/mois (livre quasi-mort)
```

**Interprétation :**
- BSR moyen top-10 < 80k ET reviews moyennes < 200 → niche viable
- BSR moyen top-10 < 30k ET reviews moyennes < 100 → niche attractive
- Si le top-3 a des couvertures amateurs (score ≤ 2/5) → avantage par la qualité possible

---

## Étape 4 : Royalty Math (15 min)

**Formule KDP (60% royalty, impression B&W 8.5×11) :**
```
Coût impression = $0.85 + ($0.012 × nb_pages)
Royalty = (prix_liste × 0.60) - coût_impression

Exemple : $8.99 liste, 60 pages
  → coût impression = $0.85 + $0.72 = $1.57
  → royalty = $5.39 - $1.57 = $3.82 / vente
```

**Calculateur rapide par prix :**
| Prix liste | 60 pages | 80 pages | 100 pages |
|-----------|----------|----------|-----------|
| $6.99     | $2.62    | $2.38    | $2.14     |
| $7.99     | $3.22    | $2.98    | $2.74     |
| $8.99     | $3.82    | $3.58    | $3.34     |
| $9.99     | $4.42    | $4.18    | $3.94     |

**Break-even €500/mois (≈ $550) :**
```
Avec royalty $3.82 → besoin de 144 ventes/mois
Réparti sur 5 livres → 29 ventes/livre/mois (≈ 1/jour)
```

---

## Étape 5 : Scoring et Shortlist

**Score de niche = moyenne pondérée :**
```
Composantes :
  A) BSR moyen top-10       : score 1–5 (5 = BSR < 30k, 1 = BSR > 200k)
  B) Reviews moyennes top-10 : score 1–5 (5 = < 50 reviews, 1 = > 500)
  C) Qualité couvertures     : score 1–5 (5 = couvertures amateurs dominantes)
  D) Royalty estimée         : score 1–5 (5 = > $4/vente, 1 = < $2)
  E) Signal Japan / tendance : 0 ou 1 (bonus)

Score final = (A×0.35 + B×0.30 + C×0.20 + D×0.15) × 2 + E
→ Max théorique : 10 + 1 = 11, noter sur 10

Shortlist : garder tout score ≥ 7
```

---

## Niches Hypothèses à Valider (à saisir dans le tracker)

| # | Niche hypothèse | Seed keyword | Raison de l'hypothèse |
|---|----------------|--------------|----------------------|
| 1 | Kawaii food coloring book girls ages 4–8 | kawaii food coloring book | Japan signal fort, esthétique exportable US |
| 2 | Summer beach coloring book for toddlers 2–4 | summer coloring book toddler | Timing parfait (avril = publier maintenant) |
| 3 | Simple mandalas for kids ages 3–5 | mandala coloring book kids | Perennial, vérifier si sous-catégorie < 100 reviews |
| 4 | Axolotl coloring book kids ages 6–10 | axolotl coloring book kids | Tendance virale, animal kawaii + Gen Z |
| 5 | Mindfulness activity book kids 6–10 | mindfulness activity book kids | Tendance santé mentale, hybride coloring + activité |

**Note :** Ces 5 hypothèses doivent être VALIDÉES par les étapes 1–4 ci-dessus avant d'entrer dans la shortlist.
