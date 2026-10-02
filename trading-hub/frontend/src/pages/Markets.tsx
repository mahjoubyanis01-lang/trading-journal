import { useMemo, useState } from 'react';
import { LineChart, Search } from 'lucide-react';
import { useMarkets } from '../hooks/data';
import { PageHeader } from '../components/ui/Kpi';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Input } from '../components/ui/Input';
import { Table, TBody, TD, TH, THead, TR } from '../components/ui/Table';
import { ErrorState, Loading, EmptyState } from '../components/ui/States';
import { confidenceColor } from '../lib/format';

export function Markets() {
  const { data, loading, error, refetch } = useMarkets();
  const [q, setQ] = useState('');

  const rows = useMemo(() => {
    const all = data?.markets ?? [];
    if (!q) return all;
    const needle = q.toLowerCase();
    return all.filter(
      (m) =>
        m.universal.toLowerCase().includes(needle) ||
        (m.real ?? '').toLowerCase().includes(needle) ||
        m.platform.toLowerCase().includes(needle) ||
        m.broker.toLowerCase().includes(needle),
    );
  }, [data, q]);

  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorState message={error} onRetry={refetch} />;

  return (
    <>
      <PageHeader title="Markets" subtitle={`${data?.markets.length ?? 0} symbol mappings`} />
      <div className="mb-3 relative w-72">
        <Search size={14} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-600" />
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search symbols, brokers…" className="pl-8" />
      </div>
      {rows.length === 0 ? (
        <EmptyState icon={<LineChart size={36} />} title="No markets" />
      ) : (
        <Card className="overflow-hidden">
          <Table>
            <THead>
              <TR>
                <TH>Universal</TH>
                <TH>Real</TH>
                <TH>Platform</TH>
                <TH>Broker</TH>
                <TH align="right">Confidence</TH>
                <TH>Status</TH>
              </TR>
            </THead>
            <TBody>
              {rows.map((m, i) => (
                <TR key={`${m.universal}-${m.platform}-${i}`}>
                  <TD className="font-medium text-zinc-200">{m.universal}</TD>
                  <TD className="font-mono text-xs text-zinc-300">{m.real ?? <span className="text-zinc-600">—</span>}</TD>
                  <TD className="text-zinc-400">{m.platform}</TD>
                  <TD className="text-zinc-500">{m.broker}</TD>
                  <TD align="right" className={`tabular ${confidenceColor(m.confidence)}`}>{(m.confidence * 100).toFixed(0)}%</TD>
                  <TD>
                    {m.status === 'verified' ? (
                      <Badge className="border-op/30 bg-op/10 text-op">verified</Badge>
                    ) : m.status === 'unresolved' ? (
                      <Badge className="border-err/30 bg-err/10 text-err">unresolved</Badge>
                    ) : (
                      <Badge className="border-attn/30 bg-attn/10 text-attn">{m.status}</Badge>
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
