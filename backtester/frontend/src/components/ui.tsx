import type { ReactNode } from 'react'
import type { Bias, Sentiment } from '../api'
import { biasLabel, SENTIMENT_LABELS } from '../format'

/** Bandeau "backend injoignable" / erreur HTTP. */
export function ErrorBanner({
  unreachable,
  error,
  onRetry,
}: {
  unreachable: boolean
  error: string | null
  onRetry?: () => void
}) {
  if (!unreachable && !error) return null
  return (
    <div className={`banner ${unreachable ? 'banner-offline' : 'banner-error'}`} role="alert">
      <span className="banner-icon" aria-hidden="true">{unreachable ? '⏻' : '⚠'}</span>
      <span>
        {unreachable
          ? 'Backend injoignable — démarrez le serveur backend (http://127.0.0.1:8000).'
          : `Erreur du backend : ${error}`}
      </span>
      {onRetry && (
        <button type="button" className="btn btn-ghost" onClick={onRetry}>
          Réessayer
        </button>
      )}
    </div>
  )
}

/** Badge coloré de biais : vert haussier, rouge baissier, gris neutre. */
export function BiasBadge({ bias, big = false }: { bias: Bias | null | undefined; big?: boolean }) {
  if (!bias) return <span className="muted">n.d.</span>
  const arrow = bias === 'bullish' ? '▲' : bias === 'bearish' ? '▼' : '◆'
  return (
    <span className={`badge badge-${bias}${big ? ' badge-big' : ''}`}>
      <span aria-hidden="true">{arrow}</span> {biasLabel(bias)}
    </span>
  )
}

/** Badge de sentiment d'actualité. */
export function SentimentBadge({ sentiment }: { sentiment: Sentiment }) {
  const cls = sentiment === 'positive' ? 'bullish' : sentiment === 'negative' ? 'bearish' : 'neutral'
  const icon = sentiment === 'positive' ? '+' : sentiment === 'negative' ? '−' : '='
  return (
    <span className={`badge badge-${cls}`}>
      <span aria-hidden="true">{icon}</span> {SENTIMENT_LABELS[sentiment]}
    </span>
  )
}

/** ✓ / ✗ / — coloré. */
export function CorrectMark({ correct }: { correct: boolean | null | undefined }) {
  if (correct == null) {
    return (
      <span className="mark mark-na" title="Non évaluable">
        —
      </span>
    )
  }
  return correct ? (
    <span className="mark mark-ok" title="Correct">✓</span>
  ) : (
    <span className="mark mark-ko" title="Incorrect">✗</span>
  )
}

/** Tuile statistique. */
export function StatTile({
  label,
  value,
  sub,
  tone,
}: {
  label: string
  value: ReactNode
  sub?: ReactNode
  tone?: 'ok' | 'ko' | 'neutral'
}) {
  return (
    <div className="tile">
      <div className="tile-label">{label}</div>
      <div className={`tile-value${tone ? ` tile-${tone}` : ''}`}>{value}</div>
      {sub != null && <div className="tile-sub">{sub}</div>}
    </div>
  )
}

/** Carte avec titre de section. */
export function Card({
  title,
  children,
  actions,
  className,
}: {
  title?: ReactNode
  children: ReactNode
  actions?: ReactNode
  className?: string
}) {
  return (
    <section className={`card${className ? ` ${className}` : ''}`}>
      {(title != null || actions != null) && (
        <div className="card-head">
          {title != null && <h2 className="card-title">{title}</h2>}
          {actions != null && <div className="card-actions">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  )
}

/** État vide. */
export function EmptyState({ message, hint }: { message: string; hint?: string }) {
  return (
    <div className="empty">
      <div className="empty-msg">{message}</div>
      {hint && <div className="empty-hint">{hint}</div>}
    </div>
  )
}

/** Indicateur de chargement. */
export function Loading() {
  return <div className="loading">Chargement…</div>
}
