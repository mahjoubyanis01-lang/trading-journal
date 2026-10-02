import type { InputHTMLAttributes, SelectHTMLAttributes, ReactNode } from 'react';
import { cn } from '../../lib/cn';

export function Input({
  className,
  ...rest
}: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        'h-9 w-full rounded-md border border-edge bg-panel2 px-3 text-sm text-zinc-100 placeholder:text-zinc-600',
        'focus:border-info/50 focus:outline-none focus:ring-1 focus:ring-info/30',
        className,
      )}
      {...rest}
    />
  );
}

export function Select({
  className,
  children,
  ...rest
}: { children: ReactNode } & SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn(
        'h-9 w-full rounded-md border border-edge bg-panel2 px-2.5 text-sm text-zinc-100',
        'focus:border-info/50 focus:outline-none focus:ring-1 focus:ring-info/30',
        className,
      )}
      {...rest}
    >
      {children}
    </select>
  );
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <div className="mb-1 flex items-baseline justify-between">
        <span className="text-xs font-medium text-zinc-400">{label}</span>
        {hint && <span className="text-2xs text-zinc-600">{hint}</span>}
      </div>
      {children}
    </label>
  );
}
