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
  FVG baissier), la box est **supprimée** du graphique.

### Paramètres

| Paramètre | Défaut | Description |
|---|---|---|
| Unité de temps des FVG | 15 | Timeframe de détection des gaps |
| Taille minimale du gap (%) | 0 | Filtre les FVG trop petits (en % du prix) |
| Nombre max de FVG affichés | 50 | Les plus anciens sont supprimés au-delà |
| Couleurs fond / bordure | teal / rouge | Style des zones haussières et baissières |
| Ligne médiane (CE) | désactivée | Affiche le milieu du gap (Consequent Encroachment) |

### Installation

1. Ouvrir TradingView → éditeur Pine.
2. Coller le contenu de `fvg-15min.pine`.
3. « Ajouter au graphique ».
