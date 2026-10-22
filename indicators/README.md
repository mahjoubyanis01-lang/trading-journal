# Indicateurs TradingView

## FVG 15min (`fvg-15min.pine`)

Indicateur Pine Script v6 qui affiche les **Fair Value Gaps (FVG)** détectés sur
l'unité de temps **15 minutes**, quel que soit le timeframe du graphique
(≤ 15 min recommandé).

### Comportement

- **Détection** : pattern classique à 3 bougies sur des bougies 15m clôturées.
  - FVG haussier : le low de la 3ᵉ bougie est au-dessus du high de la 1ʳᵉ.
  - FVG baissier : le high de la 3ᵉ bougie est en dessous du low de la 1ʳᵉ.
- **Conservation d'affichage** : chaque FVG est dessiné comme une box qui
  s'étend vers la droite et reste à l'écran tant qu'elle n'est pas touchée.
- **Mitigation au toucher** : dès que le prix revient toucher la zone
  (le low atteint le haut d'un FVG haussier, ou le high atteint le bas d'un
  FVG baissier), la box cesse d'être active. Selon l'option choisie, elle
  est **conservée en grisé** et figée au moment du toucher (défaut), ou
  **supprimée** du graphique.

### Paramètres

| Paramètre | Défaut | Description |
|---|---|---|
| Unité de temps des FVG | 15 | Timeframe de détection des gaps |
| Taille minimale du gap (%) | 0 | Filtre les FVG trop petits (en % du prix) |
| Nombre max de FVG affichés | 50 | Les plus anciens sont supprimés au-delà |
| Couleurs fond / bordure | teal / rouge | Style des zones haussières et baissières |
| Ligne médiane (CE) | désactivée | Affiche le milieu du gap (Consequent Encroachment) |
| Garder les zones touchées en grisé | activé | Conserve les zones mitigées en gris au lieu de les supprimer |
| Couleurs zone mitigée | gris | Fond et bordure des zones touchées |
| Nombre max de zones mitigées | 30 | Les plus anciennes sont supprimées au-delà |
| FVG affichés | Tous | Filtre : tous / continuation seulement / retournement seulement |
| Étiquette C / R dans la box | activé | Affiche « C » ou « R » dans chaque zone |
| Labels de structure 15m (P3 / P4) | désactivé | Affiche les événements de structure sur le graphique |

### Continuation / Retournement

Chaque FVG est classé grâce à un moteur de structure **P1→P4** (le même que
celui du LIQUIDITY DETECTOR) calculé sur les bougies 15m clôturées :

- **C — Continuation** : le FVG est créé par un **P3** (cassure dans le sens
  de la tendance 15m), ou se forme dans le sens de la tendance en cours.
- **R — Retournement** : le FVG est créé par un **P4** (cassure qui inverse
  la tendance 15m), ou se forme à contre-tendance.

Quatre alertes sont disponibles (menu « Alertes » de TradingView) : FVG
haussier/baissier × continuation/retournement.

### Installation

1. Ouvrir TradingView → éditeur Pine.
2. Coller le contenu de `fvg-15min.pine`.
3. « Ajouter au graphique ».
