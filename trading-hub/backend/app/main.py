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

from .api import accounts, dashboard, reference, system  # noqa: E402

app.include_router(dashboard.router)
app.include_router(accounts.router)
app.include_router(reference.router)
app.include_router(system.router)


@app.get("/health")
def health():
    return {"status": "ok", "app": get_settings().app_name}


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    """Live event stream (§81). The frontend reacts to typed events and
    refreshes only the affected view."""
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
