import { Fragment } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from '../api'
import type { Bias, StatsResponse } from '../api'
import { useApi } from '../hooks'
import { Card, EmptyState, ErrorBanner, Loading, StatTile } from '../components/ui'
import { BIAS_LABELS, biasLabel, fmtInt, fmtPct, fmtRate } from '../format'

const BIASES: Bias[] = ['bullish', 'bearish', 'neutral']

// ---------------------------------------------------------------

/** Matrice de confusion 3×3, intensité = part de la ligne (ramp séquentiel bleu). */
function ConfusionMatrix({ stats }: { stats: StatsResponse }) {
  const { rows, matrix } = stats.confusion_matrix
  const maxVal = Math.max(1, ...matrix.flat())
  return (
    <div className="table-wrap">
      <div className="confusion">
        <div className="conf-corner">Prédit ↓ / Réel →</div>
        {rows.map((c) => (
          <div key={`col-${c}`} className="conf-label">
            {biasLabel(c as Bias)}
          </div>
        ))}
        {rows.map((r, i) => (
          <Fragment key={`row-${r}`}>
            <div className="conf-row-label">{biasLabel(r as Bias)}</div>
            {rows.map((c, j) => {
              const v = matrix[i]?.[j] ?? 0
              const alpha = 0.08 + 0.72 * (v / maxVal)
              return (
                <div
                  key={`${r}-${c}`}
                  className={`conf-cell${i === j ? ' conf-diag' : ''}`}
                  style={{ background: `rgba(57, 135, 229, ${alpha.toFixed(2)})` }}
                  title={`Prédit ${biasLabel(r as Bias)} / Réel ${biasLabel(c as Bias)} : ${fmtInt(v)}`}
                >
                  {fmtInt(v)}
                </div>
              )
            })}
          </Fragment>
        ))}
      </div>
      <p className="chart-note">
        Lignes : biais prédit · Colonnes : direction réelle. La diagonale (encadrée) compte les
        prédictions correctes.
      </p>
    </div>
  )
}

// ---------------------------------------------------------------

function HitRateByConfidence({ stats }: { stats: StatsResponse }) {
  const data = stats.by_confidence.map((b) => ({
    ...b,
    rate: b.hit_rate == null ? null : b.hit_rate * 100,
  }))
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="var(--grid)" vertical={false} />
        <XAxis
          dataKey="bucket"
          tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
          axisLine={{ stroke: 'var(--baseline)' }}
          tickLine={false}
        />
        <YAxis
          domain={[0, 100]}
          tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          width={40}
          tickFormatter={(v: number) => `${v} %`}
        />
        <ReferenceLine y={50} stroke="var(--baseline)" strokeDasharray="4 4" />
        <Tooltip
          cursor={{ fill: 'rgba(255,255,255,0.04)' }}
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null
            const b = payload[0].payload as { bucket: string; n: number; hit_rate: number | null }
            return (
              <div className="tooltip">
                <div className="t-title">Confiance {b.bucket}</div>
                <div className="t-row">Taux de réussite : {fmtRate(b.hit_rate)}</div>
                <div className="t-row">n = {fmtInt(b.n)}</div>
              </div>
            )
          }}
        />
        <Bar dataKey="rate" fill="var(--series-1)" radius={[4, 4, 0, 0]} maxBarSize={48} />
      </BarChart>
    </ResponsiveContainer>
  )
}

function ChangeHistogram({ stats }: { stats: StatsResponse }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={stats.change_distribution} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="var(--grid)" vertical={false} />
        <XAxis
          dataKey="bin"
          tick={{ fill: 'var(--text-muted)', fontSize: 10 }}
          axisLine={{ stroke: 'var(--baseline)' }}
          tickLine={false}
          interval={0}
          angle={-28}
          textAnchor="end"
          height={58}
        />
        <YAxis
          allowDecimals={false}
          tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          width={32}
        />
        <Tooltip
          cursor={{ fill: 'rgba(255,255,255,0.04)' }}
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null
            const b = payload[0].payload as { bin: string; count: number }
            return (
              <div className="tooltip">
                <div className="t-title">{b.bin}</div>
                <div className="t-row">
                  {fmtInt(b.count)} séance{b.count > 1 ? 's' : ''}
                </div>
              </div>
            )
          }}
        />
        <Bar dataKey="count" fill="var(--series-1)" radius={[4, 4, 0, 0]} maxBarSize={40} />
      </BarChart>
    </ResponsiveContainer>
  )
}

// ---------------------------------------------------------------

