import { useNavigate } from 'react-router-dom';
import { HealthBadge, RobotBadge } from './ui/Badge';
import { Table, TBody, TD, TH, THead, TR } from './ui/Table';
import { money, pct, signClass } from '../lib/format';
import type { AccountRow } from '../types';

export function AccountsTable({ rows }: { rows: AccountRow[] }) {
  const navigate = useNavigate();
  if (rows.length === 0) {
    return <p className="py-10 text-center text-xs text-zinc-600">No accounts</p>;
  }
  return (
    <Table>
      <THead>
        <TR>
          <TH>Account</TH>
          <TH>Platform</TH>
          <TH align="right">Capital</TH>
          <TH align="right">Balance</TH>
          <TH align="right">Equity</TH>
          <TH align="right">P&L</TH>
          <TH align="right">Perf %</TH>
          <TH>Robot</TH>
          <TH>Status</TH>
        </TR>
      </THead>
      <TBody>
        {rows.map((a) => (
          <TR key={a.id} onClick={() => navigate(`/accounts/${a.id}`)}>
            <TD className="font-medium text-zinc-100">{a.name}</TD>
            <TD className="text-zinc-400">{a.platform}</TD>
            <TD align="right" className="tabular">{money(a.capital, a.currency, { compact: true })}</TD>
            <TD align="right" className="tabular">{money(a.balance, a.currency, { compact: true })}</TD>
            <TD align="right" className="tabular">{money(a.equity, a.currency, { compact: true })}</TD>
            <TD align="right" className={`tabular ${signClass(a.pnl_total)}`}>{money(a.pnl_total, a.currency, { compact: true })}</TD>
            <TD align="right" className={`tabular ${signClass(a.performance_pct)}`}>{pct(a.performance_pct)}</TD>
            <TD><RobotBadge status={a.robot_status} /></TD>
            <TD><HealthBadge health={a.health} /></TD>
          </TR>
        ))}
      </TBody>
    </Table>
  );
}
