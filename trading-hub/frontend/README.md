# Trading Hub — Frontend

A local desktop-style trading control center. Dark, dense, "everything
automatic, exceptions visible". Built with Vite + React 18 + TypeScript +
Tailwind CSS v3.4, Recharts, lucide-react and react-router-dom.

## Prerequisites

- Node 22 / npm 10
- The Python/FastAPI backend running on `http://localhost:8000`

## Run

```bash
npm install
npm run dev     # starts Vite on http://localhost:5173 (needs backend on :8000)
```

The dev server proxies:

- `/api/*` → `http://localhost:8000/*` (the `/api` prefix is stripped by a
  rewrite, because the backend routes have no prefix)
- `/ws` → the backend WebSocket (for live updates)

So the app talks to `/api/...` and `/ws` with no CORS and no hard-coded host.

## Build

```bash
npm run build   # tsc -b && vite build  — this is the release gate
npm run preview # serve the production build locally
```

## First run with no data

The Dashboard and Accounts pages show an empty state with a **"Seed 50 demo
accounts"** button (`POST /seed-demo {count:50}`) and an **"Add account"**
button, so a fresh install has something to show immediately.

## Structure

- `src/services/api.ts` — tiny typed fetch client (all calls go through `/api`)
- `src/services/useEvents.ts` — shared `/ws` WebSocket hook with auto-reconnect
- `src/hooks/data.ts` — `useDashboard`, `useAccounts`, … fetching hooks that
  re-fetch (debounced) on relevant live events
- `src/components/ui/*` — hand-written shadcn-style primitives (Card, Button,
  Badge, Table, Modal, Input, Select, Toast)
- `src/pages/*` — Dashboard, Accounts, Account detail, Prop Firms, Robots,
  Markets, Attention, Settings

## Color = state only

green = operational · orange = attention · red = error · gray =
inactive/disconnected · blue = pending/info.
