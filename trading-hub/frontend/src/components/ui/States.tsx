import type { ReactNode } from 'react';
import { AlertTriangle, Loader2 } from 'lucide-react';
import { cn } from '../../lib/cn';

export function Loading({ label = 'Loading…', className }: { label?: string; className?: string }) {
  return (
    <div className={cn('flex items-center justify-center gap-2 py-16 text-sm text-zinc-500', className)}>
      <Loader2 size={16} className="animate-spin" />
      {label}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
      <div className="flex items-center gap-2 text-err">
        <AlertTriangle size={18} />
        <span className="text-sm font-medium">Could not load data</span>
      </div>
      <p className="max-w-md text-xs text-zinc-500">{message}</p>
      <p className="max-w-md text-2xs text-zinc-600">
        Is the backend running on <code className="text-zinc-400">:8000</code>?
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-1 rounded-md border border-edge px-3 py-1.5 text-xs text-zinc-300 hover:bg-white/5"
        >
          Retry
        </button>
      )}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  children,
}: {
  icon?: ReactNode;
  title: string;
  description?: string;
  children?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-edge py-16 text-center">
      {icon && <div className="text-zinc-600">{icon}</div>}
      <h3 className="text-sm font-medium text-zinc-300">{title}</h3>
      {description && <p className="max-w-md text-xs text-zinc-500">{description}</p>}
      {children && <div className="mt-2 flex items-center gap-2">{children}</div>}
    </div>
  );
}
