"""Default offer catalogue: the offer *templates* the rules narrow. Rows live in the `offers` table once
seeded (marketers can switch them on/off); this list is the fallback and the seed."""

from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from app.contracts import Offer


def _offer(oid: str, otype: str, name: str, description: str, schema: dict, cost_model: str, **kw) -> Offer:
    return Offer(
        id=oid,
        type=otype,
        name=name,
        description=description,
        param_schema=schema,
        base_cost_model=cost_model,
        **kw,
    )


DEFAULT_OFFERS: list[Offer] = [
    _offer("OF_NUDGE", "cart_nudge", "Cart reminder", "A friendly reminder, no discount", {}, "zero"),
    _offer(
        "OF_POINTS_REMIND", "points_reminder", "Points reminder", "Reminds the customer of points", {}, "zero"
    ),
    _offer("OF_EARLY", "early_access", "Early access", "Early access to the next sale", {}, "zero"),
    _offer(
        "OF_FREE_SHIP",
        "free_shipping",
        "Free shipping",
        "Free standard shipping",
        {"min_basket": {"min": 0, "max": 999}},
        "shipping_cost",
    ),
    _offer(
        "OF_FREE_EXPRESS",
        "free_express",
        "Free express delivery",
        "Free express delivery, arrives sooner",
        {"min_basket": {"min": 0, "max": 1999}},
        "express_cost",
    ),
    _offer(
        "OF_POINTS2X",
        "bonus_points",
        "Bonus points",
        "Extra reward points on the next order",
        {"multiplier": {"min": 2, "max": 3}},
        "points_liability",
    ),
    _offer(
        "OF_PCT_CAT",
        "pct_off",
        "% off a category",
        "Percent off one category",
        {"pct": {"min": 5, "max": 30}, "min_basket": {"min": 0}},
        "pct*aov*p_redeem",
    ),
    _offer(
        "OF_WINBACK",
        "pct_off",
        "Win-back discount",
        "We-miss-you discount",
        {"pct": {"min": 10, "max": 20}, "min_basket": {"min": 999}},
        "pct*aov*p_redeem",
    ),
    _offer(
        "OF_WELCOME2",
        "pct_off",
        "Second-order welcome",
        "Welcome discount on the second order",
        {"pct": {"min": 10, "max": 15}},
        "pct*aov*p_redeem",
    ),
    _offer(
        "OF_FLAT",
        "flat_off",
        "Flat ₹ off",
        "Flat rupees off above a minimum basket",
        {"amount": {"min": 50, "max": 500}, "min_basket": {"min": 499}},
        "amount*p_redeem",
    ),
]


def load_offers() -> list[Offer]:
    from app.db import engine as db_engine
    from app.models import OfferRow

    try:
        with Session(db_engine) as s:
            rows = s.exec(select(OfferRow)).all()
    except SQLAlchemyError:
        return list(DEFAULT_OFFERS)
    return [Offer.model_validate(r.model_dump()) for r in rows] or list(DEFAULT_OFFERS)


def ensure_offers_seeded() -> int:
    """Insert missing default offers into the `offers` table. Never overwrites an edited offer."""
    from app.db import init_db, session_scope
    from app.models import OfferRow

    init_db()
    added = 0
    with session_scope() as s:
        for offer in DEFAULT_OFFERS:
            if s.get(OfferRow, offer.id) is None:
                s.add(OfferRow(**offer.model_dump()))
                added += 1
    return added
