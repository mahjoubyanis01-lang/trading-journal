# Indicateur TradingView — Biais Macro S&P 500 (5 niveaux)

Portage Pine Script (v5) du moteur de l'application : verdict quotidien
**Hausse affirmée / Hausse modérée / Neutre / Baisse modérée / Baisse
affirmée**, figé à l'heure limite (15 h 29, heure de Paris, configurable),
puis confronté au mouvement réel du ES entre 9 h 30 New York et minuit Paris.

## Installation (2 minutes)

1. Ouvrir [TradingView](https://www.tradingview.com) → graphique
   **CME_MINI:ES1!** (E-mini S&P 500 continu), unité **30 min** ou moins.
2. Ouvrir l'**Éditeur Pine** (onglet en bas) → supprimer le contenu →
   coller l'intégralité de `biais_macro_sp500.pine` → **Ajouter au graphique**.
3. (Facultatif) « Enregistrer » pour le retrouver dans *Mes scripts*.

## Ce que l'indicateur affiche

- **Courbe du score** (−100 à +100) colorée selon le verdict, avec les
  4 seuils en pointillés (±25 modéré, ±55 affirmé — réglables).
- **Fond coloré** sur la bougie où le verdict du jour est figé (heure limite).
- **Étiquette par séance** une fois minuit Paris passé :
  `verdict → réel ✓/✗` et la variation en %.
- **Tableau** (coin supérieur droit) : verdict courant, score, détail des
  7 facteurs (score/poids), et les statistiques cumulées — séances testées,
  % direction correcte, % classe exacte.
- **Alertes** disponibles : « Verdict du jour figé » et « Verdict AFFIRMÉ
  au cutoff » (menu Alertes → condition sur l'indicateur).

## Facteurs portés (et non portés)

Portés — mêmes échelles et poids par défaut que l'application :
ES préouverture (25), NQ (10), Europe/DAX (10), Asie/Nikkei (5),
VIX vs moyenne 20 séances (10), variation veille du 10 ans US (10),
variation veille du dollar (5). Le score est renormalisé sur les facteurs
disponibles, comme dans l'application.

**Non portables dans Pine** (pas d'accès API externe) : actualités,
géopolitique, publications macro point-in-time, résultats d'entreprises.
L'indicateur est donc un sous-ensemble « facteurs de marché » du moteur
complet — utilisez l'application de bureau pour l'analyse complète.

## Limites honnêtes

- Clôtures de référence ES/NQ = règlement quotidien TradingView (17 h 00 ET),
  pas la clôture cash de 16 h 00.
- Le facteur Europe est exact au moment du verdict, mais la courbe tracée
  pendant la nuit peut anticiper l'ouverture européenne du jour ; le verdict,
  lui, n'est figé qu'à l'heure limite, sur la dernière bougie terminée.
- Profondeur d'historique intraday limitée par votre abonnement TradingView.
- Les changements d'heure Paris/New York sont gérés par les fuseaux IANA de
  TradingView (y compris les semaines où le décalage vaut 5 h).
- Statistiques exploratoires : ni preuve statistique, ni preuve de
  rentabilité (pas de frais/spread/glissement).
- Script non exécutable hors TradingView : si l'éditeur Pine signale une
  erreur de version, vérifiez que la première ligne `//@version=5` est bien
  présente et que le script est collé en entier.
