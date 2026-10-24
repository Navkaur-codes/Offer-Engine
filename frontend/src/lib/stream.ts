import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { api } from './api'
import type { DecisionLight } from './types'

export type StreamMode = 'sse' | 'polling' | 'paused'

/**
 * Live decision feed: SSE from /api/decisions/stream when the real API is up,
 * falling back to polling /api/decisions every 5 s (always the case on mocks).
 */
export function useDecisionStream(limit = 30) {
  const url = api.decisionStreamUrl()
  const [sseFailed, setSseFailed] = useState(!url)
  const [paused, setPaused] = useState(false)
  const [pushed, setPushed] = useState<DecisionLight[]>([])

  const useSse = !sseFailed && !paused
  const base = useQuery({
    queryKey: ['decisions', 'stream', limit],
    queryFn: () => api.decisions({ limit }),
    refetchInterval: !useSse && !paused ? 5000 : false,
  })

  useEffect(() => {
    if (!url || !useSse) return
    const es = new EventSource(url)
    es.onmessage = (e) => {
      try {
        const d = JSON.parse(e.data) as DecisionLight
        setPushed((xs) => [d, ...xs].slice(0, limit))
      } catch {
        /* ignore malformed frames; the next poll or frame catches up */
      }
    }
    es.onerror = () => {
      es.close()
      setSseFailed(true)
    }
    return () => es.close()
  }, [url, useSse, limit])

  const items = useMemo(() => {
    const byId = new Map<string, DecisionLight>()
    for (const d of [...pushed, ...(base.data?.items ?? [])]) if (!byId.has(d.id)) byId.set(d.id, d)
    return [...byId.values()].sort((a, b) => b.ts.localeCompare(a.ts)).slice(0, limit)
  }, [pushed, base.data, limit])

  const mode: StreamMode = paused ? 'paused' : useSse ? 'sse' : 'polling'
  return { items, mode, loading: base.isLoading, paused, setPaused }
}
