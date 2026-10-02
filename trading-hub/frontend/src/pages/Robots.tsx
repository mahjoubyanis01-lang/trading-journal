import { Bot } from 'lucide-react';
import { useStrategies } from '../hooks/data';
import { PageHeader } from '../components/ui/Kpi';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Table, TBody, TD, TH, THead, TR } from '../components/ui/Table';
import { ErrorState, Loading, EmptyState } from '../components/ui/States';

export function Robots() {
  const { data, loading, error, refetch } = useStrategies();

  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorState message={error} onRetry={refetch} />;

  const strategies = data?.strategies ?? [];

  return (
    <>
      <PageHeader title="Robots" subtitle={`${strategies.length} strategies`} />
      {strategies.length === 0 ? (
        <EmptyState icon={<Bot size={36} />} title="No strategies" />
      ) : (
        <Card className="overflow-hidden">
          <Table>
            <THead>
              <TR>
                <TH>Strategy</TH>
                <TH>Version</TH>
                <TH align="right">Accounts</TH>
                <TH align="right">Active</TH>
                <TH align="right">Attention</TH>
                <TH align="right">Risk %</TH>
                <TH>Markets</TH>
                <TH>State</TH>
              </TR>
            </THead>
            <TBody>
              {strategies.map((s) => (
                <TR key={s.id}>
                  <TD className="font-medium text-zinc-100">{s.name}</TD>
                  <TD className="text-zinc-500">v{s.version}</TD>
                  <TD align="right" className="tabular">{s.accounts}</TD>
                  <TD align="right" className="tabular text-op">{s.active}</TD>
                  <TD align="right" className={`tabular ${s.attention > 0 ? 'text-attn' : 'text-zinc-600'}`}>{s.attention}</TD>
                  <TD align="right" className="tabular">{s.risk_percent}%</TD>
                  <TD>
                    <div className="flex flex-wrap gap-1">
                      {s.markets.slice(0, 6).map((m) => (
                        <span key={m} className="rounded bg-panel2 px-1.5 py-0.5 text-2xs text-zinc-400">{m}</span>
                      ))}
                      {s.markets.length > 6 && (
                        <span className="text-2xs text-zinc-600">+{s.markets.length - 6}</span>
                      )}
                    </div>
                  </TD>
                  <TD>
                    {s.enabled ? (
                      <Badge className="border-op/30 bg-op/10 text-op">enabled</Badge>
                    ) : (
                      <Badge className="border-idle/30 bg-idle/10 text-idle">disabled</Badge>
                    )}
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </Card>
      )}
    </>
  );
}
