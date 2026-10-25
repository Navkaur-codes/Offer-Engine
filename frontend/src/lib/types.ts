// Mirrors docs/contracts.md v1 (§1 enums, §2 models, §4 REST shapes). Money is whole ₹.

export type Persona =
  | 'loyal_vip' | 'deal_hunter' | 'at_risk_regular' | 'new_user' | 'dormant'
  | 'window_shopper' | 'cart_abandoner' | 'festive_gifter' | 'high_returner'
export type PolicyName =
  | 'vip' | 'deal_hunter' | 'at_risk' | 'new_user' | 'cart_abandoner'
  | 'window_shopper' | 'high_returner' | 'sleeping_dog' | 'dormant' | 'default'
export type Category =
  | 'fashion' | 'ethnic_wear' | 'electronics' | 'beauty' | 'home_decor'
  | 'kitchen' | 'grocery' | 'jewellery' | 'gifting' | 'winter_wear'
export type EventType =
  | 'session' | 'view' | 'add_to_cart' | 'checkout_started' | 'purchase'
  | 'return' | 'wishlist' | 'offer_received' | 'offer_claimed' | 'offer_declined'
export type TriggerType =
  | 'cart_abandoned' | 'browse_interest' | 'inactivity' | 'points_expiry'
  | 'festival' | 'payday' | 'welcome' | 'campaign' | 'manual' | 'lab'
export type OfferType =
  | 'pct_off' | 'flat_off' | 'free_shipping' | 'free_express' | 'bonus_points'
  | 'points_reminder' | 'cart_nudge' | 'early_access' | 'bundle' | 'gift_card' | 'birthday'
export type RuleLayer = 'global' | 'festival' | 'persona' | 'individual'
export type RuleType =
  | 'margin_guard' | 'discount_cap' | 'frequency_cap' | 'quiet_hours' | 'budget'
  | 'eligibility' | 'exclusion' | 'stacking' | 'escalation_ladder' | 'message'
  | 'festival_restriction'
export type Severity = 'hard' | 'soft'
export type DecidedBy = 'AGENT' | 'AGENT_RETRY' | 'RULES_FALLBACK' | 'BLOCKED_PREGATE' | 'HOLDOUT'
export type DecisionStatus = 'SENT' | 'QUEUED' | 'NO_OFFER' | 'BLOCKED' | 'HELD_OUT' | 'DRY_RUN'
export type Outcome = 'pending' | 'claimed' | 'redeemed' | 'ignored' | 'declined' | 'remind_later'
export type FestivalPhase = 'teaser' | 'build_up' | 'last_minute' | 'post'
export type Channel = 'dm' | 'lab_group' | 'shadow_channel' | 'none'

/** ISO-8601 string with offset, e.g. "2026-10-23T19:42:10+05:30". */
export type IsoDateTime = string
/** ISO date, e.g. "2026-10-23". */
export type IsoDate = string
type Json = Record<string, unknown>

export interface CustomerProfile {
  customer_id: string
  first_name: string
  city_tier: number
  persona: Persona
  policy: PolicyName
  rfm: { r: number; f: number; m: number; segment: string }
  recency_days: number
  orders_90d: number
  aov: number
  ltv: number
  churn_risk: number
  uplift: Partial<Record<OfferType, number>>
  price_sensitivity: number
  category_affinity: Partial<Record<Category, number>>
  return_rate: number
  discount_usage_rate: number
  points_balance: number
  points_expiring: number
  points_expiry_date: IsoDate | null
  tier: string
  open_cart: { category: Category; item: string; value: number; since: IsoDateTime } | null
  last_offer_at: IsoDateTime | null
  offers_7d: number
  active_coupon: string | null
  suppressed_categories: Category[]
  as_of: IsoDateTime
}

export interface Event {
  id: string
  customer_id: string
  type: EventType
  ts: IsoDateTime
  category: Category | null
  item: string | null
  value: number | null
  meta: Json
}

export interface Offer {
  id: string
  type: OfferType
  name: string
  description: string
  categories: Category[] | null
  param_schema: Json
  base_cost_model: string
  enabled: boolean
}

