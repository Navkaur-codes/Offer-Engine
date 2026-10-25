import { PHASE_LABEL } from '@/lib/labels'
import type { Festival, FestivalPhase } from '@/lib/types'
import { cn, formatDate } from '@/lib/utils'

const DAY = 86_400_000
const PHASES: FestivalPhase[] = ['teaser', 'build_up', 'last_minute', 'post']
// Neutral steps (no festive colours): the closer to the day, the darker. Post is an outline.
const PHASE_CLASS: Record<FestivalPhase, string> = {
  teaser: 'bg-slate/25',
  build_up: 'bg-slate/55',
  last_minute: 'bg-ink',
  post: 'border border-slate/60 bg-transparent',
}

/** One row per festival over the next `days` days; bars are its phases, the orange line is today. */
export function CalendarStrip({
  festivals, today, days = 90, selected, onSelect,
}: { festivals: Festival[]; today: Date; days?: number; selected?: string; onSelect: (id: string) => void }) {
  const start = new Date(today.getTime() - 7 * DAY)
  const span = (days + 7) * DAY
  const pos = (t: number) => Math.min(100, Math.max(0, ((t - start.getTime()) / span) * 100))
  const rows = festivals
    .map((f) => {
      const d = new Date(`${f.date}T00:00:00+05:30`).getTime()
      const offs = Object.values(f.phases).flat() as number[]
      return { f, d, from: d + Math.min(...offs) * DAY, to: d + (Math.max(...offs) + 1) * DAY }
    })
    .filter((r) => r.to >= start.getTime() && r.from <= start.getTime() + span)
    .sort((a, b) => a.d - b.d)

  const ticks = Array.from({ length: Math.floor(days / 14) + 1 }, (_, i) => new Date(start.getTime() + (7 + i * 14) * DAY))

  return (
    <div className="space-y-2">
      <div className="relative ml-[132px] h-4 text-[10.5px] text-muted">
        {ticks.map((t) => (
          <span key={t.getTime()} className="num absolute -translate-x-1/2" style={{ left: `${pos(t.getTime())}%` }}>{formatDate(t.toISOString())}</span>
        ))}
      </div>
      <ul className="relative space-y-1">
        <span aria-hidden className="pointer-events-none absolute inset-y-0 left-[132px] right-0">
          <span className="absolute inset-y-0 w-px bg-signal" style={{ left: `${pos(today.getTime())}%` }} />
        </span>
        {rows.map(({ f, d }) => (
          <li key={f.id}>
            <button
              onClick={() => onSelect(f.id)}
              aria-pressed={selected === f.id}
              aria-label={`${f.name}, ${formatDate(f.date)}`}
              className={cn('grid w-full grid-cols-[124px_1fr] items-center gap-2 rounded-[5px] py-0.5 pr-1 text-left hover:bg-surface-2', selected === f.id && 'bg-bg shadow-[inset_2px_0_0_var(--ink)]')}
            >
              <span className={cn('truncate pl-1 text-[12.5px]', selected === f.id ? 'text-ink' : 'text-muted')}>{f.name.split(/[/(]/)[0].trim()}</span>
              <span className="relative h-4">
                {PHASES.filter((p) => f.phases[p]).map((p) => {
                  const [a, b] = f.phases[p]!
                  const l = pos(d + a * DAY)
                  const r = pos(d + (b + 1) * DAY)
                  return (
                    <span
                      key={p}
                      title={`${f.name} · ${PHASE_LABEL[p]}`}
                      className={cn('absolute top-0.5 h-3 rounded-[3px]', PHASE_CLASS[p])}
                      style={{ left: `${l}%`, width: `${Math.max(0.4, r - l)}%` }}
                    />
                  )
                })}
                <span aria-hidden className="absolute top-0 h-4 w-[2px] rounded-full bg-ink" style={{ left: `${pos(d)}%` }} />
              </span>
            </button>
          </li>
        ))}
      </ul>
      <ul className="ml-[132px] flex flex-wrap gap-3 pt-1 text-[11.5px] text-muted" aria-label="Phase key">
        {PHASES.map((p) => (
          <li key={p} className="flex items-center gap-1.5"><span aria-hidden className={cn('h-2.5 w-4 rounded-[2px]', PHASE_CLASS[p])} />{PHASE_LABEL[p]}</li>
        ))}
        <li className="flex items-center gap-1.5"><span aria-hidden className="h-3 w-px bg-signal" />today</li>
      </ul>
    </div>
  )
}
