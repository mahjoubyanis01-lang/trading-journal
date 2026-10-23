// Client API typé — contrat: backtester/API_CONTRACT.md
// Backend FastAPI sur http://127.0.0.1:8000, proxifié par Vite sous /api.

/** Verdict en 5 niveaux (biais prédit ET direction réelle). */
export type Bias = 'strong_bullish' | 'bullish' | 'neutral' | 'bearish' | 'strong_bearish'
/** Direction d'un facteur individuel — reste sur 3 niveaux. */
export type FactorDirection = 'bullish' | 'bearish' | 'neutral'
export type Sentiment = 'positive' | 'negative' | 'neutral'
export type Relevance = 'high' | 'medium' | 'low'

// ---------- /api/health ----------
export interface Health {
  status: string
  version: string
}

// ---------- /api/config ----------
export interface NotificationsConfig {
  enabled: boolean
  telegram_chat_id: string
}

export interface AppConfig {
  notifications: NotificationsConfig
  lookback_sessions: number
  bullish_threshold: number
  strong_bullish_threshold: number
  bearish_threshold: number
  strong_bearish_threshold: number
  neutral_band_pct: number
  strong_band_pct: number
  cutoff_paris: string
  measure_start_ny: string
  factor_weights: Record<string, number>
  es_provider: 'yahoo' | 'databento'
}

// ---------- /api/providers ----------
export interface ProviderTestResult {
  ok: boolean
  message: string
  at: string
}

export interface ProviderStatus {
  id: string
  label: string
  requires_key: boolean
  configured: boolean
  key_masked: string | null
  categories: string[]
  last_test: ProviderTestResult | null
}

export interface ProvidersResponse {
  providers: ProviderStatus[]
}

export interface SetKeyResponse {
  ok: boolean
  key_masked: string
}

// ---------- /api/backtest ----------
export interface BacktestRunResponse {
  run_id: string
  already_running: boolean
}

export interface BacktestProgress {
  done: number
  total: number
  current_date: string | null
}

export interface BacktestStatus {
  running: boolean
  run_id: string | null
  progress: BacktestProgress | null
  started_at: string | null
  finished_at: string | null
  error: string | null
}

// ---------- /api/results/summary ----------
export interface DailyResult {
  date: string
  predicted: Bias
  actual: Bias | null
  /** Même direction (hausse/baisse/neutre, intensité ignorée). */
  correct: boolean | null
  /** Même classe parmi les 5 niveaux. */
  exact: boolean | null
  score: number
  confidence: number
  change_pct: number | null
}

export interface SummaryPeriod {
  start: string
  end: string
  sessions: number
}

export interface Summary {
  period: SummaryPeriod | null
  evaluated_sessions: number | null
  insufficient_sessions: number | null
  hit_rate: number | null
  hit_rate_excl_neutral_pred: number | null
  predictions: Record<Bias, number> | null
  correct: number | null
  incorrect: number | null
  data_completeness_pct: number | null
  last_processed_date: string | null
  daily: DailyResult[] | null
}

// ---------- /api/results/sessions ----------
export interface SessionRow {
  date: string
  predicted: Bias
  score: number
  confidence: number
  actual: Bias | null
  change_points: number | null
  change_pct: number | null
  correct: boolean | null
  exact: boolean | null
  open_price: number | null
  close_price: number | null
  data_quality: number
  insufficient: boolean
  bullish_summary: string | null
  bearish_summary: string | null
}

export interface SessionsResponse {
  sessions: SessionRow[]
}

export interface SessionsFilters {
  predicted?: Bias | ''
  actual?: Bias | ''
  correct?: 'true' | 'false' | ''
  exact?: 'true' | 'false' | ''
  min_confidence?: string
  min_quality?: string
  date_from?: string
  date_to?: string
}

