# contracts.md: shared contracts (v1)

> This is the single source of truth for everything that crosses session boundaries.
> `backend/app/contracts.py` must mirror this file exactly. The **main session** owns both files.
> **Status:** v1 draft. It freezes at the Phase-0 gate. After that, changes go only through "Contract change requests" in `docs/sessions.md`, followed by a version bump here.

---

## 1. Enums
```python
Persona        = "loyal_vip" | "deal_hunter" | "at_risk_regular" | "new_user" | "dormant"
               | "window_shopper" | "cart_abandoner" | "festive_gifter" | "high_returner"
ResponseType   = "persuadable" | "sure_thing" | "lost_cause" | "sleeping_dog"     # hidden ground truth (generator only)
PolicyName     = "vip" | "deal_hunter" | "at_risk" | "new_user" | "cart_abandoner"
               | "window_shopper" | "high_returner" | "sleeping_dog" | "dormant" | "default"
Category       = "fashion" | "ethnic_wear" | "electronics" | "beauty" | "home_decor"
               | "kitchen" | "grocery" | "jewellery" | "gifting" | "winter_wear"
EventType      = "session" | "view" | "add_to_cart" | "checkout_started" | "purchase"
               | "return" | "wishlist" | "offer_received" | "offer_claimed" | "offer_declined"
TriggerType    = "cart_abandoned" | "browse_interest" | "inactivity" | "points_expiry"
               | "festival" | "payday" | "welcome" | "campaign" | "manual" | "lab"
OfferType      = "pct_off" | "flat_off" | "free_shipping" | "free_express" | "bonus_points"
               | "points_reminder" | "cart_nudge" | "early_access" | "bundle" | "gift_card" | "birthday"
RuleLayer      = "global" | "festival" | "persona" | "individual"
RuleType       = "margin_guard" | "discount_cap" | "frequency_cap" | "quiet_hours" | "budget"
               | "eligibility" | "exclusion" | "stacking" | "escalation_ladder" | "message"
               | "festival_restriction"
Severity       = "hard" | "soft"
DecidedBy      = "AGENT" | "AGENT_RETRY" | "RULES_FALLBACK" | "BLOCKED_PREGATE" | "HOLDOUT"
DecisionStatus = "SENT" | "QUEUED" | "NO_OFFER" | "BLOCKED" | "HELD_OUT" | "DRY_RUN"
Outcome        = "pending" | "claimed" | "redeemed" | "ignored" | "declined" | "remind_later"
FestivalPhase  = "teaser" | "build_up" | "last_minute" | "post"
Channel        = "dm" | "lab_group" | "shadow_channel" | "none"
```

