"""The default rule set (PLAN §4, §4b). These are data: the engine reads them from the `rules` table once
seeded, and falls back to this list while the table is empty. Marketers edit the numbers, not this file."""

from __future__ import annotations

from datetime import datetime

from app.config import IST
from app.contracts import Rule
from app.rules.rule_types import spec_for

_SEEDED_AT = datetime(2026, 10, 24, tzinfo=IST)
DISCOUNTS = ["pct_off", "flat_off"]
ZERO_COST = ["cart_nudge", "early_access", "points_reminder"]

# Gross margin by category, in %. Margin guard = margin minus the buffer.
CATEGORY_MARGINS = {
    "fashion": 45,
    "ethnic_wear": 45,
    "winter_wear": 45,
    "beauty": 50,
    "home_decor": 40,
    "gifting": 35,
    "kitchen": 30,
    "jewellery": 20,
    "electronics": 15,
    "grocery": 12,
}


def _rule(
    rid: str,
    layer: str,
    rtype: str,
    params: dict,
    conditions: dict | None = None,
    *,
    severity: str = "hard",
    priority: int = 100,
) -> Rule:
    rule = Rule(
        id=rid,
        layer=layer,
        type=rtype,
        severity=severity,
        conditions=conditions or {},
        params=params,
        priority=priority,
        updated_by="seed",
        updated_at=_SEEDED_AT,
    )
    return rule.model_copy(update={"description": spec_for(rule).describe()})


GLOBAL_RULES = [
    _rule("G_MARGIN", "global", "margin_guard", {"buffer_pct": 5, "margins": CATEGORY_MARGINS}),
    _rule("G_CAP", "global", "discount_cap", {"max_pct": 30, "max_amount": 500, "max_multiplier": 3}),
    _rule("G_FREQ", "global", "frequency_cap", {"max_7d": 3, "min_gap_h": 48}),
    _rule("G_QUIET", "global", "quiet_hours", {"start": "21:00", "end": "09:00"}),
    _rule("G_BUDGET", "global", "budget", {"daily_cap": 50000}),
    _rule("G_ONE_COUPON", "global", "stacking", {"max_active": 1}),
    _rule("G_POST_PURCHASE", "global", "exclusion", {"offer_types": "all", "within_purchase_h": 48}),
    _rule(
        "G_MESSAGE",
        "global",
        "message",
        {
            "max_len": 280,
            "banned_phrases": ["guaranteed", "free money", "last chance"],
            "competitors": ["Amazon", "Flipkart", "Myntra", "Meesho", "Ajio", "Nykaa"],
        },
    ),
]

FESTIVAL_RULES = [
    _rule("F_POOL", "festival", "budget", {"use_festival_pool": True}, {"festival": "*"}),
    _rule(
        "F_TEASER_ZERO_COST",
        "festival",
        "eligibility",
        {"offer_types": [*ZERO_COST, "bonus_points"]},
        {"festival": "*", "phase": "teaser"},
    ),
    _rule(
        "F_BUILDUP_HERO",
        "festival",
        "eligibility",
        {"hero_only": True},
        {"festival": "*", "phase": "build_up"},
    ),
    _rule(
        "F_LASTMIN_CAP",
        "festival",
        "discount_cap",
        {"max_pct": 10},
        {"festival": "*", "phase": "last_minute"},
    ),
    # Dhanteras and Diwali: people buy anyway, so keep discounts tiny and lean on perks instead
    _rule(
        "F_PEAK_DAYS_CAP",
        "festival",
        "discount_cap",
        {"max_pct": 5, "max_amount": 100},
        {"festival": ["dhanteras", "diwali"], "phase": "last_minute"},
    ),
    _rule(
        "F_POST_NO_DISCOUNT",
        "festival",
        "exclusion",
        {"offer_types": DISCOUNTS, "within_purchase_h": 240},
        {"festival": "*", "phase": "post"},
    ),
    _rule(
        "F_RESTRICTED",
        "festival",
        "festival_restriction",
        {
            "restricted_terms": ["alcohol", "liquor", "beer", "wine", "meat", "chicken", "mutton"],
            "use_festival_list": True,
        },
        {"festival": ["navratri", "gurpurab"]},
    ),
]

FESTIVAL_RULES.append(
    _rule(
        "F_FESTIVAL_PROMOS",
        "festival",
        "festival_restriction",
        {"restricted_terms": [], "use_festival_list": True},
        {"festival": "*"},
    )
)

