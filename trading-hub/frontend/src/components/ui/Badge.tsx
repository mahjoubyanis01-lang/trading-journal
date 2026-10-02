import type { ReactNode } from 'react';
import { cn } from '../../lib/cn';
import { healthColor, robotColor } from '../../lib/format';

export function Badge({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-2xs font-medium',
        className,
      )}
    >
      {children}
    </span>
  );
}

function Dot({ className }: { className: string }) {
  return <span className={cn('h-1.5 w-1.5 rounded-full', className)} />;
}

export function HealthBadge({ health }: { health: string }) {
  const c = healthColor(health);
  return (
    <Badge className={cn(c.bg, c.text)}>
      <Dot className={c.dot} />
      {c.label}
    </Badge>
  );
}

export function RobotBadge({ status }: { status: string }) {
  const c = robotColor(status);
  const pulse = status === 'active';
  return (
    <span className={cn('inline-flex items-center gap-1.5 text-xs font-medium', c.text)}>
      <Dot className={cn(c.dot, pulse && 'animate-pulse')} />
      {c.label}
    </span>
  );
}
