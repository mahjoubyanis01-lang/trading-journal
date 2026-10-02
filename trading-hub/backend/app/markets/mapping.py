"""Market mapping engine (§25-27).

Resolves a universal market to a broker's real symbol using four escalating
signals and produces a 0-100 confidence score (§26):

  L1 exact symbol match ............ ~100  (EURUSD -> EURUSD)
  L1' exact after broker-suffix strip ~98  (EURUSD -> EURUSDm)
  L2 known alias ................... ~93-95 (NASDAQ100 -> USTEC)
  L3 description keywords .......... ~75-88 (USTEC desc "US Tech 100")
  L4 instrument characteristics .... ~55-72 (asset class + currencies)

Thresholds (configurable, §26):
  >= auto (90)   -> applied automatically
  confirm..auto  -> user confirmation
  < confirm (70) -> unresolved (§27)

The engine returns ranked candidates so the "search on platform" UI (§28) can
show the alternatives, and never invents a match (§88): no signal => no result.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..connectors.base import InstrumentInfo
from ..core.enums import MappingStatus
from .universal import UniversalDef

# Broker suffixes/affixes that decorate an otherwise-standard symbol.
_SUFFIX_TOKENS = ("MICRO", "CASH", "SPOT", "PRO", "ECN", "STP", "SB", "RAW")
_SUFFIX_CHARS = ("M", "C", "I", "Z", "R", "X", "#", "+", "-", ".")


def normalize(symbol: str) -> str:
    """Upper-case and strip non-alphanumerics: 'NAS100.cash' -> 'NAS100CASH'."""
    return re.sub(r"[^A-Z0-9]", "", symbol.upper())


def strip_broker_suffix(norm: str, root: str) -> bool:
    """True if ``norm`` is ``root`` plus only a recognised broker suffix."""
    if not norm.startswith(root):
        return False
    tail = norm[len(root):]
    if tail == "":
        return True
    for tok in _SUFFIX_TOKENS:
        if tail == tok:
            return True
    # single/paired decorative chars, e.g. 'M', 'C', 'PRO' handled above
    return all(ch in {c for c in "MCIZRX"} for ch in tail) and len(tail) <= 3


@dataclass(slots=True)
class Candidate:
    real_symbol: str
    confidence: float
    reason: str
    description: str | None = None


class MarketMappingEngine:
    def __init__(self, auto: float = 90.0, confirm: float = 70.0) -> None:
        self.auto = auto
        self.confirm = confirm

    # --- scoring ---------------------------------------------------------
    def _score(self, u: UniversalDef, inst: InstrumentInfo) -> tuple[float, str]:
        norm_inst = normalize(inst.symbol)
        aliases = [normalize(a) for a in (u.aliases or [u.symbol])]
        root = normalize(u.symbol)

        best = 0.0
        reason = ""

        # L1 / L1'
        if norm_inst == root:
            return 100.0, "exact symbol"
        if strip_broker_suffix(norm_inst, root):
            best, reason = 98.0, "exact symbol + broker suffix"

        # L2 aliases
        for alias in aliases:
            if alias == root:
                continue
            if norm_inst == alias and 95.0 > best:
                best, reason = 95.0, f"alias {alias}"
            elif strip_broker_suffix(norm_inst, alias) and 93.0 > best:
                best, reason = 93.0, f"alias {alias} + suffix"
            elif alias and alias in norm_inst and 88.0 > best:
                best, reason = 88.0, f"alias {alias} contained"

        # L3 description keywords
        if inst.description and u.keywords:
            desc = inst.description.lower()
            hits = sum(1 for kw in u.keywords if kw.lower() in desc)
            if hits:
                score = 70.0 + min(hits / len(u.keywords), 1.0) * 18.0  # 70..88
                if score > best:
                    best, reason = score, f"description ({hits} keyword(s))"

        # L4 characteristics
        char = 0.0
        if inst.asset_class == u.asset_class and u.asset_class.value != "unknown":
            char += 40.0
        if u.base and inst.base_currency and inst.base_currency.upper() == u.base.upper():
            char += 18.0
        if u.quote and inst.quote_currency and inst.quote_currency.upper() == u.quote.upper():
            char += 14.0
        if char and char < 75.0 and char > best:
            best, reason = char, "instrument characteristics"

        return round(best, 1), reason

    # --- public API ------------------------------------------------------
    def candidates(
        self, u: UniversalDef, instruments: list[InstrumentInfo], limit: int = 8
    ) -> list[Candidate]:
        scored: list[Candidate] = []
        for inst in instruments:
            score, reason = self._score(u, inst)
            if score > 0:
                scored.append(Candidate(inst.symbol, score, reason, inst.description))
        scored.sort(key=lambda c: c.confidence, reverse=True)
        return scored[:limit]

    def resolve(
        self, u: UniversalDef, instruments: list[InstrumentInfo]
    ) -> tuple[Candidate | None, MappingStatus]:
        cands = self.candidates(u, instruments, limit=1)
        if not cands:
            return None, MappingStatus.UNRESOLVED
        best = cands[0]
        if best.confidence >= self.auto:
            return best, MappingStatus.AUTO
        if best.confidence >= self.confirm:
            return best, MappingStatus.NEEDS_CONFIRMATION
        return best, MappingStatus.UNRESOLVED
