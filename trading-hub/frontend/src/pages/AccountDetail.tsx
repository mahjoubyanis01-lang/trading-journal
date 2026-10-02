import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  Bot,
  HeartPulse,
  Loader2,
  Pause,
  Play,
  Plus,
  RotateCw,
  Search,
  Shield,
  Trash2,
  Zap,
} from 'lucide-react';
import { useAccount } from '../hooks/data';
import { api } from '../services/api';
import { useToast } from '../components/ui/Toast';
import { PageHeader } from '../components/ui/Kpi';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { HealthBadge, RobotBadge, Badge } from '../components/ui/Badge';
import { Modal } from '../components/ui/Modal';
import { Field, Input, Select } from '../components/ui/Input';
import { Table, TBody, TD, TH, THead, TR } from '../components/ui/Table';
import { ErrorState, Loading } from '../components/ui/States';
import { confidenceColor, money, pct, signClass, signedMoney } from '../lib/format';
import type { AccountDetail, Market, MarketCandidate, RiskNeedsConfirmation } from '../types';

export function AccountDetailPage() {
  const { id } = useParams();
  const accountId = Number(id);
  const navigate = useNavigate();
  const toast = useToast();
  const { data, loading, error, refetch, setData } = useAccount(accountId);

  const [busy, setBusy] = useState<string | null>(null);
  const [riskOpen, setRiskOpen] = useState(false);
  const [resolveMarket, setResolveMarket] = useState<Market | null>(null);

  async function withBusy(key: string, fn: () => Promise<AccountDetail | void>, msg?: string) {
    setBusy(key);
    try {
      const res = await fn();
      if (res) setData(res);
      else refetch();
      if (msg) toast('success', msg);
    } catch (e) {
      toast('error', e instanceof Error ? e.message : 'Action failed');
    } finally {
      setBusy(null);
    }
  }

  if (loading && !data) return <Loading label="Loading account…" />;
  if (error && !data) return <ErrorState message={error} onRetry={refetch} />;
  if (!data) return null;

  const a = data;
  const robotRunning = a.robot_status === 'active' || a.robot_status === 'starting';

  async function remove() {
    if (!window.confirm(`Remove account "${a.name}"? This cannot be undone.`)) return;
    setBusy('remove');
    try {
      await api.deleteAccount(accountId);
      toast('success', 'Account removed');
      navigate('/accounts');
    } catch (e) {
      toast('error', e instanceof Error ? e.message : 'Remove failed');
      setBusy(null);
    }
  }

  async function simFault(fault: 'robot' | 'terminal' | 'heartbeat') {
    setBusy('sim');
    try {
      await api.simFault(accountId, fault);
      toast('info', `Simulated ${fault} fault`);
      refetch();
    } catch (e) {
      toast('error', e instanceof Error ? e.message : 'Sim failed');
    } finally {
      setBusy(null);
    }
  }

  async function recover() {
    setBusy('recover');
    try {
      const res = await api.recover(accountId);
      if (res.outcome === 'recovered') toast('success', 'Account recovered');
      else toast('error', 'Recovery failed');
      refetch();
    } catch (e) {
      toast('error', e instanceof Error ? e.message : 'Recover failed');
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <button
        onClick={() => navigate('/accounts')}
        className="mb-3 flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300"
      >
        <ArrowLeft size={14} /> Accounts
      </button>

      <PageHeader
        title={a.name}
        subtitle={`${a.prop_firm} · ${a.platform} · ${a.strategy ?? 'no strategy'}${a.robot_version ? ` v${a.robot_version}` : ''}`}
        actions={
          <div className="flex items-center gap-2">
            <HealthBadge health={a.health} />
            <RobotBadge status={a.robot_status} />
          </div>
        }
      />

      {/* Action bar */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {robotRunning ? (
          <Button size="sm" onClick={() => withBusy('stop', () => api.robot(accountId, 'stop'), 'Robot paused')} disabled={!!busy}>
            <Pause size={14} /> Pause robot
          </Button>
        ) : (
          <Button size="sm" variant="primary" onClick={() => withBusy('start', () => api.robot(accountId, 'start'), 'Robot started')} disabled={!!busy}>
            <Play size={14} /> Start robot
          </Button>
        )}
        <Button size="sm" onClick={() => withBusy('restart', () => api.robot(accountId, 'restart'), 'Robot restarted')} disabled={!!busy}>
          <RotateCw size={14} /> Restart
        </Button>
        <Button size="sm" onClick={() => setRiskOpen(true)} disabled={!!busy}>
          <Shield size={14} /> Configure risk
        </Button>

        <div className="ml-auto flex items-center gap-2">
          <SimFaultMenu onFault={simFault} disabled={!!busy} />
          <Button size="sm" onClick={recover} disabled={!!busy}>
            {busy === 'recover' ? <Loader2 size={14} className="animate-spin" /> : <HeartPulse size={14} />}
            Recover
          </Button>
          <Button size="sm" variant="danger" onClick={remove} disabled={!!busy}>
            <Trash2 size={14} /> Remove
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        {/* Left: financials + risk + robot */}
        <div className="space-y-4 xl:col-span-1">
          <Card>
            <CardHeader title="Financials" />
            <CardBody className="space-y-0">
              <Row label="Capital" value={money(a.capital, a.currency)} />
              <Row label="Balance" value={money(a.balance, a.currency)} />
              <Row label="Equity" value={money(a.equity, a.currency)} />
              <Row label="P&L Total" value={signedMoney(a.pnl_total, a.currency)} cls={signClass(a.pnl_total)} />
              <Row label="P&L Today" value={signedMoney(a.pnl_today, a.currency)} cls={signClass(a.pnl_today)} />
              <Row label="P&L Month" value={signedMoney(a.pnl_month, a.currency)} cls={signClass(a.pnl_month)} />
              <Row label="Performance" value={pct(a.performance_pct)} cls={signClass(a.performance_pct)} />
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Risk"
              right={<Button size="sm" variant="ghost" onClick={() => setRiskOpen(true)}>Edit</Button>}
            />
            <CardBody className="space-y-0">
              <Row label="Mode" value={a.risk_mode} />
              <Row label="Amount" value={money(a.risk_amount, a.currency)} />
              <Row label="Reference" value={`${a.risk_reference} (${money(a.risk_reference_value, a.currency, { compact: true })})`} />
              <Row label="Initial %" value={pct(a.risk_percent)} />
              <Row label="Source" value={a.risk_source} />
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Robot & terminal" />
            <CardBody className="space-y-0">
              <Row label="Robot" value={<RobotBadge status={a.robot_status} />} />
              <Row label="Heartbeat" value={<HeartbeatPill value={a.heartbeat} />} />
              <Row label="Connection" value={a.connection} />
              <Row label="Terminal" value={a.terminal} />
              {a.terminal_detail && (
                <>
                  <Row label="Instance" value={a.terminal_detail.instance_id} />
                  <Row label="Process" value={a.terminal_detail.process_id ? String(a.terminal_detail.process_id) : '—'} />
                  <Row label="Path" value={<span className="font-mono text-2xs">{a.terminal_detail.terminal_path ?? '—'}</span>} />
                </>
              )}
            </CardBody>
          </Card>
        </div>

        {/* Right: markets */}
        <div className="xl:col-span-2">
          <Card>
            <CardHeader
              title={<span className="flex items-center gap-2"><Bot size={14} className="text-zinc-500" /> Markets</span>}
              subtitle="Universal → real symbol mapping"
              right={
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => withBusy('discover', async () => { const r = await api.discoverMarkets(accountId); toast('info', `${r.instruments} instruments · ${r.unresolved.length} unresolved`); refetch(); })}
                  disabled={!!busy}
                >
                  {busy === 'discover' ? <Loader2 size={13} className="animate-spin" /> : <Zap size={13} />}
                  Discover
                </Button>
              }
            />
            <CardBody className="p-0">
              {a.markets.length === 0 ? (
                <p className="py-10 text-center text-xs text-zinc-600">No markets configured</p>
              ) : (
                <Table>
                  <THead>
                    <TR>
                      <TH>Universal</TH>
                      <TH>Real</TH>
                      <TH align="right">Confidence</TH>
                      <TH>Status</TH>
                      <TH align="right">Action</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {a.markets.map((m) => {
                      const unresolved = !m.verified || !m.real || m.status !== 'verified';
                      return (
                        <TR key={m.universal}>
                          <TD className="font-medium text-zinc-200">{m.universal}</TD>
                          <TD className="font-mono text-xs text-zinc-300">{m.real ?? <span className="text-zinc-600">unresolved</span>}</TD>
                          <TD align="right" className={`tabular ${confidenceColor(m.confidence)}`}>
                            {(m.confidence * 100).toFixed(0)}%
                          </TD>
                          <TD>
                            {m.verified ? (
                              <Badge className="border-op/30 bg-op/10 text-op">verified</Badge>
                            ) : (
                              <Badge className="border-attn/30 bg-attn/10 text-attn">{m.status}</Badge>
                            )}
                          </TD>
                          <TD align="right">
                            {unresolved && (
                              <Button size="sm" variant="ghost" onClick={() => setResolveMarket(m)}>
                                <Search size={13} /> Resolve
                              </Button>
                            )}
                          </TD>
                        </TR>
                      );
                    })}
                  </TBody>
                </Table>
              )}
            </CardBody>
          </Card>
        </div>
      </div>

      {riskOpen && (
        <RiskDialog
          account={a}
          onClose={() => setRiskOpen(false)}
          onSaved={(d) => { setData(d); setRiskOpen(false); toast('success', 'Risk updated'); }}
        />
      )}

      {resolveMarket && (
        <ResolveMarketDialog
          accountId={accountId}
          market={resolveMarket}
          onClose={() => setResolveMarket(null)}
          onMapped={(d) => { setData(d); setResolveMarket(null); toast('success', 'Market mapped to robot'); }}
        />
      )}
    </>
  );
}

function Row({ label, value, cls }: { label: string; value: React.ReactNode; cls?: string }) {
  return (
    <div className="flex items-center justify-between border-b border-edge/50 py-2 text-sm last:border-0">
      <span className="text-zinc-500">{label}</span>
      <span className={`tabular font-medium text-zinc-200 ${cls ?? ''}`}>{value}</span>
    </div>
  );
}

function HeartbeatPill({ value }: { value: string }) {
  const ok = value === 'ok';
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs ${ok ? 'text-op' : 'text-idle'}`}>
      <HeartPulse size={13} className={ok ? 'animate-pulse' : ''} />
      {value}
    </span>
  );
}

function SimFaultMenu({ onFault, disabled }: { onFault: (f: 'robot' | 'terminal' | 'heartbeat') => void; disabled: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <Button size="sm" variant="subtle" onClick={() => setOpen((o) => !o)} disabled={disabled}>
        <Zap size={13} /> Simulate fault
      </Button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute right-0 z-20 mt-1 w-40 overflow-hidden rounded-md border border-edge bg-panel shadow-xl">
            {(['robot', 'terminal', 'heartbeat'] as const).map((f) => (
              <button
                key={f}
                className="block w-full px-3 py-2 text-left text-xs text-zinc-300 hover:bg-white/5"
                onClick={() => { setOpen(false); onFault(f); }}
              >
                Break {f}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function RiskDialog({
  account,
  onClose,
  onSaved,
}: {
  account: AccountDetail;
  onClose: () => void;
  onSaved: (d: AccountDetail) => void;
}) {
  const toast = useToast();
  const [mode, setMode] = useState(account.risk_mode);
  const [amount, setAmount] = useState(String(account.risk_amount));
  const [saving, setSaving] = useState(false);
  const [confirm, setConfirm] = useState<RiskNeedsConfirmation | null>(null);

  async function submit(doConfirm = false) {
    setSaving(true);
    try {
      const res = await api.setRisk(account.id, mode, Number(amount), doConfirm || undefined);
      if (res.confirm) {
        setConfirm(res.confirm);
      } else if (res.detail) {
        onSaved(res.detail);
      }
    } catch (e) {
      toast('error', e instanceof Error ? e.message : 'Failed');
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Configure risk"
      subtitle={account.name}
      footer={
        confirm ? (
          <>
            <Button variant="ghost" onClick={() => setConfirm(null)}>Back</Button>
            <Button variant="danger" onClick={() => submit(true)} disabled={saving}>
              {saving && <Loader2 size={14} className="animate-spin" />} Confirm change
            </Button>
          </>
        ) : (
          <>
            <Button variant="ghost" onClick={onClose}>Cancel</Button>
            <Button variant="primary" onClick={() => submit(false)} disabled={saving}>
              {saving && <Loader2 size={14} className="animate-spin" />} Apply
            </Button>
          </>
        )
      }
    >
      {confirm ? (
        <div className="space-y-3">
          <div className="rounded-md border border-attn/40 bg-attn/10 px-3 py-2 text-xs text-attn">
            This change needs confirmation: {money(confirm.old_amount, account.currency)} → {money(confirm.new_amount, account.currency)}
          </div>
          <ul className="space-y-1.5">
            {confirm.warnings.map((w, i) => (
              <li key={i} className="flex gap-2 text-xs text-zinc-300">
                <span className="text-attn">•</span> {w}
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4">
          <Field label="Mode">
            <Select value={mode} onChange={(e) => setMode(e.target.value)}>
              <option value="fixed">fixed</option>
              <option value="percent">percent</option>
            </Select>
          </Field>
          <Field label="Amount">
            <Input type="number" value={amount} onChange={(e) => setAmount(e.target.value)} />
          </Field>
        </div>
      )}
    </Modal>
  );
}

function ResolveMarketDialog({
  accountId,
  market,
  onClose,
  onMapped,
}: {
  accountId: number;
  market: Market;
  onClose: () => void;
  onMapped: (d: AccountDetail) => void;
}) {
  const toast = useToast();
  const [symbol, setSymbol] = useState(market.universal);
  const [candidates, setCandidates] = useState<MarketCandidate[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [mapping, setMapping] = useState<string | null>(null);

  async function search() {
    setSearching(true);
    setCandidates(null);
    try {
      const res = await api.searchMarket(accountId, symbol);
      setCandidates(res.candidates);
    } catch (e) {
      toast('error', e instanceof Error ? e.message : 'Search failed');
    } finally {
      setSearching(false);
    }
  }

  async function map(real: string) {
    setMapping(real);
    try {
      const d = await api.mapMarket(accountId, market.universal, real);
      onMapped(d);
    } catch (e) {
      toast('error', e instanceof Error ? e.message : 'Map failed');
      setMapping(null);
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Resolve market"
      subtitle={`Find the real symbol for ${market.universal}`}
      width="max-w-xl"
    >
      <div className="flex gap-2">
        <Input value={symbol} onChange={(e) => setSymbol(e.target.value)} placeholder="Universal symbol" />
        <Button variant="primary" onClick={search} disabled={searching}>
          {searching ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />} Search
        </Button>
      </div>

      <div className="mt-4">
        {candidates === null ? (
          <p className="py-6 text-center text-xs text-zinc-600">Search to list broker candidates.</p>
        ) : candidates.length === 0 ? (
          <p className="py-6 text-center text-xs text-zinc-600">No candidates found.</p>
        ) : (
          <ul className="space-y-2">
            {candidates.map((c) => (
              <li
                key={c.real_symbol}
                className="flex items-center justify-between rounded-md border border-edge bg-panel2 px-3 py-2"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm text-zinc-100">{c.real_symbol}</span>
                    <span className={`text-2xs ${confidenceColor(c.confidence)}`}>{(c.confidence * 100).toFixed(0)}%</span>
                  </div>
                  <div className="truncate text-2xs text-zinc-500">{c.description}{c.reason ? ` · ${c.reason}` : ''}</div>
                </div>
                <Button size="sm" variant="primary" onClick={() => map(c.real_symbol)} disabled={!!mapping}>
                  {mapping === c.real_symbol ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />}
                  Add to robot
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Modal>
  );
}
