import type { CustomerProfile } from '@/lib/types'
import { cn, formatInr, formatInt } from '@/lib/utils'
import { PolicyBadge } from './badges'

function level(v: number) {
  return v >= 0.66 ? 'high' : v >= 0.33 ? 'medium' : 'low'
}

function Meter({ label, value, words }: { label: string; value: number; words: string }) {
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-[12px]">
        <span className="text-muted">{label}</span>
        <span className="text-ink">
          {words} <span className="num text-muted">{value.toFixed(2)}</span>
        </span>
      </div>
      <div className="h-1.5 rounded-full bg-surface-2" role="meter" aria-label={label} aria-valuemin={0} aria-valuemax={1} aria-valuenow={value}>
        <div className="h-full rounded-full bg-slate" style={{ width: `${Math.min(1, Math.max(0, value)) * 100}%` }} />
      </div>
    </div>
  )
}

/** The profile as the engine saw it at decision time, in plain words. */
export function ProfileSnapshot({ p }: { p: CustomerProfile }) {
  const uplift = Object.entries(p.uplift).sort((a, b) => (b[1] ?? 0) - (a[1] ?? 0))
  const facts: [string, string][] = [
    ['Last visit', `${p.recency_days} days ago`],
    ['Orders (90 d)', formatInt(p.orders_90d)],
    ['Avg order', formatInr(p.aov)],
    ['Lifetime value', formatInr(p.ltv)],
    ['Segment', `${p.rfm.segment} · R${p.rfm.r} F${p.rfm.f} M${p.rfm.m}`],
    ['Points', `${formatInt(p.points_balance)}${p.points_expiring ? ` (${formatInt(p.points_expiring)} expiring)` : ''}`],
    ['Offers in 7 d', formatInt(p.offers_7d)],
    ['City tier', String(p.city_tier)],
  ]
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 text-[13px]">
        <span className="title text-ink">{p.first_name}</span>
        <span className="num text-[12px] text-muted">{p.customer_id}</span>
        <PolicyBadge policy={p.policy} />
        <span className="text-[12px] text-muted">{p.tier} tier</span>
      </div>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-[12.5px]">
        {facts.map(([k, v]) => (
          <div key={k} className="flex justify-between gap-2 border-b border-line pb-1">
            <dt className="text-muted">{k}</dt>
            <dd className="num text-right text-ink">{v}</dd>
          </div>
        ))}
      </dl>
      {p.open_cart ? (
        <p className="rounded-[6px] border border-line bg-surface-2 px-3 py-2 text-[12.5px]">
          Open cart: <b className="font-medium">{p.open_cart.item}</b> <span className="num">{formatInr(p.open_cart.value)}</span>
        </p>
      ) : null}
      <div className="grid gap-3 sm:grid-cols-2">
        <Meter label="Churn risk" value={p.churn_risk} words={level(p.churn_risk)} />
        <Meter label="Price sensitivity" value={p.price_sensitivity} words={level(p.price_sensitivity)} />
        <Meter label="Discount usage" value={p.discount_usage_rate} words={level(p.discount_usage_rate)} />
        <Meter label="Return rate" value={p.return_rate} words={level(p.return_rate)} />
      </div>
      <div>
        <p className="mb-1 text-[12px] text-muted">
          Predicted uplift: the extra chance of buying caused by each offer type. Below 0 means the offer would put them off.
        </p>
        <ul className="num space-y-0.5 text-[12px]">
          {uplift.map(([k, v]) => (
            <li key={k} className="flex justify-between">
              <span className="text-muted">{k.replace('_', ' ')}</span>
              <span className={cn((v ?? 0) < 0 ? 'text-danger-text' : 'text-ink')}>
                {(v ?? 0) < 0 ? '▼ ' : '▲ '}
                {((v ?? 0) * 100).toFixed(1)} pts
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
