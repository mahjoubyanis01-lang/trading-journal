import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api, BackendUnreachableError } from '../api'
import type { BacktestStatus, DailyResult, Summary } from '../api'
import { useApi } from '../hooks'
import { Card, EmptyState, ErrorBanner, Loading, StatTile } from '../components/ui'
import {
  biasLabel,
  correctLabel,
  fmtDate,
  fmtDateShort,
  fmtInt,
  fmtPct,
  fmtRate,
} from '../format'

const SESSION_CHOICES = [10, 30, 60, 90, 252]

const COLOR_BULL = 'var(--bull)'
const COLOR_BEAR = 'var(--bear)'
const COLOR_NEUTRAL = 'var(--neutral)'

// ---------------------------------------------------------------
// Lancement du backtest + suivi de progression

function BacktestRunner({ onFinished }: { onFinished: () => void }) {
  const [sessions, setSessions] = useState(30)
  const [force, setForce] = useState(false)
  const [status, setStatus] = useState<BacktestStatus | null>(null)
  const [starting, setStarting] = useState(false)
  const [runError, setRunError] = useState<string | null>(null)
  const wasRunning = useRef(false)
  const timer = useRef<ReturnType<typeof setInterval> | null>(null)

  const stopPolling = useCallback(() => {
    if (timer.current) {
      clearInterval(timer.current)
      timer.current = null
    }
  }, [])

  const poll = useCallback(async () => {
    try {
      const s = await api.backtestStatus()
      setStatus(s)
      if (s.running) {
        wasRunning.current = true
      } else {
        stopPolling()
        if (wasRunning.current) {
          wasRunning.current = false
          onFinished()
        }
      }
    } catch (e) {
      stopPolling()
      if (!(e instanceof BackendUnreachableError)) {
        setRunError(e instanceof Error ? e.message : String(e))
      }
    }
  }, [onFinished, stopPolling])

  const startPolling = useCallback(() => {
    stopPolling()
    timer.current = setInterval(() => {
      void poll()
    }, 2000)
  }, [poll, stopPolling])

  // Au montage: un run est peut-être déjà en cours.
  useEffect(() => {
    void api
      .backtestStatus()
      .then((s) => {
        setStatus(s)
        if (s.running) {
          wasRunning.current = true
          startPolling()
        }
      })
      .catch(() => {
        /* backend absent: le bandeau global s'en charge */
      })
    return stopPolling
  }, [startPolling, stopPolling])

  const run = async () => {
    setStarting(true)
    setRunError(null)
    try {
      await api.runBacktest(sessions, force)
      wasRunning.current = true
      await poll()
      startPolling()
    } catch (e) {
      if (e instanceof BackendUnreachableError) {
        setRunError('Backend injoignable — démarrez le serveur backend.')
      } else {
        setRunError(e instanceof Error ? e.message : String(e))
      }
    } finally {
      setStarting(false)
    }
  }

  const running = status?.running ?? false
  const progress = status?.progress ?? null
  const pct =
    running && progress && progress.total > 0
      ? Math.round((progress.done / progress.total) * 100)
      : 0

  return (
    <Card title="Lancer le backtest">
      <div className="run-row">
        <div className="field">
          <label htmlFor="sessions-select">Nombre de séances</label>
          <select
            id="sessions-select"
            value={sessions}
            onChange={(e) => setSessions(Number(e.target.value))}
            disabled={running || starting}
          >
            {SESSION_CHOICES.map((n) => (
              <option key={n} value={n}>
                {n} séances
              </option>
            ))}
          </select>
        </div>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
          <input
            type="checkbox"
            checked={force}
            onChange={(e) => setForce(e.target.checked)}
            disabled={running || starting}
          />
          Recalculer les séances déjà analysées
        </label>
        <button
          type="button"
          className="btn btn-primary btn-big"
          onClick={() => void run()}
          disabled={running || starting}
        >
          {running ? 'Backtest en cours…' : starting ? 'Démarrage…' : '▶ Lancer le backtest'}
        </button>
      </div>

      {running && (
        <div style={{ marginTop: 16 }}>
          <div
            className="progress-track"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={progress?.total ?? 100}
            aria-valuenow={progress?.done ?? 0}
          >
            <div className="progress-fill" style={{ width: `${pct}%` }} />
          </div>
          <div className="progress-meta">
            <span>
              {progress ? `${fmtInt(progress.done)} / ${fmtInt(progress.total)} séances` : '…'}
            </span>
            <span>
              {progress?.current_date ? `Séance en cours : ${fmtDate(progress.current_date)}` : ''}
            </span>
          </div>
        </div>
      )}

      {!running && status?.error && (
        <p className="neg" style={{ marginTop: 12, fontSize: 13.5 }}>
          Dernier run en erreur : {status.error}
        </p>
      )}
      {runError && (
        <p className="neg" style={{ marginTop: 12, fontSize: 13.5 }}>
          {runError}
        </p>
      )}
    </Card>
  )
}

