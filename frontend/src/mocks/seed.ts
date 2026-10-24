// Deterministic, synthetic mock data built from contracts.md §5. No real people.
import { POLICY_LABEL } from '@/lib/labels'
import example from './fixtures/decision-example.json'
import type {
  Category, CustomerProfile, Decision, DecidedBy, DecisionLight, DecisionStatus, Event,
  Festival, Kpis, Outcome, Persona, PolicyName, Rule, RuleCheck, ToolCall, TriggerType,
} from '@/lib/types'

function rng(seed: number) {
  let s = seed >>> 0
  return () => {
    s = (s + 0x6d2b79f5) >>> 0
    let t = s
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}
const r = rng(42)
const pick = <T,>(xs: readonly T[]): T => xs[Math.floor(r() * xs.length)]
const round2 = (n: number) => Math.round(n * 100) / 100

const IST = '+05:30'
function iso(d: Date): string {
  const t = new Date(d.getTime() + 330 * 60_000)
  return t.toISOString().slice(0, 19) + IST
}

// ---------- rules (seed set, 4 layers) ----------
const R = (
  id: string, layer: Rule['layer'], type: Rule['type'], severity: Rule['severity'],
  conditions: Rule['conditions'], params: Rule['params'], description: string, version = 1,
): Rule => ({
  id, layer, type, severity, conditions, params, enabled: true, priority: 100, version, description,
  updated_by: 'seed', updated_at: '2026-10-22T10:00:00+05:30',
})

export const RULES: Rule[] = [
  R('G-MARGIN', 'global', 'margin_guard', 'hard', {}, { buffer_pct: 5 }, 'No discount may exceed the category margin minus 5%.'),
  R('G-FREQ', 'global', 'frequency_cap', 'hard', {}, { max_per_7d: 3, min_gap_h: 48 }, 'Each customer gets at most 3 offers per 7 days, at least 48 h apart.'),
  R('G-QUIET', 'global', 'quiet_hours', 'hard', {}, { start: '21:00', end: '09:00' }, 'Nothing is sent between 21:00 and 09:00 IST; those sends are queued.'),
  R('G-BUDGET', 'global', 'budget', 'hard', {}, { daily_cap: 25000, pacing_at_pct: 80 }, 'Daily offer budget is ₹25,000; caps shrink once 80% is used.'),
  R('G-STACK', 'global', 'stacking', 'hard', {}, { max_active: 1 }, 'A customer can hold only 1 active coupon at a time.'),
  R('G-POSTBUY', 'global', 'exclusion', 'hard', {}, { hours_after_purchase: 48 }, 'No discount within 48 h after a purchase.'),
  R('F-DIWALI-BU', 'festival', 'discount_cap', 'hard', { festival: 'diwali', phase: 'build_up' }, { max_pct: 15 }, 'During Diwali build-up, discounts are capped at 15%.'),
  R('F-DHAN-LM', 'festival', 'eligibility', 'soft', { festival: 'dhanteras', phase: 'last_minute' }, { prefer: ['free_express', 'bonus_points'] }, 'On Dhanteras last-minute, prefer free express shipping and points over discounts.'),
  R('F-GURPURAB', 'festival', 'festival_restriction', 'hard', { festival: 'gurpurab' }, { blocked: ['alcohol', 'meat'] }, 'During Gurpurab, alcohol and meat promotions are blocked.'),
  R('P-VIP', 'persona', 'eligibility', 'hard', { policy: 'vip' }, { blocked_types: ['pct_off', 'flat_off'] }, 'VIPs never get % or flat discounts; use early access, points and free shipping.', 2),
  R('P-DEAL', 'persona', 'discount_cap', 'hard', { policy: 'deal_hunter' }, { max_pct: 10, min_basket: 999 }, 'Deal hunters can get at most 10% off, only on baskets above ₹999.', 3),
  R('P-ATRISK', 'persona', 'discount_cap', 'hard', { policy: 'at_risk' }, { max_pct: 20, min_uplift: 0.05, once_per_days: 30 }, 'At-risk customers can get up to 20% win-back once per 30 days, only if uplift is above 0.05.'),
  R('P-NEW', 'persona', 'eligibility', 'hard', { policy: 'new_user' }, { welcome_pct: 15, once: true }, 'New users get one 15% welcome offer on their 2nd order.'),
  R('P-CART', 'persona', 'escalation_ladder', 'hard', { policy: 'cart_abandoner' }, { steps: ['cart_nudge', 'free_shipping', 'pct_off:5@24h'] }, 'Cart abandoners go nudge → free shipping → 5% off after 24 h, in that order.', 3),
  R('P-WINDOW', 'persona', 'discount_cap', 'hard', { policy: 'window_shopper' }, { max_flat: 150 }, 'Window shoppers get free shipping or at most ₹150 off.'),
  R('P-RETURN', 'persona', 'eligibility', 'hard', { policy: 'high_returner' }, { allowed_types: ['bonus_points', 'points_reminder'] }, 'High returners get points only, never discounts.'),
  R('P-SLEEP', 'persona', 'exclusion', 'hard', { policy: 'sleeping_dog' }, { proactive: false }, 'Sleeping dogs (negative uplift) get no proactive offers.'),
  R('P-DORMANT', 'persona', 'frequency_cap', 'hard', { policy: 'dormant' }, { tries: 1, cooldown_days: 90 }, 'Dormant customers get one win-back try, then a 90-day pause.'),
  R('I-C000017', 'individual', 'exclusion', 'soft', { customer_id: 'C000017' }, { suppressed: ['electronics'], days: 14 }, 'C000017 said “Not for me” to electronics; suppressed for 14 days.'),
  R('M-LEN', 'global', 'message', 'hard', {}, { max_chars: 280 }, 'Messages are at most 280 characters and must state value and expiry.'),
]

// ---------- festivals (approximate; Session A verifies the real dates) ----------
const F = (id: string, name: string, date: string, hero: Category[], budget: number, needs_opt_in: boolean, greeting: string | null): Festival => ({
  id, name, date, region: null,
  phases: { teaser: [-14, -7], build_up: [-7, -2], last_minute: [-1, 0], post: [1, 10] },
  hero_categories: hero, greeting, needs_opt_in, restricted_promos: [], budget,
  strategy: { teaser: 'Zero-cost early access', build_up: 'Hero-category offers', last_minute: 'Delivery-cutoff free express', post: 'Cross-sell, no discounts for buyers' },
  delivery_days_by_tier: { '1': 2, '2': 3, '3': 5 },
})
export const FESTIVALS: Festival[] = [
  F('karwa_chauth', 'Karwa Chauth', '2026-10-29', ['ethnic_wear', 'jewellery', 'beauty', 'gifting'], 40000, true, 'Happy Karwa Chauth'),
  F('dhanteras', 'Dhanteras', '2026-11-06', ['jewellery', 'kitchen', 'electronics'], 60000, true, 'Happy Dhanteras'),
  F('diwali', 'Diwali', '2026-11-08', ['home_decor', 'electronics', 'fashion', 'gifting'], 120000, true, 'Happy Diwali'),
  F('bhai_dooj', 'Bhai Dooj', '2026-11-11', ['gifting', 'fashion'], 30000, true, 'Happy Bhai Dooj'),
  F('gurpurab', 'Gurpurab', '2026-11-24', ['ethnic_wear', 'home_decor'], 20000, true, 'Gurpurab diyan lakh lakh vadhaiyan'),
]

// ---------- customers ----------
const NAMES = ['Aarav', 'Diya', 'Kabir', 'Meera', 'Rohan', 'Ananya', 'Ishaan', 'Simran', 'Vikram', 'Priya', 'Arjun', 'Kavya', 'Harpreet', 'Neha', 'Aditya', 'Sana', 'Rahul', 'Pooja', 'Gurleen', 'Karan', 'Tanvi', 'Yash', 'Riya', 'Manav', 'Jaspreet', 'Nikhil', 'Aisha', 'Dev', 'Ishita', 'Varun']
const PERSONA_POLICY: [Persona, PolicyName][] = [
  ['loyal_vip', 'vip'], ['deal_hunter', 'deal_hunter'], ['at_risk_regular', 'at_risk'], ['new_user', 'new_user'],
  ['cart_abandoner', 'cart_abandoner'], ['window_shopper', 'window_shopper'], ['high_returner', 'high_returner'],
  ['dormant', 'dormant'], ['festive_gifter', 'default'], ['loyal_vip', 'sleeping_dog'],
]
const CATS: Category[] = ['fashion', 'ethnic_wear', 'electronics', 'beauty', 'home_decor', 'kitchen', 'grocery', 'jewellery', 'gifting', 'winter_wear']
const ITEMS: Record<Category, string> = {
  fashion: 'Cotton Kurta', ethnic_wear: 'Silk Saree', electronics: 'Wireless Earbuds', beauty: 'Vitamin C Serum',
  home_decor: 'Brass Diya Set', kitchen: 'Steel Cookware Set', grocery: 'Dry-fruit Hamper', jewellery: 'Silver Coin 10g',
  gifting: 'Gift Hamper', winter_wear: 'Wool Shawl',
}
const SEGMENTS = ['Champions', 'Loyal', 'Potential', 'At risk', 'Hibernating', 'New']

const NOW = new Date()

export const CUSTOMERS: CustomerProfile[] = NAMES.map((first_name, i) => {
  const [persona, policy] = PERSONA_POLICY[i % PERSONA_POLICY.length]
  const aov = Math.round(400 + r() ** 2 * 4200)
  const orders = policy === 'dormant' ? 0 : Math.floor(r() * 9)
  const cat = pick(CATS)
  const affinity = Object.fromEntries(CATS.map((c) => [c, round2(c === cat ? 0.5 + r() * 0.4 : r() * 0.4)]))
  const cart = policy === 'cart_abandoner' || r() < 0.2
  return {
    customer_id: `C${String(i + 1).padStart(6, '0')}`,
    first_name,
    city_tier: 1 + Math.floor(r() * 3),
    persona,
    policy,
    rfm: { r: 1 + Math.floor(r() * 5), f: 1 + Math.floor(r() * 5), m: 1 + Math.floor(r() * 5), segment: pick(SEGMENTS) },
    recency_days: policy === 'dormant' ? 120 + Math.floor(r() * 90) : Math.floor(r() * 60),
    orders_90d: orders,
    aov,
    ltv: aov * (orders + Math.floor(r() * 12)),
    churn_risk: round2(policy === 'at_risk' ? 0.6 + r() * 0.35 : r() * 0.55),
    uplift: { free_shipping: round2(policy === 'sleeping_dog' ? -0.04 : r() * 0.25), pct_off: round2(r() * 0.3 - 0.05), bonus_points: round2(r() * 0.15) },
    price_sensitivity: round2(policy === 'deal_hunter' ? 0.7 + r() * 0.3 : r()),
    category_affinity: affinity,
    return_rate: round2(policy === 'high_returner' ? 0.42 + r() * 0.2 : r() * 0.2),
    discount_usage_rate: round2(policy === 'deal_hunter' ? 0.62 + r() * 0.3 : r() * 0.5),
    points_balance: Math.floor(r() * 2400),
    points_expiring: Math.floor(r() * 400),
    points_expiry_date: '2026-11-15',
    tier: policy === 'vip' ? 'Gold' : pick(['Silver', 'Bronze']),
    open_cart: cart ? { category: cat, item: ITEMS[cat], value: Math.round(500 + r() * 3000), since: iso(new Date(NOW.getTime() - (20 + r() * 300) * 60_000)) } : null,
    last_offer_at: iso(new Date(NOW.getTime() - r() * 7 * 86_400_000)),
    offers_7d: Math.floor(r() * 3),
    active_coupon: null,
    suppressed_categories: i === 16 ? ['electronics'] : [],
    as_of: iso(NOW),
  }
})

// ---------- decisions ----------
const TRIGGERS: TriggerType[] = ['cart_abandoned', 'cart_abandoned', 'browse_interest', 'inactivity', 'points_expiry', 'festival', 'payday', 'welcome', 'lab', 'manual']
const OFFERS: Record<string, { label: string; cost: [number, number] }> = {
  OF_FREE_SHIP: { label: 'Free shipping', cost: [40, 80] },
  OF_PCT_10: { label: '10% off', cost: [90, 260] },
  OF_PCT_5: { label: '5% off', cost: [40, 140] },
  OF_FLAT_150: { label: '₹150 off', cost: [150, 150] },
  OF_POINTS_2X: { label: '2× points', cost: [20, 60] },
  OF_EARLY: { label: 'Early access', cost: [0, 0] },
  OF_NUDGE: { label: 'Cart reminder', cost: [0, 0] },
  OF_EXPRESS: { label: 'Free express delivery', cost: [70, 120] },
}
const POLICY_OFFERS: Record<PolicyName, string[]> = {
  vip: ['OF_EARLY', 'OF_POINTS_2X', 'OF_FREE_SHIP'], deal_hunter: ['OF_PCT_10', 'OF_FLAT_150'],
  at_risk: ['OF_PCT_10', 'OF_FREE_SHIP'], new_user: ['OF_FREE_SHIP', 'OF_PCT_10'],
  cart_abandoner: ['OF_NUDGE', 'OF_FREE_SHIP', 'OF_PCT_5'], window_shopper: ['OF_FREE_SHIP', 'OF_FLAT_150'],
  high_returner: ['OF_POINTS_2X'], sleeping_dog: [], dormant: ['OF_PCT_10'], default: ['OF_FREE_SHIP', 'OF_EXPRESS'],
}
const BLOCK_REASONS = ['Frequency cap: offer sent 31 h ago (min 48 h)', 'Quiet hours: 22:14 IST, queued for 09:00', 'Kill switch on', 'Customer paused offers (/pause)', 'Daily budget exhausted']

function statusFor(policy: PolicyName, trigger: TriggerType): [DecisionStatus, DecidedBy] {
  if (trigger === 'manual') return ['BLOCKED', 'BLOCKED_PREGATE']
  if (policy === 'sleeping_dog') return ['NO_OFFER', 'RULES_FALLBACK']
  const x = r()
  if (x < 0.1) return ['HELD_OUT', 'HOLDOUT']
  if (x < 0.2) return ['BLOCKED', 'BLOCKED_PREGATE']
  if (x < 0.27) return ['NO_OFFER', 'AGENT']
  if (x < 0.33) return ['QUEUED', 'AGENT']
  if (x < 0.5) return ['SENT', 'RULES_FALLBACK']
  if (x < 0.58) return ['SENT', 'AGENT_RETRY']
  return ['SENT', 'AGENT']
}

const OUTCOMES: Outcome[] = ['pending', 'pending', 'claimed', 'redeemed', 'ignored', 'declined', 'remind_later']

export const DECISIONS: DecisionLight[] = Array.from({ length: 50 }, (_, i) => {
  const c = CUSTOMERS[Math.floor(r() * CUSTOMERS.length)]
  const trigger = pick(TRIGGERS)
  const [status, decided_by] = statusFor(c.policy, trigger)
  const offers = POLICY_OFFERS[c.policy]
  const sends = status === 'SENT' || status === 'QUEUED'
  const offerId = sends && offers.length ? pick(offers) : null
  const o = offerId ? OFFERS[offerId] : null
  const cost = o ? Math.round(o.cost[0] + r() * (o.cost[1] - o.cost[0])) : 0
  const ts = new Date(NOW.getTime() - i * (14 + r() * 40) * 60_000)
  const cat = c.open_cart?.category ?? pick(CATS)
  const title =
    status === 'SENT' || status === 'QUEUED' ? `${status === 'SENT' ? 'Sent' : 'Queued'}: ${o?.label ?? 'Offer'} on ${cat.replace('_', ' ')}`
    : status === 'BLOCKED' ? `Blocked: ${pick(BLOCK_REASONS)}`
    : status === 'HELD_OUT' ? 'Held out: control group (10%)'
    : c.policy === 'sleeping_dog' ? 'No offer: negative uplift, would buy anyway or be put off'
    : 'No offer: expected profit below cost'
  return {
    id: `D${iso(ts).slice(0, 10).replaceAll('-', '')}-${String(9000 - i).padStart(4, '0')}`,
    ts: iso(ts),
    customer_id: c.customer_id,
    first_name: c.first_name,
    policy: c.policy,
    trigger,
    decided_by,
    status,
    final_offer_id: offerId,
    headline: offerId ? `${c.first_name}, ${o!.label.toLowerCase()} on your ${ITEMS[cat].toLowerCase()}` : null,
    cost,
    expected_incremental_profit: o ? Math.round(cost * (1.5 + r() * 3)) + 40 : 0,
    outcome: status === 'SENT' ? pick(OUTCOMES) : 'pending',
    explanation_title: title,
  }
})

// The contracts §5 example, completed into a full Decision.
const TRACE: ToolCall[] = [
  { name: 'get_profile', args: { customer_id: 'TG55512345' }, result_summary: 'cart_abandoner · churn 0.42 · cart ₹1,450 fashion', ms: 120 },
  { name: 'allowed_offers', args: {}, result_summary: '3 candidates: nudge, free shipping, 5% (locked until 24 h)', ms: 340 },
  { name: 'check_offer', args: { offer_id: 'OF_FREE_SHIP', params: { min_basket: 0 } }, result_summary: 'ok · 11/11 rules passed', ms: 410 },
]
const CHECKS: RuleCheck[] = RULES.slice(0, 11).map((rule) => ({
  rule_id: rule.id, description: rule.description, passed: true, severity: rule.severity, detail: 'within limit',
}))

export function fullDecision(light: DecisionLight): Decision {
  const isExample = light.id === example.id
  const base = example as unknown as Decision
  const profile = CUSTOMERS.find((c) => c.customer_id === light.customer_id) ?? { ...CUSTOMERS[4], customer_id: light.customer_id, first_name: 'Navpreet' }
  const blocked = light.status === 'BLOCKED'
  const checks = blocked
    ? [...CHECKS.slice(0, 9), { rule_id: 'G-FREQ', description: RULES[1].description, passed: false, severity: 'hard' as const, detail: light.explanation_title.replace(/^Blocked: /, '') }]
    : CHECKS
  const viaAgent = light.decided_by === 'AGENT' || light.decided_by === 'AGENT_RETRY'
  return {
    ...(isExample ? base : {
      ...base,
      ...light,
      trigger_meta: {},
      fallback_reason: light.decided_by === 'RULES_FALLBACK' ? 'Groq timeout after 20 s' : null,
      final_params: {},
      coupon_code: light.final_offer_id ? `${light.final_offer_id.slice(3, 7)}${light.first_name.slice(0, 3).toUpperCase()}${light.id.slice(-2)}` : null,
      message: light.headline,
      is_holdout: light.status === 'HELD_OUT',
      revenue: light.outcome === 'redeemed' ? 1890 : null,
      explanation: {
        ...base.explanation,
        title: light.explanation_title,
        why_customer: `${POLICY_LABEL[profile.policy]}; churn risk ${profile.churn_risk}; ${profile.recency_days} days since last visit; AOV ₹${profile.aov.toLocaleString('en-IN')}.`,
        why_offer: light.final_offer_id
          ? `Cheapest allowed step for this policy: ₹${light.cost} cost vs ₹${light.expected_incremental_profit} expected incremental profit.`
          : 'No candidate offer was expected to earn more than it costs.',
        rejected: light.final_offer_id ? ['10% off: above this policy’s cap'] : [],
        rules_line: `${checks.filter((c) => c.passed).length} passed · ${checks.filter((c) => !c.passed).length} violations · policy ${POLICY_LABEL[light.policy]}`,
        decided_by_line: viaAgent ? `Agent (${TRACE.length} tool calls, 1.6 s)` : light.decided_by === 'RULES_FALLBACK' ? 'Rules fallback: Groq timeout' : 'Pre-gate (no LLM call)',
      },
    }),
    profile_snapshot: profile,
    context: {
      now: light.ts, is_quiet_hours: false, is_payday_window: false, festival: 'karwa_chauth', festival_phase: 'build_up',
      days_to_festival: 5, hero_categories: ['ethnic_wear', 'jewellery'], delivery_cutoff: '2026-10-27', greeting: null,
      budget_left_today: 11800, budget_left_festival: 31200, pacing_factor: 1,
    },
    effective_policy: {
      customer_id: light.customer_id, policy: light.policy, festival: 'karwa_chauth', rules: RULES.slice(0, 11), limits: { max_pct: 10, min_gap_h: 48 },
      summary: RULES.slice(0, 4).map((x) => x.description), version_hash: 'a91f3c',
    },
    candidates: [],
    agent_trace: viaAgent ? TRACE : [],
    agent_output: null,
    validation: blocked ? null : { ok: true, checks, violations: [], adjusted_params: null },
  }
}

const exampleLight: DecisionLight = {
  id: example.id, ts: example.ts, customer_id: example.customer_id, first_name: 'Navpreet', policy: 'cart_abandoner',
  trigger: 'cart_abandoned', decided_by: 'AGENT', status: 'SENT', final_offer_id: example.final_offer_id,
  headline: example.headline, cost: example.cost, expected_incremental_profit: example.expected_incremental_profit,
  outcome: 'pending', explanation_title: example.explanation.title,
}
DECISIONS.splice(3, 0, exampleLight)

export function eventsFor(c: CustomerProfile): Event[] {
  return Array.from({ length: 6 }, (_, i) => {
    const cat = c.open_cart?.category ?? 'fashion'
    const type = (['session', 'view', 'view', 'add_to_cart', 'checkout_started', 'offer_received'] as const)[i]
    return {
      id: `E${c.customer_id}-${i}`, customer_id: c.customer_id, type,
      ts: iso(new Date(NOW.getTime() - (6 - i) * 37 * 60_000)), category: cat, item: ITEMS[cat],
      value: type === 'add_to_cart' ? (c.open_cart?.value ?? 999) : null, meta: {},
    }
  })
}

export const KPIS: Kpis = {
  sent_today: DECISIONS.filter((d) => d.status === 'SENT').length * 9,
  claim_rate: 0.184,
  incremental_revenue: 48210,
  budget_used_pct: 0.53,
  blocked_by_rules: DECISIONS.filter((d) => d.status === 'BLOCKED').length * 7,
  agent_share: 0.71,
  fallback_share: 0.29,
  margin_saved: 18640,
  deltas: { sent_today: 0.12, claim_rate: 0.021, incremental_revenue: 0.08, budget_used_pct: 0.04, blocked_by_rules: -0.15, margin_saved: 0.11 },
}
