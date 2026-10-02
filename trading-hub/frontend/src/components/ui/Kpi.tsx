import type { ReactNode } from 'react';
import { cn } from '../../lib/cn';

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-5 flex items-end justify-between gap-4">
      <div>
        <h1 className="text-lg font-semibold text-zinc-100">{title}</h1>
        {subtitle && <p className="mt-0.5 text-xs text-zinc-500">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Kpi({
  label,
  value,
  sub,
  valueClass,
  accent,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  valueClass?: string;
  accent?: 'green' | 'red' | 'orange' | 'blue' | 'none';
}) {
  const bar =
    accent === 'green'
      ? 'bg-op'
      : accent === 'red'
        ? 'bg-err'
        : accent === 'orange'
          ? 'bg-attn'
          : accent === 'blue'
            ? 'bg-info'
            : 'bg-edge';
  return (
    <div className="relative overflow-hidden rounded-lg border border-edge bg-panel px-4 py-3">
      <span className={cn('absolute inset-y-0 left-0 w-0.5', bar)} />
      <div className="text-2xs uppercase tracking-wide text-zinc-500">{label}</div>
      <div className={cn('tabular mt-1 text-xl font-semibold text-zinc-100', valueClass)}>{value}</div>
      {sub && <div className="mt-0.5 text-2xs text-zinc-500">{sub}</div>}
    </div>
  );
}