// ---------------------------------------------------------------
// Graphiques

function PredictionsDonut({ summary }: { summary: Summary }) {
  const p = summary.predictions
  if (!p) return <EmptyState message="Aucune donnée" />
  const data = [
    { key: 'bullish', name: biasLabel('bullish'), value: p.bullish, color: COLOR_BULL },
    { key: 'bearish', name: biasLabel('bearish'), value: p.bearish, color: COLOR_BEAR },
    { key: 'neutral', name: biasLabel('neutral'), value: p.neutral, color: COLOR_NEUTRAL },
  ]
  const total = p.bullish + p.bearish + p.neutral
  return (
    <div>
      <ResponsiveContainer width="100%" height={240}>
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="name"
            innerRadius={62}
            outerRadius={92}
            paddingAngle={2}
            stroke="var(--surface-1)"
            strokeWidth={2}
            label={(entry) => `${String(entry.name)} : ${String(entry.value)}`}
            labelLine={false}
          >
            {data.map((d) => (
              <Cell key={d.key} fill={d.color} />
            ))}
          </Pie>
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null
              const item = payload[0]
              const v = Number(item.value ?? 0)
              return (
                <div className="tooltip">
                  <div className="t-title">{String(item.name)}</div>
                  <div className="t-row">
                    {fmtInt(v)} prédiction{v > 1 ? 's' : ''}
                    {total > 0 ? ` · ${fmtRate(v / total)}` : ''}
                  </div>
                </div>
              )
            }}
          />
        </PieChart>
      </ResponsiveContainer>
      <div className="legend">
        {data.map((d) => (
          <span key={d.key} className="legend-item">
            <span className="legend-swatch" style={{ background: d.color }} />
            {d.name} ({fmtInt(d.value)})
          </span>
        ))}
      </div>
    </div>
  )
}

function dailyColor(d: DailyResult): string {
  if (d.correct == null) return COLOR_NEUTRAL
  return d.correct ? COLOR_BULL : COLOR_BEAR
}

