import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { usePropFirm } from '../hooks/data';
import { PageHeader, Kpi } from '../components/ui/Kpi';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import { AccountsTable } from '../components/AccountsTable';
import { ErrorState, Loading } from '../components/ui/States';
import { money, pct, signClass, signedMoney } from '../lib/format';

export function PropFirmDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { data, loading, error, refetch } = usePropFirm(Number(id));

  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorState message={error} onRetry={refetch} />;
  if (!data) return null;

  return (
    <>
      <button
        onClick={() => navigate('/prop-firms')}
        className="mb-3 flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300"
      >
        <ArrowLeft size={14} /> Prop Firms
      </button>
      <PageHeader title={data.name} subtitle={`${data.accounts} accounts`} />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Kpi label="Accounts" value={data.accounts} />
        <Kpi label="Capital" value={money(data.capital, 'USD', { compact: true })} />
        <Kpi label="P&L Today" value={signedMoney(data.pnl_today)} valueClass={signClass(data.pnl_today)} accent={data.pnl_today >= 0 ? 'green' : 'red'} />
        <Kpi label="P&L Month" value={signedMoney(data.pnl_month)} valueClass={signClass(data.pnl_month)} accent={data.pnl_month >= 0 ? 'green' : 'red'} />
        <Kpi label="Performance" value={pct(data.performance_pct)} valueClass={signClass(data.performance_pct)} />
        <Kpi label="Robots active" value={data.robots_active} accent="green" />
      </div>

      <Card className="mt-4 overflow-hidden">
        <CardHeader title="Accounts" />
        <CardBody className="p-0">
          <AccountsTable rows={data.accounts_list} />
        </CardBody>
      </Card>
    </>
  );
}
