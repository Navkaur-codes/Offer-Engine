import { useQuery } from '@tanstack/react-query'
import { Play } from 'lucide-react'
import { useEffect } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { EmptyState } from '@/components/EmptyState'
import { PageHeader } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { NAV } from '@/app/nav'
import { api } from '@/lib/api'
import { POLICY_LABEL } from '@/lib/labels'
import { conditionsLabel } from '@/lib/ruleEdit'
import type { PolicyName, Rule, RuleLayer } from '@/lib/types'
import { cn } from '@/lib/utils'
import { RuleCard } from './rules/RuleCard'

const LAYERS: { id: RuleLayer; label: string; note: string }[] = [
  { id: 'global', label: 'Global', note: 'Business limits for everyone. Every other layer can only make these tighter, never looser.' },
  { id: 'festival', label: 'Festival', note: 'Switch on by date during festival phases. They can change offer types and budgets, but never beat the global caps.' },
  { id: 'persona', label: 'Persona', note: 'One policy per type of shopper. Customers move between policies automatically as their behaviour changes.' },
  { id: 'individual', label: 'Individual', note: 'Exceptions for one customer: opt-outs, “Not for me” taps, fraud flags or a manual cap.' },
]

export function Rules() {
  const [params, setParams] = useSearchParams()
  const rules = useQuery({ queryKey: ['rules', 'all'], queryFn: () => api.rules() })
  const target = params.get('rule')
  const targetRule = rules.data?.find((r) => r.id === target)
  const layer = (params.get('layer') as RuleLayer | null) ?? targetRule?.layer ?? 'global'
  const inLayer = (rules.data ?? []).filter((r) => r.layer === layer)

  useEffect(() => {
    if (targetRule) document.getElementById(`rule-${targetRule.id}`)?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }, [targetRule])

  // Group by who the rule applies to; persona groups follow the policy order marketers know.
  const groups = new Map<string, Rule[]>()
  for (const r of inLayer) {
    const key = layer === 'persona' ? String(r.conditions.policy ?? '') : conditionsLabel(r.conditions)
    groups.set(key, [...(groups.get(key) ?? []), r])
  }
  const ordered = [...groups.entries()].sort(([a], [b]) =>
    layer === 'persona' ? Object.keys(POLICY_LABEL).indexOf(a) - Object.keys(POLICY_LABEL).indexOf(b) : 0,
  )
  const meta = LAYERS.find((l) => l.id === layer)!

  return (
    <div className="mx-auto max-w-[1100px] space-y-5 p-4 md:p-6">
      <PageHeader
        title="Rules & policies"
        why={NAV[2].why}
        action={<Button asChild><Link to="/playground"><Play /> Test in Playground</Link></Button>}
      />

      <div role="tablist" aria-label="Rule layers" className="flex flex-wrap items-center gap-1 border-b border-line">
        {LAYERS.map((l, i) => {
          const n = (rules.data ?? []).filter((r) => r.layer === l.id).length
          const active = l.id === layer
          return (
            <button
              key={l.id}
              role="tab"
              aria-selected={active}
              onClick={() => setParams({ layer: l.id }, { replace: true })}
              className={cn(
                '-mb-px flex items-center gap-1.5 border-b-2 px-3 py-2 text-[13px]',
                active ? 'border-signal text-ink' : 'border-transparent text-muted hover:text-ink',
              )}
            >
              <span className="num text-[11px] text-muted">{i + 1}</span>
              {l.label}
              <span className="num rounded-[4px] border border-line px-1 text-[11px] text-muted">{n}</span>
            </button>
          )
        })}
        <span className="ml-auto hidden pb-2 text-[12px] text-muted md:block">Applied in order 1 → 4; the tightest limit wins.</span>
      </div>
      <p className="text-[13px] text-muted">{meta.note}</p>

      {rules.isLoading ? (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => <div key={i} className="h-28 animate-pulse rounded-[8px] bg-surface-2" />)}
        </div>
      ) : !inLayer.length ? (
        <EmptyState
          title={`No ${meta.label.toLowerCase()} rules yet`}
          hint="Rules are seeded by the backend. If this stays empty, check that the API is reachable."
          action={<Button onClick={() => rules.refetch()}>Reload rules</Button>}
        />
      ) : (
        ordered.map(([key, rs]) => (
          <section key={key} className="space-y-2">
            <GroupHeader layer={layer} groupKey={key} />
            {rs.map((r) => <RuleCard key={r.id} rule={r} highlight={r.id === target} />)}
          </section>
        ))
      )}
    </div>
  )
}

function GroupHeader({ layer, groupKey }: { layer: RuleLayer; groupKey: string }) {
  if (layer !== 'persona') return <h2 className="title pt-2 text-[13px] text-muted">{groupKey}</h2>
  const policy = groupKey as PolicyName
  return (
    <div className="flex items-baseline justify-between gap-2 pt-2">
      <h2 className="title text-[15px] text-ink">{POLICY_LABEL[policy] ?? policy}</h2>
      <PolicyMembers policy={policy} />
    </div>
  )
}

/** "Who is in this policy now": live count from the customers endpoint (first page). */
function PolicyMembers({ policy }: { policy: PolicyName }) {
  const { data } = useQuery({ queryKey: ['customers', 'policy-count', policy], queryFn: () => api.customers({ policy, limit: 200 }), staleTime: 60_000 })
  const n = data ? `${data.items.length}${data.next ? '+' : ''}` : '…'
  return (
    <Link to={`/customers?policy=${policy}`} className="text-[12.5px] text-muted hover:text-ink">
      <span className="num text-ink">{n}</span> customers in this policy now →
    </Link>
  )
}
