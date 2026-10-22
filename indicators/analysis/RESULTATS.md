# Analyse des signaux FVG 15m — résultats (22/10/2026)

**Données** : ES=F (futures S&P 500), 15 minutes, 60 jours (13/08 → 22/10/2026),
4 556 bougies, **828 signaux bruts** (toucher de FVG + confirmation flip ou
prise de liquidité, sans aucun filtre). Script : `analyze_fvg.py` (rejoue
fidèlement la logique de `fvg-15min.pine` : FVG, moteur P1→P4, touches,
confirmations).

**Mesure** : mouvement moyen dans le sens du signal à 4/8/16 bougies 15m
(1 h / 2 h / 4 h), en multiples d'ATR(14) 15m. `win8` = % de signaux positifs
à 2 h. Base de comparaison : tous signaux = **+0,06 ATR à 2 h, 50 %** (aucun
avantage sans filtre).

## Ce qui marche (appliqué comme défauts dans l'indicateur)

| Critère | Effet mesuré | Application |
|---|---|---|
| **Zone Continuation (C)** | +0,21 ATR à 4 h, 53 % — contre **−0,13 ATR, 46 %** pour les zones R | Signaux restreints aux zones C (option « Zones déclenchant un signal ») |
| **Tendance souple alignée** (dernier P4 compte) | **+0,33 vs −0,24 ATR à 4 h** — critère le plus discriminant | Mode tendance par défaut : Souple ; toujours obligatoire |
| **Plage 06:00–16:00 NY** | 06–09 h NY : +0,70 ATR (et **+1,57 ATR, 73 %** sur le combo final) ; **00–06 h NY : −0,62 ATR** | Signaux limités à 06:00–16:00 NY par défaut |
| **Âge de zone ≤ 20 bougies 15m** | âge > 20 : −0,26 ATR à 4 h | Filtre « Âge max de la zone » = 20 |
| **Déplacement créateur ≥ 1 ATR** (« grosse chute/hausse ») | ≥ 1 ATR : +0,15 ATR, 54 % ; **≥ 2 ATR : +2,6 ATR, n = 10 seulement** | Nouveau critère de score (seuil 1,0 ATR) |
| Corps de confirmation ≥ 0,5 ATR | 53 % vs 48 % | Conservé (critère de score) |
| Volume > moyenne 20 | +0,12 vs −0,03 ATR | Conservé (critère de score) |

Combo de référence « C + tendance souple + 06-16 h NY » : n = 177,
**+0,56 ATR à 2 h, +0,61 ATR à 4 h**, MFE 3,06 vs MAE 2,32 (~3 signaux/jour
avant score).

## Ce qui ne marche pas (retiré ou non ajouté)

- **Momentum Squeeze (LazyBear)** : aucun pouvoir prédictif (+0,05 avec vs
  +0,09 sans) → **désactivé par défaut**.
- **Tendance stricte** (P4 confirmé par un P3) : n'apporte rien (−0,02 ATR
  aligné) — la version souple est meilleure → défaut repassé à Souple.
- **Éloignement avant la touche** : contre-intuitif, les retours lointains
  font PIRE (−0,17 ATR) que les touches rapides (+0,15) → non ajouté.
- **Taille de zone ≥ 0,4 ATR** : améliore le taux (55 %) mais dégrade la
  médiane → disponible mais désactivé par défaut.

## Limites assumées

Un seul instrument (ES), 60 jours, une seule fenêtre : **statistiques
exploratoires**, sensibles au régime de marché de la période — ni preuve
statistique, ni promesse de rentabilité. Le sous-groupe « déplacement
≥ 2 ATR » (n = 10) est anecdotique. À re-tester périodiquement en relançant
`python3 analyze_fvg.py` (données Yahoo Finance gratuites, 60 jours max en
15 m).
