"""The 9 hidden personas that drive the simulation (contracts.Persona).

A persona is ground truth for the generator only. Scoring sees behaviour, never the label: the dynamic
policy is re-derived from events, so a "deal_hunter" can drift into "at_risk" like a real customer.

Rates are per active day / per session and were tuned so the whole population lands inside the
benchmark ranges in `tests/data/test_generator_stats.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.contracts import Category, Persona, ResponseType

BASE_CATEGORY_WEIGHTS: dict[Category, float] = {
    "fashion": 0.22,
    "ethnic_wear": 0.10,
    "electronics": 0.08,
    "beauty": 0.14,
    "home_decor": 0.08,
    "kitchen": 0.08,
    "grocery": 0.14,
    "jewellery": 0.04,
    "gifting": 0.06,
    "winter_wear": 0.06,
}


@dataclass(frozen=True)
class PersonaSpec:
    name: Persona
    share: float  # of the synthetic population
    visit_rate: float  # mean sessions per active day, before the per-customer lognormal spread
    p_cart: float  # session → add_to_cart
    p_checkout: float  # cart → checkout_started
    p_purchase: float  # checkout → purchase
    aov_mult: float  # scales every category's lognormal median
    discount_usage: float  # share of orders that use some coupon
    return_mult: float  # scales the category return rate
    churn_hazard: float  # daily probability of going quiet (ignored for scripted personas below)
    festival_sensitivity: float  # 1.0 = average reaction to festival lifts
    response_mix: dict[ResponseType, float]
    age_mean: float
    age_sd: float
    category_tilt: dict[Category, float] = field(default_factory=dict)  # multiplies BASE_CATEGORY_WEIGHTS

    def category_weights(self) -> dict[Category, float]:
        raw = {c: w * self.category_tilt.get(c, 1.0) for c, w in BASE_CATEGORY_WEIGHTS.items()}
        total = sum(raw.values())
        return {c: w / total for c, w in raw.items()}


PERSONAS: dict[Persona, PersonaSpec] = {
    p.name: p
    for p in [
        PersonaSpec(
            "loyal_vip",
            0.06,
            0.24,
            0.34,
            0.62,
            0.82,
            1.45,
            0.10,
            0.7,
            0.0004,
            0.7,
            {"sure_thing": 0.70, "persuadable": 0.15, "lost_cause": 0.05, "sleeping_dog": 0.10},
            36,
            8,
            {"electronics": 1.8, "jewellery": 1.6, "grocery": 0.6},
        ),
        PersonaSpec(
            "deal_hunter",
            0.16,
            0.17,
            0.26,
            0.46,
            0.66,
            0.80,
            0.70,
            1.0,
            0.0012,
            1.2,
            {"persuadable": 0.50, "sure_thing": 0.30, "lost_cause": 0.15, "sleeping_dog": 0.05},
            27,
            6,
            {"fashion": 1.2, "beauty": 1.3, "jewellery": 0.5},
        ),
        PersonaSpec(
            "at_risk_regular",
            0.10,
            0.16,
            0.30,
            0.52,
            0.72,
            1.10,
            0.25,
            0.9,
            0.0,
            1.0,
            {"persuadable": 0.55, "sure_thing": 0.10, "lost_cause": 0.25, "sleeping_dog": 0.10},
            34,
            9,
            {"home_decor": 1.4, "kitchen": 1.3},
        ),
        PersonaSpec(
            "new_user",
            0.10,
            0.15,
            0.22,
            0.42,
            0.62,
            0.90,
            0.45,
            1.0,
            0.0020,
            1.0,
            {"persuadable": 0.45, "sure_thing": 0.20, "lost_cause": 0.25, "sleeping_dog": 0.10},
            25,
            6,
            {"beauty": 1.3, "fashion": 1.1},
        ),
        PersonaSpec(
            "dormant",
            0.12,
            0.11,
            0.20,
            0.40,
            0.60,
            0.90,
            0.30,
            1.0,
            0.0,
            0.8,
            {"lost_cause": 0.55, "persuadable": 0.25, "sure_thing": 0.05, "sleeping_dog": 0.15},
            38,
            11,
            {},
        ),
        PersonaSpec(
            "window_shopper",
            0.16,
            0.20,
            0.10,
            0.36,
            0.56,
            0.85,
            0.30,
            1.0,
            0.0010,
            1.0,
            {"persuadable": 0.30, "lost_cause": 0.45, "sure_thing": 0.10, "sleeping_dog": 0.15},
            24,
            5,
            {"electronics": 1.5, "fashion": 1.2, "grocery": 0.5},
        ),
        PersonaSpec(
            "cart_abandoner",
            0.12,
            0.15,
            0.46,
            0.30,
            0.52,
            1.00,
            0.35,
            1.0,
            0.0014,
            1.0,
            {"persuadable": 0.60, "sure_thing": 0.10, "lost_cause": 0.20, "sleeping_dog": 0.10},
            29,
            7,
            {"fashion": 1.3, "electronics": 1.2},
        ),
        PersonaSpec(
            "festive_gifter",
            0.12,
            0.07,
            0.32,
            0.52,
            0.72,
            1.50,
            0.30,
            0.8,
            0.0006,
            2.4,
            {"persuadable": 0.35, "sure_thing": 0.40, "lost_cause": 0.15, "sleeping_dog": 0.10},
            40,
            10,
            {"gifting": 3.0, "jewellery": 2.5, "ethnic_wear": 1.6, "home_decor": 1.4, "grocery": 0.4},
        ),
        PersonaSpec(
            "high_returner",
            0.06,
            0.17,
            0.30,
            0.50,
            0.70,
            1.10,
            0.35,
            3.0,
            0.0010,
            1.0,
            {"persuadable": 0.25, "sure_thing": 0.30, "lost_cause": 0.20, "sleeping_dog": 0.25},
            28,
            6,
            {"fashion": 1.9, "ethnic_wear": 1.5, "grocery": 0.4},
        ),
    ]
}

assert abs(sum(p.share for p in PERSONAS.values()) - 1.0) < 1e-9

# How a hidden response type bends behaviour outside campaigns: sure-things are strong buyers anyway,
# lost causes barely buy. This is what makes "don't pay people who'd buy anyway" visible in the data.
RESPONSE_BASELINE: dict[ResponseType, tuple[float, float]] = {  # (visit mult, conversion mult)
    "sure_thing": (1.15, 1.35),
    "persuadable": (1.0, 0.85),
    "lost_cause": (0.6, 0.45),
    "sleeping_dog": (1.0, 1.0),
}

# The traces a response type leaves in observable behaviour, so an uplift model can learn it:
# persuadables buy when there is a deal (heavy coupon use), sure-things pay full price, and sleeping dogs
# push back on marketing ("Not for me").
RESPONSE_COUPON_MULT: dict[ResponseType, float] = {
    "persuadable": 1.7,
    "sure_thing": 0.3,
    "lost_cause": 1.0,
    "sleeping_dog": 0.6,
}
RESPONSE_DECLINE_P: dict[ResponseType, float] = {
    "persuadable": 0.02,
    "sure_thing": 0.04,
    "lost_cause": 0.10,
    "sleeping_dog": 0.45,
}


def response_effect(response: ResponseType, strength: float) -> tuple[float, float, float]:
    """(visit mult, conversion mult, immediate churn prob) while a customer holds a campaign offer.

    `strength` is 0..1 (a 15% discount ≈ 1.0). Persuadables move a lot, sure-things not at all, lost causes
    barely, and sleeping dogs are *put off*: some go quiet for good.
    """
    if response == "persuadable":
        return 1 + 0.7 * strength, 1 + 1.2 * strength, 0.0
    if response == "sleeping_dog":
        return 1 - 0.5 * strength, 1 - 0.5 * strength, 0.08 * strength
    if response == "lost_cause":
        return 1 + 0.05 * strength, 1 + 0.05 * strength, 0.0
    return 1.0, 1.0, 0.0
