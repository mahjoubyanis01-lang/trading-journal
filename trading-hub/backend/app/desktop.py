"""Desktop launcher - run Trading Hub as a normal windowed app (§3, §96).

`python -m app.desktop` boots the local engine + API + UI in one process and
opens a native OS window pointing at it, so it feels like Opera / MT5 / the
Claude app: launch it, it opens, done. No terminals, no proxy.

Order of preference for the window:
1. pywebview native window (Edge WebView2 on Windows, WebKit on mac/Linux);
2. if pywebview isn't available, open the default browser at the local URL.

Either way the FastAPI server (which also serves the built frontend) runs in a
background thread on 127.0.0.1.
"""
from __future__ import annotations

import logging
import socket
import threading
import time
import urllib.request

import uvicorn

from .core.config import get_settings

log = logging.getLogger("trading_hub.desktop")


def _free_port(preferred: int) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]


def _wait_until_up(url: str, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as r:  # noqa: S310 - localhost only
                if r.status == 200:
                    return True
        except Exception:  # noqa: BLE001
            time.sleep(0.25)
    return False


def main() -> None:
    settings = get_settings()
    port = _free_port(settings.port)
    base = f"http://127.0.0.1:{port}"

    from .main import app as asgi_app

    config = uvicorn.Config(asgi_app, host="127.0.0.1", port=port, log_level="info")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    if not _wait_until_up(f"{base}/health"):
        log.error("Server did not start in time")
        raise SystemExit(1)
    log.info("Trading Hub running at %s", base)

    try:
        import webview  # type: ignore

        webview.create_window(
            settings.app_name, base, width=1360, height=860, min_size=(1024, 680),
        )
        webview.start()  # blocks until the window is closed
    except Exception:  # noqa: BLE001
        import webbrowser

        log.info("pywebview unavailable - opening in the default browser.")
        webbrowser.open(base)
        try:
            while thread.is_alive():
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    finally:
        server.should_exit = True


if __name__ == "__main__":
    main()