export interface OfferCandidate {
  offer_id: string
  type: OfferType
  category: Category | null
  allowed_params: Json
  est_cost: number
  est_incremental_profit: number
  rule_notes: string[]
}

export interface Rule {
  id: string
  layer: RuleLayer
  type: RuleType
  severity: Severity
  conditions: Json
  params: Json
  enabled: boolean
  priority: number
  version: number
  description: string
  updated_by: string
  updated_at: IsoDateTime
}

export interface EffectivePolicy {
  customer_id: string
  policy: PolicyName
  festival: string | null
  rules: Rule[]
  limits: Json
  summary: string[]
  version_hash: string
}

export interface RuleCheck {
  rule_id: string
  description: string
  passed: boolean
  severity: Severity
  detail: string
}

export interface ValidationResult {
  ok: boolean
  checks: RuleCheck[]
  violations: RuleCheck[]
  adjusted_params: Json | null
}

export interface AgentReasoning {
  why_customer: string
  why_offer: string
  alternatives_rejected: { offer_id: string; reason: string }[]
  key_signals: string[]
  expected_impact_inr: number
}

export interface AgentOutput {
  decision: 'SEND' | 'NO_OFFER'
  offer_id: string | null
  params: Json
  send_at: 'now' | IsoDateTime
  headline: string
  message: string
  reasoning: AgentReasoning
  confidence: number
}

export interface ToolCall {
  name: string
  args: Json
  result_summary: string
  ms: number
}

export interface Context {
  now: IsoDateTime
  is_quiet_hours: boolean
  is_payday_window: boolean
  festival: string | null
  festival_phase: FestivalPhase | null
  days_to_festival: number | null
  hero_categories: Category[]
  delivery_cutoff: IsoDate | null
  greeting: string | null
  budget_left_today: number
  budget_left_festival: number | null
  pacing_factor: number
}

export interface Explanation {
  title: string
  why_customer: string
  why_offer: string
  rejected: string[]
  rules_line: string
  decided_by_line: string
  telegram_text: string
}

export interface Decision {
  id: string
  ts: IsoDateTime
  customer_id: string
  trigger: TriggerType
  trigger_meta: Json
  profile_snapshot: CustomerProfile
  context: Context
  effective_policy: EffectivePolicy
  candidates: OfferCandidate[]
  agent_trace: ToolCall[]
  agent_output: AgentOutput | null
  validation: ValidationResult | null
  decided_by: DecidedBy
  status: DecisionStatus
  fallback_reason: string | null
  final_offer_id: string | null
  final_params: Json
  coupon_code: string | null
  expires_at: IsoDateTime | null
  headline: string | null
  message: string | null
  cost: number
  expected_incremental_profit: number
  channel: Channel
  is_holdout: boolean
  outcome: Outcome
  outcome_at: IsoDateTime | null
  revenue: number | null
  explanation: Explanation
  llm_tokens: number
  latency_ms: number
}

/** contracts.md §4 "light decision" (DecisionLight in contracts.py). */
export interface DecisionLight {
  id: string
  ts: IsoDateTime
  customer_id: string
  first_name: string
  policy: PolicyName
  trigger: TriggerType
  decided_by: DecidedBy
  status: DecisionStatus
  final_offer_id: string | null
  headline: string | null
  cost: number
  expected_incremental_profit: number
  outcome: Outcome
  explanation_title: string
  /** v1.1: festival active at decision time, e.g. "diwali_2026", or null. */
  festival: string | null
}

export interface Festival {
  id: string
  name: string
  date: IsoDate
  region: string[] | null
  phases: Partial<Record<FestivalPhase, [number, number]>>
  hero_categories: Category[]
  greeting: string | null
  needs_opt_in: boolean
  restricted_promos: string[]
  budget: number
  strategy: Partial<Record<FestivalPhase, string>>
  delivery_days_by_tier: Record<string, number>
}

