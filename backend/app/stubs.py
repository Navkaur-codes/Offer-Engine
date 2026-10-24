"""Fixture-based stand-ins for every cross-session function (see app.ports).

They return realistic, contract-valid data so each session can build and test before the others merge.
Behaviour is deterministic by input, never random, so tests stay stable:
  - policy "vip"                → NO_OFFER (sure-thing, margin protected)
  - trigger "manual"            → BLOCKED (frequency cap)
  - opted-out / paused customer → BLOCKED (consent)
  - anything else               → SENT with the policy's typical offer
"""

from __future__ import annotations

import hashlib
import logging
from datetime import date, datetime, timedelta

from app.config import IST
from app.config import now as clock
from app.contracts import (
    AgentOutput,
    AgentReasoning,
    Context,
    Customer,
    CustomerProfile,
    Decision,
    EffectivePolicy,
    ExperimentStats,
    Explanation,
    Festival,
    Offer,
    OfferCandidate,
    PolicyName,
    RealismStats,
    Rule,
    RuleCheck,
    ToolCall,
    TriggerType,
    ValidationResult,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------- fixture profiles
_BASE_UPLIFT = {
    "pct_off": 0.08,
    "flat_off": 0.06,
    "free_shipping": 0.10,
    "bonus_points": 0.03,
    "cart_nudge": 0.05,
    "early_access": 0.01,
    "points_reminder": 0.02,
}


def _profile(customer_id: str, first_name: str, persona: str, policy: str, **kw) -> CustomerProfile:
    base = dict(
        customer_id=customer_id,
        first_name=first_name,
        city_tier=2,
        persona=persona,
        policy=policy,
        rfm={"r": 3, "f": 3, "m": 3, "segment": "Potential"},
        recency_days=12,
        orders_90d=2,
        aov=1450,
        ltv=8700,
        churn_risk=0.3,
        uplift=dict(_BASE_UPLIFT),
        price_sensitivity=0.5,
        category_affinity={"fashion": 0.5, "beauty": 0.2, "electronics": 0.1},
        return_rate=0.1,
        discount_usage_rate=0.3,
        points_balance=420,
        points_expiring=0,
        tier="Silver",
        as_of=datetime(2026, 10, 22, 19, 0, tzinfo=IST),
    )
    base.update(kw)
    return CustomerProfile(**base)


PROFILES: dict[str, CustomerProfile] = {
    p.customer_id: p
    for p in [
        _profile(
            "C000001",
            "Navpreet",
            "cart_abandoner",
            "cart_abandoner",
            open_cart={
                "category": "fashion",
                "item": "Cotton Kurta",
                "value": 1450,
                "since": "2026-10-22T18:25:00+05:30",
            },
            uplift={**_BASE_UPLIFT, "free_shipping": 0.18},
            churn_risk=0.42,
        ),
        _profile(
            "C000002",
            "Priya",
            "deal_hunter",
            "deal_hunter",
            discount_usage_rate=0.72,
            price_sensitivity=0.85,
            uplift={**_BASE_UPLIFT, "pct_off": 0.16},
            aov=1199,
            category_affinity={"ethnic_wear": 0.6, "beauty": 0.3},
        ),
        _profile(
            "C000003",
            "Arjun",
            "loyal_vip",
            "vip",
            city_tier=1,
            recency_days=4,
            orders_90d=9,
            aov=4200,
            ltv=98000,
            churn_risk=0.05,
            tier="Gold",
            points_balance=6400,
            rfm={"r": 5, "f": 5, "m": 5, "segment": "Champions"},
            uplift={k: 0.005 for k in _BASE_UPLIFT},
            category_affinity={"electronics": 0.7},
        ),
        _profile(
            "C000004",
            "Gurpreet",
            "at_risk_regular",
            "at_risk",
            recency_days=74,
            orders_90d=0,
            churn_risk=0.71,
            ltv=23000,
            aov=2100,
            rfm={"r": 1, "f": 4, "m": 4, "segment": "At Risk"},
            uplift={**_BASE_UPLIFT, "pct_off": 0.14},
            category_affinity={"home_decor": 0.5},
        ),
        _profile(
            "C000005",
            "Simran",
            "new_user",
            "new_user",
            city_tier=3,
            recency_days=6,
            orders_90d=1,
            ltv=899,
            aov=899,
            rfm={"r": 4, "f": 1, "m": 1, "segment": "New"},
            points_balance=50,
            tier="Bronze",
            category_affinity={"beauty": 0.6},
        ),
    ]
}

_POLICY_OFFER: dict[str, tuple[str, str, dict, str | None, int, int]] = {
    # policy: (offer_id, type, params, category, cost, incremental profit)
    "cart_abandoner": ("OF_FREE_SHIP", "free_shipping", {"min_basket": 0}, "fashion", 60, 210),
    "deal_hunter": ("OF_PCT_CAT", "pct_off", {"pct": 10, "min_basket": 999}, "ethnic_wear", 120, 260),
    "at_risk": ("OF_WINBACK", "pct_off", {"pct": 15, "min_basket": 1499}, "home_decor", 315, 480),
    "new_user": ("OF_WELCOME2", "pct_off", {"pct": 15, "min_basket": 0}, "beauty", 135, 190),
    "default": ("OF_POINTS2X", "bonus_points", {"multiplier": 2}, None, 40, 90),
}

_OFFER_TEXT = {
    "OF_FREE_SHIP": (
        "Your {item} is waiting, shipping's on us",
        "Hi {name}! The {item} (₹{value:,}) is still in your cart. Free shipping till {exp}, code {code}.",
    ),
    "OF_PCT_CAT": (
        "10% off ethnic wear, just for you",
        "Hi {name}, 10% off ethnic wear on orders above ₹999 till {exp}. Code {code}.",
    ),
    "OF_WINBACK": (
        "We've missed you, {name}",
        "Hi {name}, it's been a while! 15% off home decor above ₹1,499 till {exp}. Code {code}.",
    ),
    "OF_WELCOME2": (
        "15% off your second order",
        "Welcome back {name}! 15% off your next beauty order till {exp}. Code {code}.",
    ),
    "OF_POINTS2X": (
        "Double points this week",
        "Hi {name}, earn 2× reward points on every order till {exp}. Code {code}.",
    ),
}

CATALOGUE: list[Offer] = [
    Offer(
        id="OF_FREE_SHIP",
        type="free_shipping",
        name="Free shipping",
        description="Free standard shipping",
        param_schema={"min_basket": {"min": 0, "max": 999}},
        base_cost_model="shipping_cost",
    ),
    Offer(
        id="OF_PCT_CAT",
        type="pct_off",
        name="% off category",
        description="Percent off one category",
        param_schema={"pct": {"min": 5, "max": 30}, "min_basket": {"min": 0}},
        base_cost_model="pct*aov*p_redeem",
    ),
    Offer(
        id="OF_WINBACK",
        type="pct_off",
        name="Win-back",
        description="Win-back discount",
        param_schema={"pct": {"min": 10, "max": 20}, "min_basket": {"min": 999}},
        base_cost_model="pct*aov*p_redeem",
    ),
    Offer(
        id="OF_WELCOME2",
        type="pct_off",
        name="Welcome 2nd order",
        description="Second-order welcome",
        param_schema={"pct": {"min": 10, "max": 15}},
        base_cost_model="pct*aov*p_redeem",
    ),
    Offer(
        id="OF_POINTS2X",
        type="bonus_points",
        name="2× points",
        description="Double reward points",
        param_schema={"multiplier": {"min": 2, "max": 3}},
        base_cost_model="points_liability",
    ),
    Offer(
        id="OF_EARLY",
        type="early_access",
        name="Early access",
        description="Early sale access",
        param_schema={},
        base_cost_model="zero",
    ),
]

FESTIVALS: list[Festival] = [  # stub only — Session A owns the verified calendar
    Festival(
        id="karwa_chauth_2026",
        name="Karwa Chauth",
        date=date(2026, 10, 29),
        phases={"teaser": (-14, -7), "build_up": (-7, -2), "last_minute": (-1, 0), "post": (1, 3)},
        hero_categories=["ethnic_wear", "jewellery", "beauty", "gifting"],
        greeting="Happy Karwa Chauth",
        budget=40000,
    ),
    Festival(
        id="diwali_2026",
        name="Diwali",
        date=date(2026, 11, 8),
        phases={"teaser": (-14, -7), "build_up": (-7, -2), "last_minute": (-1, 0), "post": (1, 10)},
        hero_categories=["home_decor", "gifting", "electronics", "fashion"],
        greeting="Happy Diwali",
        budget=150000,
    ),
]


# ---------------------------------------------------------------- helpers
def _lookup(customer_id: str) -> CustomerProfile:
    if customer_id in PROFILES:
        return PROFILES[customer_id]
    return PROFILES["C000001"].model_copy(update={"customer_id": customer_id, "first_name": "Friend"})


def _coupon(offer_type: str, name: str, seed: str) -> str:
    prefix = {"free_shipping": "SHIP", "pct_off": "SAVE", "bonus_points": "PTS"}.get(offer_type, "OFF")
    tail = hashlib.sha1(seed.encode()).hexdigest()[:4].upper()
    return f"{prefix}{name[:3].upper()}{tail}"


def _rule(rid: str, layer: str, rtype: str, desc: str, params: dict) -> Rule:
    return Rule(
        id=rid,
        layer=layer,
        type=rtype,
        severity="hard",
        conditions={},
        params=params,
        description=desc,
        updated_at=datetime(2026, 10, 22, tzinfo=IST),
    )


_STUB_RULES = [
    _rule(
        "G_MARGIN",
        "global",
        "margin_guard",
        "Never discount more than the category margin minus 5%.",
        {"buffer_pct": 5},
    ),
    _rule(
        "G_FREQ",
        "global",
        "frequency_cap",
        "At most 3 offers per customer every 7 days, 48 h apart.",
        {"max_7d": 3, "min_gap_h": 48},
    ),
    _rule(
        "G_QUIET",
        "global",
        "quiet_hours",
        "No messages between 21:00 and 09:00 IST.",
        {"start": "21:00", "end": "09:00"},
    ),
]


# ---------------------------------------------------------------- Session A stubs
def seed_run(n_customers: int = 5000, seed: int = 42) -> None:
    from app.db import init_db, session_scope
    from app.models import CustomerRow

    init_db()
    with session_scope() as s:
        for p in PROFILES.values():
            if s.get(CustomerRow, p.customer_id) is None:
                s.add(
                    CustomerRow(
                        id=p.customer_id,
                        first_name=p.first_name,
                        city="Ludhiana",
                        city_tier=p.city_tier,
                        signup_date=date(2025, 11, 1),
                        channel="organic",
                        device="android",
                        preferred_payment="upi",
                        persona=p.persona,
                        response_type="persuadable",
                        points_balance=p.points_balance,
                        tier=p.tier,
                    )
                )
    log.info("stub seed: wrote %d fixture customers", len(PROFILES))


def create_profile_from_answers(telegram_id: int, first_name: str, answers: dict) -> Customer:
    persona = "deal_hunter" if answers.get("style") == "deal" else "new_user"
    return Customer(
        id=f"TG{telegram_id}",
        first_name=first_name,
        city="Ludhiana",
        city_tier=2,
        signup_date=clock().date(),
        channel="telegram",
        device="mobile",
        preferred_payment="upi",
        persona=persona,
        response_type="persuadable",
        telegram_chat_id=telegram_id,
        opt_in_festivals=list(answers.get("festivals", [])),
    )


def build_profile(customer_id: str, now: datetime) -> CustomerProfile:
    return _lookup(customer_id).model_copy(update={"as_of": now})


def assign_policy(profile: CustomerProfile) -> PolicyName:
    return profile.policy


def uplift_predict(profile: CustomerProfile, offer_type: str) -> float:
    return profile.uplift.get(offer_type, 0.0)


def impact_estimate(
    profile: CustomerProfile, offer_type: str, params: dict, category: str | None
) -> tuple[int, int]:
    pct = params.get("pct", 0) / 100
    cost = int(profile.aov * pct * 0.6) if pct else 60
    profit = int(uplift_predict(profile, offer_type) * profile.aov * 0.45) - cost
    return cost, profit


def realism_compute() -> RealismStats:
    return RealismStats(
        pareto_top20_share=0.72,
        cart_abandon_rate=0.70,
        funnel={"view": 100000, "add_to_cart": 10200, "checkout_started": 4300, "purchase": 3060},
        retention_cohorts=[{"cohort": "2025-11", "m1": 0.42, "m2": 0.31, "m3": 0.26}],
        aov_by_category={"fashion": 1450, "electronics": 8900, "grocery": 640},
        return_rate_by_category={"fashion": 0.24, "electronics": 0.07, "grocery": 0.03},
        seasonality_daily=[
            {"date": "2025-10-20", "revenue": 812000},
            {"date": "2025-10-27", "revenue": 401000},
        ],
        benchmarks={"pareto_top20_share": [0.65, 0.80], "cart_abandon_rate": [0.65, 0.75]},
    )


def experiments_compute(start: date, end: date) -> ExperimentStats:
    return ExperimentStats(
        treatment={"n": 4500, "conv_rate": 0.081, "revenue": 1240000, "cost": 86000},
        control={"n": 500, "conv_rate": 0.054, "revenue": 92000, "cost": 0},
        incremental_revenue=412000,
        incremental_profit=104000,
        margin_saved_sure_things=61000,
        uplift_by_policy=[{"policy": "at_risk", "uplift": 0.11}, {"policy": "vip", "uplift": 0.004}],
        roi_by_offer_type=[{"type": "free_shipping", "roi": 3.4}, {"type": "pct_off", "roi": 1.6}],
    )


# ---------------------------------------------------------------- Session B stubs
def get_context(now: datetime) -> Context:
    hour = now.astimezone(IST).hour
    return Context(
        now=now, is_quiet_hours=hour >= 21 or hour < 9, is_payday_window=now.day <= 5, budget_left_today=50000
    )


def effective_policy(profile: CustomerProfile, context: Context) -> EffectivePolicy:
    return EffectivePolicy(
        customer_id=profile.customer_id,
        policy=profile.policy,
        rules=_STUB_RULES,
        limits={"max_pct": 15, "max_offers_7d": 3},
        summary=[r.description for r in _STUB_RULES],
        version_hash="stub-v1",
    )


def allowed_offers(
    profile: CustomerProfile, context: Context, catalogue: list[Offer]
) -> list[OfferCandidate]:
    if profile.policy == "vip":
        return [
            OfferCandidate(
                offer_id="OF_EARLY",
                type="early_access",
                allowed_params={},
                est_cost=0,
                est_incremental_profit=0,
                rule_notes=["VIP policy: no % discounts"],
            )
        ]
    oid, otype, params, cat, cost, profit = _POLICY_OFFER.get(profile.policy, _POLICY_OFFER["default"])
    return [
        OfferCandidate(
            offer_id=oid,
            type=otype,
            category=cat,
            allowed_params={k: {"min": v, "max": v} for k, v in params.items()},
            est_cost=cost,
            est_incremental_profit=profit,
        )
    ]


def evaluate(
    profile: CustomerProfile, context: Context, offer_id: str | None, params: dict, message: str | None = None
) -> ValidationResult:
    checks = [
        RuleCheck(rule_id=r.id, description=r.description, passed=True, severity="hard") for r in _STUB_RULES
    ]
    if params.get("pct", 0) > 20:
        checks[0] = checks[0].model_copy(
            update={"passed": False, "detail": f"{params['pct']}% exceeds the cap"}
        )
    violations = [c for c in checks if not c.passed]
    return ValidationResult(ok=not violations, checks=checks, violations=violations)


def describe_rule(rule: Rule) -> str:
    return rule.description or f"{rule.type.replace('_', ' ')}: {rule.params}"


def rule_impact(rule: Rule) -> dict:
    return {"customers_affected": 312, "budget_delta": -18400, "examples": ["C000002", "C000004"]}


def explain(decision: Decision) -> Explanation:
    return decision.explanation


def daily_digest(day: date) -> str:
    return (
        f"Digest for {day:%d %b}: 42 offers sent, 9 blocked (mostly frequency cap), 6 held out. "
        "At-risk customers claimed most (18%). VIPs got zero-cost early access, protecting ₹6,100 margin. "
        "Suggestion: lower the deal-hunter cap from 10% to 8%; claims barely changed between them."
    )


def decide(
    customer_id: str,
    trigger: TriggerType,
    trigger_meta: dict | None = None,
    *,
    dry_run: bool = False,
    now: datetime | None = None,
) -> Decision:
    now = now or clock()
    trigger_meta = trigger_meta or {}
    profile = build_profile(customer_id, now)
    ctx = get_context(now)
    policy = effective_policy(profile, ctx)
    candidates = allowed_offers(profile, ctx, CATALOGUE)
    checks_line = f"{len(_STUB_RULES)} passed · 0 violations · policy {profile.policy} (stub)"
    did = f"D{now:%Y%m%d%H%M%S}-{customer_id[-4:]}"
    common = dict(
        id=did,
        ts=now,
        customer_id=customer_id,
        trigger=trigger,
        trigger_meta=trigger_meta,
        profile_snapshot=profile,
        context=ctx,
        effective_policy=policy,
        candidates=candidates,
    )

    if trigger == "manual":
        return Decision(
            **common,
            decided_by="BLOCKED_PREGATE",
            status="BLOCKED",
            explanation=Explanation(
                title=f"Blocked: frequency cap for {profile.first_name}",
                why_customer="Already received 3 offers in the last 7 days.",
                why_offer="No offer: the global frequency cap stops further sends.",
                rules_line="1 hard rule blocked the send",
                decided_by_line="Pre-gate (no AI call)",
                telegram_text="No new offer right now — you've had 3 this week, and we don't spam. 🙏",
            ),
        )

    if profile.policy == "vip":
        return Decision(
            **common,
            decided_by="AGENT",
            status="NO_OFFER",
            final_offer_id=None,
            explanation=Explanation(
                title=f"No offer: {profile.first_name} buys anyway (margin protected)",
                why_customer="Champion: ordered 4 days ago, 9 orders in 90 days, uplift ≈ 0.",
                why_offer="A discount would not change behaviour; only zero-cost perks are allowed.",
                rejected=["10% off: VIP policy forbids % discounts", "Free shipping: no uplift"],
                rules_line=checks_line,
                decided_by_line="Agent (stub, 0 tool calls)",
                telegram_text="No offer this time — you're already one of our best customers! 💛",
            ),
        )

    cand = candidates[0]
    params = {k: v["min"] for k, v in cand.allowed_params.items()}
    code = _coupon(cand.type, profile.first_name, f"{did}{cand.offer_id}")
    expires = (now + timedelta(days=3)).replace(hour=23, minute=59, second=0, microsecond=0)
    head_tpl, msg_tpl = _OFFER_TEXT[cand.offer_id]
    cart = profile.open_cart or {}
    fmt = dict(
        name=profile.first_name,
        item=cart.get("item", "item"),
        value=cart.get("value", 0),
        exp=f"{expires:%d %b}",
        code=code,
    )
    headline, message = head_tpl.format(**fmt), msg_tpl.format(**fmt)
    reasoning = AgentReasoning(
        why_customer=f"{profile.first_name}: churn risk {profile.churn_risk:.2f}, "
        f"uplift {profile.uplift.get(cand.type, 0):.2f} for {cand.type}.",
        why_offer=f"Best expected incremental profit: ₹{cand.est_incremental_profit} "
        f"for ₹{cand.est_cost} cost.",
        key_signals=["policy " + profile.policy, f"trigger {trigger}"],
        expected_impact_inr=cand.est_incremental_profit,
    )
    output = AgentOutput(
        decision="SEND",
        offer_id=cand.offer_id,
        params=params,
        headline=headline,
        message=message,
        reasoning=reasoning,
        confidence=0.8,
    )
    return Decision(
        **common,
        agent_trace=[
            ToolCall(name="get_profile", args={"customer_id": customer_id}, result_summary="stub", ms=3)
        ],
        agent_output=output,
        validation=evaluate(profile, ctx, cand.offer_id, params, message),
        decided_by="AGENT",
        status="DRY_RUN" if dry_run else "SENT",
        final_offer_id=cand.offer_id,
        final_params=params,
        coupon_code=None if dry_run else code,
        expires_at=expires,
        headline=headline,
        message=message,
        cost=cand.est_cost,
        expected_incremental_profit=cand.est_incremental_profit,
        channel="none" if dry_run else "dm",
        explanation=Explanation(
            title=f"Sent: {cand.offer_id} to {profile.first_name} (exp. {expires:%d %b})",
            why_customer=reasoning.why_customer,
            why_offer=reasoning.why_offer,
            rules_line=checks_line,
            decided_by_line="Agent (stub, 1 tool call)",
            telegram_text=f"Why you got this: it's the smallest offer that should help ({cand.type}). "
            f"{len(_STUB_RULES)} rules checked ✓",
        ),
    )


# ---------------------------------------------------------------- Session C stubs
def deliver(decision: Decision, channel: str) -> None:
    log.info("stub deliver %s via %s: %s", decision.id, channel, decision.headline)


def build_application():
    raise NotImplementedError("Telegram application not built yet (Session C)")


async def set_bot_commands(application) -> None:
    return None


def ensure_rules_seeded() -> int:
    return 0


def run_rounds(n: int) -> list[Decision]:
    return [decide(cid, "lab") for cid in list(PROFILES)[:n]]
