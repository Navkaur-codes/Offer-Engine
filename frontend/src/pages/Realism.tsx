import { useQuery } from '@tanstack/react-query'
import { ChartCard, LegendKey } from '@/components/ChartCard'
import { EmptyState } from '@/components/EmptyState'
import { PageHeader } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { NAV } from '@/app/nav'
import { api } from '@/lib/api'
import { useFestivals } from '@/lib/queries'
import type { Benchmark } from '@/lib/types'
import { cn, formatInr } from '@/lib/utils'
import { BandMeter, CategoryBars, CohortHeatmap, FunnelBars, SeasonalityLine } from './realism/Charts'

const pct = (v: number) => `${Math.round(v * 100)}%`
const pct1 = (v: number) => `${(v * 100).toFixed(1)}%`
const BENCH: Record<string, { label: string; format: (v: number) => string; plain: (v: number) => string }> = {
  pareto_top20_share: { label: 'Revenue from top 20% of customers', format: pct, plain: (v) => `the best 20% of customers bring ${pct(v)} of revenue` },
  cart_abandon_rate: { label: 'Cart abandonment', format: pct, plain: (v) => `${pct(v)} of carts are left without buying` },
  view_to_purchase: { label: 'Product views → orders', format: pct1, plain: (v) => `${pct1(v)} of product views end in an order` },
  fashion_return_rate: { label: 'Fashion return rate', format: pct, plain: (v) => `${pct(v)} of fashion orders come back` },
  evening_session_share: { label: 'Evening visits (19:00–24:00)', format: pct, plain: (v) => `${pct(v)} of visits happen in the evening` },
  diwali_week_ratio: { label: 'Diwali week vs normal week', format: (v) => `${v.toFixed(1)}×`, plain: (v) => `Diwali week sells ${v.toFixed(1)}× a normal week` },
}

export function Realism() {
  const q = useQuery({ queryKey: ['realism'], queryFn: api.realism, staleTime: 10 * 60_000 })
  const { data: festivals } = useFestivals()
  const r = q.data
  const bench = Object.entries(r?.benchmarks ?? {})
  const passed = bench.filter(([, b]) => b.ok).length
  const fashion = r?.benchmarks.fashion_return_rate

  return (
    <div className="mx-auto max-w-[1400px] space-y-4 p-4 md:p-6">
      <PageHeader title="Data realism" why={NAV[6].why} />

      {q.isLoading ? (
        <div className="grid gap-3 md:grid-cols-3">{[0, 1, 2, 3, 4, 5].map((i) => <div key={i} className="h-28 animate-pulse rounded-[8px] bg-surface-2" />)}</div>
      ) : !r ? (
        <EmptyState title="Couldn’t load realism stats" hint="The API didn’t answer; the Render service may be waking up." action={<Button onClick={() => q.refetch()}>Try again</Button>} />
      ) : (
        <>
          <p className="text-[13.5px] text-ink">
            <b className={cn('font-semibold', passed === bench.length ? 'text-ink' : 'text-danger-text')}>
              {passed === bench.length ? '✓' : '✗'} {passed} of {bench.length} benchmarks in range.
            </b>{' '}
            <span className="text-muted">All data is synthetic (no real customers); these checks show it behaves like real Indian e-commerce.</span>
          </p>

          <section aria-label="Benchmarks" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {bench.map(([key, b]) => <BenchTile key={key} id={key} b={b} />)}
          </section>

          <div className="grid gap-3 lg:grid-cols-2">
            <ChartCard
              title="Shopping funnel"
              takeaway={r.benchmarks.view_to_purchase ? `${BENCH.view_to_purchase.plain(r.benchmarks.view_to_purchase.value)} (target ${pct1(r.benchmarks.view_to_purchase.min)}–${pct1(r.benchmarks.view_to_purchase.max)}) ${r.benchmarks.view_to_purchase.ok ? '✓' : '✗'}` : null}
            >
              <FunnelBars funnel={r.funnel} />
            </ChartCard>
            <ChartCard
              title="Retention by first-order month"
              takeaway={retentionTakeaway(r.retention_cohorts)}
              footnote="Share of each month’s new customers who bought again N months later. Darker = more still buying."
            >
              <CohortHeatmap rows={r.retention_cohorts} />
            </ChartCard>
            <ChartCard
              className="lg:col-span-2"
              title="Daily revenue through the year"
              takeaway={r.benchmarks.diwali_week_ratio ? `${BENCH.diwali_week_ratio.plain(r.benchmarks.diwali_week_ratio.value)} (target ${r.benchmarks.diwali_week_ratio.min}–${r.benchmarks.diwali_week_ratio.max}×) ${r.benchmarks.diwali_week_ratio.ok ? '✓' : '✗'}` : null}
              legend={<LegendKey items={[['7-day average', 'var(--signal)'], ['Daily', 'var(--slate)']]} />}
              footnote="Grey bands mark festival days from the calendar."
            >
              <SeasonalityLine rows={r.seasonality_daily} festivals={festivals ?? []} />
            </ChartCard>
            <ChartCard title="Average order value by category" takeaway={aovTakeaway(r.aov_by_category)}>
              <CategoryBars values={r.aov_by_category as Record<string, number>} format={formatInr} />
            </ChartCard>
            <ChartCard
              title="Return rate by category"
              takeaway={fashion ? `${BENCH.fashion_return_rate.plain(fashion.value)} (target ${pct(fashion.min)}–${pct(fashion.max)}, shaded) ${fashion.ok ? '✓' : '✗'}` : null}
            >
              <CategoryBars values={r.return_rate_by_category as Record<string, number>} format={pct1} band={fashion ? { cat: 'fashion', min: fashion.min, max: fashion.max } : undefined} />
            </ChartCard>
          </div>
        </>
      )}
    </div>
  )
}

