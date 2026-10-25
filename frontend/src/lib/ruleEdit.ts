// Turns a rule's server-written sentence (describe()) into text + inline number inputs.
// Only scalar params are editable; lists and maps stay read-only (no JSON editors, T16).
import { POLICY_LABEL, PHASE_LABEL } from './labels'
import { festivalLabel } from './festivals'
import type { FestivalPhase, PolicyName, Rule } from './types'

export type Unit = 'pct' | 'inr' | 'days' | 'hours' | 'minutes' | 'mult' | 'points' | 'int' | 'time'

export interface EditField {
  key: string
  label: string
  unit: Unit
  /** Value as the marketer sees it (e.g. days, not hours). */
  display: string
}

const LABELS: Record<string, string> = {
  max_pct: 'Max discount', buffer_pct: 'Margin buffer', max_amount: 'Max flat discount', min_basket: 'Min basket',
  daily_cap: 'Daily budget', max_multiplier: 'Max points multiplier', max_7d: 'Offers per 7 days',
  min_gap_h: 'Min gap between offers', within_purchase_h: 'Window after a purchase', max_active: 'Active coupons',
  max_len: 'Max message length', min_uplift: 'Min uplift', start: 'Quiet from', end: 'Quiet until',
}

function unitFor(key: string, v: number | string): Unit {
  if (typeof v === 'string') return 'time'
  if (key.endsWith('_pct')) return 'pct'
  if (/amount|basket|cap$/.test(key)) return 'inr'
  if (key.endsWith('_h')) return v >= 24 && v % 24 === 0 ? 'days' : v < 1 ? 'minutes' : 'hours'
  if (key.includes('multiplier')) return 'mult'
  if (key === 'min_uplift') return 'points'
  return 'int'
}

function toDisplay(unit: Unit, v: number | string): string {
  if (typeof v === 'string') return v
  if (unit === 'days') return String(v / 24)
  if (unit === 'minutes') return String(Math.round(v * 60))
  if (unit === 'points') return String(Math.round(v * 100))
  return String(v)
}

/** Display value back to the param the API stores. Returns null when invalid. */
export function toParam(f: EditField, display: string): number | string | null {
  if (f.unit === 'time') return /^([01]\d|2[0-3]):[0-5]\d$/.test(display) ? display : null
  const n = Number(display)
  if (display.trim() === '' || !Number.isFinite(n) || n < 0) return null
  if (f.unit === 'pct' && n > 100) return null
  if (f.unit === 'days') return n * 24
  if (f.unit === 'minutes') return n / 60
  if (f.unit === 'points') return n / 100
  return n
}

export function editableFields(rule: Rule): EditField[] {
  return Object.entries(rule.params)
    .filter(([k, v]) => typeof v === 'number' || (typeof v === 'string' && /^\d{2}:\d{2}$/.test(v) && (k === 'start' || k === 'end')))
    .map(([key, v]) => {
      const value = v as number | string
      const unit = unitFor(key, value)
      return { key, label: LABELS[key] ?? key.replaceAll('_', ' '), unit, display: toDisplay(unit, value) }
    })
}

// How describe() prints each unit, so the value can be found inside the sentence.
function tokens(f: EditField): string[] {
  const d = f.display
  const n = Number(d)
  switch (f.unit) {
    case 'pct': return [`${d}%`, `${d} points`]
    case 'inr': return [`₹${n.toLocaleString('en-US')}`, `₹${n.toLocaleString('en-IN')}`]
    case 'days': return n === 1 ? ['1 day', 'one day', '1 days'] : [`${d} days`]
    case 'hours': return [`${d} h`]
    case 'minutes': return [`${d} min`]
    case 'mult': return [`${d}×`]
    case 'points': return [`${d} points`]
    default: return d === '1' ? ['1', 'one'] : [d]
  }
}

const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

export type Segment = { text: string } | { field: EditField; text: string }

/** Splits the sentence into text and field segments; fields not found in it are returned separately. */
export function segment(description: string, fields: EditField[]): { segments: Segment[]; extra: EditField[] } {
  const hits: { start: number; end: number; field: EditField }[] = []
  const extra: EditField[] = []
  for (const f of fields) {
    let found = false
    for (const t of tokens(f)) {
      // Not part of a bigger number: "3" must not match "30%" or "₹300", but "₹999." at a sentence end is fine.
      const re = new RegExp(`(?<![\\d₹]|\\d[.,])${esc(t)}(?![\\d%×]|[.,]\\d)`, 'g')
      for (const m of description.matchAll(re)) {
        const start = m.index ?? 0
        const end = start + t.length
        if (hits.some((h) => start < h.end && end > h.start)) continue
        hits.push({ start, end, field: f })
        found = true
        break
      }
      if (found) break
    }
    if (!found) extra.push(f)
  }
  hits.sort((a, b) => a.start - b.start)
  const segments: Segment[] = []
  let at = 0
  for (const h of hits) {
    if (h.start > at) segments.push({ text: description.slice(at, h.start) })
    segments.push({ field: h.field, text: description.slice(h.start, h.end) })
    at = h.end
  }
  if (at < description.length) segments.push({ text: description.slice(at) })
  return { segments, extra }
}

/** Prefix/suffix around the number for each unit, so "₹[999]" and "[10]%" read naturally. */
export const AFFIX: Record<Unit, [string, string]> = {
  pct: ['', '%'], inr: ['₹', ''], days: ['', ' days'], hours: ['', ' h'], minutes: ['', ' min'],
  mult: ['', '×'], points: ['', ' pts'], int: ['', ''], time: ['', ''],
}

/** "Policy: Deal hunter", "Any festival · build-up", "Customer C000777", "Everyone". */
export function conditionsLabel(c: Rule['conditions']): string {
  const parts: string[] = []
  if (typeof c.policy === 'string') parts.push(POLICY_LABEL[c.policy as PolicyName] ?? c.policy)
  if (c.festival === '*') parts.push('Any festival')
  else if (Array.isArray(c.festival)) parts.push(c.festival.map((f) => festivalLabel(String(f))).join(' or '))
  else if (typeof c.festival === 'string') parts.push(festivalLabel(c.festival))
  if (typeof c.phase === 'string') parts.push(PHASE_LABEL[c.phase as FestivalPhase] ?? c.phase)
  if (typeof c.customer_id === 'string') parts.push(`Customer ${c.customer_id}`)
  return parts.length ? parts.join(' · ') : 'Everyone'
}
