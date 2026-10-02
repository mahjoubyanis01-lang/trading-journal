# Reprendre Trading Hub en local (pour valider MetaTrader 5)

Ce fichier sert de passerelle : ouvre **Claude Code en local sur ton PC Windows**,
clone le projet, et colle le message de la dernière section pour que la nouvelle
conversation reprenne exactement là où on s'est arrêtés.

---

## Où on en est

- **Projet** : Trading Hub — centre de contrôle local pour gérer beaucoup de
  comptes de prop firms (détecter → configurer → exécuter → vérifier →
  surveiller → récupérer). Pas de trade copier, tout en local.
- **Dépôt** : `mahjoubyanis01-lang/trading-journal`
- **Branche** : `claude/happy-rubin-pkp5au`
- **Dossier de l'app** : `trading-hub/` (backend Python/FastAPI + frontend
  React servi par le backend = un seul processus).

### Ce qui est DÉJÀ prouvé (sans ton PC)
- Mode **mock** complet : **101 tests au vert** (dont les 10 critères
  d'acceptation + récupération auto sur panne simulée).
- **Sûreté** : jeton d'API loopback (serveur lié à 127.0.0.1), secrets dans le
  coffre de l'OS (jamais en base/API/logs), plafond de risque dur, bouton STOP
  ALL, correction d'une traversée de chemin (revue de sécurité passée).
- **Connecteurs REST** Tradovate & TradeLocker : endpoints vérifiés **joignables
  en live** + gestion des échecs d'auth réels verrouillée par tests hors-réseau.
- **Plan de contrôle MT5** (partie indépendante de l'OS) testé sans Windows :
  écriture `config.json` + preset `.set`, commandes RUN/STOP, lecture heartbeat.

### Ce qui RESTE à valider sur ton PC Windows
Les parties MT5 qui n'existent que sur Windows + MetaTrader installé :
trouver l'install, lancer le terminal portable, `mt5.initialize()/login`,
compiler l'EA pont. **C'est l'objet de la reprise en local.**

---

## Prérequis sur le PC
- **Windows** + **Python 3.11+** installés.
- **MetaTrader 5** installé, avec un **compte démo** (login / mot de passe /
  **serveur**, ex. `MetaQuotes-Demo`) — n'importe quel MT5 démo convient.
- **Claude Code** en local (appli bureau Windows, extension VS Code, ou CLI).
- Git.

## Étapes

### 1. Cloner le projet et se mettre sur la branche
```powershell
git clone https://github.com/mahjoubyanis01-lang/trading-journal.git
cd trading-journal
git checkout claude/happy-rubin-pkp5au
```

### 2. Test brut MT5 (ouvre MT5 + connecte ton compte démo AVANT)
```powershell
pip install MetaTrader5
python -c "import MetaTrader5 as m; print('init', m.initialize()); a=m.account_info(); print('compte', a.login, a.balance, a.equity, a.currency, a.server) if a else print('pas de compte', m.last_error()); print('symboles', [s.name for s in (m.symbols_get() or [])[:5]]); m.shutdown()"
```
Attendu : `init True`, ton **vrai solde**, puis 5 symboles. Si oui → la lecture
MT5 marche sur ta machine, donc le connecteur marchera.

### 3. Lancer l'app
Double-clique **`trading-hub\TradingHub.bat`** (1er lancement : installe tout,
y compris `MetaTrader5`, puis ouvre la fenêtre).

### 4. Valider le produit en mock (2 min, sans compte)
Dans l'app : **Seed 50 demo accounts** → **Add account** (Plateforme = Mock) et
suivre la progression → ouvrir le compte (Risk 50 $, marchés mappés, robot
ACTIVE) → **Simulate fault → Recover** → **STOP ALL**.

### 5. Valider le VRAI MT5
**Add account** → Plateforme = **MetaTrader 5**, saisir login / mot de passe /
**serveur**. Observer la progression : `Terminal instance` → `Connect` →
`Read account` (ton vrai solde) → `Markets` → `Risk` → `Robot` → `Heartbeat`.
Puis, dans le terminal MT5 ouvert, attacher **une fois** l'EA
`TradingHubBridge` sur un graphique avec AutoTrading activé (il a été copié +
compilé dans l'instance) → heartbeat réel + solde/positions en direct.

> Chaque broker a des variantes (chemin d'install, nom de serveur). Note
> précisément où ça bloque : la nouvelle session Claude locale corrigera le
> connecteur sur place.

---

## Carte des fichiers utiles (pour la reprise)
- `trading-hub/backend/app/connectors/mt5/mt5.py` — connecteur MT5.
- `trading-hub/backend/app/terminal/mt5_agent.py` — agent Windows (install,
  instances portables, lancement/surveillance du terminal, compilation EA).
- `trading-hub/backend/app/terminal/bridge.py` — protocole fichier (config /
  commande / heartbeat / compte).
- `trading-hub/assets/mt5/TradingHubBridge.mq5` — EA compagnon (+ `mt4/`).
- `trading-hub/backend/app/services/account_manager.py` — workflow d'ajout.
- `trading-hub/CONNECTORS.md` — statut et mise en place par plateforme.
- `trading-hub/README.md`, `trading-hub/ARCHITECTURE.md` — vue d'ensemble.
- Lancer les tests : `cd trading-hub/backend && python -m pytest -q`.

---

## Message à coller dans la NOUVELLE conversation Claude Code (en local)

> Reprends le projet **Trading Hub** sur la branche
> `claude/happy-rubin-pkp5au` (dépôt trading-journal), dossier `trading-hub/`.
> Lis `trading-hub/REPRENDRE-EN-LOCAL.md` et `trading-hub/CONNECTORS.md`.
> Je suis **en local sur Windows**, **MetaTrader 5 est ouvert avec un compte
> démo connecté** (serveur : `<le tien>`). Objectif : **valider le connecteur
> MT5 de bout en bout** (instance portable, connexion, lecture du compte,
> risque, heartbeat via l'EA pont), et corriger ce qui bloque jusqu'au vert.
> Commence par lancer le test brut `MetaTrader5` puis l'ajout d'un compte MT5
> dans l'app, et pilote tout toi-même via PowerShell.
