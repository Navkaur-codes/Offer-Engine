"""Property tests: nothing out of limits is ever approved.

The oracle below restates the hard limits from PLAN §4/§4b by hand instead of reusing engine code, so a bug
in the engine can't hide behind the same bug in the test. It only borrows `offer_category` (which category a
coupon is scoped to), because that is a definition, not a limit.
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta
from typing import get_args

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app import ports
from app.config import IST
from app.contracts import Category, Context, CustomerProfile, OfferType, PolicyName
from app.rules.engine import allowed_offers, evaluate
from app.rules.rule_types import offer_category
from app.rules.seed_rules import CATEGORY_MARGINS, SEED_RULES
from tests.core.helpers import CATALOGUE, make_profile

CATEGORIES = list(get_args(Category))
OFFER_TYPES = list(get_args(OfferType))
POLICIES = list(get_args(PolicyName))
OFFERS = {o.id: o for o in CATALOGUE}
DISCOUNTS = {"pct_off", "flat_off"}
FESTIVALS = [None, "karwa_chauth_2026", "diwali_2026", "dhanteras_2026", "navratri_2026", "gurpurab_2026"]
BANNED_WORDS = ["guaranteed", "free money", "last chance", "flipkart", "amazon", "beer"]

PERSONA_CAPS = {"deal_hunter": 10, "at_risk": 20, "new_user": 15, "dormant": 15}
PERSONA_TYPES = {
    "vip": {"early_access", "bonus_points", "free_shipping", "free_express", "points_reminder"},
    "deal_hunter": {"pct_off", "flat_off", "cart_nudge", "points_reminder"},
    "high_returner": {"bonus_points", "points_reminder"},
    "window_shopper": {"free_shipping", "flat_off", "cart_nudge", "early_access"},
    "at_risk": {"pct_off", "bundle", "free_shipping", "bonus_points", "cart_nudge"},
    "new_user": {"pct_off", "free_shipping", "cart_nudge", "points_reminder"},
    "cart_abandoner": {"cart_nudge", "free_shipping", "pct_off", "bonus_points"},
    "dormant": {"pct_off", "free_shipping", "cart_nudge"},
}
MIN_GAP_H = {"at_risk": 720, "dormant": 2160}


# ---------------------------------------------------------------- strategies
# Profiles and contexts come from one drawn seed: drawing ~25 fields via hypothesis made 10k runs slow.
def _maybe(rng: random.Random, value, p_none: float = 0.4):
    return None if rng.random() < p_none else value


def build_profile(seed: int) -> CustomerProfile:
    rng = random.Random(seed)
    now = datetime(2026, 10, 1, tzinfo=IST) + timedelta(minutes=rng.randrange(92 * 24 * 60))
    cart_since = (now - timedelta(minutes=rng.randrange(3000))).isoformat()
    return make_profile(
        rng.choice(["C000001", "C000002", "C000003", "C000004", "C000005", "C004242", "C000777"]),
        policy=rng.choice(POLICIES),
        as_of=now,
        offers_7d=rng.choice([0, 0, 0, 1, 2, 3, 4]),
        last_offer_at=_maybe(rng, now - timedelta(hours=rng.randrange(3000)), 0.7),
        active_coupon=_maybe(rng, "SAVEXYZ1234", 0.9),
        recency_days=rng.randrange(200),
        aov=rng.randrange(100, 20000),
        uplift={t: rng.uniform(-0.1, 0.3) for t in OFFER_TYPES},
        category_affinity={c: rng.random() for c in rng.sample(CATEGORIES, rng.randrange(5))},
        suppressed_categories=rng.sample(CATEGORIES, rng.randrange(4)),
        open_cart=_maybe(
            rng, {"category": rng.choice(CATEGORIES), "item": "Item", "value": 999, "since": cart_since}
        ),
    )


def build_context(seed: int, now: datetime, allow_quiet: bool = True) -> Context:
    rng = random.Random(seed)
    festival = rng.choice(FESTIVALS)
    hour = rng.randrange(24) if allow_quiet and rng.random() < 0.25 else rng.randrange(9, 21)
    return Context(
        now=now.replace(hour=hour, minute=rng.randrange(60)),
        is_quiet_hours=False,
        is_payday_window=False,
        festival=festival,
        festival_phase=rng.choice(["teaser", "build_up", "last_minute", "post"]) if festival else None,
        hero_categories=rng.sample(CATEGORIES, rng.randrange(5)),
        budget_left_today=rng.choice([0, rng.randrange(400), rng.randrange(60000), 50000, 50000]),
        budget_left_festival=_maybe(rng, rng.randrange(200000)) if festival else None,
        pacing_factor=rng.choice([1.0, rng.uniform(0.1, 1.0)]),
    )


def complete_params(params: dict, offer_id: str | None, seed: int) -> dict:
    """Usually fill in the offer's own settings near (and past) their catalogue range, so decisions get past
    the catalogue check and the persona/festival caps actually get exercised."""
    rng = random.Random(seed)
    if offer_id not in OFFERS or rng.random() < 0.2:
        return params
    out = dict(params)
    if rng.random() < 0.5:
        out.pop("category", None)
    for key, r in OFFERS[offer_id].param_schema.items():
        if key not in out or rng.random() < 0.3:
            lo = r.get("min", 0)
            out[key] = rng.randint(lo, r.get("max", lo + 1500) + 5)
    if rng.random() < 0.3:
        out["min_basket"] = rng.choice([0, 999, 1500])
    return out


seeds = st.integers(0, 2**32 - 1)


junk = st.one_of(
    st.integers(-100, 5000),
    st.floats(allow_nan=True, allow_infinity=True),
    st.text(max_size=5),
    st.booleans(),
    st.none(),
    st.sampled_from(CATEGORIES),
)
near_valid = st.fixed_dictionaries(
    {},
    optional={
        "pct": st.integers(0, 40),
        "amount": st.integers(0, 800),
        "min_basket": st.integers(0, 2000),
        "multiplier": st.integers(1, 4),
        "category": st.sampled_from(CATEGORIES),
    },
)
any_params = st.one_of(
    near_valid,
    st.dictionaries(st.sampled_from(["pct", "amount", "min_basket", "multiplier", "category", "x"]), junk),
)
messages = (
    st.none() | st.text(max_size=300) | st.sampled_from(BANNED_WORDS).map(lambda w: f"Hi, {w} deal for you")
)


# ---------------------------------------------------------------- oracle
def _is_num(v) -> bool:
    return isinstance(v, int | float) and not isinstance(v, bool) and math.isfinite(v)


def assert_inside_hard_limits(p: CustomerProfile, ctx: Context, offer_id, params: dict, message) -> None:
    hour = ctx.now.astimezone(IST).hour
    assert 9 <= hour < 21, "approved during quiet hours"
    assert p.offers_7d < 3, "approved past 3 offers / 7 days"
    gap = MIN_GAP_H.get(p.policy, 48)
    if p.last_offer_at is not None:
        assert ctx.now - p.last_offer_at >= timedelta(hours=gap), "approved inside the minimum gap"
    assert p.active_coupon is None, "approved a second active coupon"
    assert p.policy != "sleeping_dog" and p.customer_id != "C004242", "approved a blocked customer"
    assert ctx.budget_left_today > 0
    assert p.recency_days * 24 >= 48, "approved within 48 h of a purchase"
    if message is not None:
        assert len(message) <= 280
        assert not any(w in message.lower() for w in BANNED_WORDS[:5])
    if offer_id is None:
        return

    offer = OFFERS[offer_id]
    assert offer.enabled
    for key, value in params.items():
        assert key in offer.param_schema or key in {"min_basket", "category"}, f"unknown param {key}"
        if key != "category":
            assert _is_num(value) and value >= 0
    pf = ctx.pacing_factor
    cat = offer_category(offer, params, p)
    pct, amount = params.get("pct"), params.get("amount")
    basket = params.get("min_basket", 0)
    allowed_types = PERSONA_TYPES.get(p.policy)
    assert allowed_types is None or offer.type in allowed_types, f"{offer.type} approved for {p.policy}"
    if offer.type in DISCOUNTS:
        assert cat not in p.suppressed_categories
    if pct is not None:
        margin = CATEGORY_MARGINS.get(cat, min(CATEGORY_MARGINS.values()))
        assert pct <= margin - 5, f"{pct}% over the {cat} margin guard"
        assert pct <= math.floor(30 * pf), "over the global cap after pacing"
        if p.policy in PERSONA_CAPS:
            assert pct <= math.floor(PERSONA_CAPS[p.policy] * pf), f"over the {p.policy} cap"
        if p.customer_id == "C000777":
            assert pct <= math.floor(5 * pf)
        if p.policy == "cart_abandoner":
            assert pct <= 5
        if ctx.festival in {"diwali_2026", "dhanteras_2026"} and ctx.festival_phase == "last_minute":
            assert pct <= math.floor(5 * pf)
    if amount is not None:
        assert amount <= math.floor(500 * pf)
        if p.policy == "window_shopper":
            assert amount <= math.floor(150 * pf)
        margin = CATEGORY_MARGINS.get(cat, min(CATEGORY_MARGINS.values()))
        assert amount <= (margin - 5) / 100 * max(basket, p.aov)
    if p.policy == "deal_hunter" and offer.type in DISCOUNTS:
        assert basket >= 999
    if offer.type == "bonus_points":
        assert params["multiplier"] <= 3
    if ctx.festival and ctx.festival_phase == "teaser":
        assert offer.type in {"cart_nudge", "early_access", "points_reminder", "bonus_points"}
    cost, _ = ports.impact_estimate(p, offer.type, params, cat)
    assert cost <= ctx.budget_left_today
    if ctx.festival and ctx.budget_left_festival is not None:
        assert cost <= ctx.budget_left_festival


# ---------------------------------------------------------------- properties
@settings(
    max_examples=10_000,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
@given(
    seed=seeds,
    offer_id=st.none() | st.sampled_from([*OFFERS, "OF_UNKNOWN"]),
    params=any_params,
    message=messages,
)
def test_no_out_of_limit_decision_is_ever_approved(seed, offer_id, params, message):
    p = build_profile(seed)
    ctx = build_context(seed + 1, p.as_of)
    params = complete_params(params, offer_id, seed + 2)
    res = evaluate(p, ctx, offer_id, params, message, rules=SEED_RULES, catalogue=CATALOGUE)
    assert res.ok == (not any(c.severity == "hard" for c in res.violations))
    if res.ok:
        assert_inside_hard_limits(p, ctx, offer_id, params, message)
    if res.adjusted_params is not None:
        fixed = evaluate(p, ctx, offer_id, res.adjusted_params, None, rules=SEED_RULES, catalogue=CATALOGUE)
        assert fixed.ok
        assert_inside_hard_limits(p, ctx, offer_id, res.adjusted_params, None)


@settings(max_examples=1_500, deadline=None, derandomize=True, suppress_health_check=[HealthCheck.too_slow])
@given(data=st.data())
def test_anything_inside_allowed_ranges_passes_evaluate(data):
    """allowed_offers and evaluate must agree, or the agent would be handed offers the validator rejects."""
    seed = data.draw(seeds)
    p = build_profile(seed)
    ctx = build_context(seed + 1, p.as_of, allow_quiet=False)
    for cand in allowed_offers(p, ctx, CATALOGUE, rules=SEED_RULES):
        params = {}
        for key, rng in cand.allowed_params.items():
            lo = rng.get("min", 0)
            hi = rng.get("max", lo + 1000)
            params[key] = data.draw(st.integers(math.ceil(lo), math.floor(hi)))
        if cand.category is not None:
            params["category"] = cand.category
        res = evaluate(p, ctx, cand.offer_id, params, None, rules=SEED_RULES, catalogue=CATALOGUE)
        assert res.ok, (cand.offer_id, params, [(v.rule_id, v.detail) for v in res.violations])
        assert_inside_hard_limits(p, ctx, cand.offer_id, params, None)
