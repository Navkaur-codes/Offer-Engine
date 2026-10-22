"""Shared contracts (v1). Mirrors docs/contracts.md exactly. Owned by the main session.

Every object that crosses a session boundary is one of these models. Money is whole rupees (int).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CONTRACT_VERSION = "v1"

# ---------------------------------------------------------------- enums
Persona = Literal[
    "loyal_vip", "deal_hunter", "at_risk_regular", "new_user", "dormant",
    "window_shopper", "cart_abandoner", "festive_gifter", "high_returner",
]
ResponseType = Literal["persuadable", "sure_thing", "lost_cause", "sleeping_dog"]
PolicyName = Literal[
    "vip", "deal_hunter", "at_risk", "new_user", "cart_abandoner",
    "window_shopper", "high_returner", "sleeping_dog", "dormant", "default",
]
Category = Literal[
    "fashion", "ethnic_wear", "electronics", "beauty", "home_decor",
    "kitchen", "grocery", "jewellery", "gifting", "winter_wear",
]
EventType = Literal[
    "session", "view", "add_to_cart", "checkout_started", "purchase",
    "return", "wishlist", "offer_received", "offer_claimed", "offer_declined",
]
TriggerType = Literal[
    "cart_abandoned", "browse_interest", "inactivity", "points_expiry",
    "festival", "payday", "welcome", "campaign", "manual", "lab",
]
OfferType = Literal[
    "pct_off", "flat_off", "free_shipping", "free_express", "bonus_points",
    "points_reminder", "cart_nudge", "early_access", "bundle", "gift_card", "birthday",
]
RuleLayer = Literal["global", "festival", "persona", "individual"]
RuleType = Literal[
    "margin_guard", "discount_cap", "frequency_cap", "quiet_hours", "budget",
    "eligibility", "exclusion", "stacking", "escalation_ladder", "message",
    "festival_restriction",
]
Severity = Literal["hard", "soft"]
DecidedBy = Literal["AGENT", "AGENT_RETRY", "RULES_FALLBACK", "BLOCKED_PREGATE", "HOLDOUT"]
DecisionStatus = Literal["SENT", "QUEUED", "NO_OFFER", "BLOCKED", "HELD_OUT", "DRY_RUN"]
Outcome = Literal["pending", "claimed", "redeemed", "ignored", "declined", "remind_later"]
FestivalPhase = Literal["teaser", "build_up", "last_minute", "post"]
Channel = Literal["dm", "lab_group", "shadow_channel", "none"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------- core models
class Customer(Contract):
    id: str  # "C000123"; real Telegram users: "TG<telegram_id>"
    first_name: str
    age: int | None = None
    gender: str | None = None
    city: str
    city_tier: int  # 1 | 2 | 3
    signup_date: date
    channel: str
    device: str
    preferred_payment: str  # upi | cod | card
    persona: Persona
    response_type: ResponseType  # hidden ground truth, never shown to the agent
    telegram_chat_id: int | None = None
    is_lab_bot: bool = False
    opt_in_festivals: list[str] = Field(default_factory=list)
    opted_out: bool = False
    paused_until: datetime | None = None
    is_holdout: bool = False


class CustomerProfile(Contract):
    customer_id: str
    first_name: str
    city_tier: int
    persona: Persona
    policy: PolicyName  # dynamic, recomputed per event
    rfm: dict  # {"r":1-5,"f":1-5,"m":1-5,"segment":"Champions"}
    recency_days: int
    orders_90d: int
    aov: int
    ltv: int
    churn_risk: float
    uplift: dict[OfferType, float]
    price_sensitivity: float
    category_affinity: dict[Category, float]
    return_rate: float
    discount_usage_rate: float
    points_balance: int
    points_expiring: int
    points_expiry_date: date | None = None
    tier: str
    open_cart: dict | None = None  # {"category","item","value","since"}
    last_offer_at: datetime | None = None
    offers_7d: int = 0
    active_coupon: str | None = None
    suppressed_categories: list[Category] = Field(default_factory=list)
    as_of: datetime


class Event(Contract):
    id: str
    customer_id: str
    type: EventType
    ts: datetime
    category: Category | None = None
    item: str | None = None
    value: int | None = None
    meta: dict = Field(default_factory=dict)


class Offer(Contract):
    id: str
    type: OfferType
    name: str
    description: str
    categories: list[Category] | None = None  # None = any
    param_schema: dict  # e.g. {"pct": {"min":5,"max":30}, "min_basket": {"min":0}}
    base_cost_model: str
    enabled: bool = True


class OfferCandidate(Contract):
    offer_id: str
    type: OfferType
    category: Category | None = None
    allowed_params: dict
    est_cost: int
    est_incremental_profit: int
    rule_notes: list[str] = Field(default_factory=list)


class Rule(Contract):
    id: str
    layer: RuleLayer
    type: RuleType
    severity: Severity
    conditions: dict
    params: dict
    enabled: bool = True
    priority: int = 100
    version: int = 1
    description: str = ""
    updated_by: str = "system"
    updated_at: datetime


class EffectivePolicy(Contract):
    customer_id: str
    policy: PolicyName
    festival: str | None = None
    rules: list[Rule]
    limits: dict
    summary: list[str]
    version_hash: str


class RuleCheck(Contract):
    rule_id: str
    description: str
    passed: bool
    severity: Severity
    detail: str = ""


class ValidationResult(Contract):
    ok: bool
    checks: list[RuleCheck]
    violations: list[RuleCheck]
    adjusted_params: dict | None = None


class AgentReasoning(Contract):
    why_customer: str
    why_offer: str
    alternatives_rejected: list[dict] = Field(default_factory=list)  # [{"offer_id","reason"}]
    key_signals: list[str] = Field(default_factory=list)
    expected_impact_inr: int = 0


class AgentOutput(Contract):
    decision: Literal["SEND", "NO_OFFER"]
    offer_id: str | None = None
    params: dict = Field(default_factory=dict)
    send_at: Literal["now"] | datetime = "now"
    headline: str = ""
    message: str = Field(default="", max_length=280)
    reasoning: AgentReasoning
    confidence: float = Field(ge=0, le=1)


class ToolCall(Contract):
    name: str
    args: dict
    result_summary: str
    ms: int


class Context(Contract):
    now: datetime
    is_quiet_hours: bool
    is_payday_window: bool
    festival: str | None = None
    festival_phase: FestivalPhase | None = None
    days_to_festival: int | None = None
    hero_categories: list[Category] = Field(default_factory=list)
    delivery_cutoff: date | None = None
    greeting: str | None = None
    budget_left_today: int
    budget_left_festival: int | None = None
    pacing_factor: float = 1.0


class Explanation(Contract):
    title: str
    why_customer: str
    why_offer: str
    rejected: list[str] = Field(default_factory=list)
    rules_line: str
    decided_by_line: str
    telegram_text: str


class Decision(Contract):
    id: str
    ts: datetime
    customer_id: str
    trigger: TriggerType
    trigger_meta: dict = Field(default_factory=dict)
    profile_snapshot: CustomerProfile
    context: Context
    effective_policy: EffectivePolicy
    candidates: list[OfferCandidate] = Field(default_factory=list)
    agent_trace: list[ToolCall] = Field(default_factory=list)
    agent_output: AgentOutput | None = None
    validation: ValidationResult | None = None
    decided_by: DecidedBy
    status: DecisionStatus
    fallback_reason: str | None = None
    final_offer_id: str | None = None
    final_params: dict = Field(default_factory=dict)
    coupon_code: str | None = None
    expires_at: datetime | None = None
    headline: str | None = None
    message: str | None = None
    cost: int = 0
    expected_incremental_profit: int = 0
    channel: Channel = "none"
    is_holdout: bool = False
    outcome: Outcome = "pending"
    outcome_at: datetime | None = None
    revenue: int | None = None
    explanation: Explanation
    llm_tokens: int = 0
    latency_ms: int = 0


class DecisionLight(Contract):
    """List-view shape of a Decision (contracts.md §4)."""

    id: str
    ts: datetime
    customer_id: str
    first_name: str
    policy: PolicyName
    trigger: TriggerType
    decided_by: DecidedBy
    status: DecisionStatus
    final_offer_id: str | None = None
    headline: str | None = None
    cost: int = 0
    expected_incremental_profit: int = 0
    outcome: Outcome = "pending"
    explanation_title: str

    @classmethod
    def from_decision(cls, d: Decision) -> DecisionLight:
        return cls(
            id=d.id, ts=d.ts, customer_id=d.customer_id, first_name=d.profile_snapshot.first_name,
            policy=d.profile_snapshot.policy, trigger=d.trigger, decided_by=d.decided_by, status=d.status,
            final_offer_id=d.final_offer_id, headline=d.headline, cost=d.cost,
            expected_incremental_profit=d.expected_incremental_profit, outcome=d.outcome,
            explanation_title=d.explanation.title,
        )


class Festival(Contract):
    id: str
    name: str
    date: date
    region: list[str] | None = None
    phases: dict[FestivalPhase, tuple[int, int]]  # day offsets, e.g. {"teaser": (-14, -7)}
    hero_categories: list[Category]
    greeting: str | None = None
    needs_opt_in: bool = True
    restricted_promos: list[str] = Field(default_factory=list)
    budget: int
    strategy: dict[FestivalPhase, str] = Field(default_factory=dict)
    delivery_days_by_tier: dict[int, int] = Field(default_factory=lambda: {1: 2, 2: 3, 3: 5})


class RealismStats(Contract):
    pareto_top20_share: float
    cart_abandon_rate: float
    funnel: dict
    retention_cohorts: list[dict]
    aov_by_category: dict
    return_rate_by_category: dict
    seasonality_daily: list[dict]
    benchmarks: dict


class ExperimentStats(Contract):
    treatment: dict
    control: dict
    incremental_revenue: int
    incremental_profit: int
    margin_saved_sure_things: int
    uplift_by_policy: list[dict]
    roi_by_offer_type: list[dict]
    qini: list[dict] | None = None
    festival_vs_baseline: list[dict] = Field(default_factory=list)


class Kpis(Contract):
    sent_today: int
    claim_rate: float
    incremental_revenue: int
    budget_used_pct: float
    blocked_by_rules: int
    agent_share: float
    fallback_share: float
    margin_saved: int
    deltas: dict = Field(default_factory=dict)
