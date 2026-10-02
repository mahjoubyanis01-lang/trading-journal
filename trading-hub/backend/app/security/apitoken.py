"""Loopback API-token guard (local hardening).

The server binds 127.0.0.1, so it is unreachable from the network. To also stop
*other local processes* from driving the engine, we use the Jupyter model: the
desktop launcher generates a random token per run, passes it to the window it
opens (``?token=…``) and to the server (``TH_API_TOKEN``). Every API/WebSocket
call must then present the token; the HTML shell and static assets stay open so
the page can bootstrap and read the token from its URL.

When no token is configured (plain ``uvicorn`` dev run) the guard is disabled so
local development stays frictionless.
"""
from __future__ import annotations

import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

HEADER = "x-th-token"


def generate_token() -> str:
    return secrets.token_urlsafe(24)


class ApiTokenMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, token: str) -> None:
        super().__init__(app)
        self._token = token

    async def dispatch(self, request: Request, call_next):
        if not self._token:
            return await call_next(request)  # dev mode: disabled
        path = request.url.path
        # Only /api/* is protected; the SPA shell, assets and /health stay open
        # so the page can bootstrap and read the token from its URL.
        if not path.startswith("/api/"):
            return await call_next(request)
        supplied = request.headers.get(HEADER) or request.query_params.get("token")
        if not supplied or not secrets.compare_digest(supplied, self._token):
            return JSONResponse({"detail": "invalid or missing API token"}, status_code=401)
        return await call_next(request)
