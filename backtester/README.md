# S&P 500 Macro Bias Backtester

Application locale de **backtest historique** : pour chacune des N dernières
séances de bourse (10/30/60/90/252), elle reconstruit les informations
économiques, financières et géopolitiques **réellement disponibles avant
15 h 29, heure de Paris**, tranche un verdict en **cinq niveaux** —
**HAUSSE AFFIRMÉE / HAUSSE MODÉRÉE / NEUTRE / BAISSE MODÉRÉE / BAISSE
AFFIRMÉE** — puis le compare à l'évolution réelle du contrat E-mini S&P 500
(ES) entre **9 h 30, heure de New York** (ouverture de la séance régulière)
et **minuit, heure de Paris**.

Verdict prédit (score −100..+100) : ≥ +55 → hausse affirmée ; ≥ +25 → hausse
modérée ; ≤ −55 → baisse affirmée ; ≤ −25 → baisse modérée ; sinon neutre.
Direction réelle (variation mesurée) : au-delà de ±0,50 % → affirmée ; au-delà
de ±0,10 % → modérée ; sinon neutre. Tous ces seuils sont configurables. Deux
notions de justesse sont affichées : **direction** (hausse/baisse/neutre,
intensité ignorée) et **exact** (même classe parmi les cinq).

> Outil de recherche : il mesure si l'analyse macro/informationnelle a une
> valeur prédictive directionnelle. Ce n'est **pas** un outil de
> recommandation de trading, et un taux de réussite directionnelle n'est pas
> une preuve de rentabilité.

## Architecture

```
backtester/
├── backend/            # API FastAPI (Python 3.11+)
│   ├── app/
│   │   ├── main.py             # routes HTTP (voir ../API_CONTRACT.md)
│   │   ├── config.py           # réglages (data/settings.json) + clés API
│   │   ├── db.py               # SQLite : résultats, cache HTTP, erreurs
│   │   ├── timeutil.py         # fuseaux Paris/New York (zoneinfo)
│   │   ├── providers/          # fournisseurs de données (modulaires)
│   │   │   ├── yahoo.py        # ES=F, NQ, VIX, indices (sans clé)
│   │   │   ├── fred.py         # macro US point-in-time ALFRED (clé gratuite)
│   │   │   ├── gdelt.py        # actualités horodatées (sans clé)
│   │   │   ├── finnhub.py      # résultats d'entreprises (clé)
│   │   │   └── databento.py    # ES par contrat, historique profond (payant)
│   │   ├── engine/             # facteurs, sentiment, score directionnel
│   │   ├── backtest/           # calendrier, mesure 9h30 NY → minuit Paris, orchestrateur
│   │   ├── stats.py            # métriques, matrice de confusion, baselines
│   │   └── export.py           # export CSV / JSON
│   └── tests/                  # pytest : horaires, calculs, anti-look-ahead
├── frontend/           # React + TypeScript + Vite (thème sombre, 5 pages)
├── API_CONTRACT.md     # contrat d'API backend ↔ frontend
└── .env.example        # exemple de configuration sans secrets
```

## Installation et lancement (Windows)

### Mode application de bureau (recommandé — un double-clic)

