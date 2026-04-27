# Phase 2 — Pipeline PaperClip (NestJS + BullMQ)

> **Démarrer ici uniquement si :** ≥ 5 ventes confirmées dans les 14 jours post-publication Phase 1.
> Investir du temps en automatisation avant preuve de traction = erreur classique de pré-optimisation.

## Architecture cible (propose-decide-learn)

```
paperclip/
├── src/
│   ├── agents/
│   │   ├── niche-researcher.agent.ts   # Propose : génère des candidats de niches
│   │   ├── bsr-monitor.agent.ts        # Observe : suit le BSR de nos livres publiés
│   │   └── keyword-optimizer.agent.ts  # Apprend : ajuste les keywords selon les ventes
│   ├── queues/
│   │   ├── research.queue.ts           # BullMQ jobs pour la recherche de niches
│   │   └── monitor.queue.ts            # BullMQ jobs pour le monitoring BSR
│   ├── human-in-the-loop/
│   │   └── approval.service.ts         # Interface de validation humaine (webhook Telegram ?)
│   └── app.module.ts
├── package.json
└── .env.local
```

## Jobs BullMQ prévus

| Job | Fréquence | Input | Output |
|-----|-----------|-------|--------|
| `niche.scan` | Hebdo | seed keywords | CSV de candidats scorés |
| `bsr.track` | Quotidien | ASIN list | BSR historique + alerte si > 200k |
| `keyword.audit` | Mensuel | ASIN + ventes actuelles | Suggestions de keywords alternatifs |

## Dépendances prévues (à valider avant install)
- `@nestjs/bull` + `bull` (BullMQ)
- `puppeteer` ou `playwright` (scraping Amazon — vérifier CGU)
- Helium 10 API ou Publisher Rocket export (si abonnement pris en Phase 1)

## Décision gate
Ne pas construire avant d'avoir :
- [ ] ≥ 5 ventes sur premier livre
- [ ] Décidé quel outil payant on utilise (Helium 10 vs Publisher Rocket)
- [ ] Cartographié le workflow manuel exact qu'on veut automatiser