/** One benchmark row as Session A's realism_compute() sends it. */
export interface Benchmark {
  min: number
  max: number
  value: number
  ok: boolean
  source: string
}
export interface RealismStats {
  pareto_top20_share: number
  cart_abandon_rate: number
  funnel: Partial<Record<EventType, number>>
  /** {cohort: "2025-10", size, m1..m6: share still buying}. */
  retention_cohorts: ({ cohort: string; size: number } & Record<string, number | string>)[]
  aov_by_category: Partial<Record<Category, number>>
  return_rate_by_category: Partial<Record<Category, number>>
  seasonality_daily: { date: IsoDate; revenue: number }[]
  benchmarks: Record<string, Benchmark>
}

export interface ArmStats {
  n: number
  conv_rate: number
  revenue: number
  cost: number
  revenue_per_customer?: number
}

// Row shapes inside ExperimentStats' list[dict] fields, as Session A's experiments_compute() sends them.
export interface PolicyUplift {
  policy: PolicyName
  n_treated: number
  n_control: number
  treated_conv: number
  control_conv: number
  uplift: number
}
export interface OfferRoi {
  type: OfferType
  n: number
  incremental_revenue: number
  cost: number
  incremental_profit: number
  roi: number
}
export interface QiniPoint {
  targeted: number
  model: number
  random: number
}
export interface FestivalLift {
  festival: string
  id: string
  date: IsoDate
  revenue_per_day: number
  baseline_per_day: number
  lift: number
}

export interface ExperimentStats {
  treatment: ArmStats
  control: ArmStats
  incremental_revenue: number
  incremental_profit: number
  margin_saved_sure_things: number
  uplift_by_policy: PolicyUplift[]
  roi_by_offer_type: OfferRoi[]
  qini: QiniPoint[] | null
  festival_vs_baseline: FestivalLift[]
}

export interface Kpis {
  sent_today: number
  claim_rate: number
  incremental_revenue: number
  budget_used_pct: number
  blocked_by_rules: number
  agent_share: number
  fallback_share: number
  margin_saved: number
  /** v1.1: fractional change vs yesterday per KPI field (0.12 = +12%); null = no arrow. */
  deltas: Partial<Record<Exclude<keyof Kpis, 'deltas' | 'agent_share' | 'fallback_share'>, number | null>>
}

// ---- REST envelopes (contracts.md §4) ----
export interface Page<T> {
  items: T[]
  next: string | null
}
export interface LlmMeter {
  used: number
  limit: number
  model: string
}
export interface Health {
  ok: boolean
  version: string
  /** Main's extra (not in contracts §4): per-day LLM token budget from agent/budget.py. */
  llm_budget?: { agent: LlmMeter; fast: LlmMeter; mode: '70b' | '8b' | 'rules' }
}
export interface CustomerDetail {
  profile: CustomerProfile
  events: Event[]
  decisions: DecisionLight[]
}
export interface RuleImpact {
  customers_affected: number
  budget_delta: number
  /** Contract leaves the item shape open: customer IDs or small objects. */
  examples: unknown[]
}
/** GET /api/scheduler (main, outside contracts §4). */
export interface SchedulerStatus {
  running: boolean
  next_runs: Record<string, IsoDateTime | null>
}
export interface CampaignDryRun {
  rows: DecisionLight[]
  /** Contract says `{...}`; these are the keys the API sends (over_budget is Main's extra). */
  totals: {
    customers: number
    would_send: number
    no_offer: number
    blocked: number
    over_budget?: number
    cost: number
    expected_incremental_profit: number
  }
}
export interface Digest {
  day: IsoDate
  text: string
  generated_by: string
}
export interface KillSwitch {
  on: boolean
  changed_at: IsoDateTime | null
}
export interface Budget {
  today_used: number
  today_cap: number
  /** Contract says `{...}`; the API sends the active festival and its remaining pool. */
  festival: { name: string; phase: FestivalPhase | null; days_to: number | null; budget_left: number | null } | null
}
export interface Meta {
  bot_username: string
  lab_group_link: string | null
  now: IsoDateTime
  demo_time_override: IsoDateTime | null
}

export interface DecisionFilters {
  status?: DecisionStatus
  decided_by?: DecidedBy
  policy?: PolicyName
  trigger?: TriggerType
  /** v1.1: festival key ("diwali") or id ("diwali_2026"). */
  festival?: string
  q?: string
  limit?: number
  cursor?: string
}
