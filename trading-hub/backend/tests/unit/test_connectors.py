"""Offline connector contract tests (§8, §9, §88).

These NEVER touch the network. They assert each registered connector exposes a
coherent, honest surface: capabilities()/requirement()/extra_credential_fields()/
needs_server() all work without I/O, the four REST broker connectors declare reads
(and no EA/robot lifecycle), and the driver-gated connectors stay inert on a box
without their SDK/host dependency.
"""
from __future__ import annotations

import pytest

from app.connectors import registry
from app.connectors.base import CredentialField, PlatformCapabilities

# Every platform the seed lists must be registered (§95).
SEED_KEYS = {
    "mock", "mt5", "mt4", "ctrader", "tradovate", "ninjatrader", "rithmic",
    "dxtrade", "matchtrader", "tradelocker", "quantower",
}

# Real REST broker connectors: implemented, reads only (no EA lifecycle).
REST_KEYS = {"tradovate", "tradelocker", "dxtrade", "matchtrader"}

# Honest driver-gated connectors: inert on this (Linux, no SDK) box.
DRIVER_GATED_KEYS = {"ctrader", "ninjatrader", "rithmic", "quantower"}


def test_registry_covers_all_seed_platforms():
    assert SEED_KEYS <= set(registry.available_keys())


@pytest.mark.parametrize("key", sorted(SEED_KEYS))
def test_every_connector_offline_surface(key):
    """Instantiate + read the full declarative surface with no network I/O."""
    conn = registry.create(key)

    caps = conn.capabilities()
    assert isinstance(caps, PlatformCapabilities)
    # as_dict must be a plain bool map (serialisable to the UI).
    assert all(isinstance(v, bool) for v in caps.as_dict().values())

    req = conn.requirement()
    assert isinstance(req, str)

    fields = conn.extra_credential_fields()
    assert isinstance(fields, list)
    assert all(isinstance(f, CredentialField) for f in fields)

    assert isinstance(conn.needs_server(), bool)


@pytest.mark.parametrize("key", sorted(REST_KEYS))
def test_rest_connectors_read_but_no_robot(key):
    """Broker APIs can read the account but have no EA to start/stop (§88)."""
    caps = registry.create(key).capabilities()
    assert caps.can_connect is True
    assert caps.can_read_account is True
    assert caps.can_read_balance is True
    assert caps.can_read_equity is True
    assert caps.can_read_positions is True
    assert caps.can_discover_markets is True
    # Honesty check: no robot/terminal lifecycle on a broker REST API.
    assert caps.can_start_robot is False
    assert caps.can_stop_robot is False
    assert caps.can_restart_robot is False
    assert caps.can_install_robot is False
    assert caps.can_configure_robot is False
    assert caps.can_create_terminal_instance is False


@pytest.mark.parametrize("key", sorted(REST_KEYS))
def test_rest_connectors_requirement_states_unverified(key):
    """Each REST connector must admit it is not yet verified live (§88)."""
    req = registry.create(key).requirement().lower()
    assert "not yet verified" in req


def test_tradovate_defaults_to_demo_no_server_needed():
    conn = registry.create("tradovate")
    # A sensible default base URL means no server value is required.
    assert conn.needs_server() is False
    # Has the documented API-application credential fields.
    names = {f.name for f in conn.extra_credential_fields()}
    assert {"app_id", "cid", "sec", "device_id"} <= names


@pytest.mark.parametrize("key", ["tradelocker", "dxtrade", "matchtrader"])
def test_broker_url_rest_connectors_need_server(key):
    assert registry.create(key).needs_server() is True


@pytest.mark.parametrize("key", sorted(DRIVER_GATED_KEYS))
def test_driver_gated_connectors_inert_here(key):
    """No SDK/host dependency on this box -> all capabilities False, but the
    connector still explains exactly what it needs."""
    conn = registry.create(key)
    caps = conn.capabilities().as_dict()
    assert not any(caps.values()), f"{key} declared a capability it cannot perform"
    assert conn.requirement().strip(), f"{key} must state its requirement"


@pytest.mark.parametrize("key", sorted(DRIVER_GATED_KEYS))
def test_driver_gated_connect_refuses_cleanly(key):
    """Connecting without the dependency returns an honest failure, not a crash."""
    result = registry.create(key).connect("login", "password", server=None, extra={})
    assert result.ok is False
    assert result.message


def test_mock_and_mt5_still_registered():
    # The pre-existing connectors must survive the wiring change.
    assert "mock" in registry.available_keys()
    assert "mt5" in registry.available_keys()
    assert registry.create("mock").capabilities().can_start_robot is True
