// One plain-English sentence per chart, written from the data (context-4 Phase 4).
// Each returns null when the data is too thin to say anything honest.
import { POLICY_LABEL } from './labels'
import type { ArmStats, FestivalLift, OfferRoi, PolicyUplift, QiniPoint } from './types'
import { formatInr } from './utils'

const pts = (x: number) => `${x < 0 ? '−' : ''}${Math.abs(x * 100).toFixed(1)} pts`
const pct = (x: number) => `${(x * 100).toFixed(1)}%`
const OFFER: Record<string, string> = {
  pct_off: '% off', flat_off: 'Flat ₹ off', free_shipping: 'Free shipping', free_express: 'Free express delivery',
  bonus_points: 'Bonus points', points_reminder: 'Points reminders', cart_nudge: 'Cart reminders',
  early_access: 'Early access', bundle: 'Bundles', gift_card: 'Gift cards', birthday: 'Birthday treats',
}
export const offerLabel = (t: string) => OFFER[t] ?? t

export function treatmentTakeaway(t: ArmStats, c: ArmStats): string | null {
  if (!t.n || !c.n) return null
  const diff = t.conv_rate - c.conv_rate
  if (Math.abs(diff) < 0.001) return `Customers who got offers bought at the same rate as the holdout (${pct(t.conv_rate)}), so offers added nothing here.`
  const ratio = c.conv_rate > 0 ? ` (${(t.conv_rate / c.conv_rate).toFixed(1)}×)` : ''
  return `Customers who got offers bought at ${pct(t.conv_rate)} vs ${pct(c.conv_rate)} in the holdout: ${diff > 0 ? '+' : '−'}${pts(Math.abs(diff))}${diff > 0 ? ratio : ''}.`
}

export function policyTakeaway(rows: PolicyUplift[]): string | null {
  const ok = rows.filter((r) => r.n_control >= 5)
  if (ok.length < 2) return null
  const avg = ok.reduce((s, r) => s + r.uplift * r.n_treated, 0) / Math.max(1, ok.reduce((s, r) => s + r.n_treated, 0))
  const best = [...ok].sort((a, b) => b.uplift - a.uplift)[0]
  const worst = [...ok].sort((a, b) => a.uplift - b.uplift)[0]
  const times = avg > 0 ? ` ${(best.uplift / avg).toFixed(1)}× the average` : ''
  const tail = worst.uplift <= 0
    ? ` ${POLICY_LABEL[worst.policy]} customers gained nothing from offers (${pts(worst.uplift)}): don’t pay them.`
    : ''
  return `${POLICY_LABEL[best.policy]} customers respond best to offers: +${pts(best.uplift)},${times}.${tail}`
}

export function roiTakeaway(rows: OfferRoi[]): string | null {
  const ok = rows.filter((r) => r.n >= 10)
  if (!ok.length) return null
  const best = [...ok].sort((a, b) => b.incremental_profit - a.incremental_profit)[0]
  const losers = ok.filter((r) => r.incremental_profit < 0).sort((a, b) => a.incremental_profit - b.incremental_profit)
  const first = `${offerLabel(best.type)} earned the most extra profit (${formatInr(best.incremental_profit)}).`
  return losers.length
    ? `${first} ${offerLabel(losers[0].type)} lost ${formatInr(-losers[0].incremental_profit)}: those customers would have bought anyway.`
    : first
}

export function qiniTakeaway(points: QiniPoint[] | null): string | null {
  if (!points || points.length < 3) return null
  const total = points[points.length - 1].model
  if (total <= 0) return null
  const at = points.reduce((best, p) => (Math.abs(p.targeted - 0.3) < Math.abs(best.targeted - 0.3) ? p : best))
  const share = at.model / total
  return `Targeting the top ${Math.round(at.targeted * 100)}% by predicted uplift captures ${Math.round(share * 100)}% of the total gain; picking at random would capture ${Math.round(at.targeted * 100)}%.`
}

export function festivalTakeaway(rows: FestivalLift[]): string | null {
  const ok = rows.filter((r) => r.revenue_per_day > 0)
  if (!ok.length) return null
  const best = [...ok].sort((a, b) => b.lift - a.lift)[0]
  return `${best.festival} drove ${best.lift.toFixed(1)}× a normal day’s revenue, the biggest festival lift. High-demand days need fewer discounts, not more.`
}
