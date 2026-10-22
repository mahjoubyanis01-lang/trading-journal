# S&P 500 Macro Bias Backtester — Frontend

Interface web (français, thème sombre) du backtester de biais macro S&P 500.
React 18 + TypeScript + Vite, react-router-dom, recharts.

Le contrat d'API est défini dans `../API_CONTRACT.md`. Le serveur de dev Vite
proxifie `/api` vers le backend FastAPI sur `http://127.0.0.1:8000`.

## Commandes

```bash
npm install      # dépendances
npm run dev      # serveur de dev (port 5173, backend requis sur :8000)
npm run build    # vérification TypeScript + build de production (dist/)
npm run preview  # sert le build de production
```

## Pages

- `/` — Tableau de bord : tuiles de synthèse, répartition des prédictions,
  résultats par séance, lancement du backtest avec suivi de progression.
- `/sessions` — Historique filtrable des séances.
- `/sessions/:date` — Détail d'une séance : analyse avant ouverture
  (information ≤ 15:29 Paris) et résultat observé (graphique intrajournalier).
- `/stats` — Statistiques agrégées : taux de réussite, matrice de confusion,
  comparaison aux références simples.
- `/config` — Paramètres du modèle, fournisseurs de données (clés API),
  erreurs de collecte, exports CSV/JSON.
