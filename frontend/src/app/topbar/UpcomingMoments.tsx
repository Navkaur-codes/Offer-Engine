import { Link } from 'react-router-dom'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { useUpcoming } from '@/lib/festivals'
import { PHASE_LABEL } from '@/lib/labels'
import { formatDate } from '@/lib/utils'

export function Countdown({ days }: { days: number }) {
  return (
    <span className="num rounded-[4px] bg-amber-soft px-1.5 py-0.5 text-[11.5px] font-medium text-amber-text">
      {days < 0 ? `${-days}d ago` : days === 0 ? 'today' : `in ${days}d`}
    </span>
  )
}

/** Neutral chip: no regional decoration, only an amber countdown. */
export function UpcomingMoments() {
  const list = useUpcoming()
  const next = list.find((x) => x.days >= 0) ?? list[0]
  if (!next) return null

  return (
    <Popover>
      <PopoverTrigger className="hidden h-8 items-center gap-2 rounded-[6px] border border-line bg-surface px-2.5 text-[13px] hover:bg-surface-2 lg:inline-flex">
        <span className="text-ink">{next.f.name}</span>
        <Countdown days={next.days} />
        {next.phase ? <span className="text-[12px] text-muted">· {PHASE_LABEL[next.phase]}</span> : null}
      </PopoverTrigger>
      <PopoverContent className="w-80 p-0">
        <p className="border-b border-line px-3 py-2 text-[12px] font-medium text-muted">Upcoming moments</p>
        <ul className="divide-y divide-line">
          {list.slice(0, 5).map(({ f, days, phase }) => (
            <li key={f.id} className="flex items-center justify-between gap-2 px-3 py-2 text-[13px]">
              <div>
                <p className="text-ink">{f.name}</p>
                <p className="num text-[11.5px] text-muted">
                  {formatDate(f.date)}
                  {phase ? ` · ${PHASE_LABEL[phase]}` : ''}
                </p>
              </div>
              <Countdown days={days} />
            </li>
          ))}
        </ul>
        <Link to="/festivals" className="block border-t border-line px-3 py-2 text-[12.5px] text-ink hover:bg-surface-2">
          Open festival calendar →
        </Link>
      </PopoverContent>
    </Popover>
  )
}
