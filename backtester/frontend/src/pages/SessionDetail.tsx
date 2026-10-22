import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from '../api'
import type { Candle, PreopenMarket, SessionDetail } from '../api'
import { useApi } from '../hooks'
import {
  BiasBadge,
  Card,
  DirectionBadge,
  EmptyState,
  ErrorBanner,
  Loading,
  SentimentBadge,
} from '../components/ui'
import {
  CATEGORY_LABELS,
  ND,
  RELEVANCE_LABELS,
  biasLabel,
  correctLabel,
  correctSymbol,
  fmtDate,
  fmtDateTime,
  fmtInt,
  fmtNum,
  fmtPct,
  fmtPoints,
  fmtTimeTZ,
} from '../format'

// ---------------------------------------------------------------

/** Seuils de classement du score (défauts du contrat si la config est absente). */
export interface ScoreThresholds {
  bullish: number
  strongBullish: number
  bearish: number
  strongBearish: number
}

const DEFAULT_THRESHOLDS: ScoreThresholds = {
  bullish: 25,
  strongBullish: 55,
  bearish: -25,
  strongBearish: -55,
}

const toPos = (v: number) => ((Math.max(-100, Math.min(100, v)) + 100) / 200) * 100

/**
 * Jauge horizontale du score directionnel, de -100 à +100, avec repères aux
 * 4 seuils de classement (±25, ±55 par défaut).
 */
function ScoreGauge({ score, thresholds }: { score: number; thresholds: ScoreThresholds }) {
  const clamped = Math.max(-100, Math.min(100, score))
  const pos = toPos(clamped)
  const fillColor = clamped > 0 ? 'var(--bull)' : clamped < 0 ? 'var(--bear)' : 'var(--neutral)'
  const left = clamped >= 0 ? 50 : pos
  const width = Math.abs(pos - 50)
  const ticks = [
    thresholds.strongBearish,
    thresholds.bearish,
    thresholds.bullish,
    thresholds.strongBullish,
  ]
  return (
    <div className="gauge" aria-label={`Score directionnel : ${fmtInt(clamped)} sur une échelle de −100 à +100`}>
      <div className="gauge-track">
        <div className="gauge-zero" />
        {ticks.map((t) => (
          <div key={t} className="gauge-tick" style={{ left: `${toPos(t)}%` }} />
        ))}
        <div
          className="gauge-fill"
          style={{ left: `${left}%`, width: `${width}%`, background: fillColor }}
        />
        <div className="gauge-marker" style={{ left: `${pos}%` }} />
        {ticks.map((t) => (
          <span key={`l-${t}`} className="gauge-tick-label" style={{ left: `${toPos(t)}%` }}>
            {fmtInt(t)}
          </span>
        ))}
      </div>
      <div className="gauge-labels">
        <span>−100 (baisse)</span>
        <span>0</span>
        <span>+100 (hausse)</span>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------

function IntradayChart({ intraday, openPrice }: { intraday: Candle[]; openPrice: number | null }) {
  if (intraday.length === 0) {
    return <EmptyState message="Pas de données intrajournalières" />
  }
  const data = intraday.map((c) => ({ ...c, time: fmtTimeTZ(c.t, 'America/New_York') }))
  const closes = intraday.map((c) => c.c)
  let min = Math.min(...closes)
  let max = Math.max(...closes)
  if (openPrice != null) {
    min = Math.min(min, openPrice)
    max = Math.max(max, openPrice)
  }
  const pad = Math.max((max - min) * 0.1, 1)
  return (
    <div>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="var(--grid)" vertical={false} />
          <XAxis
            dataKey="time"
            tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
            axisLine={{ stroke: 'var(--baseline)' }}
            tickLine={false}
            minTickGap={40}
          />
          <YAxis
            domain={[Math.floor(min - pad), Math.ceil(max + pad)]}
            tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={62}
            tickFormatter={(v: number) => fmtNum(v)}
          />
          {openPrice != null && (
            <ReferenceLine
              y={openPrice}
              stroke="var(--text-muted)"
              strokeDasharray="4 4"
              label={{
                value: `Ouverture ${fmtNum(openPrice)}`,
                position: 'insideTopRight',
                fill: 'var(--text-muted)',
                fontSize: 11,
              }}
            />
          )}
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null
              const c = payload[0].payload as Candle & { time: string }
              return (
                <div className="tooltip">
                  <div className="t-title">{c.time} (New York)</div>
                  <div className="t-row">Clôture : {fmtNum(c.c)}</div>
                  <div className="t-row">
                    O {fmtNum(c.o)} · H {fmtNum(c.h)} · B {fmtNum(c.l)}
                  </div>
                  {openPrice != null && (
                    <div className="t-row">
                      vs ouverture : {fmtPoints(c.c - openPrice)}
                    </div>
                  )}
                </div>
              )
            }}
          />
          <Line
            type="monotone"
            dataKey="c"
            name="Clôture"
            stroke="var(--series-1)"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
      <p className="chart-note">
        Prix de clôture des bougies intrajournalières (heure de New York). Ligne pointillée :
        prix d'ouverture 09:30 NY.
      </p>
    </div>
  )
}

