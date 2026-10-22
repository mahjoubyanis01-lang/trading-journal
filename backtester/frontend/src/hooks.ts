import { useCallback, useEffect, useState } from 'react'
import { BackendUnreachableError } from './api'

export interface ApiState<T> {
  data: T | null
  loading: boolean
  /** Message d'erreur HTTP (hors backend injoignable) */
  error: string | null
  /** Le backend n'a pas répondu du tout */
  unreachable: boolean
  reload: () => void
}

/**
 * Charge une ressource API et expose data / loading / error / unreachable.
 * `fetcher` doit être stable (useCallback) ou défini hors composant.
 */
export function useApi<T>(fetcher: () => Promise<T>): ApiState<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [unreachable, setUnreachable] = useState(false)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetcher()
      .then((d) => {
        if (cancelled) return
        setData(d)
        setError(null)
        setUnreachable(false)
      })
      .catch((e: unknown) => {
        if (cancelled) return
        if (e instanceof BackendUnreachableError) {
          setUnreachable(true)
          setError(null)
        } else {
          setUnreachable(false)
          setError(e instanceof Error ? e.message : String(e))
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [fetcher, tick])

  const reload = useCallback(() => setTick((t) => t + 1), [])

  return { data, loading, error, unreachable, reload }
}
