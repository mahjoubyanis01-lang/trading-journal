import { useCallback, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import type { Bias, SessionsFilters } from '../api'
import { useApi } from '../hooks'
import { BiasBadge, Card, CorrectMark, EmptyState, ErrorBanner, Loading } from '../components/ui'
import { BIAS_ORDER, biasLabel, fmtDate, fmtInt, fmtPct, fmtPoints } from '../format'

const EMPTY_FILTERS: SessionsFilters = {
  predicted: '',
  actual: '',
  correct: '',
  exact: '',
  min_confidence: '',
  min_quality: '',
  date_from: '',
  date_to: '',
}

const BIAS_OPTIONS: Array<{ value: Bias | ''; label: string }> = [
  { value: '', label: 'Tous' },
  ...BIAS_ORDER.map((b) => ({ value: b, label: biasLabel(b) })),
]

export default function Sessions() {
  const navigate = useNavigate()
  // Filtres en cours d'édition vs filtres appliqués (envoyés à l'API).
  const [draft, setDraft] = useState<SessionsFilters>(EMPTY_FILTERS)
  const [applied, setApplied] = useState<SessionsFilters>(EMPTY_FILTERS)

  const fetcher = useCallback(() => api.sessions(applied), [applied])
  const { data, loading, error, unreachable, reload } = useApi(fetcher)

  const set = (patch: Partial<SessionsFilters>) => setDraft((d) => ({ ...d, ...patch }))

  const apply = (e: React.FormEvent) => {
    e.preventDefault()
    setApplied(draft)
  }

  const resetFilters = () => {
    setDraft(EMPTY_FILTERS)
    setApplied(EMPTY_FILTERS)
  }

  const sessions = data?.sessions ?? []

  return (
    <>
      <h1 className="page-title">Historique des séances</h1>
      <p className="page-sub">Toutes les séances analysées, filtrables par prédiction et résultat.</p>

      <ErrorBanner unreachable={unreachable} error={error} onRetry={reload} />

      <Card>
        <form className="filters" onSubmit={apply}>
          <div className="field">
            <label htmlFor="f-pred">Biais prédit</label>
            <select
              id="f-pred"
              value={draft.predicted ?? ''}
              onChange={(e) => set({ predicted: e.target.value as Bias | '' })}
            >
              {BIAS_OPTIONS.map((o) => (
                <option key={o.value || 'all'} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="f-actual">Direction réelle</label>
            <select
              id="f-actual"
              value={draft.actual ?? ''}
              onChange={(e) => set({ actual: e.target.value as Bias | '' })}
            >
              {BIAS_OPTIONS.map((o) => (
                <option key={o.value || 'all'} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="f-correct">Direction</label>
            <select
              id="f-correct"
              value={draft.correct ?? ''}
              onChange={(e) => set({ correct: e.target.value as 'true' | 'false' | '' })}
            >
              <option value="">Toutes</option>
              <option value="true">Correcte</option>
              <option value="false">Incorrecte</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="f-exact">Exact (5 niveaux)</label>
            <select
              id="f-exact"
              value={draft.exact ?? ''}
              onChange={(e) => set({ exact: e.target.value as 'true' | 'false' | '' })}
            >
              <option value="">Tous</option>
              <option value="true">Exact</option>
              <option value="false">Inexact</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="f-conf">Confiance min.</label>
            <input
              id="f-conf"
              type="number"
              min={0}
              max={100}
              placeholder="0"
              style={{ width: 90 }}
              value={draft.min_confidence ?? ''}
              onChange={(e) => set({ min_confidence: e.target.value })}
            />
          </div>
          <div className="field">
            <label htmlFor="f-qual">Qualité min.</label>
            <input
              id="f-qual"
              type="number"
              min={0}
              max={100}
              placeholder="0"
              style={{ width: 90 }}
              value={draft.min_quality ?? ''}
              onChange={(e) => set({ min_quality: e.target.value })}
            />
          </div>
          <div className="field">
            <label htmlFor="f-from">Du</label>
            <input
              id="f-from"
              type="date"
              value={draft.date_from ?? ''}
              onChange={(e) => set({ date_from: e.target.value })}
            />
          </div>
          <div className="field">
            <label htmlFor="f-to">Au</label>
            <input
              id="f-to"
              type="date"
              value={draft.date_to ?? ''}
              onChange={(e) => set({ date_to: e.target.value })}
            />
          </div>
          <button type="submit" className="btn btn-primary">
            Filtrer
          </button>
          <button type="button" className="btn btn-ghost" onClick={resetFilters}>
            Réinitialiser
          </button>
        </form>

        {loading && <Loading />}

        {!loading && sessions.length === 0 && (
          <EmptyState
            message="Aucune séance ne correspond"
            hint="Lancez un backtest depuis le tableau de bord, ou élargissez les filtres."
          />
        )}

        {!loading && sessions.length > 0 && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Biais prédit</th>
                  <th className="num">Score</th>
                  <th className="num">Confiance</th>
                  <th>Direction réelle</th>
                  <th className="num">Variation (pts)</th>
                  <th className="num">Variation (%)</th>
                  <th style={{ textAlign: 'center' }}>Direction</th>
                  <th style={{ textAlign: 'center' }}>Exact</th>
                  <th className="num">Qualité données</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((s) => (
                  <tr
                    key={s.date}
                    className="row-link"
                    onClick={() => void navigate(`/sessions/${s.date}`)}
                    title={
                      s.bullish_summary || s.bearish_summary
                        ? `↑ ${s.bullish_summary ?? '—'}\n↓ ${s.bearish_summary ?? '—'}`
                        : undefined
                    }
                  >
                    <td style={{ whiteSpace: 'nowrap' }}>{fmtDate(s.date)}</td>
                    <td>
                      <BiasBadge bias={s.predicted} />
                    </td>
                    <td className="num">{fmtInt(s.score)}</td>
                    <td className="num">{fmtInt(s.confidence)} %</td>
                    <td>
                      <BiasBadge bias={s.actual} />
                    </td>
                    <td className={`num ${(s.change_points ?? 0) >= 0 ? 'pos' : 'neg'}`}>
                      {fmtPoints(s.change_points)}
                    </td>
                    <td className={`num ${(s.change_pct ?? 0) >= 0 ? 'pos' : 'neg'}`}>
                      {fmtPct(s.change_pct, true)}
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      <CorrectMark correct={s.correct} />
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      <CorrectMark correct={s.exact} />
                    </td>
                    <td className="num">
                      {fmtInt(s.data_quality)} %{' '}
                      {s.insufficient && (
                        <span className="muted" title="Données insuffisantes">
                          ⚠
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {!loading && sessions.length > 0 && (
          <p className="chart-note">
            {fmtInt(sessions.length)} séance{sessions.length > 1 ? 's' : ''} — cliquez sur une
            ligne pour ouvrir le détail.
          </p>
        )}
      </Card>
    </>
  )
}