## 2. Core models (Pydantic v2; money in whole ₹ as int)
```python
class Customer:            # stored row (generator → DB)
    id: str                       # "C000123"; real Telegram users: "TG<telegram_id>"
    first_name: str; age: int | None; gender: str | None
    city: str; city_tier: int     # 1|2|3
    signup_date: date; channel: str; device: str; preferred_payment: str   # upi|cod|card
    persona: Persona; response_type: ResponseType          # hidden, never shown to agent
    telegram_chat_id: int | None; is_lab_bot: bool = False
    opt_in_festivals: list[str] = []; opted_out: bool = False; paused_until: datetime | None
    is_holdout: bool              # assigned once, 10%

class CustomerProfile:     # Session A builds; everyone reads
    customer_id: str; first_name: str; city_tier: int
    persona: Persona; policy: PolicyName                    # policy = dynamic, recomputed per event
    rfm: dict                     # {"r":1-5,"f":1-5,"m":1-5,"segment":"Champions"}
    recency_days: int; orders_90d: int; aov: int; ltv: int
    churn_risk: float             # 0..1
    uplift: dict[OfferType, float]   # predicted incremental conversion prob per offer type
    price_sensitivity: float      # 0..1
    category_affinity: dict[Category, float]
    return_rate: float; discount_usage_rate: float
    points_balance: int; points_expiring: int; points_expiry_date: date | None; tier: str
    open_cart: dict | None        # {"category","item","value","since"}
    last_offer_at: datetime | None; offers_7d: int; active_coupon: str | None
    suppressed_categories: list[Category]
    as_of: datetime

class Event:
    id: str; customer_id: str; type: EventType; ts: datetime
    category: Category | None; item: str | None; value: int | None; meta: dict = {}

class Offer:               # catalogue row
    id: str; type: OfferType; name: str; description: str
    categories: list[Category] | None       # None = any
    param_schema: dict            # e.g. {"pct": {"min":5,"max":30}, "min_basket": {"min":0}}
    base_cost_model: str          # "pct*aov*p_redeem" etc.
    enabled: bool

class OfferCandidate:      # rules engine → agent
    offer_id: str; type: OfferType; category: Category | None
    allowed_params: dict          # ranges after all layers, e.g. {"pct":{"min":5,"max":10}}
    est_cost: int; est_incremental_profit: int
    rule_notes: list[str]         # plain English, e.g. "capped at 10% by Deal hunter policy"

class Rule:
    id: str; layer: RuleLayer; type: RuleType; severity: Severity
    conditions: dict              # {"policy":"deal_hunter"} | {"festival":"diwali","phase":"build_up"} | {"customer_id":...}
    params: dict                  # {"max_pct":10,"min_basket":999}
    enabled: bool; priority: int; version: int
    description: str              # generated by describe(), plain English
    updated_by: str; updated_at: datetime

class EffectivePolicy:
    customer_id: str; policy: PolicyName; festival: str | None
    rules: list[Rule]             # merged, tightest wins
    limits: dict                  # flattened numeric limits
    summary: list[str]            # plain-English bullet sentences
    version_hash: str

class RuleCheck:
    rule_id: str; description: str; passed: bool; severity: Severity; detail: str

class ValidationResult:
    ok: bool; checks: list[RuleCheck]; violations: list[RuleCheck]
    adjusted_params: dict | None  # never auto-applied by agent; fallback may use

class AgentReasoning:
    why_customer: str; why_offer: str
    alternatives_rejected: list[dict]   # [{"offer_id","reason"}]
    key_signals: list[str]; expected_impact_inr: int

class AgentOutput:         # strict JSON from LLM
    decision: Literal["SEND","NO_OFFER"]
    offer_id: str | None; params: dict; send_at: Literal["now"] | datetime
    headline: str; message: str          # message ≤ 280 chars
    reasoning: AgentReasoning; confidence: float

class ToolCall:
    name: str; args: dict; result_summary: str; ms: int

class Context:             # get_context()
    now: datetime; is_quiet_hours: bool; is_payday_window: bool
    festival: str | None; festival_phase: FestivalPhase | None; days_to_festival: int | None
    hero_categories: list[Category]; delivery_cutoff: date | None; greeting: str | None
    budget_left_today: int; budget_left_festival: int | None; pacing_factor: float  # 1.0 → shrinks caps

class Decision:            # the log row; THE central object
    id: str; ts: datetime; customer_id: str
    trigger: TriggerType; trigger_meta: dict
    profile_snapshot: CustomerProfile; context: Context
    effective_policy: EffectivePolicy; candidates: list[OfferCandidate]
    agent_trace: list[ToolCall]; agent_output: AgentOutput | None
    validation: ValidationResult | None
    decided_by: DecidedBy; status: DecisionStatus; fallback_reason: str | None
    final_offer_id: str | None; final_params: dict; coupon_code: str | None; expires_at: datetime | None
    headline: str | None; message: str | None
    cost: int; expected_incremental_profit: int
    channel: Channel; is_holdout: bool
    outcome: Outcome; outcome_at: datetime | None; revenue: int | None
    explanation: "Explanation"
    llm_tokens: int; latency_ms: int

class Explanation:
    title: str            # "Sent: Free shipping on Fashion (exp. 25 Oct)"
    why_customer: str; why_offer: str; rejected: list[str]
    rules_line: str       # "11 passed · 0 violations · policy Cart abandoner v3"
    decided_by_line: str  # "Agent (3 tool calls, 1.8 s)" | "Rules fallback — Groq timeout"
    telegram_text: str    # compact version for /why

class Festival:
    id: str; name: str; date: date; region: list[str] | None
    phases: dict[FestivalPhase, tuple[int,int]]   # day offsets, e.g. {"teaser":(-14,-7)}
    hero_categories: list[Category]; greeting: str | None; needs_opt_in: bool
    restricted_promos: list[str]; budget: int; strategy: dict[FestivalPhase, str]
    delivery_days_by_tier: dict[int,int]

class RealismStats:        # Session A → dashboard
    pareto_top20_share: float; cart_abandon_rate: float; funnel: dict
    retention_cohorts: list[dict]; aov_by_category: dict; return_rate_by_category: dict
    seasonality_daily: list[dict]; benchmarks: dict   # target ranges per stat

class ExperimentStats:
    treatment: dict; control: dict          # {"n","conv_rate","revenue","cost"}
    incremental_revenue: int; incremental_profit: int; margin_saved_sure_things: int
    uplift_by_policy: list[dict]; roi_by_offer_type: list[dict]; qini: list[dict] | None
    festival_vs_baseline: list[dict]

class Kpis:
    sent_today: int; claim_rate: float; incremental_revenue: int; budget_used_pct: float
    blocked_by_rules: int; agent_share: float; fallback_share: float; margin_saved: int
    deltas: dict   # vs yesterday, for ▲▼
```