export default function Stats() {
  const { data: stats, loading, error, unreachable, reload } = useApi(api.stats)

  return (
    <>
      <h1 className="page-title">Statistiques</h1>
      <p className="page-sub">Performance agrégée du modèle de biais sur la période analysée.</p>

      <ErrorBanner unreachable={unreachable} error={error} onRetry={reload} />

      {loading && <Loading />}

      {!loading && stats == null && !unreachable && !error && (
        <Card>
          <EmptyState
            message="Aucun backtest — lancez une analyse"
            hint="Les statistiques apparaîtront après un premier backtest."
          />
        </Card>
      )}

      {stats && (
        <>
          <div className="disclaimer" role="note">
            <span aria-hidden="true">⚠</span>
            <span>{stats.disclaimer}</span>
          </div>

          <div className="tiles">
            <StatTile
              label="Séances"
              value={fmtInt(stats.n_sessions)}
              sub={`${fmtInt(stats.n_evaluated)} évaluées · ${fmtInt(stats.n_insufficient)} insuffisantes`}
            />
            <StatTile
              label="Taux de réussite (avec neutres)"
              value={fmtRate(stats.hit_rate)}
              sub={`n = ${fmtInt(stats.n_evaluated)}`}
              tone={stats.hit_rate == null ? undefined : stats.hit_rate >= 0.5 ? 'ok' : 'ko'}
            />
            <StatTile
              label="Taux de réussite (hors neutres)"
              value={fmtRate(stats.hit_rate_excl_neutral)}
              sub={`n = ${fmtInt(
                (stats.by_category.bullish?.predicted ?? 0) +
                  (stats.by_category.bearish?.predicted ?? 0),
              )}`}
              tone={
                stats.hit_rate_excl_neutral == null
                  ? undefined
                  : stats.hit_rate_excl_neutral >= 0.5
                    ? 'ok'
                    : 'ko'
              }
            />
          </div>

          <div className="grid-2">
            <Card title="Par catégorie de prédiction">
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Prédiction</th>
                      <th className="num">Prédites</th>
                      <th className="num">Correctes</th>
                      <th className="num">Taux de réussite</th>
                      <th className="num">Variation moy.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {BIASES.map((b) => {
                      const c = stats.by_category[b]
                      if (!c) return null
                      return (
                        <tr key={b}>
                          <td>{BIAS_LABELS[b]}</td>
                          <td className="num">{fmtInt(c.predicted)}</td>
                          <td className="num">{fmtInt(c.correct)}</td>
                          <td className="num">{fmtRate(c.hit_rate)}</td>
                          <td
                            className={`num ${
                              c.avg_change_pct == null
                                ? ''
                                : c.avg_change_pct >= 0
                                  ? 'pos'
                                  : 'neg'
                            }`}
                          >
                            {fmtPct(c.avg_change_pct, true)}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </Card>

            <Card title="Matrice de confusion">
              <ConfusionMatrix stats={stats} />
            </Card>

            <Card title="Taux de réussite par niveau de confiance">
              {stats.by_confidence.length > 0 ? (
                <HitRateByConfidence stats={stats} />
              ) : (
                <EmptyState message="Aucune donnée" />
              )}
              <p className="chart-note">Ligne pointillée : 50 % (hasard).</p>
            </Card>

            <Card title="Distribution des variations journalières">
              {stats.change_distribution.length > 0 ? (
                <ChangeHistogram stats={stats} />
              ) : (
                <EmptyState message="Aucune donnée" />
              )}
            </Card>

            <Card title="Résultats par semaine">
              {stats.by_week.length === 0 ? (
                <EmptyState message="Aucune donnée" />
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Semaine</th>
                        <th className="num">Séances</th>
                        <th className="num">Correctes</th>
                        <th className="num">Taux de réussite</th>
                      </tr>
                    </thead>
                    <tbody>
                      {stats.by_week.map((w) => (
                        <tr key={w.week}>
                          <td>{w.week}</td>
                          <td className="num">{fmtInt(w.n)}</td>
                          <td className="num">{fmtInt(w.correct)}</td>
                          <td className="num">{fmtRate(w.hit_rate)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>

            <Card title="Variation moyenne selon la prédiction">
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Prédiction</th>
                      <th className="num">Variation moyenne observée</th>
                    </tr>
                  </thead>
                  <tbody>
                    {BIASES.map((b) => {
                      const v = stats.avg_change_by_prediction[b]
                      return (
                        <tr key={b}>
                          <td>{BIAS_LABELS[b]}</td>
                          <td className={`num ${v == null ? '' : v >= 0 ? 'pos' : 'neg'}`}>
                            {fmtPct(v, true)}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
              <p className="chart-note">
                Un modèle informatif devrait montrer une variation moyenne positive après une
                prédiction haussière et négative après une prédiction baissière.
              </p>
            </Card>
          </div>

          <Card title="Comparaison aux références simples">
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Stratégie</th>
                    <th className="num">Taux de réussite</th>
                    <th className="num">n</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>
                      <strong>Modèle macro (ce backtest)</strong>
                    </td>
                    <td className="num">
                      <strong>{fmtRate(stats.hit_rate)}</strong>
                    </td>
                    <td className="num">{fmtInt(stats.n_evaluated)}</td>
                  </tr>
                  {stats.baselines.map((b) => (
                    <tr key={b.id}>
                      <td>{b.label}</td>
                      <td className="num">{fmtRate(b.hit_rate)}</td>
                      <td className="num">{fmtInt(b.n)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="chart-note">
              Le modèle n'apporte de valeur que s'il bat durablement ces références naïves.
            </p>
          </Card>
        </>
      )}
    </>
  )
}
