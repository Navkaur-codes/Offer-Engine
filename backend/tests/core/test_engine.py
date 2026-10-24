"""effective_policy (tighten-only merge), allowed_offers, evaluate, budget pacing."""

from __future__ import annotations

import logging
from datetime import timedelta

from app import ports
from app.contracts import Rule
from app.rules.engine import allowed_offers, effective_policy, evaluate, screen_offers
from app.rules.seed_rules import SEED_RULES
from tests.core.helpers import CATALOGUE, NOW, make_context, make_profile


def _rule(rid: str, layer: str, rtype: str, params: dict, conditions: dict | None = None) -> Rule:
    return Rule(
        id=rid,
        layer=layer,
        type=rtype,
        severity="hard",
        conditions=conditions or {},
        params=params,
        updated_at=NOW,
    )


def ev(profile, ctx, offer_id, params, message=None, rules=SEED_RULES):
    return evaluate(profile, ctx, offer_id, params, message, rules=rules, catalogue=CATALOGUE)


def test_ports_resolve_to_the_real_engine():
    ports.reset_cache()
    status = ports.status()
    assert status["evaluate"] == status["effective_policy"] == status["allowed_offers"] == "real"
    assert status["describe_rule"] == "real"


def test_effective_policy_orders_layers_and_merges_tightest():
    p = make_profile("C000002")
    pol = effective_policy(p, make_context(), rules=SEED_RULES)
    layers = [r.layer for r in pol.rules]
    assert layers == sorted(layers, key=["global", "festival", "persona", "individual"].index)
    assert pol.limits["max_pct"] == 10 and pol.limits["min_basket"] == 999
    assert pol.limits["allowed_offer_types"] == ["cart_nudge", "flat_off", "pct_off", "points_reminder"]
    assert any(s.startswith("Discounts never go above") for s in pol.summary)
    assert pol.version_hash == effective_policy(p, make_context(), rules=SEED_RULES).version_hash


def test_lower_layer_cannot_loosen(caplog):
    loose_persona = _rule("P_LOOSE", "persona", "discount_cap", {"max_pct": 40}, {"policy": "deal_hunter"})
    loose_person = _rule("I_LOOSE", "individual", "discount_cap", {"max_pct": 60}, {"customer_id": "C000002"})
    rules = [*SEED_RULES, loose_persona, loose_person]
    p = make_profile("C000002")
    with caplog.at_level(logging.WARNING, logger="app.rules.engine"):
        pol = effective_policy(p, make_context(), rules=rules)
    assert pol.limits["max_pct"] == 10
    assert any("P_LOOSE" in m and "loosen" in m for m in caplog.messages)
    assert any("I_LOOSE" in s for s in pol.summary)
    res = ev(p, make_context(), "OF_PCT_CAT", {"pct": 25, "min_basket": 999}, rules=rules)
    assert not res.ok and [v.rule_id for v in res.violations] == ["P_DEAL_CAP"]


def test_lower_layer_can_tighten():
    tight = _rule("I_TIGHT", "individual", "discount_cap", {"max_pct": 7}, {"customer_id": "C000002"})
    p = make_profile("C000002")
    pol = effective_policy(p, make_context(), rules=[*SEED_RULES, tight])
    assert pol.limits["max_pct"] == 7
    assert not ev(
        p, make_context(), "OF_PCT_CAT", {"pct": 8, "min_basket": 999}, rules=[*SEED_RULES, tight]
    ).ok


def test_budget_pacing_shrinks_caps_and_says_so():
    p = make_profile("C000002")
    paced = make_context(pacing_factor=0.6)
    pol = effective_policy(p, paced, rules=SEED_RULES)
    assert pol.limits["max_pct"] == 6
    assert any("pacing" in s.lower() for s in pol.summary)
    cand = next(
        c for c in allowed_offers(p, paced, CATALOGUE, rules=SEED_RULES) if c.offer_id == "OF_PCT_CAT"
    )
    assert cand.allowed_params["pct"]["max"] == 6
    assert any("pacing" in n for n in cand.rule_notes)
    assert not ev(p, paced, "OF_PCT_CAT", {"pct": 7, "min_basket": 999}).ok


