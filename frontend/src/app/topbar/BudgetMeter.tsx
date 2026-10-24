import { Money } from '@/components/Money'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { useBudget } from '@/lib/queries'
import { cn } from '@/lib/utils'

function Bar({ used, cap, label }: { used: number; cap: number; label: string }) {
  const pct = cap ? Math.min(1, used / cap) : 0
  const pacing = pct >= 0.8
  return (
    <div
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={cap}
      aria-valuenow={used}
      className="h-1.5 w-full overflow-hidden rounded-full bg-surface-2"
    >
      <div className={cn('h-full rounded-full', pacing ? 'bg-amber' : 'bg-ink')} style={{ width: `${pct * 100}%` }} />
    </div>
  )
}

export function BudgetMeter() {
  const { data } = useBudget()
  if (!data) return <div className="h-8 w-32 animate-pulse rounded-[6px] bg-surface-2" />
  const pct = data.today_cap ? data.today_used / data.today_cap : 0
  const f = data.festival
  return (
    <Popover>
      <PopoverTrigger className="flex h-8 w-36 flex-col justify-center gap-1 rounded-[6px] px-2 hover:bg-surface-2" aria-label="Budget used today">
        <span className="flex w-full items-baseline justify-between text-[11.5px]">
          <span className="text-muted">Budget</span>
          <span className="num text-ink">
            {Math.round(pct * 100)}%{pct >= 0.8 ? <span className="text-amber-text"> ⚠</span> : null}
          </span>
        </span>
        <Bar used={data.today_used} cap={data.today_cap} label="Today's budget" />
      </PopoverTrigger>
      <PopoverContent className="space-y-3">
        <div className="space-y-1.5">
          <div className="flex justify-between text-[13px]">
            <span>Today</span>
            <span>
              <Money value={data.today_used} /> <span className="text-muted">/ <Money value={data.today_cap} /></span>
            </span>
          </div>
          <Bar used={data.today_used} cap={data.today_cap} label="Today's budget" />
        </div>
        {f?.cap ? (
          <div className="space-y-1.5">
            <div className="flex justify-between text-[13px]">
              <span>{f.name ?? 'Festival'} pool</span>
              <span>
                <Money value={f.used ?? 0} /> <span className="text-muted">/ <Money value={f.cap} /></span>
              </span>
            </div>
            <Bar used={f.used ?? 0} cap={f.cap} label="Festival budget pool" />
          </div>
        ) : null}
        <p className="text-[12px] text-muted">Above 80% the engine shrinks discount caps automatically (pacing).</p>
      </PopoverContent>
    </Popover>
  )
}
