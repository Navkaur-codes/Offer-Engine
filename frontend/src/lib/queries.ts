import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './api'

export const useMeta = () => useQuery({ queryKey: ['meta'], queryFn: api.meta, staleTime: 5 * 60_000 })
export const useBudget = () => useQuery({ queryKey: ['budget'], queryFn: api.budget, refetchInterval: 60_000 })
export const useFestivals = () => useQuery({ queryKey: ['festivals'], queryFn: api.festivals, staleTime: 10 * 60_000 })
export const useKillswitch = () => useQuery({ queryKey: ['killswitch'], queryFn: api.killswitch, refetchInterval: 30_000 })

export function useSetKillswitch() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.setKillswitch,
    onSuccess: (data) => qc.setQueryData(['killswitch'], data),
  })
}