// ---------- /api/results/sessions/{date} ----------
export interface Factor {
  id: string
  label: string
  value: string | null
  score: number | null
  max_weight: number
  direction: FactorDirection
  rationale: string | null
  available: boolean
  as_of: string | null
}

export interface NewsItem {
  title: string
  source: string
  published_at: string
  url: string | null
  sentiment: Sentiment
  relevance: Relevance
  category: string
}

export interface MacroRelease {
  series: string
  name: string
  period: string
  released_at: string | null
  value: number | null
  previous: number | null
  consensus: number | null
  consensus_available: boolean
  surprise_vs_previous: number | null
  interpretation: string | null
}

export interface PreopenMarket {
  es_move_pct: number | null
  nq_move_pct: number | null
  europe_pct: number | null
  nikkei_pct: number | null
  vix_prev_close: number | null
  vix_20d_avg: number | null
  us10y_prev: number | null
  us10y_change_bp: number | null
  us2y_prev: number | null
  dxy_prev_change_pct: number | null
  oil_pct: number | null
  gold_pct: number | null
  as_of: string | null
}

export interface Measurement {
  open_price: number | null
  open_at: string | null
  close_price: number | null
  close_at: string | null
  change_points: number | null
  change_pct: number | null
  actual: Bias | null
  correct: boolean | null
  exact: boolean | null
  contract_note: string | null
  /** Mode temps réel : séance en cours, mesure partielle. */
  in_progress?: boolean
  note?: string
}

export interface Candle {
  t: string
  o: number
  h: number
  l: number
  c: number
}

export interface CollectionError {
  source: string
  message: string
  date?: string
  at?: string
}

export interface SessionDetail {
  date: string
  cutoff_at: string | null
  measure_start_at: string | null
  measure_end_at: string | null
  predicted: Bias
  score: number
  confidence: number
  reasoning: string | null
  macro_summary: string | null
  factors: Factor[]
  bullish_factors: string[]
  bearish_factors: string[]
  contradictions: string[]
  news: NewsItem[]
  macro_releases: MacroRelease[]
  preopen_market: PreopenMarket | null
  measurement: Measurement | null
  intraday: Candle[]
  data_quality: number
  insufficient: boolean
  limitations: string[]
  collection_errors: CollectionError[]
}

// ---------- /api/live/verdict ----------
export interface LiveSession extends SessionDetail {
  live: boolean
  /** true avant l'heure limite (verdict provisoire sur données ≤ maintenant). */
  provisional: boolean
  as_of: string
}

export interface LiveVerdict {
  available: boolean
  message?: string
  session?: LiveSession
}

// ---------- /api/notify ----------
export interface NotifyChannelResult {
  ok: boolean
  message: string
}

export interface NotifyTestResult {
  toast: NotifyChannelResult
  telegram: NotifyChannelResult | null
}

export interface NotifyStatus {
  enabled: boolean
  cutoff_paris: string
  next_trigger: string
  last_sent_date: string | null
  windows_toast_available: boolean
  telegram_configured: boolean
}

// ---------- /api/results/stats ----------
export interface CategoryStats {
  predicted: number
  correct: number
  exact: number
  hit_rate: number | null
  avg_change_pct: number | null
}

export interface ConfusionMatrix {
  rows: string[]
  matrix: number[][]
}

export interface ConfidenceBucket {
  bucket: string
  n: number
  hit_rate: number | null
}

export interface WeekStats {
  week: string
  n: number
  correct: number
  hit_rate: number | null
}

export interface ChangeBin {
  bin: string
  count: number
}

export interface Baseline {
  id: string
  label: string
  hit_rate: number | null
  n: number
}

export interface StatsResponse {
  n_sessions: number
  n_evaluated: number
  n_insufficient: number
  hit_rate: number | null
  hit_rate_excl_neutral: number | null
  exact_rate: number | null
  by_category: Record<Bias, CategoryStats>
  confusion_matrix: ConfusionMatrix
  by_confidence: ConfidenceBucket[]
  by_week: WeekStats[]
  change_distribution: ChangeBin[]
  avg_change_by_prediction: Record<Bias, number | null>
  baselines: Baseline[]
  disclaimer: string
}

