import { Link } from 'react-router-dom'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { PHASE_LABEL } from '@/lib/labels'
import { useFestivals, useMeta } from '@/lib/queries'
import type { Festival, FestivalPhase } from '@/lib/types'
import { daysUntil, formatDate } from '@/lib/utils'

function phaseFor(f: Festival, days: number): FestivalPhase | null {
  for (const [phase, [from, to]] of Object.entries(f.phases) as [FestivalPhase, [number, number]][])
    if (-days >= from && -days <= to) return phase
  return null
}

/** Neutral chip: no regional decoration, only an amber countdown. */
export function UpcomingMoments() {
  const { data: festivals } = useFestivals()
  const { data: meta } = useMeta()
  const now = meta ? new Date(meta.demo_time_override ?? meta.now) : new Date()
  const upcoming = (festivals ?? [])
    .map((f) => ({ f, days: daysUntil(f.date, now) }))
    .filter((x) => x.days >= -10)
    .sort((a, b) => a.days - b.days)
  const next = upcoming.find((x) => x.days >= 0) ?? upcoming[0]
  if (!next) return null
  const phase = phaseFor(next.f, next.days)

  return (
    <Popover>
      <PopoverTrigger className="hidden h-8 items-center gap-2 rounded-[6px] border border-line bg-surface px-2.5 text-[13px] hover:bg-surface-2 lg:inline-flex">
        <span className="text-ink">{next.f.name}</span>
        <span className="num rounded-[4px] bg-amber-soft px-1.5 py-0.5 text-[11.5px] font-medium text-amber-text">
          {next.days === 0 ? 'today' : `in ${next.days}d`}
        </span>
        {phase ? <span className="text-[12px] text-muted">· {PHASE_LABEL[phase]}</span> : null}
      </PopoverTrigger>
      <PopoverContent className="w-80 p-0">
        <p className="border-b border-line px-3 py-2 text-[12px] font-medium text-muted">Upcoming moments</p>
        <ul className="divide-y divide-line">
          {upcoming.slice(0, 5).map(({ f, days }) => {
            const p = phaseFor(f, days)
            return (
              <li key={f.id} className="flex items-center justify-between gap-2 px-3 py-2 text-[13px]">
                <div>
                  <p className="text-ink">{f.name}</p>
                  <p className="num text-[11.5px] text-muted">
                    {formatDate(f.date)}
                    {p ? ` · ${PHASE_LABEL[p]}` : ''}
                  </p>
                </div>
                <span className="num rounded-[4px] bg-amber-soft px-1.5 py-0.5 text-[11.5px] font-medium text-amber-text">
                  {days < 0 ? `${-days}d ago` : days === 0 ? 'today' : `${days}d`}
                </span>
              </li>
            )
          })}
        </ul>
        <Link to="/festivals" className="block border-t border-line px-3 py-2 text-[12.5px] text-ink hover:bg-surface-2">
          Open festival calendar →
        </Link>
      </PopoverContent>
    </Popover>
  )
}
