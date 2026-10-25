"""One test per rule type: check() and constrain() on the seed rules."""

from __future__ import annotations

from datetime import timedelta
from typing import get_args

from app.contracts import OfferCandidate, Rule, RuleType
from app.rules.describe import describe
from app.rules.rule_types import RULE_TYPES, spec_for
from app.rules.seed_rules import POLICIES_COVERED, SEED_RULES
from tests.core.helpers import CATALOGUE, NOW, make_context, make_profile, rule_by_id

OFFERS = {o.id: o for o in CATALOGUE}


def check(rule_id: str, profile, ctx, offer_id: str | None, params: dict | None = None, message=None):
    offer = OFFERS[offer_id] if offer_id else None
    return spec_for(rule_by_id(rule_id)).check(profile, ctx, offer, params or {}, message)


def candidate(offer_id: str, profile, **allowed) -> OfferCandidate:
    from app.rules.engine import _seed_candidate

    cand = _seed_candidate(OFFERS[offer_id], profile)
    return cand.model_copy(update={"allowed_params": {**cand.allowed_params, **allowed}})


def test_every_rule_type_has_a_class():
    assert set(RULE_TYPES) == set(get_args(RuleType))


def test_seed_covers_all_layers_and_nine_policies():
    assert {r.layer for r in SEED_RULES} == {"global", "festival", "persona", "individual"}
    assert {
        "vip",
        "deal_hunter",
        "at_risk",
        "new_user",
        "cart_abandoner",
        "window_shopper",
        "high_returner",
        "sleeping_dog",
        "dormant",
    } == POLICIES_COVERED
    assert len({r.id for r in SEED_RULES}) == len(SEED_RULES)


def test_every_seed_rule_has_a_readable_sentence():
    for rule in SEED_RULES:
        text = describe(rule)
        assert text == rule.description
        assert text[0].isupper() and text.endswith(".")
        assert "{" not in text and "None" not in text and "_" not in text.replace("C00", ""), text


def test_margin_guard():
    p, ctx = make_profile("C000002"), make_context()
    assert check("G_MARGIN", p, ctx, "OF_ELEC", {"pct": 10}).passed  # electronics margin 15 − 5
    res = check("G_MARGIN", p, ctx, "OF_ELEC", {"pct": 11})
    assert not res.passed and "10%" in res.detail
    # flat ₹ off is judged against max(min_basket, aov): 40% of ₹1,199 → ₹479 on ethnic wear
    assert check("G_MARGIN", p, ctx, "OF_FLAT", {"amount": 479}).passed
    assert not check("G_MARGIN", p, ctx, "OF_FLAT", {"amount": 480}).passed
    spec = spec_for(rule_by_id("G_MARGIN"))
    narrowed = spec.constrain(candidate("OF_ELEC", p), OFFERS["OF_ELEC"], p, ctx)
    assert narrowed.allowed_params["pct"] == {"min": 5, "max": 10}
    assert "margin guard" in narrowed.rule_notes[0]


def test_discount_cap_and_pacing():
    p = make_profile("C000002")
    ctx = make_context()
    assert check("P_DEAL_CAP", p, ctx, "OF_PCT_CAT", {"pct": 10, "min_basket": 999}).passed
    assert not check("P_DEAL_CAP", p, ctx, "OF_PCT_CAT", {"pct": 11, "min_basket": 999}).passed
    assert not check("P_DEAL_CAP", p, ctx, "OF_PCT_CAT", {"pct": 10, "min_basket": 500}).passed
    paced = make_context(pacing_factor=0.5)
    assert not check("P_DEAL_CAP", p, paced, "OF_PCT_CAT", {"pct": 6, "min_basket": 999}).passed
    assert check("P_DEAL_CAP", p, paced, "OF_PCT_CAT", {"pct": 5, "min_basket": 999}).passed
    assert not check("G_CAP", p, ctx, "OF_POINTS2X", {"multiplier": 4}).passed
    spec = spec_for(rule_by_id("P_DEAL_CAP"))
    narrowed = spec.constrain(candidate("OF_PCT_CAT", p), OFFERS["OF_PCT_CAT"], p, paced)
    assert narrowed.allowed_params["pct"] == {"min": 5, "max": 5}
    assert narrowed.allowed_params["min_basket"] == {"min": 999}
    assert any("pacing" in n for n in narrowed.rule_notes)


def test_frequency_cap():
    ctx = make_context()
    assert check("G_FREQ", make_profile(offers_7d=2), ctx, None).passed
    assert not check("G_FREQ", make_profile(offers_7d=3), ctx, None).passed
    assert not check("G_FREQ", make_profile(last_offer_at=NOW - timedelta(hours=10)), ctx, None).passed
    assert check("G_FREQ", make_profile(last_offer_at=NOW - timedelta(hours=49)), ctx, None).passed
    # at-risk customers: one offer per 30 days
    at_risk = make_profile("C000004", last_offer_at=NOW - timedelta(days=20))
    assert not check("P_ATRISK_MONTHLY", at_risk, ctx, None).passed


