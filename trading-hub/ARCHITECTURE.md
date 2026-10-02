# Trading Hub — Architecture

Built engine-first (spec §87): the UI is the thin layer, the local core engine
is where the logic lives. The frontend never holds business logic.

```
            React cockpit (frontend/)                 ← presentation only
                     │  REST + WebSocket
┌────────────────────┼─────────────────────────────────────────────────┐
│  FastAPI app (app/main.py)        API routers (app/api/)   WS /ws       │
│                     │                                                   │
│  ┌──────────────────┴─────────── CORE ENGINE ───────────────────────┐  │
│  │ services/        account_manager (workflow §12), market_service,  │  │
│  │                  strategy_manager, recovery_service, monitor,     │  │
│  │                  health, journal, sessions                        │  │
│  │ risk/            fixed-money + dynamic %, volume sizing, guards    │  │
│  │ markets/         universal catalogue + 4-level mapping + score    │  │
│  │ performance/     P&L, performance %, drawdown (5 types)           │  │
│  │ recovery/        auto-healing state machine (never closes trades) │  │
│  │ robots/          robot manager + heartbeat                        │  │
│  │ terminal/        terminal/instance manager                        │  │
│  │ alerts/ events/  EventBus (pub/sub) + alert catalogue             │  │
│  │ security/        credential manager (OS keyring / DPAPI)          │  │
│  └───────────────────────────────┬──────────────────────────────────┘  │
│                                   │                                      │
│  connectors/  PlatformConnector ABC + PlatformCapabilities + registry   │
│      ├── mock     (full simulation, fault injection)                    │
│      ├── mt5      (real reads; lifecycle delegated to Windows agent)    │
│      └── <new>    register a factory → available everywhere, no core edit│
│                                   │                                      │
│  database/   SQLAlchemy 2.0 models + SQLite (→ PostgreSQL-ready)         │
└──────────────────────────────────┼──────────────────────────────────────┘
                                    │
                    Platforms / Terminals / Robots (MT5, …)
```

## Request → engine flow (add account, spec §12)

```
POST /accounts
  → account_manager.add_account()
      1  validate credentials
      2  store password in OS secret store (handle only in DB)      security/
      3  create connector by platform key                           connectors/registry
      4  connect + read account (balance/equity)                    connector
      5  auto-name ("FundedNext 10K")
      6  allocate dedicated terminal instance (MOCK-001/MT5-017)     terminal/
      7  ensure robot instance                                       robots/
      8  discover instruments + map universal→real + confidence      markets/
      9  resolve effective risk (0.5% → 50 $ fixed money)            risk/
     10  configure robot (RISK_MODE + RISK_AMOUNT + real symbols)    connector
     11  apply template + start robot + heartbeat                    terminal/robots
     12  compute health, snapshot, emit WORKFLOW_STEP events         services/health + events
  → returns {account, steps[]}   (steps also streamed over /ws)
```

## Key design rules enforced in code

- **Capabilities are honest (§9, §88).** `PlatformConnector.capabilities()` gates
  every action; the MT5 connector reports *nothing* when its Windows runtime is
  absent instead of pretending. Unknown instrument specs stay `None`, and the
  risk engine refuses to size a position rather than guess.
- **Risk is money, not a bare % (§90).** Stored and shown as Mode + Amount +
  Reference + initial %. Default FIXED_MONEY; DYNAMIC_PERCENT is opt-in.
- **Config inheritance (§59).** Strategy defines defaults; an account overrides
  explicitly, and the override is surfaced as "override" vs "inherited".
- **Recovery restores infrastructure only (§52).** The state machine never
  exposes close/flatten/liquidate — verified by a test.
- **No trade copier (§2).** Nothing in the schema or services links one account's
  positions to another's. `positions` is monitoring-only.
- **Scalable (§72-73).** Async EventBus with bounded per-subscriber queues (a slow
  WebSocket never stalls the engine); the monitor does one cheap pass per interval
  and touches only changed rows; the frontend refetches only the affected view on
  the matching event.

## Database (spec §6)

SQLite via SQLAlchemy 2.0, portable types only → PostgreSQL is a connection-string
+ migration change, not a rewrite. Prop firm / broker / platform / account are
distinct tables (§10) so no single firm or platform is hard-coded. See
`app/database/models.py`.

## Adding a platform (spec §8)

1. Create `app/connectors/<key>/<key>.py` subclassing `PlatformConnector`.
2. Implement `capabilities()` honestly + the methods it enables.
3. `register("<key>", factory)` in `app/connectors/registry.py`.

It appears in `/platforms`, the Add-Account form, and the whole engine with no
other change.

## Tests (spec §69-71, §86)

- `tests/unit/` — risk, market mapping + confidence, drawdown, performance,
  config inheritance, health, heartbeat, recovery state machine.
- `tests/integration/` — the full add-account workflow and every acceptance
  test (1–10) through the real API, including fault injection + recovery.
