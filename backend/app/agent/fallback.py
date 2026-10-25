"""Deterministic rules fallback (PLAN §3): used whenever the agent can't give a compliant answer.

Picks the allowed candidate with the highest expected incremental profit at its cheapest allowed point, or no
offer if nothing is expected to pay for itself, and fills a fixed template. No LLM involved.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.contracts import CustomerProfile, OfferCandidate, TriggerType
from app.rules.rule_types import NO_COUPON_TYPES, VALUE_KEYS, ZERO_COST_TYPES, category_label, inr


@dataclass
class FallbackChoice:
    candidate: OfferCandidate
    params: dict


def cheapest_params(cand: OfferCandidate) -> dict:
    params: dict = {}
    for key, rng in cand.allowed_params.items():
        lo = rng.get("min")
        if lo is None and key in VALUE_KEYS:
            lo = rng.get("max")
        if lo is not None:
            params[key] = lo
    if cand.category is not None:
        params["category"] = cand.category
    return params


def worth_sending(c: OfferCandidate) -> bool:
    """Paid offers must earn more than they cost; a free perk only must not lose anything."""
    return c.est_incremental_profit >= 0 if c.type in ZERO_COST_TYPES else c.est_incremental_profit > 0


def choose(candidates: list[OfferCandidate]) -> FallbackChoice | None:
    paying = [c for c in candidates if worth_sending(c)]
    if not paying:
        return None
    best = max(paying, key=lambda c: (c.est_incremental_profit, -c.est_cost))
    return FallbackChoice(best, cheapest_params(best))


def welcome_perk(candidates: list[OfferCandidate]) -> FallbackChoice | None:
    """Welcome guarantee: a first-time customer always gets the best allowed free perk (free shipping if no
    zero-cost perk is allowed), so onboarding never ends in silence."""
    perks = [c for c in candidates if c.type in ZERO_COST_TYPES] or [
        c for c in candidates if c.type == "free_shipping"
    ]
    if not perks:
        return None
    best = max(perks, key=lambda c: (c.est_incremental_profit, -c.est_cost, c.offer_id))
    return FallbackChoice(best, cheapest_params(best))


def offer_value(offer_type: str, params: dict) -> str:
    """'10% off ethnic wear', '₹150 off', 'Free shipping' — the exact value, used in messages and titles."""
    cat = params.get("category")
    on = f" {category_label(cat)}" if cat and offer_type in {"pct_off", "flat_off"} else ""
    return {
        "pct_off": f"{params.get('pct', 0):g}% off{on}",
        "flat_off": f"{inr(params.get('amount', 0))} off{on}",
        "free_shipping": "Free shipping",
        "free_express": "Free express delivery",
        "bonus_points": f"{params.get('multiplier', 2):g}× reward points",
        "points_reminder": "Points reminder",
        "cart_nudge": "Cart reminder",
        "early_access": "Early access",
    }.get(offer_type, offer_type.replace("_", " ").capitalize())


def coupon_prefix(offer_type: str) -> str:
    return {
        "pct_off": "SAVE",
        "flat_off": "FLAT",
        "free_shipping": "SHIP",
        "free_express": "EXPR",
        "bonus_points": "PTS",
        "early_access": "EARLY",
        "gift_card": "GIFT",
        "bundle": "BNDL",
        "birthday": "BDAY",
    }.get(offer_type, "OFF")


def safe_name(first_name: str) -> str:
    """Names are customer-typed: keep them short and plain in templates."""
    name = " ".join(first_name.split())[:20]
    return name or "there"


def template(
    profile: CustomerProfile,
    trigger: TriggerType,
    offer_type: str,
    params: dict,
    expires_at: datetime | None,
    opted_in_greeting: str | None,
) -> tuple[str, str]:
    """(headline, message). The message carries `{CODE}` where the coupon goes."""
    name = safe_name(profile.first_name)
    opener = f"{opted_in_greeting}, {name}!" if opted_in_greeting else f"Hi {name}!"
    exp = f" till {expires_at:%d %b}" if expires_at else ""
    code = " Code {CODE}." if offer_type not in NO_COUPON_TYPES else ""
    cart = profile.open_cart or {}
    item = cart.get("item")
    basket = params.get("min_basket") or 0
    above = f" on orders above {inr(basket)}" if basket else ""
    value = offer_value(offer_type, params)

    if offer_type == "cart_nudge":
        thing = f"Your {item}" if item else "Your cart"
        return "Still thinking it over?", f"{opener} {thing} is saved and waiting whenever you're ready."
    if offer_type == "points_reminder":
        pts = profile.points_balance
        return (
            "Your points are waiting",
            f"{opener} You have {pts:,} reward points to use on your next order.",
        )
    if offer_type == "early_access":
        return "You're on the early list", f"{opener} You get early access to our next sale{exp}.{code}"
    if offer_type in {"free_shipping", "free_express"}:
        lead = f"Your {item} is still in your cart. " if item and trigger == "cart_abandoned" else ""
        headline = "Shipping's on us" if offer_type == "free_shipping" else "Express delivery, on us"
        return headline, f"{opener} {lead}{value}{above}{exp}.{code}"
    if offer_type == "bonus_points":
        return "Extra points this week", f"{opener} Earn {value} on your next order{exp}.{code}"
    headline = f"{value.split(' off')[0]} off, just for you"
    if trigger == "inactivity":
        return "We've missed you", f"{opener} It's been a while. {value}{above}{exp}.{code}"
    return headline, f"{opener} {value}{above}{exp}.{code}"
