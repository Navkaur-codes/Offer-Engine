import { CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from 'recharts'
import { POLICY_LABEL } from '@/lib/labels'
import type { CustomerProfile, PolicyName } from '@/lib/types'
import { cn, formatInr, formatInrCompact } from '@/lib/utils'

// Colour AND shape per policy, so the chart reads without colour (CLAUDE.md §7).
type Shape = 'circle' | 'square' | 'triangle' | 'diamond' | 'cross' | 'star' | 'wye'
const POLICY_MARK: Record<PolicyName, { color: string; shape: Shape }> = {
  vip: { color: 'var(--signal)', shape: 'star' },
  deal_hunter: { color: 'var(--violet)', shape: 'diamond' },
  at_risk: { color: 'var(--amber)', shape: 'triangle' },
  new_user: { color: 'var(--slate)', shape: 'circle' },
  cart_abandoner: { color: 'var(--signal)', shape: 'square' },
  window_shopper: { color: 'var(--violet)', shape: 'circle' },
  high_returner: { color: 'var(--slate)', shape: 'cross' },
  sleeping_dog: { color: 'var(--muted)', shape: 'wye' },
  dormant: { color: 'var(--amber)', shape: 'square' },
  default: { color: 'var(--slate)', shape: 'diamond' },
}

const GLYPH: Record<Shape, string> = { circle: '●', square: '■', triangle: '▲', diamond: '◆', cross: '✚', star: '★', wye: 'Y' }

export function PolicyGlyph({ policy }: { policy: PolicyName }) {
  const m = POLICY_MARK[policy]
  return <span aria-hidden style={{ color: m.color }} className="text-[11px]">{GLYPH[m.shape]}</span>
}

/** Recency × lifetime value, one series per policy. Click a point to open the customer. */
export function SegmentScatter({
  customers, selected, onSelect, onTogglePolicy, activePolicy,
}: {
  customers: CustomerProfile[]
  selected?: string | null
  onSelect: (id: string) => void
  onTogglePolicy: (p: PolicyName) => void
  activePolicy?: string | null
}) {
  const byPolicy = new Map<PolicyName, CustomerProfile[]>()
  for (const c of customers) byPolicy.set(c.policy, [...(byPolicy.get(c.policy) ?? []), c])
  const series = (Object.keys(POLICY_LABEL) as PolicyName[]).filter((p) => byPolicy.has(p))

  return (
    <div className="space-y-3">
      <div className="h-[300px]" role="img" aria-label={`Scatter of ${customers.length} customers: days since last visit against lifetime value, by policy`}>
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 8, right: 16, bottom: 20, left: 8 }}>
            <CartesianGrid stroke="var(--line)" strokeDasharray="0" />
            <XAxis
              type="number" dataKey="recency_days" name="Days since last visit" stroke="var(--muted)" tickLine={false}
              fontSize={11} fontFamily="var(--font-mono)"
              label={{ value: 'days since last visit →', position: 'insideBottom', offset: -12, fill: 'var(--muted)', fontSize: 11 }}
            />
            <YAxis
              type="number" dataKey="ltv" name="Lifetime value" stroke="var(--muted)" tickLine={false} fontSize={11}
              // Spend is Pareto-shaped; a √ scale keeps the long tail readable without hiding zeros (log can't).
              scale="sqrt" domain={[0, 'auto']}
              fontFamily="var(--font-mono)" tickFormatter={(v: number) => formatInrCompact(v)} width={56}
              label={{ value: 'lifetime value (√ scale)', angle: -90, position: 'insideLeft', offset: 4, fill: 'var(--muted)', fontSize: 11, dy: 60 }}
            />
            <ZAxis range={[36, 36]} />
            <Tooltip
              cursor={{ stroke: 'var(--line)' }}
              content={({ payload }) => {
                const c = payload?.[0]?.payload as CustomerProfile | undefined
                if (!c) return null
                return (
                  <div className="rounded-[6px] border border-line bg-surface px-2.5 py-1.5 text-[12px] shadow-menu">
                    <p className="text-ink">{c.first_name} <span className="num text-muted">{c.customer_id}</span></p>
                    <p className="text-muted">{POLICY_LABEL[c.policy]} · {c.recency_days} d · LTV <span className="num">{formatInr(c.ltv)}</span></p>
                  </div>
                )
              }}
            />
            {series.map((p) => (
              <Scatter
                key={p}
                name={POLICY_LABEL[p]}
                data={byPolicy.get(p)}
                shape={POLICY_MARK[p].shape}
                fill={POLICY_MARK[p].color}
                fillOpacity={selected ? 0.35 : 0.85}
                isAnimationActive={false}
                cursor="pointer"
                onClick={(d) => {
                  const c = (d as unknown as { payload?: CustomerProfile }).payload
                  if (c) onSelect(c.customer_id)
                }}
              />
            ))}
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <ul className="flex flex-wrap gap-1.5" aria-label="Policies (click to filter)">
        {series.map((p) => (
          <li key={p}>
            <button
              onClick={() => onTogglePolicy(p)}
              aria-pressed={activePolicy === p}
              className={cn(
                'inline-flex h-6 items-center gap-1.5 rounded-[5px] border px-2 text-[12px]',
                activePolicy === p ? 'border-ink text-ink' : 'border-line text-muted hover:text-ink',
              )}
            >
              <PolicyGlyph policy={p} />
              {POLICY_LABEL[p]}
              <span className="num text-[11px] text-muted">{byPolicy.get(p)?.length}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
