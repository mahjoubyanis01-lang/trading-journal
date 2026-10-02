"""Trading Hub backend entrypoint (§5, §80-81, §87).

Boots the local engine: init DB, seed reference data, start the background
monitor loop, expose the REST API + a WebSocket that streams EventBus events to
the frontend so it updates only the components that changed (§81)."""
from __future__ import annotations

import asyncio
import contextlib
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .core.config import get_settings
from .core.events import bus
from .database.base import SessionLocal, init_db
from .database.seed import seed_reference
from .services.monitor import monitor_loop

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("trading_hub")


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    session = SessionLocal()
    try:
        seed_reference(session)
    finally:
        session.close()
    stop = asyncio.Event()
    task = None
    if get_settings().monitor_enabled:
        task = asyncio.create_task(monitor_loop(stop))
    log.info("Trading Hub engine started (mock_mode=%s)", get_settings().mock_mode)
    try:
        yield
    finally:
        stop.set()
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


app = FastAPI(title="Trading Hub", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Loopback API-token guard (local hardening). No-op when no token configured.
from .security.apitoken import ApiTokenMiddleware  # noqa: E402

app.add_middleware(ApiTokenMiddleware, token=get_settings().api_token)

from .api import accounts, dashboard, reference, system  # noqa: E402

# All API routes live under /api so they never collide with the SPA's own
# client-side routes (e.g. the page /accounts vs the API GET /api/accounts).
app.include_router(dashboard.router, prefix="/api")
app.include_router(accounts.router, prefix="/api")
app.include_router(reference.router, prefix="/api")
app.include_router(system.router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok", "app": get_settings().app_name}


def _mount_frontend() -> None:
    """Serve the built React app from the same origin (single-process desktop
    app - no dev server/proxy at runtime). SPA routes fall back to index.html."""
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    from .paths import frontend_dist

    dist = frontend_dist()
    index = dist / "index.html"
    if not get_settings().serve_frontend or not index.exists():
        log.info("Frontend build not found at %s - API-only mode.", dist)
        return
    if (dist / "assets").exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):  # noqa: ANN202 - FastAPI route
        candidate = dist / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)  # SPA client-side routing

    log.info("Serving frontend from %s", dist)


_mount_frontend()


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    """Live event stream (§81). The frontend reacts to typed events and
    refreshes only the affected view."""
    token = get_settings().api_token
    if token:
        import secrets as _secrets

        supplied = websocket.query_params.get("token", "")
        if not _secrets.compare_digest(supplied, token):
            await websocket.close(code=1008)
            return
    await websocket.accept()
    async with bus.subscribe() as queue:
        try:
            while True:
                event = await queue.get()
                await websocket.send_json(event.as_dict())
        except WebSocketDisconnect:
            pass
        except Exception:  # noqa: BLE001
            with contextlib.suppress(Exception):
                await websocket.close()
