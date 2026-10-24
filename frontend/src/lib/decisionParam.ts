import { useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'

/** The decision drawer is driven by `?decision=<id>` so any view of it is a shareable link. */
export const DECISION_PARAM = 'decision'

export function useDecisionParam() {
  const [params, setParams] = useSearchParams()
  const open = useCallback(
    (id: string) =>
      setParams((p) => {
        p.set(DECISION_PARAM, id)
        return p
      }),
    [setParams],
  )
  const close = useCallback(
    () =>
      setParams(
        (p) => {
          p.delete(DECISION_PARAM)
          return p
        },
        { replace: true },
      ),
    [setParams],
  )
  return { id: params.get(DECISION_PARAM), open, close }
}
