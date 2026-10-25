import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ChartCard, LegendKey } from '@/components/ChartCard'
import { EmptyState } from '@/components/EmptyState'
import { Kpi } from '@/components/Kpi'
import { Money } from '@/components/Money'
import { PageHeader } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { NAV } from '@/app/nav'
import { api } from '@/lib/api'
import { festivalTakeaway, policyTakeaway, qiniTakeaway, roiTakeaway, treatmentTakeaway } from '@/lib/takeaways'
import { cn } from '@/lib/utils'
import { ArmsBars, FestivalLiftChart, PolicyUpliftChart, QiniChart, RoiChart } from './experiments/Charts'

const RANGES = [
  { id: '30d', label: '30 days', days: 30 },
  { id: '90d', label: '90 days', days: 90 },
  { id: '12m', label: '12 months', days: 365 },
] as const

const isoIst = (d: Date) => new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata' }).format(d)

export function Experiments() {
  const [params, setParams] = useSearchParams()
  const range = RANGES.find((r) => r.id === params.get('range')) ?? RANGES[2]
  const [today] = useState(() => new Date())
  const end = isoIst(today)
  const start = isoIst(new Date(today.getTime() - range.days * 86_400_000))
  const q = useQuery({ queryKey: ['experiments', start, end], queryFn: () => api.experiments(start, end), staleTime: 5 * 60_000 })
  const e = q.data

  return (
    <div className="mx-auto max-w-[1400px] space-y-4 p-4 md:p-6">
      <PageHeader
        title="Experiments"
        why={NAV[4].why}
        action={
          <div role="radiogroup" aria-label="Period" className="flex rounded-[6px] border border-line bg-surface p-0.5">
            {RANGES.map((r) => (
              <button
                key={r.id}
                role="radio"
                aria-checked={r.id === range.id}
                onClick={() => setParams({ range: r.id }, { replace: true })}
                className={cn('h-7 rounded-[5px] px-2.5 text-[12.5px]', r.id === range.id ? 'bg-ink text-bg' : 'text-muted hover:text-ink')}
              >
                {r.label}
              </button>
            ))}
          </div>
        }
      />

      {q.isLoading ? (
        <div className="grid gap-3 lg:grid-cols-2">{[0, 1, 2, 3].map((i) => <div key={i} className="h-64 animate-pulse rounded-[8px] bg-surface-2" />)}</div>
      ) : !e ? (
        <EmptyState title="Couldn’t load experiment results" hint="The analytics endpoint didn’t answer. The Render service may be waking up." action={<Button onClick={() => q.refetch()}>Try again</Button>} />
      ) : !e.treatment.n ? (
        <EmptyState
          title="No offers in this period yet"
          hint="Results need customers who got offers and a holdout that didn’t. Try a longer period."
          action={<Button onClick={() => setParams({ range: '12m' })}>Show 12 months</Button>}
        />
      ) : (
        <>
          <section aria-label="Incrementality" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Kpi hero label="Incremental revenue" value={<Money value={e.incremental_revenue} />} hint="Caused by offers, vs the holdout" />
            <Kpi label="Incremental profit" value={<Money value={e.incremental_profit} />} hint="After offer costs" />
            <Kpi label="Margin saved on sure-things" value={<Money value={e.margin_saved_sure_things} />} hint="Not discounted: they’d buy anyway" />
            <Kpi
              label="Uplift in buying rate"
              value={`${e.treatment.conv_rate >= e.control.conv_rate ? '+' : '−'}${(Math.abs(e.treatment.conv_rate - e.control.conv_rate) * 100).toFixed(1)} pts`}
              hint={`${(e.treatment.conv_rate * 100).toFixed(1)}% with offers vs ${(e.control.conv_rate * 100).toFixed(1)}% holdout`}
            />
          </section>

          <div className="grid gap-3 lg:grid-cols-2">
            <ChartCard
              title="Offers vs holdout"
              takeaway={treatmentTakeaway(e.treatment, e.control)}
              legend={<LegendKey items={[['Got offers', 'var(--signal)'], ['Holdout', 'var(--slate)']]} />}
              footnote="The holdout is a random 10% of synthetic customers who never get proactive offers."
            >
              <ArmsBars t={e.treatment} c={e.control} />
            </ChartCard>
            <ChartCard title="Uplift by policy" takeaway={policyTakeaway(e.uplift_by_policy)} footnote="Uplift = buying rate with offers minus the holdout’s, in percentage points. ▼ = offers didn’t help.">
              {e.uplift_by_policy.length ? <PolicyUpliftChart rows={e.uplift_by_policy} /> : <Thin />}
            </ChartCard>
            <ChartCard title="Extra profit by offer type" takeaway={roiTakeaway(e.roi_by_offer_type)} footnote="Hover a bar for cost, extra revenue and number of offers.">
              {e.roi_by_offer_type.length ? <RoiChart rows={e.roi_by_offer_type} /> : <Thin />}
            </ChartCard>
            <ChartCard
              title="Qini curve: is the uplift model better than random?"
              takeaway={qiniTakeaway(e.qini)}
              legend={<LegendKey items={[['By uplift model', 'var(--signal)'], ['Random', 'var(--slate)']]} />}
              footnote="The further the orange line sits above the dashed one, the better the model picks who to target."
            >
              {e.qini?.length ? <QiniChart points={e.qini} /> : <Thin />}
            </ChartCard>
            <ChartCard
              className="lg:col-span-2"
              title="Festival vs a normal day"
              takeaway={festivalTakeaway(e.festival_vs_baseline)}
              footnote="Revenue per day during each festival window divided by the baseline day."
            >
              {e.festival_vs_baseline.some((f) => f.revenue_per_day > 0) ? <FestivalLiftChart rows={e.festival_vs_baseline} /> : <Thin />}
            </ChartCard>
          </div>
        </>
      )}
    </div>
  )
}

function Thin() {
  return <p className="dot-grid rounded-[6px] border border-dashed border-line px-4 py-10 text-center text-[12.5px] text-muted">Not enough data in this period. Try 12 months.</p>
}