// ---------------------------------------------------------------

const PREOPEN_FIELDS: Array<{ key: keyof PreopenMarket; label: string; unit: 'pct' | 'num' | 'bp' }> = [
  { key: 'es_move_pct', label: 'ES préouverture', unit: 'pct' },
  { key: 'nq_move_pct', label: 'NQ préouverture', unit: 'pct' },
  { key: 'europe_pct', label: 'Europe', unit: 'pct' },
  { key: 'nikkei_pct', label: 'Nikkei', unit: 'pct' },
  { key: 'vix_prev_close', label: 'VIX (clôture veille)', unit: 'num' },
  { key: 'vix_20d_avg', label: 'VIX (moy. 20 j)', unit: 'num' },
  { key: 'us10y_prev', label: 'US 10 ans (veille)', unit: 'num' },
  { key: 'us10y_change_bp', label: 'US 10 ans (variation)', unit: 'bp' },
  { key: 'us2y_prev', label: 'US 2 ans (veille)', unit: 'num' },
  { key: 'dxy_prev_change_pct', label: 'DXY (variation veille)', unit: 'pct' },
  { key: 'oil_pct', label: 'Pétrole', unit: 'pct' },
  { key: 'gold_pct', label: 'Or', unit: 'pct' },
]

function preopenValue(v: PreopenMarket[keyof PreopenMarket], unit: 'pct' | 'num' | 'bp'): string {
  if (v == null || typeof v === 'string') return typeof v === 'string' ? v : ND
  if (unit === 'pct') return fmtPct(v, true)
  if (unit === 'bp') return `${fmtNum(v)} pb`
  return fmtNum(v)
}

// ---------------------------------------------------------------

