import { useQuery } from '@tanstack/react-query'
import { Play } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { DataTable } from '@/components/DataTable'
import { Kpi } from '@/components/Kpi'
import { Money } from '@/components/Money'
import { PageHeader } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle } from '@/components/ui/card'
import { NAV } from '@/app/nav'
import { api } from '@/lib/api'
import { formatInt, formatPct } from '@/lib/utils'
import { decisionColumns } from './decisionColumns'

// Phase-1 Overview: KPI strip + recent decisions. Bento, feed and digest arrive in Phase 2.
const SPARK = {
  sent: [31, 40, 36, 52, 47, 58, 63],
  revenue: [21, 26, 24, 33, 38, 41, 48],
  claim: [14, 15, 17, 16, 18, 17, 18],
  margin: [9, 11, 10, 14, 15, 17, 19],
}

export function Overview() {
  const navigate = useNavigate()
  const kpis = useQuery({ queryKey: ['kpis'], queryFn: () => api.kpis() })
  const recent = useQuery({ queryKey: ['decisions', 'recent'], queryFn: () => api.decisions({ limit: 8 }) })
  const k = kpis.data

  return (
    <div className="mx-auto max-w-[1400px] space-y-5 p-4 md:p-6">
      <PageHeader
        title="Overview"
        why={NAV[0].why}
        action={
          <Button variant="primary" asChild>
            <Link to="/playground"><Play /> Run a decision</Link>
          </Button>
        }
      />
      <section aria-label="Key numbers" className="grid grid-cols-2 gap-3 lg:grid-cols-6">
        <Kpi
          hero
          className="col-span-2 lg:row-span-1"
          label="Incremental revenue vs holdout"
          value={k ? <Money value={k.incremental_revenue} /> : '…'}
          delta={k?.deltas.incremental_revenue}
          spark={SPARK.revenue}
          hint="Sales that would not have happened without an offer"
        />
        <Kpi label="Sent today" value={k ? formatInt(k.sent_today) : '…'} delta={k?.deltas.sent_today} spark={SPARK.sent} />
        <Kpi label="Claim rate" value={k ? formatPct(k.claim_rate) : '…'} delta={k?.deltas.claim_rate} spark={SPARK.claim} />
        <Kpi label="Margin saved" value={k ? <Money value={k.margin_saved} compact /> : '…'} delta={k?.deltas.margin_saved} spark={SPARK.margin} hint="Sure-things not discounted" />
        <Kpi label="Blocked by rules" value={k ? formatInt(k.blocked_by_rules) : '…'} delta={k?.deltas.blocked_by_rules} goodWhen="down" hint={k ? `Agent ${formatPct(k.agent_share, 0)} · fallback ${formatPct(k.fallback_share, 0)}` : undefined} />
      </section>

      <Card>
        <CardHeader>
          <CardTitle>Latest decisions</CardTitle>
          <Link to="/decisions" className="text-[12.5px] text-muted hover:text-ink">All decisions →</Link>
        </CardHeader>
        <DataTable
          className="rounded-none border-0"
          columns={decisionColumns}
          data={recent.data?.items ?? []}
          loading={recent.isLoading}
          getRowId={(d) => d.id}
          onRowClick={(d) => navigate(`/decisions?id=${encodeURIComponent(d.id)}`)}
        />
      </Card>
    </div>
  )
}
