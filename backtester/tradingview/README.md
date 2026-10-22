# Indicateur TradingView — Biais Macro S&P 500 (5 niveaux, v2)

Portage Pine Script (v5) du moteur de l'application : verdict quotidien
**Hausse affirmée / Hausse modérée / Neutre / Baisse modérée / Baisse
affirmée**, figé à l'heure limite (15 h 29, heure de Paris, configurable),
puis confronté au mouvement réel du ES entre 9 h 30 New York et minuit Paris.

## Ce qui rend la v2 plus précise

Mécanismes documentés — aucun paramètre ajusté sur l'historique :

1. **Échelles adaptatives à la volatilité** : les mouvements préouverture de
   l'ES et du NQ sont normalisés par leur ATR(14) quotidien — un −0,4 % pèse
   lourd en régime calme, peu en régime agité.
2. **Pondération par cohérence** : signaux discordants ⇒ score contracté
   vers zéro (×0,7 à ×1,0 selon l'accord) — moins de verdicts tranchés à tort.
3. **Confiance explicite** (couverture des données × cohérence) : un verdict
   AFFIRMÉ exige une confiance minimale (55 par défaut), sinon il est
   rétrogradé en modéré.
4. **Garde-fou de régime** : VIX ≥ niveau de stress (28) ou structure par
   terme inversée (VIX > VIX3M) ⇒ seuils « affirmé » relevés (×1,25) et fond
   rouge discret — les signaux sont moins fiables dans la tempête.
5. **5 facteurs de risque supplémentaires** : structure par terme VIX/VIX3M,
   variation veille du 2 ans US (anticipations Fed), poussée de l'or
   (refuge), choc pétrolier haussier, tendance de fond (dérive 5 jours +
   position vs moyenne 50 jours).

Le tableau affiche en plus : confiance, régime, statistiques des verdicts
affirmés seuls, et variation moyenne observée après chaque type de verdict.

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

Portés (12 facteurs) : ES préouverture (22, adaptatif ATR), NQ (9,
adaptatif ATR), Europe/DAX (9), Asie/Nikkei (5), VIX vs moyenne 20 séances
(8), structure par terme VIX/VIX3M (7), 10 ans US (8), 2 ans US (5),
dollar (5), or-refuge (4), choc pétrolier (4), tendance de fond (6).
Le score est renormalisé sur les facteurs disponibles, comme dans
l'application.

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