function DailyChart({ daily }: { daily: DailyResult[] }) {
  const navigate = useNavigate()
  const data = daily.map((d) => ({ ...d, change: d.change_pct }))
  return (
    <div>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="var(--grid)" vertical={false} />
          <XAxis
            dataKey="date"
            tickFormatter={fmtDateShort}
            tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
            axisLine={{ stroke: 'var(--baseline)' }}
            tickLine={false}
            interval="preserveStartEnd"
            minTickGap={24}
          />
          <YAxis
            tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={44}
            tickFormatter={(v: number) => `${v} %`}
          />
          <ReferenceLine y={0} stroke="var(--baseline)" />
          <Tooltip
            cursor={{ fill: 'rgba(255,255,255,0.04)' }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null
              const d = payload[0].payload as DailyResult
              return (
                <div className="tooltip">
                  <div className="t-title">{fmtDate(d.date)}</div>
                  <div className="t-row">Variation : {fmtPct(d.change_pct, true)}</div>
                  <div className="t-row">Prédit : {biasLabel(d.predicted)}</div>
                  <div className="t-row">Réel : {biasLabel(d.actual)}</div>
                  <div className="t-row">{correctLabel(d.correct)}</div>
                </div>
              )
            }}
          />
          <Bar
            dataKey="change"
            radius={[4, 4, 0, 0]}
            maxBarSize={22}
            cursor="pointer"
            onClick={(entry) => {
              const d = (entry as unknown as { payload?: DailyResult }).payload
              if (d?.date) void navigate(`/sessions/${d.date}`)
            }}
          >
            {data.map((d) => (
              <Cell key={d.date} fill={dailyColor(d)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <div className="legend">
        <span className="legend-item">
          <span className="legend-swatch" style={{ background: COLOR_BULL }} />
          Prédiction correcte
        </span>
        <span className="legend-item">
          <span className="legend-swatch" style={{ background: COLOR_BEAR }} />
          Prédiction incorrecte
        </span>
        <span className="legend-item">
          <span className="legend-swatch" style={{ background: COLOR_NEUTRAL }} />
          Non évaluable
        </span>
      </div>
      <p className="chart-note">
        Variation en % de chaque séance (ouverture 09:30 NY → minuit Paris). Cliquez sur une barre
        pour ouvrir le détail de la séance.
      </p>
    </div>
  )
}

// ---------------------------------------------------------------

export default function Dashboard() {
  const { data: summary, loading, error, unreachable, reload } = useApi(api.summary)

  const hasData = summary != null && summary.period != null

  return (
    <>
      <h1 className="page-title">Tableau de bord</h1>
      <p className="page-sub">
        Biais macro avant ouverture (information ≤ 15:29 Paris) comparé à la direction réelle du
        S&amp;P 500.
      </p>

      <ErrorBanner unreachable={unreachable} error={error} onRetry={reload} />

      <BacktestRunner onFinished={reload} />

      {loading && <Loading />}

      {!loading && summary != null && !hasData && (
        <Card>
          <EmptyState
            message="Aucun backtest — lancez une analyse"
            hint="Choisissez un nombre de séances ci-dessus puis cliquez sur « Lancer le backtest »."
          />
        </Card>
      )}

      {hasData && summary && (
        <>
          <div className="tiles">
            <StatTile
              label="Période analysée"
              value={
                summary.period
                  ? `${fmtDate(summary.period.start)} → ${fmtDate(summary.period.end)}`
                  : 'n.d.'
              }
              sub={summary.period ? `${fmtInt(summary.period.sessions)} séances demandées` : undefined}
            />
            <StatTile
              label="Séances analysées"
              value={fmtInt(summary.evaluated_sessions)}
              sub={
                summary.insufficient_sessions != null
                  ? `${fmtInt(summary.insufficient_sessions)} non évaluable${(summary.insufficient_sessions ?? 0) > 1 ? 's' : ''}`
                  : undefined
              }
            />
            <StatTile
              label="Taux de réussite global"
              value={fmtRate(summary.hit_rate)}
              sub={`Hors prédictions neutres : ${fmtRate(summary.hit_rate_excl_neutral_pred)}`}
              tone={
                summary.hit_rate == null ? undefined : summary.hit_rate >= 0.5 ? 'ok' : 'ko'
              }
            />
            <StatTile
              label="Correctes / incorrectes"
              value={
                <>
                  <span className="pos">{fmtInt(summary.correct)}</span>
                  <span className="muted"> / </span>
                  <span className="neg">{fmtInt(summary.incorrect)}</span>
                </>
              }
            />
            <StatTile
              label="Données complètes"
              value={fmtPct(summary.data_completeness_pct)}
              sub="Part moyenne des facteurs disponibles"
            />
            <StatTile
              label="Dernière date traitée"
              value={fmtDate(summary.last_processed_date)}
            />
          </div>

          <div className="grid-2">
            <Card title="Répartition des prédictions">
              <PredictionsDonut summary={summary} />
            </Card>
            <Card title="Résultats par séance">
              {summary.daily && summary.daily.length > 0 ? (
                <DailyChart daily={summary.daily} />
              ) : (
                <EmptyState message="Aucune séance à afficher" />
              )}
            </Card>
          </div>
        </>
      )}
    </>
  )
}
