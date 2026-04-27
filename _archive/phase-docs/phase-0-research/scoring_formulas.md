# Formules Google Sheets — Tracker Niches KDP

## Import du CSV
Fichier → Importer → `tracker.csv` → Séparateur : virgule

## Formules à coller dans les colonnes calculées

### Colonne G : `est_monthly_sales` (basé sur BSR moyen)
```
=IF(E2="","",IF(E2<10000,400,IF(E2<30000,150,IF(E2<50000,80,IF(E2<100000,30,IF(E2<200000,10,3))))))
```
_Estimation grossière. À affiner avec DS Amazon Quick View sur les vrais listings._

### Colonne J : `royalty_per_book_usd` (60 pages, 8.5×11, B&W)
```
=(I2*0.60)-(0.85+(0.012*60))
```
_Remplacer 60 par le nombre de pages réel._

### Colonne K : `est_monthly_revenue_usd`
```
=G2*J2
```

### Colonne M : `score_bsr_1to5`
```
=IF(E2="","",IF(E2<30000,5,IF(E2<50000,4,IF(E2<80000,3,IF(E2<150000,2,1)))))
```

### Colonne N : `score_reviews_1to5`
```
=IF(F2="","",IF(F2<50,5,IF(F2<100,4,IF(F2<200,3,IF(F2<400,2,1)))))
```

### Colonne O : `cover_quality_score_1to5`
_Saisie manuelle (1=couvertures pro partout, 5=couvertures amateurs dominantes)_

### Colonne P : `score_royalty_1to5`
```
=IF(J2="","",IF(J2>4,5,IF(J2>3.5,4,IF(J2>3,3,IF(J2>2.5,2,1)))))
```

### Colonne Q : `score_japan_bonus`
```
=IF(L2="yes",1,0)
```

### Colonne R : `SCORE_FINAL`
```
=(M2*0.35 + N2*0.30 + O2*0.20 + P2*0.15)*2 + Q2
```
**Shortlist : garder tout score ≥ 7**

## Mise en forme conditionnelle recommandée
- SCORE_FINAL ≥ 7 → fond vert
- SCORE_FINAL 5–6.9 → fond jaune
- SCORE_FINAL < 5 → fond rouge

## Colonnes de statut (colonne S)
Valeurs valides : `researching` | `validated` | `rejected` | `in-production` | `published`