Prérequis : uniquement [Python 3.11+](https://www.python.org/downloads/)
(cocher « Add python.exe to PATH » à l'installation). Node.js n'est **pas**
nécessaire : l'interface compilée (`frontend/dist`) est incluse et servie par
le backend.

1. Télécharger/cloner ce dossier `backtester` sur le PC.
2. Double-cliquer sur **`Installer sur le Bureau.bat`** (une fois) : un
   raccourci « S&P 500 Backtester » apparaît sur le Bureau.
3. Double-cliquer sur le raccourci : au premier lancement, l'environnement
   Python s'installe tout seul, puis le navigateur s'ouvre sur
   http://127.0.0.1:8000. Fermer la fenêtre noire pour arrêter l'application.

### Mode développement (backend + frontend séparés)

Prérequis : Python 3.11+ et [Node.js 18+](https://nodejs.org/).

```bat
:: 1. Backend — depuis le dossier backtester\
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy ..\.env.example .env        :: puis renseigner les clés (facultatif)
python -m uvicorn app.main:app --port 8000

:: 2. Frontend — dans un second terminal, depuis backtester\
cd frontend
npm install
npm run dev
```

Ouvrir ensuite http://localhost:5173. Le backend doit rester lancé
(http://127.0.0.1:8000). Scripts de démarrage : `start-backend.bat` et
`start-frontend.bat`.

Tests backend : `cd backend && python -m pytest`.

## Notification quotidienne à l'heure limite

Page Configuration → « Notification quotidienne » : une fois activée, chaque
jour de semaine à 15 h 29 (heure de Paris, suit le réglage de l'heure
limite), l'application calcule le verdict FIGÉ du jour avec le moteur
complet puis notifie :

- **Toast Windows** natif sur le PC (aucune installation) ;
- **Telegram** (facultatif) : jeton de bot (@BotFather) à saisir dans la
  liste des fournisseurs, chat_id dans les paramètres de notification —
  pour recevoir le verdict sur téléphone.

Le serveur backend doit être lancé à cette heure-là (raccourci Bureau).
Un garde-fou sur disque évite les doublons, y compris après redémarrage ;
bouton « Envoyer une notification de test » pour vérifier les canaux.
Les changements d'heure été/hiver sont gérés automatiquement.

## Sources de données

| Source | Clé | Rôle | Limites réelles |
|---|---|---|---|
| **Yahoo Finance** (API chart non officielle) | aucune | ES=F intraday 30 min, NQ=F, ^VIX, ^TNX, DXY, indices EU/Asie, pétrole, or ; calendrier des séances via ^GSPC | Intraday 30 min ≈ **60 jours** en arrière ; contrat **continu** front-month ; API non officielle (peut changer) |
| **GDELT DOC 2.0** | aucune | Titres de presse horodatés (macro/Fed, géopolitique, entreprises) | 1 requête/5 s (throttle intégré) ; horodatage = découverte GDELT (±15 min) ; titres seulement |
| **FRED / ALFRED** | gratuite | CPI, Core CPI, PCE, NFP, chômage, inscriptions, PIB, ventes au détail, confiance UMich, taux 2a/10a, dollar — **en vintage point-in-time** (valeurs telles que connues à la date, jamais révisées rétroactivement) | **Pas de consensus** des économistes ; heure de publication reconstruite depuis les créneaux officiels (08:30 ET, 10:00 ET…) |
| **Finnhub** | gratuite (limitée) | Calendrier des résultats + surprise BPA, pondérée par poids indiciel | Historique limité en plan gratuit ; l'estimation BPA n'est pas une archive stricte point-in-time |
| **Databento** | **payante** | ES en vraies données de contrat (GLBX.MDP3, symbole continu `ES.c.0`), intraday 1 min sans limite de profondeur | Facturé à l'usage ; requis seulement pour > ~60 jours d'historique intraday |

**Si une source n'est pas configurée** : le facteur correspondant est marqué
indisponible, la qualité/confiance de la séance baisse, la limite est
affichée — **aucune donnée n'est inventée**.

## Gestion des échéances ES (continuité)

Yahoo (`ES=F`) et Databento (`ES.c.0`) fournissent un contrat **continu
front-month sans ajustement rétroactif des prix**. Toutes les mesures de
l'application sont **intra-journée** (préouverture du jour, et 9h30 NY →
minuit Paris) : les deux bornes d'une même mesure proviennent donc toujours du
même contrat, et aucun écart de roll n'entre dans les variations calculées.
Seule la comparaison « clôture de la veille → préouverture » peut chevaucher
deux contrats autour des rolls trimestriels (mars/juin/sept/déc) ; cette
limite est signalée dans chaque séance (`contract_note`). Avec Databento, le
contrat réel de chaque bougie est tracé. Les prix du SPX ou d'un ETF ne sont
jamais présentés comme des prix ES.

## Horaires et anti-look-ahead

- Limite d'information : **15:29 Europe/Paris** (configurable). Mesure :
  **09:30 America/New_York → 00:00 Europe/Paris** (lendemain calendaire).
  Les fuseaux sont gérés par `zoneinfo` : le décalage Paris–NY vaut 6 h la
  plupart de l'année mais **5 h** pendant les fenêtres de bascule d'heure
  (testé), il n'est jamais supposé constant.
- Marché préouverture : uniquement des bougies **entièrement terminées** avant
  la limite.
- Séries quotidiennes (VIX, taux, dollar) : uniquement des jours
  **strictement antérieurs** à la séance (leur clôture du jour n'est connue
  qu'après la limite). Exception documentée : clôture du Nikkei du jour,
  intervenue avant ~8 h Paris.
- Actualités : filtrées sur l'horodatage GDELT ≤ limite ; sans horodatage →
  exclues.
- Macro : vintages ALFRED (valeur telle que connue ce jour-là) + heure de
  publication officielle ; une publication de 10:00 ET tombe après 15:29
  Paris en régime 6 h et est exclue de la séance (testé).
- Les valeurs révisées ne sont jamais présentées comme publiées initialement
  (vintages ALFRED).
- La mesure du marché est calculée **après** la prévision et n'entre dans
  aucun facteur (testé).
- Si les archives ne permettent pas de reconstruire ce qui était connu, la
  séance est marquée **« NEUTRE — données insuffisantes »** et comptée à
  part ; rien n'est reconstruit artificiellement.

## Conventions de mesure

- Prix d'ouverture : open de la bougie commençant à 09:30 NY (sinon première
  bougie dans les 30 min, signalé).
- Prix à minuit Paris : open d'une bougie commençant exactement à 00:00 Paris
  si elle existe (réouverture CME 18:00 ET en régime 6 h), sinon close de la
  dernière bougie terminée avant minuit (le CME est en pause 17h–18h ET).
  L'horodatage réellement utilisé est toujours affiché.
- Variation : `prix final − prix initial` (points) et `(final−initial)/initial×100` (%).
- Direction réelle : haussière/baissière au-delà d'une bande neutre
  configurable (défaut ±0,10 %) ; la bande sert au classement, jamais à
  modifier les prix. Le résultat mesure l'intervalle défini, pas toute la
  séance américaine.

## Moteur de décision

11 facteurs pondérés (poids configurables) : ES préouverture, NQ, Europe,
Asie, VIX, taux 2a/10a, dollar, publications macro, sentiment presse,
géopolitique (asymétrique risk-off), résultats d'entreprises. Le score
[-100, +100] est la somme des contributions renormalisée sur les poids
**disponibles** ; seuils initiaux ±25 (modéré) et ±55 (affirmé) —
configurables, valeurs de départ, pas des seuils optimisés. La confiance 0–100 reflète complétude + nombre de
facteurs + cohérence des signaux ; **ce n'est pas une probabilité calibrée**.
L'interprétation macro n'est pas mécanique : une inflation chaude est lue via
le canal des taux (défavorable), une activité très forte est ambivalente
(« higher for longer »).

## Validation

- Les séances déjà calculées (mêmes paramètres) sont rechargées : un
  traitement interrompu **reprend** sans tout recalculer ; `force` recalcule.
- Changer les seuils/poids crée une nouvelle clé de paramètres : les anciens
  résultats ne sont pas écrasés. Si vous ajustez les seuils, faites-le sur
  une période puis évaluez sur une période **postérieure** distincte (10/30
  vs 60/90) — n'optimisez pas et ne validez pas sur les mêmes séances.
- Page Statistiques : comparaison systématique à des références simples
  (toujours haussier, toujours baissier, suivre la préouverture, momentum
  veille), résultats avec et sans séances neutres, avec le nombre
  d'observations, et un avertissement sur la taille d'échantillon.

## Limites connues (transparence)

1. **Consensus historique indisponible** sur les sources gratuites : les
   surprises macro sont mesurées vs valeur précédente, pas vs attentes.
2. **Sentiment presse heuristique** (lexique de mots-clés sur les titres,
   transparent dans `engine/sentiment.py`) — pas un modèle calibré.
3. Intraday ES > 60 jours : nécessite Databento (payant). Sans lui, les
   séances trop anciennes sont marquées non mesurables, jamais approximées
   par le SPX.
4. API Yahoo non officielle : en cas de panne, les erreurs sont journalisées
   et visibles page Configuration.
5. ~30 séances = résultats **exploratoires**, pas une preuve statistique.
