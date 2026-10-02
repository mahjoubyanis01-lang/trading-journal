import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { cn } from '../../lib/cn';

type Variant = 'default' | 'primary' | 'danger' | 'ghost' | 'subtle';
type Size = 'sm' | 'md' | 'icon';

const VARIANTS: Record<Variant, string> = {
  default: 'border border-edge bg-panel2 text-zinc-200 hover:border-zinc-600 hover:bg-[#161f2e]',
  primary: 'border border-info/40 bg-info/15 text-info hover:bg-info/25',
  danger: 'border border-err/40 bg-err/10 text-err hover:bg-err/20',
  ghost: 'text-zinc-400 hover:text-zinc-100 hover:bg-white/5',
  subtle: 'border border-edge bg-transparent text-zinc-400 hover:text-zinc-100 hover:bg-white/5',
};

const SIZES: Record<Size, string> = {
  sm: 'h-7 px-2.5 text-xs gap-1.5',
  md: 'h-9 px-3.5 text-sm gap-2',
  icon: 'h-8 w-8 justify-center',
};

export function Button({
  children,
  variant = 'default',
  size = 'md',
  className,
  ...rest
}: {
  children: ReactNode;
  variant?: Variant;
  size?: Size;
} & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={cn(
        'inline-flex items-center rounded-md font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40',
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  );
}
