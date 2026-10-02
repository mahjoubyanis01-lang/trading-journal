"""Connector registry (§8).

Platforms register a factory under a key. The engine creates connectors by key
without importing concrete classes, so adding a NewPlatformConnector is a
one-line registration and never edits the core (§8, §94).
"""
from __future__ import annotations

from collections.abc import Callable

from .base import PlatformConnector
from .mock.mock import MockConnector
from .mt5.mt5 import MT5Connector

ConnectorFactory = Callable[..., PlatformConnector]

_REGISTRY: dict[str, ConnectorFactory] = {}


def register(key: str, factory: ConnectorFactory) -> None:
    _REGISTRY[key] = factory


def create(key: str, **kwargs) -> PlatformConnector:
    if key not in _REGISTRY:
        raise KeyError(f"No connector registered for '{key}'")
    return _REGISTRY[key](**kwargs)


def available_keys() -> list[str]:
    return sorted(_REGISTRY)


# Built-in connectors. Others (cTrader, Tradovate, NinjaTrader, ...) register
# here as they are implemented; until then they are simply absent from the UI.
register("mock", lambda seed_balance=10_000.0: MockConnector(seed_balance=seed_balance))
register("mt5", lambda: MT5Connector())
