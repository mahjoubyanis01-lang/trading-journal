"""Credential manager (§7).

Trading passwords are NEVER stored in the database, logs, JSON, API responses
or Git. They live in the OS secret store:

- Windows  -> Windows Credential Manager (via the ``keyring`` backend, which
  wraps DPAPI-protected storage).
- macOS    -> Keychain.
- Linux    -> Secret Service / kwallet.

The database only keeps a *handle* (``secret_ref``) of the form
``trading-hub:account:<id>``. Retrieval is deliberately explicit and scoped:
the only consumer is a platform connector at connect time. The frontend never
receives the password (§7).

If no OS keyring is available (headless CI, some containers), we fall back to
an in-memory store for the current process only, and log a clear warning. The
secret still never touches disk.
"""
from __future__ import annotations

import logging

log = logging.getLogger("trading_hub.security")

_SERVICE = "trading-hub"

try:  # pragma: no cover - depends on host
    import keyring

    kr = keyring.get_keyring()
    # A priority <= 0 backend (e.g. keyring's fail/null backend) is not usable.
    _HAS_KEYRING = getattr(kr, "priority", 0) > 0
except Exception:  # noqa: BLE001
    keyring = None  # type: ignore[assignment]
    _HAS_KEYRING = False

# Process-only fallback (never persisted). Keyed by secret_ref.
_memory_store: dict[str, str] = {}


def _ref(account_id: int, field: str = "password") -> str:
    # One handle per (account, field) so brokers needing api_key/secret/etc.
    # keep every secret in the OS store, never the DB (§7).
    return f"account:{account_id}:{field}" if field != "password" else f"account:{account_id}"


class CredentialManager:
    """Stateless helper around the OS secret store."""

    @staticmethod
    def backend() -> str:
        return "os-keyring" if _HAS_KEYRING else "process-memory"

    @staticmethod
    def store_field(account_id: int, field: str, value: str) -> str:
        """Persist one named secret field (api_key, api_secret, ...)."""
        return CredentialManager._store_ref(_ref(account_id, field), value)

    @staticmethod
    def retrieve_field(account_id: int, field: str) -> str | None:
        return CredentialManager.retrieve(_ref(account_id, field))

    @staticmethod
    def delete_account(account_id: int, fields: list[str]) -> None:
        for f in ["password", *fields]:
            CredentialManager.delete(_ref(account_id, f))

    @staticmethod
    def _store_ref(ref: str, value: str) -> str:
        if _HAS_KEYRING:
            try:
                keyring.set_password(_SERVICE, ref, value)
                return ref
            except Exception:  # noqa: BLE001
                log.warning("OS keyring write failed; using process-memory store.")
        _memory_store[ref] = value
        return ref

    @staticmethod
    def store(account_id: int, password: str) -> str:
        """Persist a password, return its opaque handle (safe to store in DB)."""
        ref = _ref(account_id)
        if _HAS_KEYRING:
            try:
                keyring.set_password(_SERVICE, ref, password)
                return ref
            except Exception:  # noqa: BLE001 - degrade, never crash on secrets
                log.warning("OS keyring write failed; using process-memory store.")
        else:
            log.warning(
                "No OS keyring available - using process-memory credential store. "
                "Install a keyring backend on the target machine for persistence."
            )
        _memory_store[ref] = password
        return ref

    @staticmethod
    def retrieve(secret_ref: str) -> str | None:
        """Fetch a password by handle. Only connectors should call this."""
        if secret_ref in _memory_store:
            return _memory_store[secret_ref]
        if _HAS_KEYRING:
            try:
                return keyring.get_password(_SERVICE, secret_ref)
            except Exception:  # noqa: BLE001
                return None
        return None

    @staticmethod
    def delete(secret_ref: str) -> None:
        _memory_store.pop(secret_ref, None)
        if _HAS_KEYRING:
            try:
                keyring.delete_password(_SERVICE, secret_ref)
            except Exception:  # noqa: BLE001 - deleting a missing secret is fine
                pass


credential_manager = CredentialManager()
