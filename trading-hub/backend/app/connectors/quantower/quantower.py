"""Quantower connector (§8, §88) - driver-gated, honest-empty.

Quantower is a .NET desktop platform. There is no remote/web API: automation runs
as in-app strategies, and external control requires a custom plugin running inside
Quantower on the host that bridges its API (e.g. over a local socket). No such
bridge is present on this host and none can be assumed, so this connector declares
no capabilities rather than faking one (§88). It exists so the platform is listed
truthfully with an exact requirement.

Nothing here performs I/O at import or in ``capabilities()``.
"""
from __future__ import annotations

from ..base import (
    ConnectResult,
    CredentialField,
    PlatformCapabilities,
    PlatformConnector,
)


class QuantowerConnector(PlatformConnector):
    key = "quantower"
    display_name = "Quantower"

    @classmethod
    def requirement(cls) -> str:
        return (
            "Quantower running on the host with a Trading Hub bridge plugin installed "
            "(Quantower's API is a .NET in-process SDK; external control needs an in-app "
            "plugin exposing a local socket). No bridge is present on this host, so the "
            "connector is inactive (not faked). `server` = the local bridge address once "
            "the plugin is installed."
        )

    @classmethod
    def extra_credential_fields(cls) -> list[CredentialField]:
        return [
            CredentialField("bridge_port", "Local bridge port", secret=False, required=False),
        ]

    @classmethod
    def needs_server(cls) -> bool:
        return True  # the local bridge address is required once installed

    def capabilities(self) -> PlatformCapabilities:
        return PlatformCapabilities()  # all False - honest (§88)

    def connect(self, login: str, password: str, server: str | None = None,
                extra: dict | None = None) -> ConnectResult:
        return ConnectResult(ok=False, message=self.requirement())
