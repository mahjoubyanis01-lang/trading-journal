import type { Health, RobotStatus } from '../types';

export function money(value: number, currency = 'USD', opts: { compact?: boolean } = {}): string {
  if (value == null || Number.isNaN(value)) return '—';
  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency || 'USD',
      maximumFractionDigits: opts.compact && Math.abs(value) >= 10000 ? 0 : 2,
      notation: opts.compact && Math.abs(value) >= 1_000_000 ? 'compact' : 'standard',
    }).format(value);
  } catch {
    // Unknown currency code fallback
    return `${value.toLocaleString('en-US', { maximumFractionDigits: 2 })} ${currency}`;
  }
}

export function num(value: number, digits = 0): string {
  if (value == null || Number.isNaN(value)) return '—';
  return value.toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

// Signed percentage, e.g. "+2.34%" / "-1.10%"
export function pct(value: number, digits = 2): string {
  if (value == null || Number.isNaN(value)) return '—';
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(digits)}%`;
}

export function signedMoney(value: number, currency = 'USD'): string {
  if (value == null || Number.isNaN(value)) return '—';
  const sign = value > 0 ? '+' : '';
  return sign + money(value, currency);
}

// Tailwind text color class for a signed number (green up / red down).
export function signClass(value: number): string {
  if (value > 0) return 'text-op';
  if (value < 0) return 'text-err';
  return 'text-zinc-400';
}

export function relTime(ts: number): string {
  if (!ts) return '';
  // Backend ts may be seconds or ms; normalize to ms.
  const ms = ts > 1e12 ? ts : ts * 1000;
  const diff = Date.now() - ms;
  const s = Math.round(diff / 1000);
  if (s < 5) return 'just now';
  if (s < 60) return `${s}s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.round(h / 24);
  return `${d}d ago`;
}

export function clockTime(ts: number): string {
  if (!ts) return '';
  const ms = ts > 1e12 ? ts : ts * 1000;
  return new Date(ms).toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

// --- State → color mapping (color ONLY conveys state) ---

export const HEALTH_COLORS: Record<Health, { dot: string; text: string; bg: string; label: string }> = {
  operational: { dot: 'bg-op', text: 'text-op', bg: 'bg-op/10 border-op/30', label: 'Operational' },
  attention: { dot: 'bg-attn', text: 'text-attn', bg: 'bg-attn/10 border-attn/30', label: 'Attention' },
  error: { dot: 'bg-err', text: 'text-err', bg: 'bg-err/10 border-err/30', label: 'Error' },
  disconnected: { dot: 'bg-idle', text: 'text-idle', bg: 'bg-idle/10 border-idle/30', label: 'Disconnected' },
  pending: { dot: 'bg-info', text: 'text-info', bg: 'bg-info/10 border-info/30', label: 'Pending' },
};

export function healthColor(h: string) {
  return HEALTH_COLORS[(h as Health)] ?? HEALTH_COLORS.disconnected;
}

export const ROBOT_COLORS: Record<RobotStatus, { dot: string; text: string; label: string }> = {
  active: { dot: 'bg-op', text: 'text-op', label: 'Active' },
  stopped: { dot: 'bg-idle', text: 'text-idle', label: 'Stopped' },
  starting: { dot: 'bg-info', text: 'text-info', label: 'Starting' },
  stopping: { dot: 'bg-info', text: 'text-info', label: 'Stopping' },
  error: { dot: 'bg-err', text: 'text-err', label: 'Error' },
  unknown: { dot: 'bg-idle', text: 'text-idle', label: 'Unknown' },
};

export function robotColor(s: string) {
  return ROBOT_COLORS[(s as RobotStatus)] ?? ROBOT_COLORS.unknown;
}

export function confidenceColor(c: number): string {
  if (c >= 0.9) return 'text-op';
  if (c >= 0.7) return 'text-attn';
  return 'text-err';
}
