import { NavLink } from 'react-router-dom';
import {
  Activity,
  Bot,
  Building2,
  LayoutDashboard,
  LineChart,
  Settings as SettingsIcon,
  TriangleAlert,
  Wallet,
} from 'lucide-react';
import { cn } from '../../lib/cn';

interface NavItemDef {
  to: string;
  label: string;
  icon: typeof Activity;
  end?: boolean;
}

const NAV: NavItemDef[] = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/accounts', label: 'Accounts', icon: Wallet },
  { to: '/prop-firms', label: 'Prop Firms', icon: Building2 },
  { to: '/robots', label: 'Robots', icon: Bot },
  { to: '/markets', label: 'Markets', icon: LineChart },
  { to: '/attention', label: 'Attention', icon: TriangleAlert },
  { to: '/settings', label: 'Settings', icon: SettingsIcon },
];

export function Sidebar({ attentionCount }: { attentionCount?: number }) {
  return (
    <aside className="flex w-56 shrink-0 flex-col border-r border-edge bg-panel2">
      <div className="flex h-14 items-center gap-2 border-b border-edge px-4">
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-info/15 text-info">
          <Activity size={16} />
        </div>
        <div className="leading-tight">
          <div className="text-sm font-semibold text-zinc-100">Trading Hub</div>
          <div className="text-2xs text-zinc-500">Control Center</div>
        </div>
      </div>
      <nav className="flex-1 space-y-0.5 p-2">
        {NAV.map((item) => {
          const Icon = item.icon;
          const showBadge = item.to === '/attention' && !!attentionCount;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  'flex items-center justify-between rounded-md px-3 py-2 text-sm transition-colors',
                  isActive
                    ? 'bg-info/10 text-zinc-100'
                    : 'text-zinc-400 hover:bg-white/5 hover:text-zinc-200',
                )
              }
            >
              <span className="flex items-center gap-2.5">
                <Icon size={16} />
                {item.label}
              </span>
              {showBadge && (
                <span className="rounded-full bg-attn/20 px-1.5 text-2xs font-semibold text-attn">
                  {attentionCount}
                </span>
              )}
            </NavLink>
          );
        })}
      </nav>
      <div className="border-t border-edge p-3 text-2xs text-zinc-600">
        Everything automatic.
        <br />
        Exceptions visible.
      </div>
    </aside>
  );
}
