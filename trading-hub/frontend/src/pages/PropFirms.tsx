import { useNavigate } from 'react-router-dom';
import { Building2, ArrowRight } from 'lucide-react';
import { usePropFirms } from '../hooks/data';
import { PageHeader } from '../components/ui/Kpi';
import { Card, CardBody } from '../components/ui/Card';
import { ErrorState, Loading, EmptyState } from '../components/ui/States';
import { money } from '../lib/format';

export function PropFirms() {
  const { data, loading, error, refetch } = usePropFirms();
  const navigate = useNavigate();

  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorState message={error} onRetry={refetch} />;

  const firms = data?.prop_firms ?? [];

  return (
    <>
      <PageHeader title="Prop Firms" subtitle={`${firms.length} firms`} />
      {firms.length === 0 ? (
        <EmptyState icon={<Building2 size={36} />} title="No prop firms" />
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {firms.map((f) => (
            <Card key={f.id} onClick={() => navigate(`/prop-firms/${f.id}`)}>
              <CardBody className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-md bg-info/10 text-info">
                    <Building2 size={16} />
                  </div>
                  <div>
                    <div className="text-sm font-medium text-zinc-100">{f.name}</div>
                    <div className="text-2xs text-zinc-500">
                      {f.accounts} account{f.accounts === 1 ? '' : 's'}
                      {f.capital != null && ` · ${money(f.capital, 'USD', { compact: true })}`}
                    </div>
                  </div>
                </div>
                <ArrowRight size={16} className="text-zinc-600" />
              </CardBody>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
