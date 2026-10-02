import { useEffect, useMemo, useState } from 'react';
import { CheckCircle2, Loader2, XCircle } from 'lucide-react';
import { Modal } from './ui/Modal';
import { Button } from './ui/Button';
import { Field, Input, Select } from './ui/Input';
import { api } from '../services/api';
import { useEvents } from '../services/useEvents';
import { usePlatforms, usePropFirms, useStrategies } from '../hooks/data';
import type { AccountDetail, WorkflowStep } from '../types';

interface LiveStep {
  name: string;
  ok: boolean | null; // null = running
  detail: string;
}

export function AddAccountModal({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (account: AccountDetail) => void;
}) {
  const propFirms = usePropFirms();
  const platforms = usePlatforms();
  const strategies = useStrategies();

  const [propFirmId, setPropFirmId] = useState('');
  const [platformKey, setPlatformKey] = useState('');
  const [strategyId, setStrategyId] = useState('');
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [server, setServer] = useState('');
  const [name, setName] = useState('');
  const [seedBalance, setSeedBalance] = useState('100000');

  const isMock = platformKey === 'mock';
  const selectedPlatform = platforms.data?.platforms.find((p) => p.key === platformKey);

  const [submitting, setSubmitting] = useState(false);
  const [steps, setSteps] = useState<LiveStep[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  // Live workflow steps arriving over the WS while the backend provisions.
  useEvents(['workflow.step'], (msg) => {
    if (!submitting) return;
    const p = msg.payload as { name?: string; ok?: boolean; detail?: string };
    if (!p?.name) return;
    setSteps((prev) => {
      const next = [...prev];
      const idx = next.findIndex((s) => s.name === p.name);
      const entry: LiveStep = {
        name: p.name!,
        ok: p.ok ?? null,
        detail: p.detail ?? '',
      };
      if (idx >= 0) next[idx] = entry;
      else next.push(entry);
      return next;
    });
  });

  useEffect(() => {
    if (!open) {
      // reset after close animation
      setPropFirmId('');
      setPlatformKey('');
      setStrategyId('');
      setLogin('');
      setPassword('');
      setServer('');
      setName('');
      setSeedBalance('100000');
      setSubmitting(false);
      setSteps([]);
      setError(null);
      setDone(false);
    }
  }, [open]);

  // Default selects to the first options once loaded.
  useEffect(() => {
    if (!propFirmId && propFirms.data?.prop_firms.length) {
      setPropFirmId(String(propFirms.data.prop_firms[0].id));
    }
  }, [propFirms.data, propFirmId]);
  useEffect(() => {
    const avail = platforms.data?.platforms.find((p) => p.available);
    if (!platformKey && avail) setPlatformKey(avail.key);
  }, [platforms.data, platformKey]);

  const valid = useMemo(
    () =>
      propFirmId &&
      platformKey &&
      login.trim() &&
      password.trim() &&
      (isMock ? Boolean(seedBalance) : Boolean(server.trim())),
    [propFirmId, platformKey, login, password, seedBalance, server, isMock],
  );

  async function submit() {
    if (!valid) return;
    setSubmitting(true);
    setError(null);
    setSteps([]);
    setDone(false);
    try {
      const res = await api.createAccount({
        prop_firm_id: Number(propFirmId),
        platform_key: platformKey,
        login: login.trim(),
        password: password.trim(),
        server: server.trim() || undefined,
        name: name.trim() || undefined,
        strategy_id: strategyId ? Number(strategyId) : undefined,
        seed_balance: Number(seedBalance),
      });
      // Reconcile with the authoritative steps from the response.
      setSteps(
        res.steps.map((s: WorkflowStep) => ({ name: s.name, ok: s.ok, detail: s.detail })),
      );
      setDone(true);
      onCreated(res.account);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }

  const running = submitting || steps.length > 0;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Add account"
      subtitle="Provision a new trading account. Everything else is automatic."
      width="max-w-xl"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            {done ? 'Close' : 'Cancel'}
          </Button>
          {!done && (
            <Button variant="primary" onClick={submit} disabled={!valid || submitting}>
              {submitting && <Loader2 size={14} className="animate-spin" />}
              {submitting ? 'Provisioning…' : 'Create account'}
            </Button>
          )}
        </>
      }
    >
      <div className="grid grid-cols-2 gap-4">
        <Field label="Prop Firm">
          <Select value={propFirmId} onChange={(e) => setPropFirmId(e.target.value)} disabled={running}>
            <option value="">Select…</option>
            {propFirms.data?.prop_firms.map((f) => (
              <option key={f.id} value={f.id}>
                {f.name}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="Platform">
          <Select value={platformKey} onChange={(e) => setPlatformKey(e.target.value)} disabled={running}>
            <option value="">Select…</option>
            {platforms.data?.platforms.map((p) => (
              <option key={p.key} value={p.key} disabled={!p.available}>
                {p.name}
                {p.available ? '' : ' (unavailable here)'}
              </option>
            ))}
          </Select>
          {selectedPlatform && !selectedPlatform.available && selectedPlatform.requirement && (
            <p className="mt-1 text-[11px] leading-snug text-attn">
              Requires: {selectedPlatform.requirement}
            </p>
          )}
        </Field>

        <Field label="Login">
          <Input
            value={login}
            onChange={(e) => setLogin(e.target.value)}
            placeholder="Account login"
            disabled={running}
          />
        </Field>

        <Field label="Password">
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            disabled={running}
          />
        </Field>

        <Field label="Server" hint={isMock ? 'not needed for mock' : 'e.g. FundedNext-Server'}>
          <Input
            value={server}
            onChange={(e) => setServer(e.target.value)}
            placeholder={isMock ? 'optional' : 'Broker / server'}
            disabled={running || isMock}
          />
        </Field>

        <Field label="Name" hint="leave blank for auto">
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="auto"
            disabled={running}
          />
        </Field>

        {isMock && (
          <Field label="Starting balance (mock)">
            <Input
              type="number"
              value={seedBalance}
              onChange={(e) => setSeedBalance(e.target.value)}
              disabled={running}
            />
          </Field>
        )}

        <Field label="Strategy" hint="optional">
          <Select value={strategyId} onChange={(e) => setStrategyId(e.target.value)} disabled={running}>
            <option value="">Default</option>
            {strategies.data?.strategies.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </Select>
        </Field>
      </div>

      {error && (
        <div className="mt-4 rounded-md border border-err/40 bg-err/10 px-3 py-2 text-xs text-err">
          {error}
        </div>
      )}

      {steps.length > 0 && (
        <div className="mt-5 rounded-lg border border-edge bg-panel2 p-3">
          <div className="mb-2 text-xs font-medium text-zinc-400">Provisioning workflow</div>
          <ul className="space-y-1.5">
            {steps.map((s, i) => (
              <li key={`${s.name}-${i}`} className="flex items-start gap-2 text-xs">
                {s.ok === null ? (
                  <Loader2 size={14} className="mt-0.5 shrink-0 animate-spin text-info" />
                ) : s.ok ? (
                  <CheckCircle2 size={14} className="mt-0.5 shrink-0 text-op" />
                ) : (
                  <XCircle size={14} className="mt-0.5 shrink-0 text-err" />
                )}
                <span className="text-zinc-300">{s.name}</span>
                {s.detail && <span className="text-zinc-600">— {s.detail}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}

      {done && !error && (
        <div className="mt-3 flex items-center gap-2 text-xs text-op">
          <CheckCircle2 size={14} />
          Account created and running.
        </div>
      )}
    </Modal>
  );
}
