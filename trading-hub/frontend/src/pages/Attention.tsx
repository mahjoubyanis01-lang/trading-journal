import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, CheckCircle2, HeartPulse, Loader2, TriangleAlert } from 'lucide-react';
import { useAttention } from '../hooks/data';
import { api } from '../services/api';
import { useToast } from '../components/ui/Toast';
import { PageHeader } from '../components/ui/Kpi';
import { Card, CardBody } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { HealthBadge } from '../components/ui/Badge';
import { ErrorState, Loading } from '../components/ui/States';
import { cn } from '../lib/cn';

export function Attention() {
  const { data, loading, error, refetch } = useAttention();
  const navigate = useNavigate();
  const toast = useToast();
  const [busy, setBusy] = useState<number | null>(null);

  async function recover(id: number) {
    setBusy(id);
    try {
      const res = await api.recover(id);
      if (res.outcome === 'recovered') toast('success', 'Account recovered');
      else toast('error', 'Recovery failed — needs manual review');
      refetch();
    } catch (e) {
      toast('error', e instanceof Error ? e.message : 'Recover failed');
    } finally {
      setBusy(null);
    }
  }

  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorState message={error} onRetry={refetch} />;

  const accounts = data?.accounts ?? [];

  return (
    <>
      <PageHeader
        title="Attention"
        subtitle="Accounts that need a human — exceptions surfaced automatically"
      />
      {accounts.length === 0 ? (
        <Card>
          <CardBody>
            <div className="flex flex-col items-center justify-center gap-2 py-16 text-center">
              <CheckCircle2 size={40} className="text-op" />
              <h3 className="text-sm font-medium text-zinc-200">All clear</h3>
              <p className="text-xs text-zinc-500">No accounts currently require attention.</p>
            </div>
          </CardBody>
        </Card>
      ) : (
        <div className="space-y-3">
          {accounts.map((a) => (
            <Card key={a.id}>
              <CardBody>
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <TriangleAlert size={15} className="text-attn" />
                      <span className="text-sm font-medium text-zinc-100">{a.name}</span>
                      <HealthBadge health={a.health} />
                    </div>
                    <div className="mt-0.5 text-2xs text-zinc-500">
                      {a.prop_firm} · {a.platform} · {a.strategy ?? 'no strategy'}
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <Button size="sm" onClick={() => recover(a.id)} disabled={busy === a.id}>
                      {busy === a.id ? <Loader2 size={13} className="animate-spin" /> : <HeartPulse size={13} />}
                      Recover
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => navigate(`/accounts/${a.id}`)}>
                      Open <ArrowRight size={13} />
                    </Button>
                  </div>
                </div>

                {a.alerts.length > 0 && (
                  <ul className="mt-3 space-y-1.5 border-t border-edge/60 pt-3">
                    {a.alerts.map((al) => (
                      <li key={al.id} className="flex items-start gap-2 text-xs">
                        <span
                          className={cn(
                            'mt-0.5 rounded px-1.5 py-0.5 text-2xs font-medium uppercase',
                            al.severity === 'critical' || al.severity === 'error'
                              ? 'bg-err/15 text-err'
                              : al.severity === 'warning'
                                ? 'bg-attn/15 text-attn'
                                : 'bg-info/15 text-info',
                          )}
                        >
                          {al.severity}
                        </span>
                        <span className="text-zinc-300">{al.message}</span>
                        <span className="ml-auto text-2xs text-zinc-600">{al.type}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </CardBody>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
