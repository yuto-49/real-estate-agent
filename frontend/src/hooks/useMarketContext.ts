import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../utils/api'
import type { MarketContextSnapshot } from '../utils/types'

const CACHE_TTL_MS = 5 * 60 * 1000

interface CacheEntry {
  data: MarketContextSnapshot
  fetchedAt: number
}

const cache = new Map<string, CacheEntry>()

interface UseMarketContextResult {
  data: MarketContextSnapshot | null
  loading: boolean
  error: string | null
  refresh: () => void
}

export function useMarketContext(propertyId: string | null | undefined): UseMarketContextResult {
  const [data, setData] = useState<MarketContextSnapshot | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const fetchData = useCallback(
    async (skipCache = false) => {
      if (!propertyId) {
        setData(null)
        return
      }

      if (!skipCache) {
        const cached = cache.get(propertyId)
        if (cached && Date.now() - cached.fetchedAt < CACHE_TTL_MS) {
          setData(cached.data)
          return
        }
      }

      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      setLoading(true)
      setError(null)

      try {
        const result = await api.properties.marketContext(propertyId)
        if (!controller.signal.aborted) {
          cache.set(propertyId, { data: result, fetchedAt: Date.now() })
          setData(result)
        }
      } catch (err) {
        if (!controller.signal.aborted) {
          setError(err instanceof Error ? err.message : 'Failed to load market context')
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false)
        }
      }
    },
    [propertyId],
  )

  useEffect(() => {
    void fetchData()
    return () => {
      abortRef.current?.abort()
    }
  }, [fetchData])

  const refresh = useCallback(() => {
    void fetchData(true)
  }, [fetchData])

  return { data, loading, error, refresh }
}
