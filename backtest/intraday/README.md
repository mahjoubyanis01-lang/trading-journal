# Recherche intraday ES / NQ — méthode et résultats

## Données
- **Prix** : Dukascopy US500 et US Tech 100 (CFD sur indices cash), bougies 5 min, 2020 → 2026, téléchargées avec [`dukascopy-node`](https://github.com/Leo4815162342/dukascopy-node) (`timeframe: 'm5'`). Les signaux sont **identiques sur les vrais futures ES/NQ** (vérifié sur 60 jours Yahoo : 28/28 signaux ES, 19/20 NQ).
- **Macro** : VIX, VIX3M, VIX9D (CBOE), taux 10 ans / 2 ans et dollar (FRED), dates des décisions FOMC (Fed). Les annonces de 8h30 (CPI, emploi…) sont détectées dans les prix (bougie de 8h30 > 4× le bruit pré-marché).
- Chemins : variables d'environnement `DUKA_DIR` (fichiers `usa500idxusd_<année>.json`, `usatechidxusd_<année>.json`) et `MACRO_DIR`.

## Séances (heure de New York)
Asie 18h00–2h00 · Londres 2h00–8h30 · ouverture NY 9h30 · matin 9h30–12h00 · après-midi 12h00–16h00.

## Ce qui a été testé
| Famille | Résultat |
|---|---|
| Variables de biais avant 9h30 (tendance 20/50 j, nuit, Londres, gap, VIX et sa structure, taux, dollar, FOMC, annonces 8h30) pour prédire la direction de la séance NY | **aucune n'est fiable** seule (45–56 % d'accord, instable d'une année à l'autre) — `bias_study.py` |
| Faux cassements (sweeps) des niveaux Asie / Londres / veille / nuit à l'ouverture | **perdants** |
| Cassure + retest des niveaux de séance en 5 min, repli VWAP, cassure de la 1re heure | ≈ neutres |
| Setups d'après-midi (continuation / rejet des extrêmes du matin, momentum de fin de séance) | ≈ neutres ou perdants |
| **Cassure du range d'ouverture 9h30–9h45 dans le sens de Londres** | **retenu (signal A)** |
| Filtres de régime (range d'ouverture étroit, veille comprimée, VIX en hausse) choisis sur 2020–2022 | n'améliorent pas 2023–2026 → **rejetés** (`regime_study.py`) |
| Seconde entrée après un stop | dégrade → **rejetée** |

## Signal A (`orb_london.py`)
Biais = sens de Londres (2h00 → 9h25). Première clôture 5 min hors du range 9h30–9h45 avant 11h30 : trade si elle va dans le sens du biais, sinon rien ce jour-là. **Ventes seulement si la tendance 20 jours est baissière** (les ventes à contre-tendance perdent en découverte comme en validation). Stop au milieu du range, objectif 2R, sortie au plus tard 15h55. Frais : 0,5 pt ES / 2 pts NQ.

Résultats complets : `backtest/intraday_results.json` (par marché, par année, découverte 2020–2022 / validation 2023–2026, portefeuille ES+NQ, liste des trades). Suivi glissant sur les vrais futures (60 jours) : `backtest/recent_results.json`, recalculé chaque samedi.

L'indicateur Pine reproduit ce backtest **trade pour trade** (transcription vérifiée : 563/563 trades ES et 513/513 NQ identiques au R près ; il n'ajoute que les jours fériés / séances anormales, filtrés en direct par la liste des jours fériés).

## Reproduire
```bash
DUKA_DIR=... MACRO_DIR=... python3 backtest/intraday/make_results.py
DUKA_DIR=... MACRO_DIR=... python3 backtest/intraday/bias_study.py
DUKA_DIR=... MACRO_DIR=... python3 backtest/intraday/regime_study.py
```
