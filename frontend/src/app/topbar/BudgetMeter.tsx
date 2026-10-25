import { Money } from '@/components/Money'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { PHASE_LABEL } from '@/lib/labels'
import { useBudget, useHealth } from '@/lib/queries'
import { festivalLabel } from '@/lib/festivals'
import { cn, formatInt } from '@/lib/utils'

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
      <div className="flex items-center">
      <PopoverTrigger className="flex h-8 w-36 flex-col justify-center gap-1 rounded-[6px] px-2 hover:bg-surface-2" aria-label="Budget used today">
        <span className="flex w-full items-baseline justify-between text-[11.5px]">
          <span className="text-muted">Budget</span>
          <span className="num text-ink">
            {Math.round(pct * 100)}%{pct >= 0.8 ? <span className="text-amber-text"> ⚠</span> : null}
          </span>
        </span>
        <Bar used={data.today_used} cap={data.today_cap} label="Today's budget" />
      </PopoverTrigger>
      <AiModeChip />
      </div>
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
        {f ? (
          <div className="flex justify-between gap-2 border-t border-line pt-2 text-[13px]">
            <span>
              {festivalLabel(f.name)} pool
              {f.phase ? <span className="text-muted"> · {PHASE_LABEL[f.phase]}</span> : null}
            </span>
            <span>
              {f.budget_left !== null ? <Money value={f.budget_left} /> : '—'} <span className="text-muted">left</span>
            </span>
          </div>
        ) : null}
        <p className="text-[12px] text-muted">Above 80% the engine shrinks discount caps automatically (pacing).</p>
        <AiBudget />
      </PopoverContent>
    </Popover>
  )
}

// agent/budget.py degrades 120b → 20b at 80% → rules at 100% of the daily token budget.
const MODE: Record<'70b' | '8b' | 'rules', [string, string]> = {
  '70b': ['Full AI model', 'The main model decides, inside the rules.'],
  '8b': ['Fast AI model', 'Over 80% of today’s token budget: a smaller model decides.'],
  rules: ['Rules only', 'Today’s AI budget is used up: the rules fallback decides every offer.'],
}

/** Shown only when the AI is degraded, so the normal state stays quiet. */
function AiModeChip() {
  const { data } = useHealth()
  const mode = data?.llm_budget?.mode
  if (!mode || mode === '70b') return null
  return (
    <span className="num ml-1 rounded-[4px] bg-amber-soft px-1.5 py-0.5 text-[11px] font-medium text-amber-text" title={MODE[mode][1]}>
      ⚠ AI: {mode === 'rules' ? 'rules only' : 'fast model'}
    </span>
  )
}

function AiBudget() {
  const { data } = useHealth()
  const b = data?.llm_budget
  if (!b) return null
  return (
    <div className="space-y-2 border-t border-line pt-2">
      <div className="flex items-baseline justify-between text-[13px]">
        <span>AI budget today</span>
        <span className={cn('text-[12px]', b.mode === '70b' ? 'text-muted' : 'text-amber-text')}>
          {b.mode === '70b' ? '' : '⚠ '}{MODE[b.mode][0]}
        </span>
      </div>
      {(['agent', 'fast'] as const).map((k) => (
        <div key={k} className="space-y-1">
          <div className="flex justify-between text-[12px] text-muted">
            <span className="num">{b[k].model.replace(/^openai\//, '')}</span>
            <span className="num">{formatInt(b[k].used)} / {formatInt(b[k].limit)} tokens</span>
          </div>
          <Bar used={b[k].used} cap={b[k].limit} label={`${k} model tokens used today`} />
        </div>
      ))}
      <p className="text-[12px] text-muted">{MODE[b.mode][1]}</p>
    </div>
  )
}
