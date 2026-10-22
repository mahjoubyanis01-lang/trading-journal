"""Calcul des facteurs directionnels à partir des données collectées.

Chaque facteur produit : un score borné par son poids configurable, une
valeur lisible, une justification, et un indicateur de disponibilité.
Un facteur sans données vaut 0 et est marqué indisponible (il dégrade la
complétude, jamais il n'est inventé).

Règle d'interprétation NON mécanique pour la macro : une inflation plus forte
qu'attendu est lue via le canal des taux (défavorable aux actions) ; des
données d'activité très fortes sont lues comme un soutien modéré mais avec un
contrepoids « higher for longer » si les rendements montent le même matin —
les deux lectures sont explicitées dans la justification.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class Factor:
    id: str
    label: str
    weight: float
    score: float = 0.0
    value: str = "n.d."
    rationale: str = "Données indisponibles"
    available: bool = False
    as_of: str | None = None
    details: dict = field(default_factory=dict)

    @property
    def direction(self) -> str:
        if self.score > 1:
            return "bullish"
        if self.score < -1:
            return "bearish"
        return "neutral"

    def to_dict(self) -> dict:
        return {
            "id": self.id, "label": self.label, "value": self.value,
            "score": round(self.score, 2), "max_weight": self.weight,
            "direction": self.direction, "rationale": self.rationale,
            "available": self.available, "as_of": self.as_of,
        }


def _scaled(move_pct: float | None, full_scale_pct: float, weight: float) -> float:
    """Transforme un mouvement en % en score borné ±weight (tanh doux)."""
    if move_pct is None:
        return 0.0
    return weight * math.tanh(move_pct / full_scale_pct)


def preopen_move_factor(fid: str, label: str, move_pct: float | None, weight: float,
                        as_of: str | None, scale: float = 0.6) -> Factor:
    f = Factor(fid, label, weight, as_of=as_of)
    if move_pct is None:
        return f
    f.available = True
    f.score = _scaled(move_pct, scale, weight)
    f.value = f"{move_pct:+.2f} %"
    f.rationale = (f"Mouvement de {move_pct:+.2f} % mesuré avant la limite "
                   "d'information — indication de tendance, sans garantie de continuation.")
    return f


def vix_factor(prev_close: float | None, avg20: float | None, weight: float,
               as_of: str | None) -> Factor:
    f = Factor("vix", "VIX (volatilité implicite)", weight, as_of=as_of)
    if prev_close is None:
        return f
    f.available = True
    f.value = f"{prev_close:.1f}" + (f" (moy. 20 s.: {avg20:.1f})" if avg20 else "")
    if avg20:
        rel = (prev_close - avg20) / avg20
        f.score = -_scaled(rel * 100, 12.0, weight)
        if prev_close >= 28:
            f.score = min(f.score, -0.5 * weight)
            f.rationale = f"VIX élevé ({prev_close:.1f}) : régime de stress, aversion au risque."
        elif rel > 0.08:
            f.rationale = (f"VIX {prev_close:.1f} nettement au-dessus de sa moyenne 20 séances "
                           f"({avg20:.1f}) : montée de l'incertitude, défavorable aux actions.")
        elif rel < -0.08:
            f.rationale = (f"VIX {prev_close:.1f} sous sa moyenne 20 séances ({avg20:.1f}) : "
                           "climat de faible aversion au risque.")
        else:
            f.rationale = f"VIX {prev_close:.1f} proche de sa moyenne : signal faible."
    else:
        f.score = -_scaled((prev_close - 18) , 8.0, weight * 0.6)
        f.rationale = f"VIX {prev_close:.1f} (pas de moyenne de référence disponible)."
    return f


def yields_factor(us10_prev: float | None, us10_change_bp: float | None,
                  us2_prev: float | None, weight: float, as_of: str | None) -> Factor:
    f = Factor("yields", "Rendements US 2a/10a (veille)", weight, as_of=as_of)
    if us10_prev is None:
        return f
    f.available = True
    parts = [f"10a {us10_prev:.2f} %"]
    if us2_prev is not None:
        parts.append(f"2a {us2_prev:.2f} %")
    if us10_change_bp is not None:
        parts.append(f"Δ10a {us10_change_bp:+.0f} pb")
        f.score = -_scaled(us10_change_bp, 9.0, weight)
        if abs(us10_change_bp) >= 6:
            sens = "hausse" if us10_change_bp > 0 else "détente"
            effet = "pèse sur les valorisations actions" if us10_change_bp > 0 else "soutient les valorisations actions"
            f.rationale = (f"{sens.capitalize()} marquée du 10 ans ({us10_change_bp:+.0f} pb la veille) : "
                           f"{effet} via le taux d'actualisation.")
        else:
            f.rationale = "Variation modérée des rendemements la veille : effet limité."
    else:
        f.rationale = "Niveau des taux connu mais variation veille indisponible."
    f.value = ", ".join(parts)
    return f


def dxy_factor(change_pct: float | None, weight: float, as_of: str | None) -> Factor:
    f = Factor("dxy", "Dollar US (veille)", weight, as_of=as_of)
    if change_pct is None:
        return f
    f.available = True
    f.value = f"{change_pct:+.2f} %"
    f.score = -_scaled(change_pct, 0.7, weight)
    f.rationale = ("Dollar en hausse la veille : durcissement des conditions financières, "
                   "léger vent contraire pour les actions." if change_pct > 0.15 else
                   "Dollar en baisse la veille : léger soutien aux actifs risqués."
                   if change_pct < -0.15 else "Dollar stable la veille : signal faible.")
    return f


def macro_factor(releases: list[dict], weight: float) -> Factor:
    f = Factor("macro", "Publications macro (≤ limite)", weight)
    if not releases:
        f.rationale = "Aucune publication macro dans la fenêtre, ou source non configurée."
        return f
    f.available = True
    total, notes = 0.0, []
    for r in releases:
        kind = r.get("kind")
        contrib = 0.0
        prev = r.get("previous")
        val = r.get("value")
        if val is None or prev in (None, 0):
            continue
        if kind == "inflation":
            mom = r.get("change_pct")
            if mom is not None:
                # > ~0.30 % m/m = inflation chaude -> anticipations de taux plus
                # hautes -> défavorable actions ; < ~0.15 % = modération -> favorable.
                contrib = -_scaled((mom - 0.22) * 100, 25.0, 1.0)
                notes.append(f"{r['name']} {mom:+.2f} % m/m "
                             + ("(chaud, pèse via les taux)" if mom > 0.3 else
                                "(modéré, favorable)" if mom < 0.15 else "(en ligne)"))
        elif kind == "claims":
            delta = val - prev
            contrib = -_scaled(delta, 35.0, 0.7)
            notes.append(f"Inscriptions chômage {val:.0f}k ({delta:+.0f}k) "
                         + ("(marché du travail se dégrade)" if delta > 15 else
                            "(marché du travail résilient)" if delta < -10 else ""))
        elif kind == "growth":
            chg = r.get("change_pct") or r.get("change")
            if chg is not None:
                contrib = _scaled(float(chg), 1.2, 0.6)
                notes.append(f"{r['name']} {chg:+.2f} "
                             + ("(activité solide — lecture ambivalente si les taux montent)"
                                if float(chg) > 0 else "(activité faible)"))
        elif kind == "unemployment":
            delta = val - prev
            contrib = -_scaled(delta * 10, 2.0, 0.8)
            notes.append(f"Chômage {val:.1f} % ({delta:+.1f} pt)")
        elif kind == "sentiment":
            delta = val - prev
            contrib = _scaled(delta, 6.0, 0.4)
            notes.append(f"{r['name']} {val:.1f} ({delta:+.1f})")
        total += contrib
        r["interpretation"] = notes[-1] if notes else ""
    f.score = max(-weight, min(weight, total * weight * 0.6))
    f.value = f"{len(releases)} publication(s)"
    f.rationale = ("Surprise mesurée vs valeur précédente (consensus historique "
                   "indisponible sur les sources gratuites). " + " ; ".join(notes))[:600] \
        if notes else "Publications présentes mais non interprétables."
    return f


def news_factor(articles: list[dict], weight: float) -> Factor:
    f = Factor("news", "Sentiment des actualités", weight)
    scored = [a for a in articles if a.get("category") != "geopolitics"]
    if not scored:
        f.rationale = "Aucune actualité horodatée disponible avant la limite."
        return f
    f.available = True
    weights = [2.0 if a.get("trusted") else 1.0 for a in scored]
    vals = [a["_sent"]["score"] for a in scored]
    wsum = sum(weights)
    avg = sum(v * w for v, w in zip(vals, weights)) / wsum if wsum else 0.0
    f.score = _scaled(avg * 100, 45.0, weight)
    n_pos = sum(1 for a in scored if a["_sent"]["sentiment"] == "positive")
    n_neg = sum(1 for a in scored if a["_sent"]["sentiment"] == "negative")
    f.value = f"{len(scored)} titres ({n_pos}+ / {n_neg}−)"
    f.rationale = (f"Lexique heuristique sur {len(scored)} titres (sources fiables "
                   f"pondérées ×2) : tonalité moyenne {avg:+.2f}.")
    return f


def geopolitics_factor(articles: list[dict], weight: float) -> Factor:
    f = Factor("geopolitics", "Risque géopolitique", weight)
    geo = [a for a in articles if a.get("category") == "geopolitics"]
    if not geo:
        f.rationale = "Aucune actualité géopolitique horodatée avant la limite."
        return f
    f.available = True
    risk = sum((2.0 if a.get("trusted") else 1.0) * len(a["_sent"]["geo_risk_terms"]) for a in geo)
    relief = sum((2.0 if a.get("trusted") else 1.0) * len(a["_sent"]["geo_relief_terms"]) for a in geo)
    n = len(geo)
    intensity = (risk - 1.5 * relief) / max(n, 1)
    # Asymétrique : le risque géopolitique pèse, l'apaisement ne compense qu'en partie.
    f.score = -weight * math.tanh(max(intensity - 0.35, -0.5) / 1.2)
    f.score = min(f.score, weight * 0.4)
    confirmed = sum(1 for a in geo if a.get("trusted"))
    f.value = f"{n} titres (dont {confirmed} de sources établies)"
    f.rationale = (f"Densité de termes de risque {risk:.0f} vs apaisement {relief:.0f} "
                   f"sur {n} titres. Les titres de sources non établies sont traités comme "
                   "non confirmés (pondération réduite).")
    return f


def earnings_factor(earnings: list[dict], weight: float, configured: bool) -> Factor:
    f = Factor("earnings", "Résultats d'entreprises", weight)
    if not configured:
        f.rationale = "Finnhub non configuré : facteur désactivé."
        return f
    if not earnings:
        f.available = True
        f.value = "aucune publication majeure"
        f.rationale = "Aucun résultat de grande capitalisation dans la fenêtre."
        return f
    f.available = True
    total, notes = 0.0, []
    for e in earnings:
        s = e.get("surprise_pct")
        if s is None:
            continue
        w = min(e.get("index_weight_pct", 0.1), 8.0) / 8.0
        total += math.tanh(s / 10.0) * w
        if e.get("index_weight_pct", 0) >= 1.0:
            notes.append(f"{e['symbol']} BPA {s:+.1f} % vs est.")
    f.score = max(-weight, min(weight, total * weight))
    f.value = f"{len(earnings)} publication(s)"
    f.rationale = ("Surprises BPA pondérées par le poids indiciel. " + " ; ".join(notes[:6])) \
        if notes else "Publications sans surprise exploitable."
    return f
