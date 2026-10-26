import { useQuery } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Money } from '@/components/Money'
import { api } from '@/lib/api'
import { offerLabel } from '@/lib/takeaways'
import { cn, formatInrCompact, formatInt } from '@/lib/utils'

const isoIst = (d: Date) => new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata' }).format(d)

/**
 * The one orange number, plus the 12-month evidence behind it so the card isn't half empty:
 * supporting stats and extra profit by offer type (same query as the Experiments page).
 */
export function HeroCard({ revenue, className }: { revenue?: number; className?: string }) {
  const [today] = useState(() => new Date())
  const end = isoIst(today)
  const start = isoIst(new Date(today.getTime() - 365 * 86_400_000))
  const { data: e } = useQuery({ queryKey: ['experiments', start, end], queryFn: () => api.experiments(start, end), staleTime: 5 * 60_000 })

  const roi = [...(e?.roi_by_offer_type ?? [])].filter((r) => r.n >= 10).sort((a, b) => b.incremental_profit - a.incremental_profit).slice(0, 5)
  const max = Math.max(1, ...roi.map((r) => Math.abs(r.incremental_profit)))
  const hasNeg = roi.some((r) => r.incremental_profit < 0)

  return (
    <section aria-label="Incremental revenue" className={cn('flex flex-col gap-4 rounded-[8px] border border-line bg-surface p-4', className)}>
      <div className="space-y-2">
        <span className="text-[12px] font-medium text-muted">Incremental revenue vs holdout · last 12 months</span>
        <div className="num title whitespace-nowrap text-[clamp(28px,3.2vw,40px)] leading-none text-signal">
          {revenue !== undefined ? <Money value={revenue} /> : '…'}
        </div>
        <p className="text-[12px] text-muted">Extra sales compared with the 10% holdout that got no offers. This is money offers actually caused.</p>
      </div>

      <dl className="grid grid-cols-1 gap-1.5 border-y border-line py-3 sm:grid-cols-3 sm:gap-3">
        <Stat term="Incremental profit">{e ? <Money value={e.incremental_profit} /> : '…'}</Stat>
        <Stat term="Margin saved on sure-things">{e ? <Money value={e.margin_saved_sure_things} /> : '…'}</Stat>
        <Stat term="Customers measured">
          {e ? <>{formatInt(e.treatment.n)} <span className="text-[11px] text-muted">vs {formatInt(e.control.n)} holdout</span></> : '…'}
        </Stat>
      </dl>

      <div className="mt-auto space-y-1.5">
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-[12px] font-medium text-muted">Extra profit by offer type</span>
          <Link to="/experiments" className="text-[11.5px] text-muted hover:text-ink">Experiments →</Link>
        </div>
        {roi.length ? (
          <ul className="space-y-1" aria-label="Extra profit by offer type, last 12 months">
            {roi.map((r) => {
              const neg = r.incremental_profit < 0
              const w = `${(Math.abs(r.incremental_profit) / max) * (hasNeg ? 50 : 100)}%`
              return (
                <li key={r.type} className="grid grid-cols-[104px_1fr_auto] items-center gap-2 text-[12px]" title={`${offerLabel(r.type)}: ${r.n} offers`}>
                  <span className="truncate text-ink">{offerLabel(r.type)}</span>
                  {/* Diverging around a centre line when any type lost money, so ▼ bars read left of zero. */}
                  <span className="relative h-2.5 rounded-[3px] bg-surface-2">
                    {hasNeg ? <span aria-hidden className="absolute inset-y-[-2px] left-1/2 w-px bg-muted/50" /> : null}
                    <span
                      className={cn('absolute inset-y-0 rounded-[3px]', neg ? 'bg-danger' : 'bg-slate')}
                      style={hasNeg ? (neg ? { right: '50%', width: w } : { left: '50%', width: w }) : { left: 0, width: w }}
                    />
                  </span>
                  <span className={cn('num min-w-[72px] whitespace-nowrap text-right', neg ? 'text-danger-text' : 'text-ink')}>
                    {neg ? '▼ ' : ''}{formatInrCompact(r.incremental_profit)}
                  </span>
                </li>
              )
            })}
          </ul>
        ) : (
          <div className="h-16 animate-pulse rounded-[6px] bg-surface-2" />
        )}
      </div>
    </section>
  )
}

function Stat({ term, children }: { term: string; children: ReactNode }) {
  return (
    // Phones: one "label ……… value" row each; wider: three columns.
    <div className="flex min-w-0 items-baseline justify-between gap-2 sm:block">
      <dt className="truncate text-[11.5px] text-muted" title={term}>{term}</dt>
      <dd className="num truncate text-[15px] text-ink sm:mt-1">{children}</dd>
    </div>
  )
}
