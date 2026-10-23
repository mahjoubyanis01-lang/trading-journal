import { useEffect, useState } from 'react'
import { api, BackendUnreachableError, EXPORT_CSV_URL, EXPORT_JSON_URL } from '../api'
import type { AppConfig, NotifyStatus, NotifyTestResult, ProviderStatus, ProviderTestResult } from '../api'
import { useApi } from '../hooks'
import { Card, EmptyState, ErrorBanner, Loading } from '../components/ui'
import { FACTOR_LABELS, fmtDateTime, fmtInt } from '../format'

const LOOKBACK_CHOICES = [10, 30, 60, 90, 252]

function errMessage(e: unknown): string {
  if (e instanceof BackendUnreachableError) return 'Backend injoignable — démarrez le serveur backend.'
  return e instanceof Error ? e.message : String(e)
}

// ---------------------------------------------------------------

function ConfigForm({ initial, onSaved }: { initial: AppConfig; onSaved: (c: AppConfig) => void }) {
  const [cfg, setCfg] = useState<AppConfig>(initial)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  useEffect(() => setCfg(initial), [initial])

  const setField = <K extends keyof AppConfig>(key: K, value: AppConfig[K]) => {
    setSaved(false)
    setCfg((c) => ({ ...c, [key]: value }))
  }

  const setWeight = (id: string, value: number) => {
    setSaved(false)
    setCfg((c) => ({ ...c, factor_weights: { ...c.factor_weights, [id]: value } }))
  }

  const save = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setSaveError(null)
    try {
      const updated = await api.putConfig(cfg)
      setCfg(updated)
      onSaved(updated)
      setSaved(true)
    } catch (err) {
      setSaveError(errMessage(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={(e) => void save(e)}>
      <div className="form-grid" style={{ marginBottom: 18 }}>
        <div className="field">
          <label htmlFor="c-lookback">Séances analysées (lookback)</label>
          <select
            id="c-lookback"
            value={cfg.lookback_sessions}
            onChange={(e) => setField('lookback_sessions', Number(e.target.value))}
          >
            {LOOKBACK_CHOICES.map((n) => (
              <option key={n} value={n}>
                {n} séances
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="c-bull">Seuil hausse modérée (score ≥)</label>
          <input
            id="c-bull"
            type="number"
            value={cfg.bullish_threshold}
            onChange={(e) => setField('bullish_threshold', Number(e.target.value))}
          />
        </div>
        <div className="field">
          <label htmlFor="c-sbull">Seuil hausse affirmée (score ≥)</label>
          <input
            id="c-sbull"
            type="number"
            value={cfg.strong_bullish_threshold}
            onChange={(e) => setField('strong_bullish_threshold', Number(e.target.value))}
          />
        </div>
        <div className="field">
          <label htmlFor="c-bear">Seuil baisse modérée (score ≤)</label>
          <input
            id="c-bear"
            type="number"
            value={cfg.bearish_threshold}
            onChange={(e) => setField('bearish_threshold', Number(e.target.value))}
          />
        </div>
        <div className="field">
          <label htmlFor="c-sbear">Seuil baisse affirmée (score ≤)</label>
          <input
            id="c-sbear"
            type="number"
            value={cfg.strong_bearish_threshold}
            onChange={(e) => setField('strong_bearish_threshold', Number(e.target.value))}
          />
        </div>
        <div className="field">
          <label htmlFor="c-band">Bande neutre (± %)</label>
          <input
            id="c-band"
            type="number"
            step="0.01"
            min="0"
            value={cfg.neutral_band_pct}
            onChange={(e) => setField('neutral_band_pct', Number(e.target.value))}
          />
        </div>
        <div className="field">
          <label htmlFor="c-strongband">Seuil direction affirmée (± %)</label>
          <input
            id="c-strongband"
            type="number"
            step="0.01"
            min="0"
            value={cfg.strong_band_pct}
            onChange={(e) => setField('strong_band_pct', Number(e.target.value))}
          />
        </div>
        <div className="field">
          <label htmlFor="c-es">Fournisseur ES</label>
          <select
            id="c-es"
            value={cfg.es_provider}
            onChange={(e) => setField('es_provider', e.target.value as AppConfig['es_provider'])}
          >
            <option value="yahoo">Yahoo Finance (ES=F continu)</option>
            <option value="databento">Databento (contrat par contrat)</option>
          </select>
        </div>
        <div className="field">
          <label>Heure limite info (Paris)</label>
          <input value={cfg.cutoff_paris} readOnly disabled title="Fixe : définition du backtest" />
        </div>
        <div className="field">
          <label>Début de mesure (New York)</label>
          <input
            value={cfg.measure_start_ny}
            readOnly
            disabled
            title="Fixe : définition du backtest"
          />
        </div>
      </div>

      <h3 style={{ fontSize: 13, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 10 }}>
        Poids des facteurs
      </h3>
      <div className="weights-grid" style={{ marginBottom: 18 }}>
        {Object.entries(cfg.factor_weights).map(([id, w]) => (
          <div className="field" key={id}>
            <label htmlFor={`w-${id}`}>{FACTOR_LABELS[id] ?? id}</label>
            <input
              id={`w-${id}`}
              type="number"
              min={0}
              value={w}
              onChange={(e) => setWeight(id, Number(e.target.value))}
            />
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        <button type="submit" className="btn btn-primary" disabled={saving}>
          {saving ? 'Enregistrement…' : 'Enregistrer la configuration'}
        </button>
        {saved && <span className="save-note">✓ Configuration enregistrée</span>}
        {saveError && <span className="neg" style={{ fontSize: 13 }}>{saveError}</span>}
      </div>
    </form>
  )
}

// ---------------------------------------------------------------

function ProviderRow({ provider, onChanged }: { provider: ProviderStatus; onChanged: () => void }) {
  const [keyInput, setKeyInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [testResult, setTestResult] = useState<ProviderTestResult | null>(provider.last_test)
  const [opError, setOpError] = useState<string | null>(null)

  useEffect(() => setTestResult(provider.last_test), [provider.last_test])

  const saveKey = async () => {
    if (!keyInput.trim()) return
    setBusy(true)
    setOpError(null)
    try {
      await api.setProviderKey(provider.id, keyInput.trim())
      setKeyInput('') // la clé ne reste jamais affichée
      onChanged()
    } catch (e) {
      setOpError(errMessage(e))
    } finally {
      setBusy(false)
    }
  }

  const deleteKey = async () => {
    setBusy(true)
    setOpError(null)
    try {
      await api.deleteProviderKey(provider.id)
      onChanged()
    } catch (e) {
      setOpError(errMessage(e))
    } finally {
      setBusy(false)
    }
  }

  const test = async () => {
    setBusy(true)
    setOpError(null)
    try {
      const r = await api.testProvider(provider.id)
      setTestResult(r)
    } catch (e) {
      setOpError(errMessage(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="provider">
      <div className="provider-head">
        <span
          className={`dot ${provider.configured ? 'dot-ok' : 'dot-off'}`}
          title={provider.configured ? 'Configuré' : 'Non configuré'}
        />
        <span className="provider-label">{provider.label}</span>
        <span className="chips">
          {provider.categories.map((c) => (
            <span key={c} className="chip">
              {c}
            </span>
          ))}
        </span>
      </div>

      <div className="provider-controls">
        {provider.requires_key ? (
          <>
            {provider.key_masked && <span className="key-masked">Clé : {provider.key_masked}</span>}
            <input
              type="password"
              autoComplete="off"
              placeholder={provider.configured ? 'Remplacer la clé API…' : 'Clé API…'}
              value={keyInput}
              onChange={(e) => setKeyInput(e.target.value)}
              style={{ width: 220 }}
            />
            <button
              type="button"
              className="btn"
              onClick={() => void saveKey()}
              disabled={busy || !keyInput.trim()}
            >
              Enregistrer la clé
            </button>
            {provider.configured && (
              <button
                type="button"
                className="btn btn-ghost btn-danger"
                onClick={() => void deleteKey()}
                disabled={busy}
              >
                Supprimer la clé
              </button>
            )}
          </>
        ) : (
          <span className="muted" style={{ fontSize: 13 }}>
            Aucune clé requise
          </span>
        )}
        <button type="button" className="btn" onClick={() => void test()} disabled={busy}>
          {busy ? '…' : 'Tester'}
        </button>
        {testResult && (
          <span className={`test-msg ${testResult.ok ? 'pos' : 'neg'}`}>
            {testResult.ok ? '✓' : '✗'} {testResult.message}
            <span className="muted"> · {fmtDateTime(testResult.at)}</span>
          </span>
        )}
      </div>
      {opError && (
        <p className="neg" style={{ fontSize: 13, margin: '6px 0 0' }}>
          {opError}
        </p>
      )}
    </div>
  )
}

// ---------------------------------------------------------------

/** Notification quotidienne du verdict à l'heure limite (toast Windows +
 *  Telegram optionnel). Le jeton du bot Telegram se saisit dans la liste des
 *  fournisseurs ci-dessous ; le chat_id ici. */
function NotificationsCard({ config, onSaved }: { config: AppConfig; onSaved: () => void }) {
  const [enabled, setEnabled] = useState(config.notifications?.enabled ?? false)
  const [chatId, setChatId] = useState(config.notifications?.telegram_chat_id ?? '')
  const [saving, setSaving] = useState(false)
  const [saveMsg, setSaveMsg] = useState<string | null>(null)
  const [status, setStatus] = useState<NotifyStatus | null>(null)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<NotifyTestResult | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    setEnabled(config.notifications?.enabled ?? false)
    setChatId(config.notifications?.telegram_chat_id ?? '')
  }, [config])

  useEffect(() => {
    api.notifyStatus().then(setStatus).catch(() => setStatus(null))
  }, [config])

  const save = async () => {
    setSaving(true)
    setErr(null)
    setSaveMsg(null)
    try {
      await api.putConfig({ notifications: { enabled, telegram_chat_id: chatId } })
      setSaveMsg('Enregistré.')
      onSaved()
      setStatus(await api.notifyStatus())
    } catch (e) {
      setErr(errMessage(e))
    } finally {
      setSaving(false)
    }
  }

  const test = async () => {
    setTesting(true)
    setErr(null)
    setTestResult(null)
    try {
      setTestResult(await api.notifyTest())
    } catch (e) {
      setErr(errMessage(e))
    } finally {
      setTesting(false)
    }
  }

  return (
    <Card title={`Notification quotidienne (${config.cutoff_paris} Paris)`}>
      <p className="muted">
        À l'heure limite, les jours de semaine, l'application calcule le verdict figé du jour
        (moteur complet) et vous notifie : toast Windows sur le PC, et Telegram si un bot est
        configuré (jeton dans la liste des fournisseurs, chat_id ci-dessous). Le serveur backend
        doit être lancé à cette heure-là.
      </p>
      <div className="form-grid" style={{ marginBottom: 12 }}>
        <div className="field">
          <label htmlFor="n-enabled">Notification automatique</label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input
              id="n-enabled"
              type="checkbox"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
            />
            Activée
          </label>
        </div>
        <div className="field">
          <label htmlFor="n-chat">Telegram chat_id (facultatif)</label>
          <input
            id="n-chat"
            type="text"
            value={chatId}
            placeholder="ex: 123456789"
            onChange={(e) => setChatId(e.target.value)}
          />
        </div>
      </div>
      <div className="row-actions">
        <button className="btn" onClick={() => void save()} disabled={saving}>
          Enregistrer
        </button>
        <button className="btn btn-ghost" onClick={() => void test()} disabled={testing}>
          {testing ? 'Envoi…' : 'Envoyer une notification de test'}
        </button>
        {saveMsg && <span className="pos">{saveMsg}</span>}
      </div>
      {err && <p className="neg">{err}</p>}
      {status && (
        <p className="muted" style={{ marginTop: 10 }}>
          {status.enabled
            ? `Prochain envoi : ${fmtDateTime(status.next_trigger)} (Paris)`
            : 'Notification désactivée.'}
          {status.last_sent_date ? ` · Dernier envoi : ${status.last_sent_date}` : ''}
          {' · Toast Windows : '}
          {status.windows_toast_available ? 'disponible' : 'indisponible sur ce système'}
          {' · Telegram : '}
          {status.telegram_configured ? 'configuré' : 'non configuré'}
        </p>
      )}
      {testResult && (
        <ul style={{ marginTop: 8 }}>
          <li className={testResult.toast.ok ? 'pos' : 'muted'}>
            Toast Windows : {testResult.toast.message}
          </li>
          {testResult.telegram && (
            <li className={testResult.telegram.ok ? 'pos' : 'muted'}>
              Telegram : {testResult.telegram.message}
            </li>
          )}
        </ul>
      )}
    </Card>
  )
}

export default function ConfigPage() {
  const configState = useApi(api.getConfig)
  const providersState = useApi(api.providersStatus)
  const errorsState = useApi(api.errors)

  const unreachable = configState.unreachable || providersState.unreachable
  const error = configState.error ?? providersState.error

  const reloadAll = () => {
    configState.reload()
    providersState.reload()
    errorsState.reload()
  }

  return (
    <>
      <h1 className="page-title">Configuration</h1>
      <p className="page-sub">Paramètres du modèle, fournisseurs de données et exports.</p>

      <ErrorBanner unreachable={unreachable} error={error} onRetry={reloadAll} />

      <Card title="Paramètres du modèle">
        {configState.loading && <Loading />}
        {configState.data && (
          <ConfigForm initial={configState.data} onSaved={() => configState.reload()} />
        )}
      </Card>

      {configState.data && (
        <NotificationsCard config={configState.data} onSaved={() => configState.reload()} />
      )}

      <Card title="Fournisseurs de données">
        {providersState.loading && <Loading />}
        {providersState.data && providersState.data.providers.length === 0 && (
          <EmptyState message="Aucun fournisseur" />
        )}
        {providersState.data?.providers.map((p) => (
          <ProviderRow key={p.id} provider={p} onChanged={() => providersState.reload()} />
        ))}
      </Card>

      <Card title="Erreurs de collecte">
        {errorsState.loading && <Loading />}
        {!errorsState.loading && (errorsState.data?.errors.length ?? 0) === 0 && (
          <p className="muted" style={{ margin: 0, fontSize: 13.5 }}>
            Aucune erreur de collecte enregistrée.
          </p>
        )}
        {(errorsState.data?.errors.length ?? 0) > 0 && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Date de séance</th>
                  <th>Source</th>
                  <th>Message</th>
                  <th>Horodatage</th>
                </tr>
              </thead>
              <tbody>
                {errorsState.data!.errors.map((e, i) => (
                  <tr key={i}>
                    <td>{e.date ?? 'n.d.'}</td>
                    <td>
                      <span className="chip">{e.source}</span>
                    </td>
                    <td>{e.message}</td>
                    <td style={{ whiteSpace: 'nowrap' }}>{fmtDateTime(e.at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {(errorsState.data?.errors.length ?? 0) > 0 && (
          <p className="chart-note">
            {fmtInt(errorsState.data!.errors.length)} erreur
            {errorsState.data!.errors.length > 1 ? 's' : ''} au total.
          </p>
        )}
      </Card>

      <Card title="Exports">
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <a className="btn" href={EXPORT_CSV_URL} download>
            ⬇ Exporter en CSV
          </a>
          <a className="btn" href={EXPORT_JSON_URL} download>
            ⬇ Exporter en JSON (analyses complètes)
          </a>
        </div>
        <p className="chart-note">
          CSV : une ligne par séance. JSON : analyses détaillées complètes.
        </p>
      </Card>
    </>
  )
}