def test_allowed_offers_respects_policy():
    ctx = make_context()
    vip = allowed_offers(make_profile("C000003"), ctx, CATALOGUE, rules=SEED_RULES)
    assert vip and all(c.type not in {"pct_off", "flat_off"} for c in vip)
    returner = allowed_offers(make_profile(policy="high_returner"), ctx, CATALOGUE, rules=SEED_RULES)
    assert {c.type for c in returner} <= {"bonus_points", "points_reminder"}
    assert allowed_offers(make_profile(policy="sleeping_dog"), ctx, CATALOGUE, rules=SEED_RULES) == []
    assert allowed_offers(make_profile(offers_7d=3), ctx, CATALOGUE, rules=SEED_RULES) == []
    cands, rejected = screen_offers(make_profile("C000003"), ctx, CATALOGUE, rules=SEED_RULES)
    assert {"offer_id": "OF_PCT_CAT", "rule_id": "P_VIP_PERKS"} in [
        {k: r[k] for k in ("offer_id", "rule_id")} for r in rejected
    ]
    assert [c.est_incremental_profit for c in cands] == sorted(
        (c.est_incremental_profit for c in cands), reverse=True
    )


def test_festival_teaser_is_zero_cost_and_peak_days_are_capped():
    p = make_profile("C000002")
    teaser = make_context(festival="diwali_2026", festival_phase="teaser", budget_left_festival=100000)
    assert all(
        c.type in {"cart_nudge", "points_reminder"}
        for c in allowed_offers(p, teaser, CATALOGUE, rules=SEED_RULES)
    )
    peak = make_context(festival="diwali_2026", festival_phase="last_minute", budget_left_festival=100000)
    assert ev(p, peak, "OF_PCT_CAT", {"pct": 5, "min_basket": 999}).ok
    assert not ev(p, peak, "OF_PCT_CAT", {"pct": 6, "min_basket": 999}).ok
    karwa = make_context(
        festival="karwa_chauth_2026", festival_phase="last_minute", budget_left_festival=100000
    )
    assert ev(
        p, karwa, "OF_PCT_CAT", {"pct": 10, "min_basket": 999}
    ).ok  # the 5% cap is Diwali/Dhanteras only


def test_pre_gate_uses_evaluate_without_an_offer():
    ctx = make_context()
    assert ev(make_profile(), ctx, None, {}).ok
    night = make_context(now=NOW.replace(hour=22))
    res = ev(make_profile(), night, None, {})
    assert not res.ok and [v.rule_id for v in res.violations] == ["G_QUIET"]
    assert not ev(make_profile(last_offer_at=NOW - timedelta(hours=3)), ctx, None, {}).ok
    assert not ev(make_profile("C004242"), ctx, None, {}).ok


def test_catalogue_check():
    p, ctx = make_profile("C000002"), make_context()
    for params in (
        {"pct": 10, "min_basket": 999, "hack": 1},
        {"min_basket": 999},
        {"pct": "10", "min_basket": 999},
        {"pct": 10, "min_basket": -5},
        {"pct": 10, "min_basket": 999, "category": "weapons"},
    ):
        res = ev(p, ctx, "OF_PCT_CAT", params)
        assert not res.ok and res.violations[0].rule_id == "CATALOGUE", params
    assert not ev(p, ctx, "OF_NOPE", {}).ok
    assert not ev(p, ctx, "OF_OFF", {"pct": 5}).ok
    assert not ev(p, ctx, "OF_ELEC", {"pct": 5, "category": "fashion"}).ok


def test_missing_min_basket_counts_as_zero():
    p, ctx = make_profile("C000002"), make_context()
    assert not ev(p, ctx, "OF_PCT_CAT", {"pct": 10}).ok
    assert ev(p, ctx, "OF_PCT_CAT", {"pct": 10, "min_basket": 999}).ok


def test_adjusted_params_offer_a_compliant_version():
    p, ctx = make_profile("C000002"), make_context()
    res = ev(p, ctx, "OF_PCT_CAT", {"pct": 50, "min_basket": 0})
    assert not res.ok and res.adjusted_params == {"pct": 10, "min_basket": 999}
    assert ev(p, ctx, "OF_PCT_CAT", res.adjusted_params).ok
    # nothing to adjust when the customer can't be contacted at all
    assert ev(make_profile(policy="sleeping_dog"), ctx, "OF_FREE_SHIP", {}).adjusted_params is None


def test_message_is_checked_by_evaluate():
    p, ctx = make_profile("C000002"), make_context()
    res = ev(
        p, ctx, "OF_PCT_CAT", {"pct": 10, "min_basket": 999}, message="Guaranteed savings on Myntra prices"
    )
    assert not res.ok and [v.rule_id for v in res.violations] == ["G_MESSAGE"]


def test_disabled_rule_is_ignored():
    rules = [r.model_copy(update={"enabled": False}) if r.id == "G_QUIET" else r for r in SEED_RULES]
    night = make_context(now=NOW.replace(hour=23))
    assert ev(make_profile(), night, None, {}, rules=rules).ok
