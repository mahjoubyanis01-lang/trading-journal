# Indicateurs TradingView

## Niveaux d'ouverture horaires (`niveaux-horaires.pine`)

Indicateur Pine Script (v6) qui trace sur le graphique le **prix d'ouverture** de la bougie de chaque horaire clé de la journée :

- **00:00** — minuit (blanc)
- **06:00** (cyan)
- **09:00** (orange)
- **10:00** (jaune)
- **15:30** — ouverture de New York (vert)
- **22:00** (magenta)

Chaque niveau est prolongé en ligne horizontale jusqu'à la fin de la journée (ou à l'infini vers la droite si l'option est activée), avec une étiquette indiquant l'horaire et le prix.

### Installation

1. Ouvrir [TradingView](https://www.tradingview.com) et afficher un graphique.
2. Ouvrir l'**Éditeur Pine** (onglet en bas de l'écran).
3. Copier-coller le contenu de `niveaux-horaires.pine`.
4. Cliquer sur **Ajouter au graphique**.

### Réglages

- **Fuseau horaire** : `Europe/Paris` par défaut (les horaires ci-dessus sont donc en heure de Paris). Peut être changé pour Londres, New York, UTC ou le fuseau de la bourse du symbole.
- **Activation / couleur** de chaque niveau individuellement.
- **Prolonger les lignes à droite**, style et épaisseur des lignes, taille des étiquettes, affichage du prix.
- **Nombre de jours d'historique** : limite le tracé aux N derniers jours (5 par défaut) pour garder le graphique lisible.

### Remarques

- À utiliser sur une unité de temps **intrajournalière** (≤ 30 min conseillé ; pour le niveau de 15:30, une unité de temps de 30 min ou moins est nécessaire pour avoir une bougie qui ouvre exactement à 15:30).
- Si le marché est fermé à un horaire donné (week-end, nuit sur actions), le niveau est pris sur la première bougie qui ouvre à ou après cet horaire.
