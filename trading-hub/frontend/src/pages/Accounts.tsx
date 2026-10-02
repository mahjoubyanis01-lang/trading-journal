import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loader2, Play, RotateCw, Search, Square, Wallet } from 'lucide-react';
import { useAccounts, usePropFirms } from '../hooks/data';
import { api } from '../services/api';
import { useToast } from '../components/ui/Toast';
import { useAddAccount } from '../components/AddAccountContext';
import { PageHeader } from '../components/ui/Kpi';
import { Button } from '../components/ui/Button';
import { Input, Select } from '../components/ui/Input';
import { Card } from '../components/ui/Card';
import { HealthBadge, RobotBadge } from '../components/ui/Badge';
import { Table, TBody, TD, TH, THead, TR } from '../components/ui/Table';
import { EmptyState, ErrorState, Loading } from '../components/ui/States';
import { money, pct, signClass } from '../lib/format';
import type { AccountRow } from '../types';

type SortKey = keyof Pick<
  AccountRow,
  'name' | 'prop_firm' | 'platform' | 'capital' | 'balance' | 'equity' | 'pnl_total' | 'performance_pct' | 'risk_amount' | 'robot_status' | 'health'
>;

const STATUSES = ['operational', 'attention', 'error', 'disconnected', 'pending'];
const PLATFORMS = ['MT4', 'MT5', 'cTrader', 'DXtrade', 'NinjaTrader'];

