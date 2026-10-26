import { useQuery } from '@tanstack/react-query'
import { Play } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Kpi } from '@/components/Kpi'
import { PageHeader } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { NAV } from '@/app/nav'
import { api } from '@/lib/api'
import type { DecisionLight } from '@/lib/types'
import { formatInt, formatPct } from '@/lib/utils'
import { HeroCard } from './overview/HeroCard'
import { LiveStream } from './overview/LiveStream'
import { AutomationsCard, DecidedByShare, DigestCard, Funnel, MarginCallout, MomentsStrip } from './overview/Panels'

/** Count of matching decisions per hour over the last `hours` hours (oldest first). */
function hourly(decisions: DecisionLight[], match: (d: DecisionLight) => boolean, hours = 12): number[] {
  const now = Date.now()
  const buckets = Array<number>(hours).fill(0)
  for (const d of decisions) {
    const h = Math.floor((now - new Date(d.ts).getTime()) / 3_600_000)
    if (h >= 0 && h < hours && match(d)) buckets[hours - 1 - h]++
  }
  return buckets
}

export function Overview() {
  const kpis = useQuery({ queryKey: ['kpis'], queryFn: () => api.kpis(), refetchInterval: 60_000 })
  const recent = useQuery({ queryKey: ['decisions', 'overview'], queryFn: () => api.decisions({ limit: 200 }), refetchInterval: 60_000 })
  const k = kpis.data
  const ds = recent.data?.items ?? []

  return (
    // A column that fills the viewport, so the middle row can take the leftover height on tall screens.
    <div className="mx-auto flex min-h-full max-w-[1400px] flex-col gap-4 p-4 md:p-6">
      <PageHeader
        title="Overview"
        why={NAV[0].why}
        action={
          <Button variant="primary" asChild>
            <Link to="/playground"><Play /> Run a decision</Link>
          </Button>
        }
      />

      <section aria-label="Key numbers" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <HeroCard className="col-span-2 lg:row-span-2" revenue={k?.incremental_revenue} />
        <Kpi className="justify-between" label="Sent today" value={k ? formatInt(k.sent_today) : '…'} delta={k?.deltas.sent_today} spark={hourly(ds, (d) => d.status === 'SENT')} />
        <Kpi className="justify-between" label="Claim rate" value={k ? formatPct(k.claim_rate) : '…'} delta={k?.deltas.claim_rate} />
        <Kpi className="justify-between" label="Budget used" value={k ? formatPct(k.budget_used_pct, 0) : '…'} delta={k?.deltas.budget_used_pct} goodWhen="down" hint="Caps shrink above 80%" />
        <Kpi className="justify-between" label="Blocked by rules" value={k ? formatInt(k.blocked_by_rules) : '…'} delta={k?.deltas.blocked_by_rules} goodWhen="down" hint="Stopped by guardrails" />
      </section>

      <div className="grid gap-3 lg:flex-1 lg:grid-cols-2">
        {/* The stream is absolutely placed so its long list never sets the row height:
            the row is as tall as the right column or the leftover viewport, whichever is larger. */}
        <div className="relative h-[440px] lg:h-auto lg:min-h-[420px]">
          <LiveStream className="h-full lg:absolute lg:inset-0" />
        </div>
        <div className="grid gap-3 sm:grid-cols-2 sm:grid-rows-[auto_auto_1fr]">
          <Funnel className="sm:col-span-2" decisions={ds} />
          <DecidedByShare kpis={k} decisions={ds} />
          <MarginCallout kpis={k} />
          <AutomationsCard className="sm:col-span-2" />
        </div>
      </div>
      <div className="grid gap-3 lg:grid-cols-2">
        <DigestCard />
        <MomentsStrip />
      </div>
    </div>
  )
}
