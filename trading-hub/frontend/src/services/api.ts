// Tiny typed fetch client. All paths are prefixed with /api, which the Vite
// dev proxy rewrites to / before forwarding to the FastAPI backend on :8000.
import type {
  AccountDetail,
  AccountRow,
  Alert,
  AppConfig,
  AttentionResponse,
  CreateAccountResponse,
  Dashboard,
  EventItem,
  MarketCandidate,
  MarketRow,
  Platform,
  PropFirmDetail,
  PropFirmSummary,
  RiskNeedsConfirmation,
  Strategy,
  Terminal,
} from '../types';
import { getToken } from './token';

const BASE = '/api';

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, message: string, body: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  const tok = getToken();
  if (tok) headers['x-th-token'] = tok;
  const opts: RequestInit = {
    method,
    headers: Object.keys(headers).length ? headers : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  };
  const res = await fetch(`${BASE}${path}`, opts);
  if (res.status === 204) {
    return undefined as T;
  }
  let data: unknown = null;
  const text = await res.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }
  if (!res.ok) {
    const msg =
      (data && typeof data === 'object' && 'detail' in data
        ? String((data as { detail: unknown }).detail)
        : res.statusText) || `HTTP ${res.status}`;
    throw new ApiError(res.status, msg, data);
  }
  return data as T;
}

function qs(params: Record<string, string | number | undefined>): string {
  const parts = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== '')
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`);
  return parts.length ? `?${parts.join('&')}` : '';
}

export interface AccountsFilter {
  prop_firm?: string;
  platform?: string;
  status?: string;
  q?: string;
}

export interface CreateAccountBody {
  prop_firm_id: number;
  platform_key: string;
  login: string;
  password: string;
  server?: string;
  extra?: Record<string, string>;
  name?: string;
  strategy_id?: number;
  seed_balance: number;
}

export interface RiskResult {
  // Either an updated AccountDetail or a confirmation request.
  detail?: AccountDetail;
  confirm?: RiskNeedsConfirmation;
}

function isNeedsConfirmation(x: unknown): x is RiskNeedsConfirmation {
  return !!x && typeof x === 'object' && 'needs_confirmation' in x;
}

export const api = {
  getDashboard: () => request<Dashboard>('GET', '/dashboard'),

  getAccounts: (f: AccountsFilter = {}) =>
    request<{ accounts: AccountRow[]; total: number }>(
      'GET',
      `/accounts${qs({ prop_firm: f.prop_firm, platform: f.platform, status: f.status, q: f.q })}`,
    ),

  getAccount: (id: number) => request<AccountDetail>('GET', `/accounts/${id}`),

  createAccount: (body: CreateAccountBody) =>
    request<CreateAccountResponse>('POST', '/accounts', body),

  deleteAccount: (id: number) => request<void>('DELETE', `/accounts/${id}`),

  robot: (id: number, action: 'start' | 'stop' | 'restart') =>
    request<AccountDetail>('POST', `/accounts/${id}/robot/${action}`),

  discoverMarkets: (id: number) =>
    request<{ resolved: { universal: string; real: string; confidence: number }[]; unresolved: string[]; instruments: number }>(
      'POST',
      `/accounts/${id}/markets/discover`,
    ),

  searchMarket: (id: number, universal_symbol: string) =>
    request<{ candidates: MarketCandidate[] }>('POST', `/accounts/${id}/markets/search`, {
      universal_symbol,
    }),

  mapMarket: (id: number, universal_symbol: string, real_symbol: string) =>
    request<AccountDetail>('POST', `/accounts/${id}/markets/map`, {
      universal_symbol,
      real_symbol,
    }),

  async setRisk(
    id: number,
    mode: string,
    amount: number,
    confirm?: boolean,
  ): Promise<RiskResult> {
    const data = await request<AccountDetail | RiskNeedsConfirmation>(
      'POST',
      `/accounts/${id}/risk`,
      { mode, amount, confirm },
    );
    if (isNeedsConfirmation(data)) return { confirm: data };
    return { detail: data };
  },

  massRisk: (body: {
    account_ids?: number[];
    strategy_id?: number;
    amount: number;
    mode: string;
    confirm?: boolean;
  }) =>
    request<
      | { needs_confirmation: boolean; affected: number; message: string }
      | { applied: number }
    >('POST', '/accounts/risk/mass', body),

  massAction: (account_ids: number[], action: 'start' | 'stop' | 'restart') =>
    request<{ applied: number; action: string }>('POST', '/accounts/mass-action', {
      account_ids,
      action,
    }),

  stopAll: () => request<{ stopped: number }>('POST', '/accounts/stop-all'),

  getPropFirms: () =>
    request<{ prop_firms: PropFirmSummary[] }>('GET', '/prop-firms'),

  getPropFirm: (id: number) => request<PropFirmDetail>('GET', `/prop-firms/${id}`),

  getPlatforms: () => request<{ platforms: Platform[] }>('GET', '/platforms'),

  getStrategies: () => request<{ strategies: Strategy[] }>('GET', '/strategies'),

  getTerminals: () => request<{ terminals: Terminal[] }>('GET', '/terminals'),

  getMarkets: () => request<{ markets: MarketRow[] }>('GET', '/markets'),

  getEvents: (limit = 50, account_id?: number) =>
    request<{ events: EventItem[] }>(
      'GET',
      `/events${qs({ limit, account_id })}`,
    ),

  getAlerts: (resolved = false) =>
    request<{ alerts: Alert[] }>('GET', `/alerts${qs({ resolved: String(resolved) })}`),

  getAttention: () => request<AttentionResponse>('GET', '/attention'),

  getSettings: () => request<{ settings: Record<string, string> }>('GET', '/settings'),

  putSettings: (body: Record<string, string>) =>
    request<{ ok: true }>('PUT', '/settings', body),

  seedDemo: (count: number) =>
    request<{ created: number }>('POST', '/seed-demo', { count }),

  simFault: (
    id: number,
    fault: 'robot' | 'terminal' | 'heartbeat' | 'connection' | 'restore',
  ) =>
    request<{ ok: boolean; fault: string; heartbeat: string }>('POST', `/sim/${id}/fault`, {
      fault,
    }),

  recover: (id: number) =>
    request<{ outcome: 'recovered' | 'failed' }>('POST', `/accounts/${id}/recover`),

  getConfig: () => request<AppConfig>('GET', '/config'),
};
