"""Expected cost and incremental profit of one offer for one customer (whole ₹).

    cost               = what we give away, paid on *every* redemption, including by people who'd buy anyway
                         (discount × basket, shipping cost, or points liability) × P(buy | offer)
    incremental_profit = (uplift − error band) × basket × margin − cost     (paid offers)
                       = max(uplift, 0) × basket × margin                   (zero-cost offers; a clear
                         negative uplift beyond the error band still counts: contact annoys sleeping dogs)

Sure-things therefore come out negative for any paid offer (high P(buy), uplift ≈ 0), which is exactly the
margin the engine saves by not discounting them. Zero-cost offers cost nothing and earn their uplift.
"""

from __future__ import annotations

from app.contracts import CustomerProfile, OfferType
from app.data.catalog import CATEGORIES
from app.scoring import uplift

DEFAULT_BASKET = 1200  # ₹, for customers with no order history yet
POINT_VALUE_INR = 1.0  # what one reward point costs us when redeemed
POINTS_REDEEM_SHARE = 0.6  # share of awarded points that ever get redeemed
EXPRESS_COST_MULT = 2.0  # express delivery vs standard shipping
ZERO_COST: set[str] = {"cart_nudge", "points_reminder", "early_access"}
UPLIFT_ERROR_BAND = 0.01  # ≈ the T-learner's per-customer noise (held-out); paid offers must beat it
REFERENCE_STRENGTH = {"pct_off": 12.5, "flat_off": 250}  # what the past campaigns offered, on average


def _category(profile: CustomerProfile, category: str | None) -> str | None:
    if category in CATEGORIES:
        return category
    if profile.category_affinity:
        return max(profile.category_affinity, key=profile.category_affinity.get)
    return None


def _basket(profile: CustomerProfile, category: str | None, params: dict) -> int:
    base = profile.aov or (CATEGORIES[category].aov_median if category else DEFAULT_BASKET)
    return int(max(base, params.get("min_basket") or 0))


def _strength(offer_type: str, params: dict, basket: int) -> float:
    """A bigger incentive moves people more, with diminishing returns; 1.0 = what past campaigns offered."""
    if offer_type == "pct_off" and params.get("pct"):
        ratio = params["pct"] / REFERENCE_STRENGTH["pct_off"]
    elif offer_type == "flat_off" and params.get("amount"):
        ratio = (params["amount"] / max(basket, 1)) / (REFERENCE_STRENGTH["flat_off"] / 2000)
    elif offer_type == "bonus_points" and params.get("multiplier"):
        ratio = (params["multiplier"] - 1) / 1.0
    else:
        return 1.0
    return max(0.3, min(ratio, 2.0)) ** 0.7


def _giveaway(offer_type: str, params: dict, basket: int, category: str | None) -> float:
    ship = CATEGORIES[category].shipping_cost if category else 70
    if offer_type == "pct_off":
        return basket * params.get("pct", 10) / 100
    if offer_type == "flat_off":
        return params.get("amount", 100)
    if offer_type == "free_shipping":
        return ship
    if offer_type == "free_express":
        return ship * EXPRESS_COST_MULT
    if offer_type == "bonus_points":
        extra_points = (params.get("multiplier", 2) - 1) * basket / 100  # 1 point per ₹100
        return extra_points * POINT_VALUE_INR * POINTS_REDEEM_SHARE
    if offer_type in {"bundle", "gift_card", "birthday"}:
        return basket * 0.10
    return 0.0


def estimate(
    profile: CustomerProfile, offer_type: OfferType, params: dict, category: str | None
) -> tuple[int, int]:
    """(expected cost ₹, expected incremental profit ₹)."""
    cat = _category(profile, params.get("category") or category)
    basket = _basket(profile, cat, params)
    margin = CATEGORIES[cat].margin if cat else 0.35
    strength = _strength(offer_type, params, basket)
    lift = uplift.predict(profile, offer_type) * strength
    _, p_no_offer = uplift.p_buy(profile, offer_type)
    p_offer = min(max(p_no_offer + lift, 0.0), 1.0)  # everyone who buys with the offer redeems it
    if offer_type in ZERO_COST:
        # nothing is given away, so only a clear predicted backlash (a sleeping dog) counts against it
        value = lift if lift < -UPLIFT_ERROR_BAND else max(lift, 0.0)
        return 0, int(round(value * basket * margin))
    cost = _giveaway(offer_type, params, basket, cat) * p_offer
    # money is only spent when the predicted lift clears the model's error band
    profit = (lift - UPLIFT_ERROR_BAND) * basket * margin - cost
    return int(round(cost)), int(round(profit))
