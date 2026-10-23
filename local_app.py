#!/usr/bin/env python3
"""Application locale Trading Journal + Options GEX.

Lance un serveur local, ouvre le navigateur, et prend automatiquement des
snapshots d'options CBOE (SPX, SPY, NDX, QQQ) toutes les 30 minutes pendant
les heures de marché US — directement depuis ce PC, sans dépendre de GitHub.
Les snapshots sont enregistrés dans data/options/ (même format que le workflow
GitHub Actions, donc le backtest reste unifié).

Usage : python local_app.py        (ou double-clic sur "Lancer Trading Journal.bat")
Arrêt : Ctrl+C (ou fermer la fenêtre).
"""
import http.server
import socket
import sys
import threading
import time
import webbrowser
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))
import fetch_options_snapshot as snapshots  # noqa: E402

INTERVAL_S = 30 * 60  # 30 minutes
PORTS = range(8765, 8786)


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # les données changent toutes les 30 min : jamais de cache navigateur
        if self.path.startswith(("/data/", "/tradingview/")):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):  # journal serveur silencieux
        pass


def snapshot_loop():
    while True:
        try:
            snapshots.run()
        except Exception as e:  # noqa: BLE001 — le serveur doit survivre à un échec réseau
            print(f"⚠ Snapshot échoué : {e}")
        time.sleep(INTERVAL_S)


def pick_port() -> int:
    for port in PORTS:
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise SystemExit(f"Aucun port libre entre {PORTS.start} et {PORTS.stop - 1}.")


def main():
    port = pick_port()
    url = f"http://127.0.0.1:{port}/"
    print("=" * 56)
    print("  Trading Journal + Options GEX — application locale")
    print(f"  ➜ {url}")
    print("  Snapshots CBOE automatiques toutes les 30 min")
    print("  (heures de marché US). Arrêt : Ctrl+C")
    print("=" * 56)

    threading.Thread(target=snapshot_loop, daemon=True).start()

    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", port), partial(Handler, directory=str(ROOT))
    )
    threading.Timer(0.8, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt de l'application.")


if __name__ == "__main__":
    main()
