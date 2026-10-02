import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Activity,
  ArrowRight,
  Bot,
  CircleDot,
  Loader2,
  TriangleAlert,
  Wallet,
} from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { useDashboard } from '../hooks/data';
import { api } from '../services/api';
import { useToast } from '../components/ui/Toast';
import { useAddAccount } from '../components/AddAccountContext';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import { Kpi, PageHeader } from '../components/ui/Kpi';
import { Button } from '../components/ui/Button';
import { HealthBadge } from '../components/ui/Badge';
import { EmptyState, ErrorState, Loading } from '../components/ui/States';
import { healthColor, money, pct, relTime, signClass, signedMoney } from '../lib/format';
import type { AccountRow, EventItem, PropFirmSummary } from '../types';

export function Dashboard() {
  const { data, loading, error, refetch } = useDashboard();
  const navigate = useNavigate();
  const toast = useToast();
  const openAdd = useAddAccount();
  const [seeding, setSeeding] = useState(false);

  async function seed() {
    setSeeding(true);
    try {
      const res = await api.seedDemo(50);
      toast('success', `Seeded ${res.created} demo accounts`);
      refetch();
    } catch (e) {
      toast('error', e instanceof Error ? e.message : 'Seed failed');
    } finally {
      setSeeding(false);
    }
  }

  if (loading && !data) return <Loading label="Loading dashboard…" />;
  if (error && !data) return <ErrorState message={error} onRetry={refetch} />;
  if (!data) return null;

  if (data.accounts === 0) {
    return (
      <>
        <PageHeader title="Dashboard" subtitle="Trading control center" />
        <EmptyState
          icon={<Wallet size={40} />}
          title="No accounts yet"
          description="Seed a batch of demo accounts to explore the cockpit, or add a real one."
        >
          <Button variant="primary" onClick={seed} disabled={seeding}>
            {seeding && <Loader2 size={14} className="animate-spin" />}
            Seed 50 demo accounts
          </Button>
          <Button onClick={openAdd}>Add account</Button>
        </EmptyState>
      </>
    );
  }

  const op = data.by_health.operational ?? 0;
  const attn = data.by_health.attention ?? 0;
  const errCount = data.by_health.error ?? 0;
  const healthChip =
    attn + errCount === 0
      ? { text: `${op}/${data.accounts} OPERATIONAL`, cls: 'border-op/40 bg-op/10 text-op' }
      : errCount > 0
        ? { text: `${errCount} ERROR · ${attn} ATTENTION`, cls: 'border-err/40 bg-err/10 text-err' }
        : { text: `${attn} ATTENTION`, cls: 'border-attn/40 bg-attn/10 text-attn' };

  return (
    <>
      <PageHeader
        title="Dashboard"
        subtitle="Trading control center"
        actions={
          <>
            <span
              className={`flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium ${healthChip.cls}`}
            >
              <CircleDot size={13} />
              {healthChip.text}
            </span>
            <Button onClick={openAdd} variant="primary" size="sm">
              Add account
            </Button>
          </>
        }
      />

      {/* KPI row */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
        <Kpi label="Accounts" value={data.accounts} sub={`${data.prop_firms.length} prop firms`} />
        <Kpi label="Capital managed" value={money(data.capital, 'USD', { compact: true })} />
        <Kpi label="Balance total" value={money(data.balance_total, 'USD', { compact: true })} />
        <Kpi label="Equity total" value={money(data.equity_total, 'USD', { compact: true })} />
        <Kpi
          label="Robots active"
          value={`${data.robots_active}/${data.robots_total}`}
          accent="green"
          sub="running"
        />
        <Kpi
          label="P&L Today"
          value={signedMoney(data.pnl_today)}
          valueClass={signClass(data.pnl_today)}
          accent={data.pnl_today >= 0 ? 'green' : 'red'}
        />
        <Kpi
          label="P&L Month"
          value={signedMoney(data.pnl_month)}
          valueClass={signClass(data.pnl_month)}
          accent={data.pnl_month >= 0 ? 'green' : 'red'}
        />
        <Kpi
          label="Performance"
          value={pct(data.performance_pct)}
          valueClass={signClass(data.performance_pct)}
          accent={data.performance_pct >= 0 ? 'green' : 'red'}
        />
        <Kpi
          label="Drawdown global"
          value={pct(-Math.abs(data.drawdown_global))}
          valueClass="text-err"
          accent="orange"
        />
        <HealthMini byHealth={data.by_health} total={data.accounts} />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
        <div className="xl:col-span-2 space-y-4">
          <BalanceEquityChart firms={data.prop_firms} />
          <AttentionPanel rows={data.attention} onOpen={(id) => navigate(`/accounts/${id}`)} />
        </div>
        <div className="space-y-4">
          <CapitalByFirm firms={data.prop_firms} onOpen={(id) => navigate(`/prop-firms/${id}`)} />
          <RecentEvents events={data.recent_events} />
        </div>
      </div>
    </>
  );
}

function HealthMini({ byHealth, total }: { byHealth: Record<string, number>; total: number }) {
  const order = ['operational', 'attention', 'error', 'disconnected', 'pending'];
  return (
    <div className="relative overflow-hidden rounded-lg border border-edge bg-panel px-4 py-3">
      <div className="text-2xs uppercase tracking-wide text-zinc-500">Health</div>
      <div className="mt-2 flex h-2 overflow-hidden rounded-full bg-panel2">
        {order.map((h) => {
          const n = byHealth[h] ?? 0;
          if (!n) return null;
          const c = healthColor(h);
          return <span key={h} className={c.dot} style={{ width: `${(n / total) * 100}%` }} />;
        })}
      </div>
      <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1">
        {order
          .filter((h) => (byHealth[h] ?? 0) > 0)
          .map((h) => {
            const c = healthColor(h);
            return (
              <span key={h} className="flex items-center gap-1 text-2xs text-zinc-400">
                <span className={`h-1.5 w-1.5 rounded-full ${c.dot}`} />
                {byHealth[h]} {c.label.toLowerCase()}
              </span>
            );
          })}
      </div>
    </div>
  );
}

function BalanceEquityChart({ firms }: { firms: PropFirmSummary[] }) {
  const navigate = useNavigate();
  const rows = firms.map((f) => ({
    name: f.name.length > 12 ? f.name.slice(0, 12) + '…' : f.name,
    id: f.id,
    capital: f.capital ?? 0,
    pnl: f.pnl_month ?? 0,
  }));
  return (
    <Card>
      <CardHeader title="Capital by prop firm" subtitle="Managed capital, with month P&L" />
      <CardBody>
        {rows.length === 0 ? (
          <p className="py-8 text-center text-xs text-zinc-600">No data</p>
        ) : (
          <div className="h-56 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={rows} margin={{ top: 4, right: 8, left: 8, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2a3a" vertical={false} />
                <XAxis dataKey="name" tick={{ fill: '#64748b', fontSize: 11 }} stroke="#1f2a3a" />
                <YAxis
                  tick={{ fill: '#64748b', fontSize: 11 }}
                  stroke="#1f2a3a"
                  tickFormatter={(v) => money(Number(v), 'USD', { compact: true })}
                  width={56}
                />
                <Tooltip
                  cursor={{ fill: '#ffffff08' }}
                  contentStyle={{
                    background: '#121824',
                    border: '1px solid #1f2a3a',
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                  labelStyle={{ color: '#e4e4e7' }}
                  formatter={(v: number) => money(Number(v), 'USD', { compact: true })}
                />
                <Bar
                  dataKey="capital"
                  radius={[3, 3, 0, 0]}
                  onClick={(d: { id?: number }) => d?.id && navigate(`/prop-firms/${d.id}`)}
                  cursor="pointer"
                >
                  {rows.map((r) => (
                    <Cell key={r.id} fill="#3b82f6" />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardBody>
    </Card>
  );
}

function CapitalByFirm({
  firms,
  onOpen,
}: {
  firms: PropFirmSummary[];
  onOpen: (id: number) => void;
}) {
  const total = firms.reduce((s, f) => s + (f.capital ?? 0), 0) || 1;
  return (
    <Card>
      <CardHeader title="Prop firms" subtitle={`${firms.length} firms`} />
      <CardBody className="space-y-2.5">
        {firms.map((f) => {
          const cap = f.capital ?? 0;
          return (
            <button
              key={f.id}
              onClick={() => onOpen(f.id)}
              className="group w-full text-left"
            >
              <div className="flex items-baseline justify-between text-xs">
                <span className="text-zinc-300 group-hover:text-zinc-100">{f.name}</span>
                <span className="tabular text-zinc-400">
                  {money(cap, 'USD', { compact: true })}{' '}
                  <span className="text-zinc-600">· {f.accounts}</span>
                </span>
              </div>
              <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-panel2">
                <span className="block h-full bg-info/70" style={{ width: `${(cap / total) * 100}%` }} />
              </div>
            </button>
          );
        })}
      </CardBody>
    </Card>
  );
}

function AttentionPanel({ rows, onOpen }: { rows: AccountRow[]; onOpen: (id: number) => void }) {
  return (
    <Card>
      <CardHeader
        title={
          <span className="flex items-center gap-2">
            <TriangleAlert size={14} className="text-attn" />
            Accounts requiring attention
          </span>
        }
        subtitle={rows.length ? `${rows.length} need review` : undefined}
      />
      <CardBody>
        {rows.length === 0 ? (
          <div className="flex items-center justify-center gap-2 py-6 text-xs text-op">
            <Activity size={14} /> All systems operational
          </div>
        ) : (
          <ul className="divide-y divide-edge/60">
            {rows.map((a) => (
              <li
                key={a.id}
                className="flex cursor-pointer items-center justify-between py-2 hover:bg-white/[0.02]"
                onClick={() => onOpen(a.id)}
              >
                <div className="min-w-0">
                  <div className="truncate text-sm text-zinc-200">{a.name}</div>
                  <div className="text-2xs text-zinc-500">
                    {a.prop_firm} · {a.platform}
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <HealthBadge health={a.health} />
                  <ArrowRight size={14} className="text-zinc-600" />
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}

function RecentEvents({ events }: { events: EventItem[] }) {
  return (
    <Card>
      <CardHeader
        title={
          <span className="flex items-center gap-2">
            <Bot size={14} className="text-zinc-500" />
            Recent events
          </span>
        }
      />
      <CardBody className="max-h-80 overflow-y-auto p-0">
        {events.length === 0 ? (
          <p className="py-8 text-center text-xs text-zinc-600">No events yet</p>
        ) : (
          <ul className="divide-y divide-edge/50">
            {events.map((e) => (
              <li key={e.id} className="flex items-start gap-2 px-4 py-2">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-info/60" />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-xs text-zinc-300">{e.message}</div>
                  <div className="text-2xs text-zinc-600">
                    {e.type} · {relTime(e.ts)}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}