PERSONA_RULES = [
    _rule(
        "P_VIP_PERKS",
        "persona",
        "eligibility",
        {"offer_types": ["early_access", "bonus_points", "free_shipping", "free_express", "points_reminder"]},
        {"policy": "vip"},
    ),
    _rule(
        "P_DEAL_CAP", "persona", "discount_cap", {"max_pct": 10, "min_basket": 999}, {"policy": "deal_hunter"}
    ),
    _rule(
        "P_DEAL_TYPES",
        "persona",
        "eligibility",
        {"offer_types": [*DISCOUNTS, "cart_nudge", "points_reminder"]},
        {"policy": "deal_hunter"},
    ),
    _rule(
        "P_ATRISK_WINBACK",
        "persona",
        "eligibility",
        {
            "offer_types": ["pct_off", "bundle", "free_shipping", "bonus_points", "cart_nudge"],
            "min_uplift": 0.05,
        },
        {"policy": "at_risk"},
    ),
    _rule("P_ATRISK_CAP", "persona", "discount_cap", {"max_pct": 20}, {"policy": "at_risk"}),
    _rule("P_ATRISK_MONTHLY", "persona", "frequency_cap", {"min_gap_h": 720}, {"policy": "at_risk"}),
    _rule(
        "P_NEW_WELCOME",
        "persona",
        "eligibility",
        {"offer_types": ["pct_off", "free_shipping", "cart_nudge", "points_reminder"]},
        {"policy": "new_user"},
    ),
    _rule("P_NEW_CAP", "persona", "discount_cap", {"max_pct": 15}, {"policy": "new_user"}),
    _rule(
        "P_CART_LADDER",
        "persona",
        "escalation_ladder",
        {
            "steps": [
                {"after_h": 0.5, "offer_types": ["cart_nudge", "free_shipping"]},
                {"after_h": 24, "offer_types": ["pct_off"], "max_pct": 5},
            ]
        },
        {"policy": "cart_abandoner"},
    ),
    _rule(
        "P_CART_TYPES",
        "persona",
        "eligibility",
        {"offer_types": ["cart_nudge", "free_shipping", "pct_off", "bonus_points"]},
        {"policy": "cart_abandoner"},
    ),
    _rule(
        "P_WINDOW_TYPES",
        "persona",
        "eligibility",
        {"offer_types": ["free_shipping", "flat_off", "cart_nudge", "early_access"]},
        {"policy": "window_shopper"},
    ),
    _rule("P_WINDOW_CAP", "persona", "discount_cap", {"max_amount": 150}, {"policy": "window_shopper"}),
    _rule(
        "P_RETURNER_POINTS",
        "persona",
        "eligibility",
        {"offer_types": ["bonus_points", "points_reminder"]},
        {"policy": "high_returner"},
    ),
    _rule("P_SLEEPING_DOG", "persona", "exclusion", {"offer_types": "all"}, {"policy": "sleeping_dog"}),
    _rule(
        "P_DORMANT_TYPES",
        "persona",
        "eligibility",
        {"offer_types": ["pct_off", "free_shipping", "cart_nudge"]},
        {"policy": "dormant"},
    ),
    _rule("P_DORMANT_CAP", "persona", "discount_cap", {"max_pct": 15}, {"policy": "dormant"}),
    _rule("P_DORMANT_ONE_TRY", "persona", "frequency_cap", {"min_gap_h": 2160}, {"policy": "dormant"}),
]

INDIVIDUAL_RULES = [
    _rule("I_NOT_FOR_ME", "individual", "exclusion", {"use_suppressed": True}),
    # examples of per-customer overrides a marketer adds from the dashboard
    _rule("I_FRAUD_C004242", "individual", "exclusion", {"offer_types": "all"}, {"customer_id": "C004242"}),
    _rule("I_TIGHT_C000777", "individual", "discount_cap", {"max_pct": 5}, {"customer_id": "C000777"}),
]

SEED_RULES: list[Rule] = [*GLOBAL_RULES, *FESTIVAL_RULES, *PERSONA_RULES, *INDIVIDUAL_RULES]
POLICIES_COVERED = {r.conditions["policy"] for r in PERSONA_RULES}


def ensure_seeded() -> int:
    """Insert any seed rule missing from the `rules` table. Never overwrites a rule a marketer has edited."""
    from app.db import init_db, session_scope
    from app.models import RuleRow

    init_db()
    added = 0
    with session_scope() as s:
        for rule in SEED_RULES:
            if s.get(RuleRow, rule.id) is None:
                s.add(RuleRow(**rule.model_dump()))
                added += 1
    return added
