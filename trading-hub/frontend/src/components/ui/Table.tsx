import type { ReactNode } from 'react';
import { ArrowDown, ArrowUp, ChevronsUpDown } from 'lucide-react';
import { cn } from '../../lib/cn';

export function Table({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn('w-full overflow-x-auto', className)}>
      <table className="w-full border-collapse text-sm">{children}</table>
    </div>
  );
}

export function THead({ children }: { children: ReactNode }) {
  return (
    <thead className="sticky top-0 z-10 bg-panel2 text-left text-2xs uppercase tracking-wide text-zinc-500">
      {children}
    </thead>
  );
}

export function TBody({ children }: { children: ReactNode }) {
  return <tbody className="divide-y divide-edge/70">{children}</tbody>;
}

export function TR({
  children,
  onClick,
  className,
  selected,
}: {
  children: ReactNode;
  onClick?: () => void;
  className?: string;
  selected?: boolean;
}) {
  return (
    <tr
      onClick={onClick}
      className={cn(
        onClick && 'cursor-pointer',
        'transition-colors hover:bg-white/[0.03]',
        selected && 'bg-info/5',
        className,
      )}
    >
      {children}
    </tr>
  );
}

export function TH({
  children,
  sortable,
  active,
  dir,
  onSort,
  className,
  align = 'left',
}: {
  children?: ReactNode;
  sortable?: boolean;
  active?: boolean;
  dir?: 'asc' | 'desc';
  onSort?: () => void;
  className?: string;
  align?: 'left' | 'right' | 'center';
}) {
  const alignCls = align === 'right' ? 'text-right' : align === 'center' ? 'text-center' : 'text-left';
  return (
    <th
      className={cn('whitespace-nowrap px-3 py-2 font-medium', alignCls, className)}
    >
      {sortable ? (
        <button
          onClick={onSort}
          className={cn(
            'inline-flex items-center gap-1 hover:text-zinc-300',
            align === 'right' && 'flex-row-reverse',
            active && 'text-zinc-200',
          )}
        >
          {children}
          {active ? (
            dir === 'asc' ? <ArrowUp size={11} /> : <ArrowDown size={11} />
          ) : (
            <ChevronsUpDown size={11} className="opacity-40" />
          )}
        </button>
      ) : (
        children
      )}
    </th>
  );
}

export function TD({
  children,
  className,
  align = 'left',
  onClick,
}: {
  children: ReactNode;
  className?: string;
  align?: 'left' | 'right' | 'center';
  onClick?: (e: React.MouseEvent) => void;
}) {
  const alignCls = align === 'right' ? 'text-right' : align === 'center' ? 'text-center' : 'text-left';
  return (
    <td onClick={onClick} className={cn('whitespace-nowrap px-3 py-2 text-zinc-300', alignCls, className)}>
      {children}
    </td>
  );
}