function BenchTile({ id, b }: { id: string; b: Benchmark }) {
  const meta = BENCH[id] ?? { label: id.replaceAll('_', ' '), format: (v: number) => v.toFixed(2), plain: () => '' }
  return (
    <div className={cn('space-y-2 rounded-[8px] border bg-surface p-4', b.ok ? 'border-line' : 'border-danger/50')}>
      <div className="flex items-start justify-between gap-2">
        <span className="text-[12px] font-medium text-muted">{meta.label}</span>
        <span className={cn('text-[12px] font-medium', b.ok ? 'text-ink' : 'text-danger-text')}>{b.ok ? '✓ in range' : '✗ out of range'}</span>
      </div>
      <p className="num title text-[26px] leading-none text-ink">{meta.format(b.value)}</p>
      <BandMeter b={b} format={meta.format} />
      <p className="text-[11px] leading-snug text-muted" title={b.source}>Source: {b.source}</p>
    </div>
  )
}

function retentionTakeaway(rows: { cohort: string; size: number; m1?: unknown; m3?: unknown }[]): string | null {
  const ok = rows.filter((r) => typeof r.m1 === 'number' && typeof r.m3 === 'number' && r.size >= 20)
  if (!ok.length) return null
  const m1 = ok.reduce((s, r) => s + (r.m1 as number) * r.size, 0) / ok.reduce((s, r) => s + r.size, 0)
  const m3 = ok.reduce((s, r) => s + (r.m3 as number) * r.size, 0) / ok.reduce((s, r) => s + r.size, 0)
  return `About ${pct(m1)} of new customers buy again the next month and ${pct(m3)} in month 3: retention decays gradually, as in real stores.`
}

function aovTakeaway(aov: Partial<Record<string, number>>): string | null {
  const e = Object.entries(aov).filter((x): x is [string, number] => typeof x[1] === 'number').sort((a, b) => b[1] - a[1])
  if (e.length < 2) return null
  const [hi, lo] = [e[0], e[e.length - 1]]
  return `${hi[0].replace('_', ' ').replace(/^./, (s) => s.toUpperCase())} orders average ${formatInr(hi[1])}, ${Math.round(hi[1] / lo[1])}× ${lo[0].replace('_', ' ')} (${formatInr(lo[1])}), so one flat discount can’t fit every category.`
}