function PreOpeningZone({ d, thresholds }: { d: SessionDetail; thresholds: ScoreThresholds }) {
  return (
    <section className="zone zone-pre">
      <div className="zone-head">
        <h2 className="zone-title">A · Analyse avant ouverture</h2>
        <span className="zone-sub">
          Information ≤ 15:29 Paris — date limite : {fmtDateTime(d.cutoff_at)}
        </span>
      </div>

      <div className="bias-hero">
        <div className="hero-metric">
          <span className="lbl">Biais final</span>
          <BiasBadge bias={d.predicted} big />
        </div>
        <div className="hero-metric" style={{ flex: '1 1 260px', minWidth: 240 }}>
          <span className="lbl">Score directionnel : {fmtInt(d.score)}</span>
          <ScoreGauge score={d.score} thresholds={thresholds} />
        </div>
        <div className="hero-metric">
          <span className="lbl">Confiance</span>
          <span className="val">{fmtInt(d.confidence)} %</span>
        </div>
        <div className="hero-metric">
          <span className="lbl">Qualité données</span>
          <span className="val">
            {fmtInt(d.data_quality)} %{d.insufficient ? ' ⚠' : ''}
          </span>
        </div>
      </div>

      {d.macro_summary && (
        <div className="subcard">
          <h3>Résumé macro</h3>
          <p className="prose">{d.macro_summary}</p>
        </div>
      )}

      {d.reasoning && (
        <div className="subcard">
          <h3>Raisonnement</h3>
          <p className="prose">{d.reasoning}</p>
        </div>
      )}

      <div className="subcard">
        <h3>Facteurs</h3>
        {d.factors.length === 0 ? (
          <p className="muted">Aucun facteur.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Facteur</th>
                  <th>Valeur</th>
                  <th className="num">Score / poids</th>
                  <th>Direction</th>
                  <th>Justification</th>
                  <th>Disponible</th>
                </tr>
              </thead>
              <tbody>
                {d.factors.map((f) => (
                  <tr key={f.id}>
                    <td style={{ whiteSpace: 'nowrap' }}>{f.label}</td>
                    <td>{f.value ?? ND}</td>
                    <td className="num">
                      {f.score == null ? ND : fmtNum(f.score)} / {fmtInt(f.max_weight)}
                    </td>
                    <td>
                      <DirectionBadge direction={f.direction} />
                    </td>
                    <td style={{ maxWidth: 420 }}>{f.rationale ?? ND}</td>
                    <td>
                      {f.available ? (
                        <span className="mark mark-ok">✓</span>
                      ) : (
                        <span className="mark mark-na" title="Donnée indisponible">
                          —
                        </span>
                      )}
                      {f.as_of && (
                        <span className="muted" style={{ fontSize: 11, marginLeft: 6 }}>
                          {fmtDateTime(f.as_of)}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="grid-2">
        <div className="subcard">
          <h3>Éléments haussiers</h3>
          {d.bullish_factors.length === 0 ? (
            <p className="muted">Aucun.</p>
          ) : (
            <ul className="list-plain">
              {d.bullish_factors.map((x, i) => (
                <li key={i}>
                  <span className="pos">▲</span> {x}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="subcard">
          <h3>Éléments baissiers</h3>
          {d.bearish_factors.length === 0 ? (
            <p className="muted">Aucun.</p>
          ) : (
            <ul className="list-plain">
              {d.bearish_factors.map((x, i) => (
                <li key={i}>
                  <span className="neg">▼</span> {x}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {d.contradictions.length > 0 && (
        <div className="subcard">
          <h3>Contradictions</h3>
          <ul className="list-plain">
            {d.contradictions.map((x, i) => (
              <li key={i}>{x}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="subcard">
        <h3>Actualités</h3>
        {d.news.length === 0 ? (
          <p className="muted">Aucune actualité retenue.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Titre</th>
                  <th>Source</th>
                  <th>Heure</th>
                  <th>Sentiment</th>
                  <th>Pertinence</th>
                  <th>Catégorie</th>
                </tr>
              </thead>
              <tbody>
                {d.news.map((n, i) => (
                  <tr key={i}>
                    <td style={{ maxWidth: 420 }}>
                      {n.url ? (
                        <a href={n.url} target="_blank" rel="noreferrer">
                          {n.title}
                        </a>
                      ) : (
                        n.title
                      )}
                    </td>
                    <td>{n.source}</td>
                    <td style={{ whiteSpace: 'nowrap' }}>{fmtDateTime(n.published_at)}</td>
                    <td>
                      <SentimentBadge sentiment={n.sentiment} />
                    </td>
                    <td>{RELEVANCE_LABELS[n.relevance] ?? n.relevance}</td>
                    <td>
                      <span className="chip">{CATEGORY_LABELS[n.category] ?? n.category}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="subcard">
        <h3>Publications macro</h3>
        {d.macro_releases.length === 0 ? (
          <p className="muted">Aucune publication macro ce jour.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Série</th>
                  <th>Période</th>
                  <th>Publié à</th>
                  <th className="num">Valeur</th>
                  <th className="num">Précédent</th>
                  <th className="num">Consensus</th>
                  <th className="num">Surprise vs préc.</th>
                  <th>Interprétation</th>
                </tr>
              </thead>
              <tbody>
                {d.macro_releases.map((m, i) => (
                  <tr key={i}>
                    <td style={{ whiteSpace: 'nowrap' }}>
                      <strong>{m.series}</strong>
                      <div className="muted" style={{ fontSize: 11.5 }}>
                        {m.name}
                      </div>
                    </td>
                    <td>{m.period}</td>
                    <td style={{ whiteSpace: 'nowrap' }}>{fmtDateTime(m.released_at)}</td>
                    <td className="num">{fmtNum(m.value)}</td>
                    <td className="num">{fmtNum(m.previous)}</td>
                    <td className="num">
                      {m.consensus_available && m.consensus != null ? fmtNum(m.consensus) : ND}
                    </td>
                    <td className="num">
                      {m.surprise_vs_previous == null ? ND : fmtPct(m.surprise_vs_previous, true)}
                    </td>
                    <td style={{ maxWidth: 320 }}>{m.interpretation ?? ND}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="subcard">
        <h3>Données préouverture</h3>
        {d.preopen_market == null ? (
          <p className="muted">{ND}</p>
        ) : (
          <>
            <div className="kv-grid">
              {PREOPEN_FIELDS.map((f) => (
                <div className="kv" key={f.key}>
                  <span className="k">{f.label}</span>
                  <span className="v">{preopenValue(d.preopen_market![f.key], f.unit)}</span>
                </div>
              ))}
            </div>
            {d.preopen_market.as_of && (
              <p className="chart-note">Relevé au {fmtDateTime(d.preopen_market.as_of)}</p>
            )}
          </>
        )}
      </div>
    </section>
  )
}

// ---------------------------------------------------------------

function ResultZone({ d }: { d: SessionDetail }) {
  const m = d.measurement
  return (
    <section className="zone zone-result">
      <div className="zone-head">
        <h2 className="zone-title">B · Résultat observé</h2>
        <span className="zone-sub">
          Mesure : {fmtDateTime(d.measure_start_at)} → {fmtDateTime(d.measure_end_at)}
        </span>
      </div>

      {m == null ? (
        <EmptyState
          message="Résultat non disponible"
          hint="La séance n'a pas pu être mesurée (données manquantes)."
        />
      ) : (
        <>
          <div className="kv-grid" style={{ marginBottom: 16 }}>
            <div className="kv">
              <span className="k">Prix d'ouverture (09:30 NY)</span>
              <span className="v">{fmtNum(m.open_price)}</span>
            </div>
            <div className="kv">
              <span className="k">Prix à minuit (Paris)</span>
              <span className="v">{fmtNum(m.close_price)}</span>
            </div>
            <div className="kv">
              <span className="k">Variation (points)</span>
              <span className={`v ${(m.change_points ?? 0) >= 0 ? 'pos' : 'neg'}`}>
                {fmtPoints(m.change_points)}
              </span>
            </div>
            <div className="kv">
              <span className="k">Variation (%)</span>
              <span className={`v ${(m.change_pct ?? 0) >= 0 ? 'pos' : 'neg'}`}>
                {fmtPct(m.change_pct, true)}
              </span>
            </div>
            <div className="kv">
              <span className="k">Direction réelle</span>
              <span className="v">
                <BiasBadge bias={m.actual} />
              </span>
            </div>
            <div className="kv">
              <span className="k">Direction (intensité ignorée)</span>
              <span
                className={`v ${m.correct == null ? 'muted' : m.correct ? 'pos' : 'neg'}`}
              >
                {correctSymbol(m.correct)} {correctLabel(m.correct)}
              </span>
            </div>
            <div className="kv">
              <span className="k">Exact (classe parmi les 5)</span>
              <span className={`v ${m.exact == null ? 'muted' : m.exact ? 'pos' : 'neg'}`}>
                {correctSymbol(m.exact)}{' '}
                {m.exact == null ? 'Non évaluable' : m.exact ? 'Exact' : 'Inexact'}
              </span>
            </div>
          </div>

          <IntradayChart intraday={d.intraday} openPrice={m.open_price} />

          {m.contract_note && (
            <p className="chart-note" style={{ marginTop: 12 }}>
              Contrat : {m.contract_note}
            </p>
          )}
        </>
      )}

      {d.limitations.length > 0 && (
        <div className="subcard" style={{ marginTop: 16 }}>
          <h3>Limitations</h3>
          <ul className="list-plain">
            {d.limitations.map((x, i) => (
              <li key={i}>{x}</li>
            ))}
          </ul>
        </div>
      )}

      {d.collection_errors.length > 0 && (
        <div className="subcard">
          <h3>Erreurs de collecte</h3>
          <ul className="list-plain">
            {d.collection_errors.map((e, i) => (
              <li key={i}>
                <strong>{e.source}</strong> — {e.message}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

// ---------------------------------------------------------------

export default function SessionDetailPage() {
  const { date } = useParams<{ date: string }>()
  const fetcher = useCallback(() => api.sessionDetail(date ?? ''), [date])
  const { data, loading, error, unreachable, reload } = useApi(fetcher)

  // Seuils de la jauge depuis la config ; défauts du contrat en cas d'échec.
  const [thresholds, setThresholds] = useState<ScoreThresholds>(DEFAULT_THRESHOLDS)
  useEffect(() => {
    let cancelled = false
    api
      .getConfig()
      .then((c) => {
        if (cancelled) return
        setThresholds({
          bullish: c.bullish_threshold ?? DEFAULT_THRESHOLDS.bullish,
          strongBullish: c.strong_bullish_threshold ?? DEFAULT_THRESHOLDS.strongBullish,
          bearish: c.bearish_threshold ?? DEFAULT_THRESHOLDS.bearish,
          strongBearish: c.strong_bearish_threshold ?? DEFAULT_THRESHOLDS.strongBearish,
        })
      })
      .catch(() => {
        /* backend absent ou ancienne config : on garde les défauts */
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <>
      <p style={{ margin: '0 0 8px' }}>
        <Link to="/sessions" style={{ fontSize: 13 }}>
          ← Retour à l'historique
        </Link>
      </p>
      <h1 className="page-title">Séance du {fmtDate(date)}</h1>
      <p className="page-sub">
        Prédiction : {data ? biasLabel(data.predicted) : '…'} — comparée à la direction réelle du
        S&amp;P 500.
      </p>

      <ErrorBanner unreachable={unreachable} error={error} onRetry={reload} />

      {loading && <Loading />}

      {!loading && !unreachable && !error && data == null && (
        <Card>
          <EmptyState message="Séance introuvable" />
        </Card>
      )}

      {data && (
        <>
          <PreOpeningZone d={data} thresholds={thresholds} />
          <ResultZone d={data} />
        </>
      )}
    </>
  )
}