export function Accounts() {
  const navigate = useNavigate();
  const toast = useToast();
  const openAdd = useAddAccount();
  const propFirms = usePropFirms();

  const [q, setQ] = useState('');
  const [propFirm, setPropFirm] = useState('');
  const [platform, setPlatform] = useState('');
  const [status, setStatus] = useState('');
  const filter = useMemo(() => ({ q, prop_firm: propFirm, platform, status }), [q, propFirm, platform, status]);
  const { data, loading, error, refetch } = useAccounts(filter);

  const [sortKey, setSortKey] = useState<SortKey>('performance_pct');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [busyAction, setBusyAction] = useState(false);

  function toggleSort(k: SortKey) {
    if (sortKey === k) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else {
      setSortKey(k);
      setSortDir('desc');
    }
  }

  const rows = useMemo(() => {
    const list = [...(data?.accounts ?? [])];
    list.sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      let cmp: number;
      if (typeof av === 'number' && typeof bv === 'number') cmp = av - bv;
      else cmp = String(av).localeCompare(String(bv));
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return list;
  }, [data, sortKey, sortDir]);

  const allSelected = rows.length > 0 && rows.every((r) => selected.has(r.id));

  function toggleAll() {
    setSelected(allSelected ? new Set() : new Set(rows.map((r) => r.id)));
  }
  function toggleOne(id: number) {
    setSelected((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function massAction(action: 'start' | 'stop' | 'restart') {
    const ids = [...selected];
    if (ids.length === 0) return;
    if (!window.confirm(`${action.toUpperCase()} robots on ${ids.length} account(s)?`)) return;
    setBusyAction(true);
    try {
      const res = await api.massAction(ids, action);
      toast('success', `${action} applied to ${res.applied} account(s)`);
      setSelected(new Set());
      refetch();
    } catch (e) {
      toast('error', e instanceof Error ? e.message : 'Action failed');
    } finally {
      setBusyAction(false);
    }
  }

  const hasFilters = !!(q || propFirm || platform || status);

  return (
    <>
      <PageHeader
        title="Accounts"
        subtitle={data ? `${data.total} accounts` : undefined}
        actions={<Button variant="primary" size="sm" onClick={openAdd}>Add account</Button>}
      />

      {/* Filters */}
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="relative w-64">
          <Search size={14} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-600" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search accounts…"
            className="pl-8"
          />
        </div>
        <Select value={propFirm} onChange={(e) => setPropFirm(e.target.value)} className="w-44">
          <option value="">All prop firms</option>
          {propFirms.data?.prop_firms.map((f) => (
            <option key={f.id} value={f.name}>
              {f.name}
            </option>
          ))}
        </Select>
        <Select value={platform} onChange={(e) => setPlatform(e.target.value)} className="w-40">
          <option value="">All platforms</option>
          {PLATFORMS.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </Select>
        <Select value={status} onChange={(e) => setStatus(e.target.value)} className="w-40">
          <option value="">All statuses</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s[0].toUpperCase() + s.slice(1)}
            </option>
          ))}
        </Select>
        {hasFilters && (
          <Button variant="ghost" size="sm" onClick={() => { setQ(''); setPropFirm(''); setPlatform(''); setStatus(''); }}>
            Clear
          </Button>
        )}
      </div>

      {/* Mass-action bar */}
      {selected.size > 0 && (
        <div className="mb-3 flex items-center gap-3 rounded-lg border border-info/40 bg-info/10 px-4 py-2.5">
          <span className="text-sm font-medium text-zinc-100">{selected.size} selected</span>
          <span className="text-xs text-zinc-500">Mass action on robots:</span>
          <div className="flex items-center gap-2">
            <Button size="sm" onClick={() => massAction('start')} disabled={busyAction}>
              <Play size={13} /> Start
            </Button>
            <Button size="sm" onClick={() => massAction('stop')} disabled={busyAction}>
              <Square size={13} /> Stop
            </Button>
            <Button size="sm" onClick={() => massAction('restart')} disabled={busyAction}>
              <RotateCw size={13} /> Restart
            </Button>
          </div>
          {busyAction && <Loader2 size={14} className="animate-spin text-info" />}
          <button className="ml-auto text-xs text-zinc-500 hover:text-zinc-300" onClick={() => setSelected(new Set())}>
            Clear selection
          </button>
        </div>
      )}

      {loading && !data ? (
        <Loading label="Loading accounts…" />
      ) : error && !data ? (
        <ErrorState message={error} onRetry={refetch} />
      ) : rows.length === 0 ? (
        <EmptyState
          icon={<Wallet size={36} />}
          title={hasFilters ? 'No accounts match your filters' : 'No accounts yet'}
          description={hasFilters ? 'Try clearing the filters.' : 'Add an account or seed demo data from the dashboard.'}
        >
          {!hasFilters && <Button variant="primary" onClick={openAdd}>Add account</Button>}
        </EmptyState>
      ) : (
        <Card className="overflow-hidden">
          <Table>
            <THead>
              <TR>
                <TH align="center">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    onChange={toggleAll}
                    className="h-3.5 w-3.5 accent-info"
                  />
                </TH>
                <TH sortable active={sortKey === 'name'} dir={sortDir} onSort={() => toggleSort('name')}>Account</TH>
                <TH sortable active={sortKey === 'prop_firm'} dir={sortDir} onSort={() => toggleSort('prop_firm')}>Prop Firm</TH>
                <TH sortable active={sortKey === 'platform'} dir={sortDir} onSort={() => toggleSort('platform')}>Platform</TH>
                <TH align="right" sortable active={sortKey === 'capital'} dir={sortDir} onSort={() => toggleSort('capital')}>Capital</TH>
                <TH align="right" sortable active={sortKey === 'balance'} dir={sortDir} onSort={() => toggleSort('balance')}>Balance</TH>
                <TH align="right" sortable active={sortKey === 'equity'} dir={sortDir} onSort={() => toggleSort('equity')}>Equity</TH>
                <TH align="right" sortable active={sortKey === 'pnl_total'} dir={sortDir} onSort={() => toggleSort('pnl_total')}>P&L</TH>
                <TH align="right" sortable active={sortKey === 'performance_pct'} dir={sortDir} onSort={() => toggleSort('performance_pct')}>Perf %</TH>
                <TH align="right" sortable active={sortKey === 'risk_amount'} dir={sortDir} onSort={() => toggleSort('risk_amount')}>Risk</TH>
                <TH sortable active={sortKey === 'robot_status'} dir={sortDir} onSort={() => toggleSort('robot_status')}>Robot</TH>
                <TH sortable active={sortKey === 'health'} dir={sortDir} onSort={() => toggleSort('health')}>Status</TH>
              </TR>
            </THead>
            <TBody>
              {rows.map((a) => (
                <TR key={a.id} selected={selected.has(a.id)} onClick={() => navigate(`/accounts/${a.id}`)}>
                  <TD align="center" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={selected.has(a.id)}
                      onChange={() => toggleOne(a.id)}
                      className="h-3.5 w-3.5 accent-info"
                    />
                  </TD>
                  <TD>
                    <div className="font-medium text-zinc-100">{a.name}</div>
                    <div className="text-2xs text-zinc-600">{a.strategy ?? 'no strategy'}</div>
                  </TD>
                  <TD className="text-zinc-400">{a.prop_firm}</TD>
                  <TD className="text-zinc-400">{a.platform}</TD>
                  <TD align="right" className="tabular">{money(a.capital, a.currency, { compact: true })}</TD>
                  <TD align="right" className="tabular">{money(a.balance, a.currency, { compact: true })}</TD>
                  <TD align="right" className="tabular">{money(a.equity, a.currency, { compact: true })}</TD>
                  <TD align="right" className={`tabular ${signClass(a.pnl_total)}`}>{money(a.pnl_total, a.currency, { compact: true })}</TD>
                  <TD align="right" className={`tabular ${signClass(a.performance_pct)}`}>{pct(a.performance_pct)}</TD>
                  <TD align="right" className="tabular text-zinc-400">
                    {money(a.risk_amount, a.currency, { compact: true })}
                    <span className="ml-1 text-2xs text-zinc-600">{a.risk_mode}</span>
                  </TD>
                  <TD><RobotBadge status={a.robot_status} /></TD>
                  <TD><HealthBadge health={a.health} /></TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </Card>
      )}
    </>
  );
}
