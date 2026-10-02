"""Verify a connector against a REAL broker account, from the command line.

This is how a REST connector moves from "implemented" to "verified": run it once
with your own (ideally demo) credentials and see it read the live account.

    python -m app.connectors.probe tradovate \
        --login you@example.com --password '***' --server demo \
        --extra app_id=MyApp --extra cid=1234 --extra sec='***' --extra device_id=abc

    python -m app.connectors.probe tradelocker \
        --login you@example.com --password '***' --server https://demo.tradelocker.com \
        --extra tl_server=OSP-DEMO

It prints capabilities, the connection result, account balance/equity, a few
discovered instruments and the open-position count. Secrets are never printed.
Exit code 0 on success, 1 on failure.
"""
from __future__ import annotations

import argparse
import sys

from . import registry


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="probe", description="Verify a connector live.")
    ap.add_argument("platform", help="connector key, e.g. tradovate, tradelocker, dxtrade, matchtrader")
    ap.add_argument("--login", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--server", default=None, help="server/endpoint ('demo'/'live' or a URL)")
    ap.add_argument("--extra", action="append", default=[], metavar="name=value",
                    help="extra credential field (repeatable)")
    args = ap.parse_args(argv)

    try:
        conn = registry.create(args.platform)
    except KeyError:
        print(f"Unknown platform '{args.platform}'. Known: {', '.join(registry.available_keys())}")
        return 1

    caps = conn.capabilities()
    print(f"Connector: {conn.display_name} ({args.platform})")
    print(f"Requirement: {conn.requirement() or 'ready'}")
    print(f"can_connect={caps.can_connect} can_read_account={caps.can_read_account} "
          f"can_discover_markets={caps.can_discover_markets}")
    if not caps.can_connect:
        print("This connector cannot connect on this machine (see requirement above).")
        return 1

    extra = {}
    for item in args.extra:
        if "=" not in item:
            print(f"Bad --extra '{item}', expected name=value")
            return 1
        k, v = item.split("=", 1)
        extra[k.strip()] = v

    print("\nConnecting…")
    res = conn.connect(args.login, args.password, args.server, extra)
    if not res.ok:
        print(f"  ✗ connect failed: {res.message}")
        return 1
    acc = res.account
    print(f"  ✓ connected — login={acc.login} balance={acc.balance} {acc.currency} "
          f"equity={acc.equity} server={acc.server}")

    if caps.can_discover_markets:
        try:
            markets = conn.get_available_markets()
            print(f"\nInstruments discovered: {len(markets)} (first 5)")
            for inst in markets[:5]:
                print(f"  - {inst.symbol}  {inst.description or ''}  tick={inst.tick_size}")
        except Exception as e:  # noqa: BLE001
            print(f"  (market discovery error: {e})")

    if caps.can_read_positions:
        try:
            print(f"\nOpen positions: {len(conn.get_positions())}")
        except Exception as e:  # noqa: BLE001
            print(f"  (positions error: {e})")

    conn.disconnect()
    print("\n✓ Live verification succeeded. This connector works against your account.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
