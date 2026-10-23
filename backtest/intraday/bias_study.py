"""Pouvoir prédictif des variables de biais (connues avant 9h30 NY) sur la
direction de la séance NY : globale (9h30-16h), matin (9h30-12h), après-midi
(12h-16h). In-sample <= 2023, hors échantillon >= 2024."""
import math
import pickle
import sys
from research import build, load_macro, add_macro

CUT = int(__import__("os").environ.get("CUT", "2024"))


def sgn(x):
    return 1 if x > 0 else -1 if x < 0 else 0


FEATURES = {
    "tendance 20 j": lambda f: f.get("trend20"),
    "tendance 50 j": lambda f: f.get("trend50"),
    "nuit (clôture veille -> 9h25)": lambda f: sgn(f["ret_on"]) if "ret_on" in f else None,
    "Londres (2h -> 9h25)": lambda f: sgn(f["ret_lon"]) if "ret_lon" in f else None,
    "gap à l'ouverture": lambda f: sgn(f["gap"]) if "gap" in f else None,
    "ouverture hors range veille": lambda f: f.get("open_vs_pd") or None,
    "clôture veille dans son range (haut/bas)": lambda f: sgn(f["clv_prev"]) if "clv_prev" in f else None,
    "séance veille (hausse/baisse)": lambda f: sgn(f["ret_prev"]) if "ret_prev" in f else None,
    "VIX en baisse la veille (= +1)": lambda f: -sgn(f["vix_chg"]) if "vix_chg" in f else None,
    "VIX structure normale (VIX<VIX3M = +1)": lambda f: (1 if f["vix_ts"] < 1 else -1) if "vix_ts" in f else None,
    "taux 10 ans en baisse la veille (= +1)": lambda f: -sgn(f["y10_chg"]) if "y10_chg" in f else None,
    "dollar en baisse la veille (= +1)": lambda f: -sgn(f["usd_chg"]) if "usd_chg" in f else None,
}


def evaluate(days, label):
    print(f"\n===== {label} : {len(days)} séances ({days[0].d} -> {days[-1].d}) =====")
    print(f"{'variable':<42} | {'cible':<6} | {'in-sample: n  accord  t':<26} | {'hors échant.: n  accord  t':<26}")
    for name, fn in FEATURES.items():
        for tgt in ("rth", "am", "pm"):
            row = f"{name:<42} | {tgt:<6} |"
            for part in (lambda D: D.d.year < CUT, lambda D: D.d.year >= CUT):
                xs = []
                for D in days:
                    if not part(D):
                        continue
                    v = fn(D.f)
                    if not v:
                        continue
                    y = getattr(D, "y_" + tgt)
                    xs.append(v * y)
                if len(xs) < 30:
                    row += f" {'-':>26} |"
                    continue
                n = len(xs)
                hit = 100 * sum(1 for x in xs if x > 0) / n
                mu = sum(xs) / n
                sd = math.sqrt(sum((x - mu) ** 2 for x in xs) / (n - 1)) or 1e-12
                t = mu / (sd / math.sqrt(n))
                row += f" {n:>5} {hit:>6.1f}% {t:>+6.2f}{' *' if abs(t) > 2 else '  '}     |"
            print(row)
    # Jours d'événement : amplitude
    for nm, cond in (("jour de FOMC", lambda D: D.f.get("fomc")), ("annonce 8h30 (bougie > 4x le bruit)", lambda D: D.f.get("ev830", 0) > 4)):
        ev = [D for D in days if cond(D)]
        ot = [D for D in days if not cond(D)]
        rng = lambda ds: sum(abs(D.y_rth) for D in ds) / max(1, len(ds)) * 100
        print(f"{nm}: {len(ev)} séances, |mouvement NY| moyen {rng(ev):.2f} % contre {rng(ot):.2f} % les autres jours")


if __name__ == "__main__":
    macro, fomc = load_macro()
    res = {}
    for inst, lab in (("usa500idxusd", "S&P 500 (US500)"), ("usatechidxusd", "Nasdaq 100 (US Tech)")):
        days = build(inst)
        add_macro(days, macro, fomc)
        res[inst] = days
        evaluate(days, lab)
    pickle.dump(res, open("days.pkl", "wb"))
