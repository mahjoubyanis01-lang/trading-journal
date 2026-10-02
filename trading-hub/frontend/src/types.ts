// Frozen API contract types for Trading Hub.

export type Health =
  | 'operational'
  | 'attention'
  | 'error'
  | 'disconnected'
  | 'pending';

export type RobotStatus =
  | 'active'
  | 'stopped'
  | 'starting'
  | 'stopping'
  | 'error'
  | 'unknown';

export interface AccountRow {
  id: number;
  name: string;
  prop_firm: string;
  prop_firm_id: number;
  platform: string;
  platform_key: string;
  strategy: string | null;
  robot_version: string | null;
  capital: number;
  balance: number;
  equity: number;
  currency: string;
  pnl_total: number;
  performance_pct: number;
  risk_mode: string;
  risk_amount: number;
  risk_source: string;
  robot_status: RobotStatus;
  terminal: string;
  health: Health;
  connection: string;
}

export interface Market {
  universal: string;
  real: string | null;
  confidence: number;
  status: string;
  verified: boolean;
}

export interface TerminalDetail {
  instance_id: string;
  status: string;
  process_id: number | null;
  terminal_path: string | null;
}

export interface AccountDetail extends AccountRow {
  pnl_today: number;
  pnl_month: number;
  risk_reference: string;
  risk_reference_value: number;
  risk_percent: number;
  heartbeat: string;
  markets: Market[];
  terminal_detail: TerminalDetail | null;
}

export interface WorkflowStep {
  name: string;
  ok: boolean;
  detail: string;
}

export interface CreateAccountResponse {
  account: AccountDetail;
  steps: WorkflowStep[];
}

export interface EventItem {
  id: number;
  account_id: number | null;
  type: string;
  message: string;
  ts: number;
}

export interface Alert {
  id: number;
  account_id: number | null;
  type: string;
  severity: string;
  message: string;
  resolved: boolean;
  ts: number;
}

export interface PropFirmSummary {
  id: number;
  name: string;
  accounts: number;
  capital?: number;
  pnl_today?: number;
  pnl_month?: number;
  performance_pct?: number;
  robots_active?: number;
}

export interface PropFirmDetail {
  id: number;
  name: string;
  accounts: number;
  capital: number;
  pnl_today: number;
  pnl_month: number;
  performance_pct: number;
  robots_active: number;
  accounts_list: AccountRow[];
}

export interface Dashboard {
  accounts: number;
  capital: number;
  balance_total: number;
  equity_total: number;
  pnl_today: number;
  pnl_month: number;
  performance_pct: number;
  drawdown_global: number;
  robots_active: number;
  robots_total: number;
  by_health: Record<string, number>;
  prop_firms: PropFirmSummary[];
  attention: AccountRow[];
  recent_events: EventItem[];
}

export interface CredentialField {
  name: string;
  label: string;
  secret: boolean;
  required: boolean;
}

export interface Platform {
  id: number;
  key: string;
  name: string;
  available: boolean;
  requirement?: string;
  needs_server?: boolean;
  credential_fields?: CredentialField[];
  capabilities: Record<string, boolean>;
}

export interface Strategy {
  id: number;
  name: string;
  enabled: boolean;
  accounts: number;
  active: number;
  attention: number;
  markets: string[];
  risk_percent: number;
  version: string;
}

export interface Terminal {
  instance_id: string;
  account_id: number;
  platform_key: string;
  status: string;
  process_id: number | null;
  terminal_path: string | null;
}

export interface MarketRow {
  universal: string;
  real: string | null;
  platform: string;
  broker: string;
  confidence: number;
  status: string;
}

export interface MarketCandidate {
  real_symbol: string;
  confidence: number;
  description: string;
  reason: string;
}

export interface RiskNeedsConfirmation {
  needs_confirmation: true;
  warnings: string[];
  old_amount: number;
  new_amount: number;
}

export interface AttentionResponse {
  accounts: (AccountRow & { alerts: Alert[] })[];
  count: number;
}

export interface AppConfig {
  mock_mode: boolean;
  credential_backend: string;
  confidence_auto: number;
  confidence_confirm: number;
  heartbeat_timeout_s: number;
}

export interface WsMessage {
  type: string;
  payload: {
    account_id?: number;
    message?: string;
    [k: string]: unknown;
  };
  ts: number;
}