## 3. Python interfaces between sessions (through `app.ports`; stubbed in `app.stubs`)
```python
# Session A provides
data.seed.run(n_customers: int = 5000, seed: int = 42) -> None
data.festivals.FESTIVALS: list[Festival]
scoring.profile.build_profile(customer_id: str, now: datetime) -> CustomerProfile
scoring.profile.assign_policy(profile: CustomerProfile) -> PolicyName
scoring.uplift.predict(profile: CustomerProfile, offer_type: OfferType) -> float
scoring.impact.estimate(profile, offer_type, params, category) -> tuple[int, int]   # (cost, incremental_profit)
scoring.realism.compute() -> RealismStats
scoring.experiments.compute(start: date, end: date) -> ExperimentStats
data.onboarding.create_profile_from_answers(telegram_id: int, first_name: str, answers: dict) -> Customer

# Session B provides
rules.engine.effective_policy(profile, context) -> EffectivePolicy
rules.engine.allowed_offers(profile, context, catalogue) -> list[OfferCandidate]
rules.engine.evaluate(profile, context, offer_id, params, message: str | None) -> ValidationResult
rules.describe.describe(rule: Rule) -> str
rules.preview.impact(rule: Rule) -> dict      # {"customers_affected","budget_delta","examples"}
agent.context.get_context(now: datetime) -> Context
agent.harness.decide(customer_id: str, trigger: TriggerType, trigger_meta: dict = {},
                     *, dry_run: bool = False, now: datetime | None = None) -> Decision
agent.explainer.explain(decision: Decision) -> Explanation
agent.digest.daily(day: date) -> str

# Session C provides
bot.sender.deliver(decision: Decision, channel: Channel) -> None
bot.app.build_application() -> telegram.ext.Application
lab.runner.run_rounds(n: int) -> list[Decision]

# Main provides
db.get_session(); config.now(); config.settings; api routers; scheduler jobs
```

## 4. REST API (main session builds it; Session D consumes it, mocked under `frontend/src/mocks/`)
Base URL is `VITE_API_URL`. Writes require the header `X-Admin-Passcode`. Everything is JSON.

