import { useEffect, useState } from 'react';
import { Plus, Wifi, WifiOff, OctagonX } from 'lucide-react';
import { Button } from '../ui/Button';
import { eventBus, useEvents } from '../../services/useEvents';
import { api } from '../../services/api';
import { useToast } from '../ui/Toast';
import { money, pct, signClass } from '../../lib/format';
import type { Dashboard } from '../../types';

function Stat({ label, value, className }: { label: string; value: string; className?: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-2xs uppercase tracking-wide text-zinc-600">{label}</span>
      <span className={`tabular text-sm font-semibold ${className ?? 'text-zinc-200'}`}>{value}</span>
    </div>
  );
}

export function TopBar({ dashboard, onAddAccount }: { dashboard: Dashboard | null; onAddAccount: () => void }) {
  const [connected, setConnected] = useState(eventBus.isConnected());
  const toast = useToast();

  async function panicStop() {
    if (!window.confirm('Stop ALL robots now? Open positions are left untouched.')) return;
    try {
      const res = await api.stopAll();
      toast('success', `Stopped ${res.stopped} robot(s). Positions left open.`);
    } catch (e) {
      toast('error', e instanceof Error ? e.message : 'Stop-all failed');
    }
  }

  // Keep a live view of the WS connection state.
  useEvents(['*'], () => setConnected(true));
  useEffect(() => {
    const t = window.setInterval(() => setConnected(eventBus.isConnected()), 2000);
    return () => window.clearInterval(t);
  }, []);

  return (
    <header className="flex h-14 shrink-0 items-center justify-between gap-6 border-b border-edge bg-panel px-5">
      <div className="flex items-center gap-7 overflow-x-auto">
        {dashboard ? (
          <>
            <Stat label="Accounts" value={String(dashboard.accounts)} />
            <Stat label="Capital" value={money(dashboard.capital, 'USD', { compact: true })} />
            <Stat label="Equity" value={money(dashboard.equity_total, 'USD', { compact: true })} />
            <Stat
              label="P&L Today"
              value={money(dashboard.pnl_today, 'USD', { compact: true })}
              className={signClass(dashboard.pnl_today)}
            />
            <Stat
              label="Perf"
              value={pct(dashboard.performance_pct)}
              className={signClass(dashboard.performance_pct)}
            />
            <Stat
              label="Robots"
              value={`${dashboard.robots_active}/${dashboard.robots_total}`}
              className="text-op"
            />
          </>
        ) : (
          <span className="text-sm text-zinc-600">Trading Hub</span>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-3">
        <span
          className={`flex items-center gap-1.5 text-2xs ${connected ? 'text-op' : 'text-idle'}`}
          title={connected ? 'Live updates connected' : 'Disconnected from live feed'}
        >
          {connected ? <Wifi size={13} /> : <WifiOff size={13} />}
          {connected ? 'LIVE' : 'OFFLINE'}
        </span>
        <button
          onClick={panicStop}
          title="Emergency: stop all robots (positions stay open)"
          className="flex items-center gap-1.5 rounded-md border border-err/50 px-2.5 py-1.5 text-2xs font-semibold text-err transition hover:bg-err/10"
        >
          <OctagonX size={14} />
          STOP ALL
        </button>
        <Button variant="primary" size="sm" onClick={onAddAccount}>
          <Plus size={14} />
          Add account
        </Button>
      </div>
    </header>
  );
}
