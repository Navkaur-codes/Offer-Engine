import { useFestivals, useMeta } from './queries'
import type { Festival, FestivalPhase } from './types'
import { daysUntil } from './utils'

/** Upcoming festivals relative to the backend clock (honours demo time-travel). */
export function useUpcoming() {
  const { data: festivals } = useFestivals()
  const { data: meta } = useMeta()
  const now = meta ? new Date(meta.demo_time_override ?? meta.now) : new Date()
  return upcoming(festivals ?? [], now)
}

export function phaseFor(f: Festival, days: number): FestivalPhase | null {
  for (const [phase, [from, to]] of Object.entries(f.phases) as [FestivalPhase, [number, number]][])
    if (-days >= from && -days <= to) return phase
  return null
}

/** Festivals from 10 days ago onwards, soonest first, with their countdown and phase. */
export function upcoming(festivals: Festival[], now: Date) {
  return festivals
    .map((f) => {
      const days = daysUntil(f.date, now)
      return { f, days, phase: phaseFor(f, days) }
    })
    .filter((x) => x.days >= -10)
    .sort((a, b) => a.days - b.days)
}
