import { useQuery } from '@tanstack/react-query'
import { Play } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Kpi } from '@/components/Kpi'
import { Money } from '@/components/Money'
import { PageHeader } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { NAV } from '@/app/nav'
import { api } from '@/lib/api'
import type { DecisionLight } from '@/lib/types'
import { formatInt, formatPct } from '@/lib/utils'
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
    <div className="mx-auto max-w-[1400px] space-y-4 p-4 md:p-6">
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
        <Kpi
          hero
          className="col-span-2 lg:row-span-2"
          label="Incremental revenue vs holdout"
          value={k ? <Money value={k.incremental_revenue} /> : '…'}
          delta={k?.deltas.incremental_revenue}
          spark={hourly(ds, (d) => d.outcome === 'redeemed')}
          hint="Extra sales compared with the 10% holdout that got no offers. This is money offers actually caused."
        />
        <Kpi label="Sent today" value={k ? formatInt(k.sent_today) : '…'} delta={k?.deltas.sent_today} spark={hourly(ds, (d) => d.status === 'SENT')} />
        <Kpi label="Claim rate" value={k ? formatPct(k.claim_rate) : '…'} delta={k?.deltas.claim_rate} />
        <Kpi label="Budget used" value={k ? formatPct(k.budget_used_pct, 0) : '…'} delta={k?.deltas.budget_used_pct} goodWhen="down" hint="Caps shrink above 80%" />
        <Kpi label="Blocked by rules" value={k ? formatInt(k.blocked_by_rules) : '…'} delta={k?.deltas.blocked_by_rules} goodWhen="down" hint="Stopped by guardrails" />
      </section>

      <div className="grid gap-3 lg:grid-cols-2">
        <LiveStream className="h-[520px]" />
        <div className="grid content-start gap-3 sm:grid-cols-2">
          <Funnel className="sm:col-span-2" decisions={ds} />
          <DecidedByShare kpis={k} decisions={ds} />
          <MarginCallout kpis={k} decisions={ds} />
          <AutomationsCard className="sm:col-span-2" />
        </div>
        <DigestCard />
        <MomentsStrip />
      </div>
    </div>
  )
}