def test_quiet_hours():
    p = make_profile()
    for hh, mm, quiet in [(21, 0, True), (23, 30, True), (8, 59, True), (9, 0, False), (20, 59, False)]:
        ctx = make_context(now=NOW.replace(hour=hh, minute=mm))
        assert check("G_QUIET", p, ctx, None).passed is not quiet, (hh, mm)


def test_budget_daily_and_festival_pool():
    p = make_profile("C000002")
    assert check("G_BUDGET", p, make_context(budget_left_today=1000), "OF_PCT_CAT", {"pct": 10}).passed
    assert not check("G_BUDGET", p, make_context(budget_left_today=10), "OF_PCT_CAT", {"pct": 10}).passed
    assert not check("G_BUDGET", p, make_context(budget_left_today=0), None).passed
    fest = make_context(festival="diwali_2026", festival_phase="build_up", budget_left_festival=20)
    res = check("F_POOL", p, fest, "OF_PCT_CAT", {"pct": 10})
    assert not res.passed and "festival budget pool" in res.detail


def test_eligibility_whitelist_uplift_and_hero():
    ctx = make_context()
    vip = make_profile("C000003")
    assert check("P_VIP_PERKS", vip, ctx, "OF_EARLY").passed
    assert not check("P_VIP_PERKS", vip, ctx, "OF_PCT_CAT", {"pct": 5}).passed
    at_risk = make_profile("C000004")  # pct_off uplift 0.14, bonus_points 0.03
    assert check("P_ATRISK_WINBACK", at_risk, ctx, "OF_WINBACK", {"pct": 15}).passed
    assert not check("P_ATRISK_WINBACK", at_risk, ctx, "OF_POINTS2X", {"multiplier": 2}).passed
    fest = make_context(festival="diwali_2026", festival_phase="build_up", hero_categories=["home_decor"])
    p = make_profile("C000002")
    assert not check("F_BUILDUP_HERO", p, fest, "OF_PCT_CAT", {"pct": 5, "category": "beauty"}).passed
    assert check("F_BUILDUP_HERO", p, fest, "OF_PCT_CAT", {"pct": 5, "category": "home_decor"}).passed
    assert check("F_BUILDUP_HERO", p, fest, "OF_FREE_SHIP", {"category": "beauty"}).passed


def test_exclusion_sleeping_dog_post_purchase_and_suppressed():
    ctx = make_context()
    dog = make_profile(policy="sleeping_dog")
    assert not check("P_SLEEPING_DOG", dog, ctx, None).passed  # blocks even the pre-gate
    just_bought = make_profile("C000002", recency_days=1)
    assert not check("G_POST_PURCHASE", just_bought, ctx, "OF_PCT_CAT", {"pct": 5}).passed
    assert not check("G_POST_PURCHASE", just_bought, ctx, "OF_FREE_SHIP").passed  # no offers at all for 48 h
    assert not check("G_POST_PURCHASE", just_bought, ctx, None).passed
    assert check(
        "G_POST_PURCHASE", make_profile("C000002", recency_days=2), ctx, "OF_PCT_CAT", {"pct": 5}
    ).passed
    fed_up = make_profile("C000002", suppressed_categories=["beauty"])
    res = check("I_NOT_FOR_ME", fed_up, ctx, "OF_PCT_CAT", {"pct": 5, "category": "beauty"})
    assert not res.passed and "Not for me" in res.detail
    # the suppressed category is also never picked as the default target
    assert check("I_NOT_FOR_ME", fed_up, ctx, "OF_PCT_CAT", {"pct": 5}).passed


def test_stacking_one_active_coupon():
    ctx = make_context()
    assert check("G_ONE_COUPON", make_profile(), ctx, None).passed
    assert not check("G_ONE_COUPON", make_profile(active_coupon="SAVEPRI1A2B"), ctx, None).passed


def test_escalation_ladder():
    def cart(minutes: int):
        since = (NOW - timedelta(minutes=minutes)).isoformat()
        return make_profile(open_cart={"category": "fashion", "item": "Kurta", "value": 1450, "since": since})

    ctx = make_context()
    assert not check("P_CART_LADDER", cart(10), ctx, "OF_FREE_SHIP").passed
    assert check("P_CART_LADDER", cart(35), ctx, "OF_FREE_SHIP").passed
    assert check("P_CART_LADDER", cart(35), ctx, "OF_NUDGE").passed
    res = check("P_CART_LADDER", cart(35), ctx, "OF_PCT_CAT", {"pct": 5})
    assert not res.passed and "24 h" in res.detail
    assert check("P_CART_LADDER", cart(25 * 60), ctx, "OF_PCT_CAT", {"pct": 5}).passed
    assert not check("P_CART_LADDER", cart(25 * 60), ctx, "OF_PCT_CAT", {"pct": 6}).passed
    assert check("P_CART_LADDER", cart(35), ctx, "OF_POINTS2X", {"multiplier": 2}).passed  # not on the ladder


