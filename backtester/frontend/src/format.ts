// Formatage des nombres et dates en français (fr-FR).
import type { Bias, Sentiment } from './api'

const nf2 = new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const nf2Signed = new Intl.NumberFormat('fr-FR', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
  signDisplay: 'exceptZero',
})
const nfInt = new Intl.NumberFormat('fr-FR')
const nf1 = new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 0, maximumFractionDigits: 1 })

export const ND = 'n.d.'

/** Nombre à 2 décimales, ex: 6 935,25 */
export function fmtNum(v: number | null | undefined): string {
  return v == null ? ND : nf2.format(v)
}

/** Pourcentage à 2 décimales à partir d'une valeur déjà en %, ex: 0.42 -> "+0,42 %" */
export function fmtPct(v: number | null | undefined, signed = false): string {
  if (v == null) return ND
  return `${signed ? nf2Signed.format(v) : nf2.format(v)} %`
}

/** Taux 0..1 -> pourcentage à 2 décimales, ex: 0.52 -> "52,00 %" */
export function fmtRate(v: number | null | undefined): string {
  return v == null ? ND : `${nf2.format(v * 100)} %`
}

/** Points d'indice à 2 décimales, signés, ex: -18.5 -> "-18,50 pts" */
export function fmtPoints(v: number | null | undefined): string {
  return v == null ? ND : `${nf2Signed.format(v)} pts`
}

export function fmtInt(v: number | null | undefined): string {
  return v == null ? ND : nfInt.format(v)
}

export function fmtNum1(v: number | null | undefined): string {
  return v == null ? ND : nf1.format(v)
}

/** Date de séance YYYY-MM-DD -> "mar. 21 oct. 2026" */
export function fmtDate(date: string | null | undefined): string {
  if (!date) return ND
  const d = new Date(`${date}T12:00:00`)
  if (Number.isNaN(d.getTime())) return date
  return new Intl.DateTimeFormat('fr-FR', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(d)
}

/** Date courte YYYY-MM-DD -> "21/10" (axes de graphiques) */
export function fmtDateShort(date: string): string {
  const d = new Date(`${date}T12:00:00`)
  if (Number.isNaN(d.getTime())) return date
  return new Intl.DateTimeFormat('fr-FR', { day: '2-digit', month: '2-digit' }).format(d)
}

/** Horodatage ISO -> date + heure locale, ex: "21/10/2026 15:29" */
export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return ND
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return new Intl.DateTimeFormat('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(d)
}

/** Heure d'un horodatage ISO dans un fuseau donné, ex: "09:30" (New York) */
export function fmtTimeTZ(iso: string, timeZone: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return new Intl.DateTimeFormat('fr-FR', { hour: '2-digit', minute: '2-digit', timeZone }).format(d)
}

// ---------- Libellés français ----------

export const BIAS_LABELS: Record<Bias, string> = {
  bullish: 'Haussier',
  bearish: 'Baissier',
  neutral: 'Neutre',
}

export function biasLabel(b: Bias | null | undefined): string {
  return b ? BIAS_LABELS[b] : ND
}

export const SENTIMENT_LABELS: Record<Sentiment, string> = {
  positive: 'Positif',
  negative: 'Négatif',
  neutral: 'Neutre',
}

export const RELEVANCE_LABELS: Record<string, string> = {
  high: 'Haute',
  medium: 'Moyenne',
  low: 'Faible',
}

export const CATEGORY_LABELS: Record<string, string> = {
  macro: 'Macro',
  fed: 'Fed',
  geopolitics: 'Géopolitique',
  earnings: 'Résultats',
  markets: 'Marchés',
}

export const FACTOR_LABELS: Record<string, string> = {
  es_preopen: 'ES avant ouverture',
  nq_preopen: 'NQ avant ouverture',
  europe: 'Europe',
  asia: 'Asie',
  vix: 'VIX',
  yields: 'Taux (obligations)',
  dxy: 'Dollar (DXY)',
  macro: 'Publications macro',
  news: 'Actualités',
  geopolitics: 'Géopolitique',
  earnings: 'Résultats d’entreprises',
}

/** correct: true/false/null -> ✓ / ✗ / — */
export function correctSymbol(correct: boolean | null | undefined): string {
  if (correct == null) return '—'
  return correct ? '✓' : '✗'
}

export function correctLabel(correct: boolean | null | undefined): string {
  if (correct == null) return 'Non évaluable'
  return correct ? 'Correct' : 'Incorrect'
}