| Method | Path | Returns |
|---|---|---|
| GET | `/health` | `{"ok":true,"version":"0.1"}` |
| GET | `/api/kpis?day=` | `Kpis` |
| GET | `/api/decisions?status=&decided_by=&policy=&trigger=&q=&limit=&cursor=` | `{"items": Decision[] (light), "next": str\|null}` |
| GET | `/api/decisions/{id}` | `Decision` (full, with trace + explanation) |
| GET | `/api/decisions/stream` | SSE of new Decision (light) for the live feed |
| GET | `/api/customers?q=&policy=&limit=&cursor=` | `{"items": CustomerProfile[], "next"}` |
| GET | `/api/customers/{id}` | `{"profile": CustomerProfile, "events": Event[], "decisions": Decision[] (light)}` |
| POST | `/api/customers/{id}/simulate` `{trigger, meta}` | `Decision` |
| POST | `/api/playground/run` `{customer_id, trigger, meta, now?}` | `Decision` (dry_run) |
| GET | `/api/rules?layer=` | `Rule[]` |
| PATCH | `/api/rules/{id}` `{params?, enabled?, priority?}` | `Rule` (new version) |
| POST | `/api/rules/preview` `{rule}` | `{"customers_affected", "budget_delta", "examples": [...]}` |
| GET | `/api/rules/{id}/versions` | `Rule[]` |
| POST | `/api/rules/{id}/revert/{version}` | `Rule` |
| GET / PATCH | `/api/offers`, `/api/offers/{id}` | `Offer[]` / `Offer` |
| GET / PATCH | `/api/festivals`, `/api/festivals/{id}` | `Festival[]` / `Festival` |
| POST | `/api/campaigns/dry-run` `{policy?, festival?, offer_ids?, budget, limit}` | `{"rows": Decision[] (light), "totals": {...}}` |
| GET | `/api/experiments?start=&end=` | `ExperimentStats` |
| GET | `/api/realism` | `RealismStats` |
| GET | `/api/digest?day=` | `{"day","text","generated_by"}` |
| GET / POST | `/api/settings/killswitch` `{on: bool}` | `{"on": bool, "changed_at"}` |
| GET | `/api/budget` | `{"today_used","today_cap","festival": {...}}` |
| GET | `/api/meta` | `{"bot_username","lab_group_link","now","demo_time_override"}` |

A **light decision** is the `DecisionLight` model in `contracts.py`. It contains `id, ts, customer_id, first_name, policy, trigger, decided_by, status, final_offer_id, headline, cost, expected_incremental_profit, outcome, explanation_title`. Build one with `DecisionLight.from_decision(d)`.

## 5. Example Decision (use as mock fixture)
```json
{
  "id": "D20261023-0042", "ts": "2026-10-23T19:42:10+05:30", "customer_id": "TG55512345",
  "trigger": "cart_abandoned", "trigger_meta": {"category": "fashion", "item": "Cotton Kurta", "value": 1450, "minutes": 35},
  "decided_by": "AGENT", "status": "SENT", "fallback_reason": null,
  "final_offer_id": "OF_FREE_SHIP", "final_params": {"min_basket": 0},
  "coupon_code": "SHIPNAV7Q", "expires_at": "2026-10-25T23:59:00+05:30",
  "headline": "Your kurta is waiting, shipping's on us",
  "message": "Hi Navpreet! The Cotton Kurta (₹1,450) is still in your cart. Free shipping till 25 Oct, code SHIPNAV7Q.",
  "cost": 60, "expected_incremental_profit": 210, "channel": "dm", "is_holdout": false, "outcome": "pending",
  "explanation": {
    "title": "Sent: Free shipping on Fashion (exp. 25 Oct)",
    "why_customer": "Cart ₹1,450 open 35 min; churn risk 0.42; uplift 0.18 (persuadable).",
    "why_offer": "Cheapest step on the cart ladder; ₹60 cost vs ₹210 expected incremental profit.",
    "rejected": ["10% off: exceeds cart-abandoner ladder before 24 h", "2× points: low points engagement"],
    "rules_line": "11 passed · 0 violations · policy Cart abandoner v3",
    "decided_by_line": "Agent (3 tool calls, 1.8 s)",
    "telegram_text": "Why you got this: your kurta is still in the cart, so free shipping is the smallest nudge that helps. 11 rules checked ✓"
  },
  "llm_tokens": 1840, "latency_ms": 1800
}
```

## 6. Changelog
- **v1** (22 Oct): initial draft.