// ---------- /api/errors ----------
export interface ErrorsResponse {
  errors: CollectionError[]
}

// ===================================================================
// Client

/** Erreur réseau: le backend est injoignable (serveur non démarré). */
export class BackendUnreachableError extends Error {
  constructor() {
    super('Backend injoignable — démarrez le serveur backend')
    this.name = 'BackendUnreachableError'
  }
}

/** Erreur HTTP renvoyée par le backend. */
export class ApiError extends Error {
  readonly status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, {
      headers: { Accept: 'application/json', ...(init?.body ? { 'Content-Type': 'application/json' } : {}) },
      ...init,
    })
  } catch {
    throw new BackendUnreachableError()
  }
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body: unknown = await res.json()
      if (body && typeof body === 'object' && 'detail' in body && typeof (body as { detail: unknown }).detail === 'string') {
        detail = (body as { detail: string }).detail
      }
    } catch {
      // corps non JSON — on garde le statut HTTP
    }
    throw new ApiError(res.status, detail)
  }
  return (await res.json()) as T
}

function qs(params: Record<string, string | undefined>): string {
  const sp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== '') sp.set(k, v)
  }
  const s = sp.toString()
  return s ? `?${s}` : ''
}

export const api = {
  health: () => request<Health>('/api/health'),

  getConfig: () => request<AppConfig>('/api/config'),
  putConfig: (patch: Partial<AppConfig>) =>
    request<AppConfig>('/api/config', { method: 'PUT', body: JSON.stringify(patch) }),

  providersStatus: () => request<ProvidersResponse>('/api/providers/status'),
  setProviderKey: (id: string, key: string) =>
    request<SetKeyResponse>(`/api/providers/${encodeURIComponent(id)}/key`, {
      method: 'POST',
      body: JSON.stringify({ key }),
    }),
  deleteProviderKey: (id: string) =>
    request<unknown>(`/api/providers/${encodeURIComponent(id)}/key`, { method: 'DELETE' }),
  testProvider: (id: string) =>
    request<ProviderTestResult>(`/api/providers/${encodeURIComponent(id)}/test`, { method: 'POST' }),

  runBacktest: (sessions: number, force = false) =>
    request<BacktestRunResponse>('/api/backtest/run', {
      method: 'POST',
      body: JSON.stringify({ sessions, force }),
    }),
  backtestStatus: () => request<BacktestStatus>('/api/backtest/status'),

  summary: () => request<Summary>('/api/results/summary'),
  sessions: (filters: SessionsFilters = {}) =>
    request<SessionsResponse>(
      `/api/results/sessions${qs({
        predicted: filters.predicted || undefined,
        actual: filters.actual || undefined,
        correct: filters.correct || undefined,
        exact: filters.exact || undefined,
        min_confidence: filters.min_confidence || undefined,
        min_quality: filters.min_quality || undefined,
        date_from: filters.date_from || undefined,
        date_to: filters.date_to || undefined,
      })}`,
    ),
  sessionDetail: (date: string) =>
    request<SessionDetail>(`/api/results/sessions/${encodeURIComponent(date)}`),
  stats: () => request<StatsResponse>('/api/results/stats'),
  errors: () => request<ErrorsResponse>('/api/errors'),
  liveVerdict: (refresh = false) =>
    request<LiveVerdict>(`/api/live/verdict${refresh ? '?refresh=true' : ''}`),
  notifyStatus: () => request<NotifyStatus>('/api/notify/status'),
  notifyTest: () => request<NotifyTestResult>('/api/notify/test', { method: 'POST' }),
}

export const EXPORT_CSV_URL = '/api/export/csv'
export const EXPORT_JSON_URL = '/api/export/json'