def test_message_rule():
    p, ctx = make_profile(), make_context()
    assert check("G_MESSAGE", p, ctx, "OF_FREE_SHIP", message="Hi! Free shipping till 26 Oct.").passed
    assert check("G_MESSAGE", p, ctx, "OF_FREE_SHIP", message=None).passed
    assert not check("G_MESSAGE", p, ctx, "OF_FREE_SHIP", message="x" * 281).passed
    assert not check("G_MESSAGE", p, ctx, "OF_FREE_SHIP", message="Guaranteed lowest price!").passed
    assert not check("G_MESSAGE", p, ctx, "OF_FREE_SHIP", message="Cheaper than Flipkart").passed


def test_festival_restriction():
    p = make_profile()
    navratri = make_context(festival="navratri_2026", festival_phase="build_up")
    spec = spec_for(rule_by_id("F_RESTRICTED"))
    assert spec.applies(p, navratri)
    assert not spec.applies(p, make_context(festival="diwali_2026", festival_phase="build_up"))
    assert not check("F_RESTRICTED", p, navratri, "OF_FREE_SHIP", message="Free shipping on beer mugs").passed
    assert check("F_RESTRICTED", p, navratri, "OF_FREE_SHIP", message="Free shipping on kurtas").passed


def test_unknown_condition_key_never_applies():
    rule = Rule(
        id="X",
        layer="global",
        type="stacking",
        severity="hard",
        conditions={"moon_phase": "full"},
        params={},
        updated_at=NOW,
    )
    assert not spec_for(rule).applies(make_profile(), make_context())


def test_message_facts_must_match_the_offer():
    p = make_profile("C000002")  # deal hunter, no open cart
    ctx = make_context()  # 24 Oct 14:00 → coupons expire 26 Oct
    params = {"pct": 10, "min_basket": 999, "category": "ethnic_wear"}

    def ok(msg, offer="OF_PCT_CAT", prm=params, c=ctx):
        return check("G_MESSAGE", p, c, offer, prm, message=msg)

    assert ok("Hi Priya! 10% off ethnic wear above ₹999 till 26 Oct. Code SAVEPRI7QX2.").passed
    assert ok("Hi Priya! 10% off ethnic wear above ₹999 till 26 October. Code SAVEPRI7QX2.").passed
    res = ok("Hi Priya! 15% off ethnic wear above ₹999 till 26 Oct.")
    assert not res.passed and "15%" in res.detail
    assert "₹499" in ok("Hi Priya! 10% off above ₹499 till 26 Oct.").detail
    assert "ends 28 Oct" in ok("Hi Priya! 10% off above ₹999 till 28 Oct.").detail
    assert "expiry" in ok("Hi Priya! 10% off ethnic wear above ₹999.").detail
    assert "48" in ok("Hi Priya! 10% off above ₹999 for 48 hours, till 26 Oct.").detail
    # a reminder has no coupon, so no expiry is needed; the points balance is a real number
    assert ok("Hi Priya! Your cart is waiting.", "OF_NUDGE", {}).passed
    assert ok(f"Hi Priya! You have {p.points_balance} points.", "OF_NUDGE", {}).passed
    # the cart's own price and item name may be quoted
    carted = make_profile(
        open_cart={"category": "electronics", "item": "Redmi 13C", "value": 8999, "since": "x"}
    )
    msg = "Hi! Your Redmi 13C (₹8,999) ships free till 26 Oct. Code SHIPNAV8K2P."
    assert check("G_MESSAGE", carted, ctx, "OF_FREE_SHIP", {"min_basket": 0}, message=msg).passed


def test_greeting_only_with_opt_in():
    p = make_profile()
    diwali = make_context(festival="diwali_2026", festival_phase="teaser")
    msg = "Happy Diwali, Navpreet! Early access to our sale till 26 Oct. Code EARLYNAV7Q2X."
    res = check("G_MESSAGE", p, diwali, "OF_EARLY", {}, message=msg)
    assert not res.passed and "opt-in" in res.detail  # harness leaves greeting empty without opt-in
    opted = diwali.model_copy(update={"greeting": "Happy Diwali"})
    assert check("G_MESSAGE", p, opted, "OF_EARLY", {}, message=msg).passed
    altered = msg.replace("Happy Diwali", "happy diwali")
    assert "exactly" in check("G_MESSAGE", p, opted, "OF_EARLY", {}, message=altered).detail
