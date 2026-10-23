# Trading Journal — Institutional

Application web de journal de trading, installable sur PC et téléphone (PWA).

## 🚀 Déploiement sur GitHub Pages (5 minutes)

### 1. Créer le repository

1. Va sur [github.com](https://github.com) → **New repository**
2. Nom : `trading-journal`
3. Visibilité : **Public** (obligatoire pour GitHub Pages gratuit)
4. Clique **Create repository**

### 2. Uploader les fichiers

**Option A — via l'interface web GitHub (le plus simple) :**

1. Dans ton nouveau repo, clique **"uploading an existing file"**
2. Glisse-dépose **tous les fichiers** de ce dossier
3. Clique **Commit changes**

**Option B — via Git :**
```bash
cd trading-journal
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/TON-USERNAME/trading-journal.git
git push -u origin main
```

### 3. Activer GitHub Pages

1. Dans ton repo → **Settings** → **Pages**
2. Source : **GitHub Actions**
3. Le déploiement se lance automatiquement (~1 minute)
4. Ton URL : `https://TON-USERNAME.github.io/trading-journal`

---

## 📱 Installer sur téléphone

### iPhone (Safari obligatoire)
1. Ouvre l'URL dans **Safari**
2. Tape l'icône **Partager** (carré avec flèche)
3. → **"Sur l'écran d'accueil"**
4. L'app apparaît comme une vraie appli

### Android (Chrome)
1. Ouvre l'URL dans **Chrome**
2. Menu ⋮ → **"Ajouter à l'écran d'accueil"**
3. Ou la bannière d'installation apparaît automatiquement

---

## 💾 Sauvegarde des données

Les données sont stockées dans le `localStorage` du navigateur.

**Pour transférer PC → Téléphone :**
1. Sur PC : bouton **💾** (haut à droite) → télécharge `tj_backup_XXXX.json`
2. Envoie le fichier sur ton téléphone (mail, AirDrop, WhatsApp...)
3. Sur téléphone : bouton **📂** → importe le fichier

**Export CSV :** section Trades → bouton "Exporter CSV"

---

## 📋 Utilisation

| Champ | Description |
|---|---|
| **Date** | Optionnel — les trades sans date héritent de la date précédente |
| **Rendement %** | Obligatoire — saisir en % direct : `2.5` pour +2.5%, `-1` pour -1% |
| **Lien TradingView** | Optionnel — reste cliquable dans le journal |
| **Commentaire** | Optionnel |

### Raccourcis
- **Entrée** dans le formulaire → ajoute le trade
- **F9** → relance les simulations Monte Carlo

---

## 🏆 Score de rentabilité /100

| Score | Label | Critères |
|---|---|---|
| 80–100 | 🟢 Excellent | Tous ratios au vert |
| 65–79 | 🟢 Profitable | Bonne régularité |
| 50–64 | 🟡 Correct | Optimisations possibles |
| 35–49 | 🟠 Fragile | Revoir RR ou winrate |
| 0–34 | 🔴 Non rentable | Stratégie à retravailler |

**Décomposition :** Winrate (25pts) + Profit Factor (20pts) + Sharpe (20pts) + Max DD (20pts) + Expectancy (15pts)

---

## ⚠️ Important — format du rendement

Saisir le % directement : `2.5` pour +2.5%, `-1` pour -1%, `0` pour breakeven.

Ne pas saisir `0.025` — l'application divise automatiquement par 100.

---

## 🔥 Indicateur Options GEX (heatmap)

Page : **`options.html`** (lien « Options GEX » dans la navigation du journal).

- **Fournisseur de données réel et gratuit** : chaînes d'options [CBOE delayed quotes](https://cdn.cboe.com/api/global/delayed_quotes/options/_SPX.json) (cotations différées ~15 min, sans clé API). Symboles : SPX, SPY.
- **Indicateur** : GEX (Gamma Exposure) par strike — `gamma × open interest × 100 × spot² × 1 %`, calls positifs / puts négatifs. KPIs : GEX net total, gamma flip, call wall, put wall, IV 30 j.
- **Heatmap intrajournalière** : strikes en Y, heure (NY) en X, couleur = GEX net (bleu positif / rouge négatif), ligne de spot et niveaux de flip superposés. Clic sur une colonne → profil GEX détaillé de ce snapshot.
- **Mise à jour & reset journalier** : le workflow `.github/workflows/options-snapshot.yml` prend un snapshot **toutes les 30 min pendant les heures de marché US** et le committe dans `data/options/<SYM>/<YYYY-MM-DD>/`. Chaque jour de bourse démarre un nouveau dossier (reset automatique), la page charge le dernier jour par défaut.
- **Backtest** : toutes les journées restent archivées dans le repo — sélecteur « Journée (backtest) » dans la page, et bouton **Export** pour télécharger le JSON complet de la journée. Lancement manuel possible : onglet *Actions* → *Options GEX snapshot* → *Run workflow*.

Ajouter un symbole : éditer le dict `SYMBOLS` dans `scripts/fetch_options_snapshot.py`.
