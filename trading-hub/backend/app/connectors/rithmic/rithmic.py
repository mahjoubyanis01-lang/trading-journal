"""Rithmic connector (§8, §88) - driver-gated, honest-empty.

Rithmic is reached through R|API+ (a licensed, Protobuf-over-TLS protocol) or the
R|Protocol gateway. Both require a signed license agreement, per-user gateway
credentials and a vendor SDK that cannot be redistributed or `pip install`-ed.
There is no library to import on this host, so this connector declares no
capabilities and will not fake the protocol (§88). It exists so the platform is
listed truthfully with an exact requirement rather than silently working.

Nothing here performs I/O at import or in ``capabilities()``.
"""
from __future__ import annotations

from ..base import (
    ConnectResult,
    CredentialField,
    PlatformCapabilities,
    PlatformConnector,
)


class RithmicConnector(PlatformConnector):
    key = "rithmic"
    display_name = "Rithmic"

    @classmethod
    def requirement(cls) -> str:
        return (
            "Rithmic R|API+ access: a signed Rithmic license agreement, the vendor "
            "R|API+ SDK/gateway installed on the host, a system/gateway name "
            "(e.g. 'Rithmic Paper Trading'), and per-user credentials (user, password, "
            "app name/version). The SDK is licensed and cannot be bundled; no driver is "
            "present on this host, so the connector is inactive (not faked)."
        )

    @classmethod
    def extra_credential_fields(cls) -> list[CredentialField]:
        return [
            CredentialField("system_name", "Rithmic system/gateway", secret=False, required=True),
            CredentialField("app_name", "App name", secret=False, required=True),
            CredentialField("app_version", "App version", secret=False, required=False),
        ]

    @classmethod
    def needs_server(cls) -> bool:
        return True  # the R|API+ gateway host/system is required

    def capabilities(self) -> PlatformCapabilities:
        return PlatformCapabilities()  # all False - honest (§88)

    def connect(self, login: str, password: str, server: str | None = None,
                extra: dict | None = None) -> ConnectResult:
        return ConnectResult(ok=False, message=self.requirement())
