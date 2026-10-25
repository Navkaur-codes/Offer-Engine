"""Turn a Telegram user's onboarding taps into a synthetic customer with ~6 months of matching history.

The answers (categories, frequency, style, festivals) pick a hidden persona and drive a one-customer run of
the same behaviour model as the generator, so a classmate's profile, RFM and policy look real from the
first message. Nothing is inferred from the name; festival opt-ins are exactly what the user tapped.

Writes the customer row (before its history, for the foreign keys) and the history rows. Re-running
/start replaces only the generated history (ids `E<customer>-…`, `O<customer>-…`), never `/simulate` events.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import numpy as np
from sqlalchemy import delete
from sqlmodel import Session

from app import db
from app.config import IST, now
from app.contracts import Customer, Persona
from app.data.catalog import CATEGORIES, PRODUCTS
from app.data.festivals import OPT_IN_KEYS
from app.data.generator import CATS, CITIES, HOUR_WEIGHTS, _day_factors, _match_products
from app.data.personas import PERSONAS, RESPONSE_BASELINE, RESPONSE_COUPON_MULT
from app.models import CustomerRow, EventRow, OrderRow, PointsLedgerRow

HISTORY_DAYS = 365
FREQUENCY_MULT = {"weekly": 1.6, "monthly": 0.9, "occasionally": 0.55, "rarely": 0.35}
POINTS_EXPIRY_DAYS = 180
MIN_ORDERS: dict[str, int] = {"new_user": 0, "window_shopper": 0, "loyal_vip": 6, "at_risk_regular": 4}
MIN_DAYS_SINCE_PURCHASE = 3
AT_RISK_BROWSE_SHARE = 0.7  # visits an at-risk regular keeps making after they stop buying
RECENT_PURCHASE_DAYS = {"weekly": 21, "monthly": 45}  # latest order is at most this old, per stated frequency
_PERSONA: dict[tuple[str, str], Persona] = {
    ("weekly", "deal"): "deal_hunter",
    ("monthly", "deal"): "deal_hunter",
    ("occasionally", "deal"): "cart_abandoner",
    ("weekly", "quality"): "loyal_vip",
    ("monthly", "quality"): "loyal_vip",
    ("occasionally", "quality"): "window_shopper",
    ("weekly", "balanced"): "cart_abandoner",
    ("monthly", "balanced"): "at_risk_regular",
    ("occasionally", "balanced"): "window_shopper",
}


def persona_for(answers: dict) -> Persona:
    freq, style = answers.get("frequency", "monthly"), answers.get("style", "balanced")
    if freq == "rarely":
        return "new_user"
    persona = _PERSONA.get((freq, style), "new_user")
    if style == "quality" and freq != "weekly" and answers.get("festivals"):
        return "festive_gifter"  # buys big around the festivals they care about
    return persona


def create_profile_from_answers(telegram_id: int, first_name: str, answers: dict) -> Customer:
    clock = now()
    rng = np.random.default_rng(abs(telegram_id) % (2**32))
    categories = [c for c in answers.get("categories", []) if c in CATEGORIES]
    festivals = [f for f in answers.get("festivals", []) if f in OPT_IN_KEYS]
    persona = persona_for(answers)
    spec = PERSONAS[persona]
    # someone who just opted in to an offers bot is, by definition, not offer-averse: no sleeping dogs
    mix = {r: w for r, w in spec.response_mix.items() if r != "sleeping_dog"}
    total = sum(mix.values())
    city, tier, state, _ = CITIES[rng.choice(len(CITIES), p=_city_weights())]
    history_days = (
        int(rng.integers(8, 13)) if persona == "new_user" else HISTORY_DAYS + int(rng.integers(180, 420))
    )
    customer = Customer(
        id=f"TG{telegram_id}",
        first_name=first_name,
        city=city,
        city_tier=tier,
        signup_date=clock.date() - timedelta(days=history_days),
        channel="telegram",
        device="mobile",
        preferred_payment="upi",
        persona=persona,
        response_type=str(rng.choice(list(mix), p=[w / total for w in mix.values()])),
        telegram_chat_id=telegram_id,
        opt_in_festivals=festivals,
        # Real classmates are never held out: a silent bot would read as broken during judging.
        is_holdout=False,
    )
    events, orders, ledger = _history(customer, categories, answers.get("frequency", "monthly"), clock, rng)
    _save(customer, state, answers, events, orders, ledger, clock)
    return customer


def _city_weights() -> np.ndarray:
    w = np.array([c[3] for c in CITIES])
    return w / w.sum()


# ------------------------------------------------------------------ one-customer simulation
def _history(
    customer: Customer, categories: list[str], frequency: str, clock: datetime, rng: np.random.Generator
):
    spec = PERSONAS[customer.persona]
    base_visit, base_conv = RESPONSE_BASELINE[customer.response_type]
    # the simulated window is at most the last year; established customers signed up well before it, as in
    # the seeded world (a one-year-old account with a year of heavy buying looks like nobody real)
    start = max(customer.signup_date, clock.date() - timedelta(days=HISTORY_DAYS))
    days = [start + timedelta(days=i) for i in range((clock.date() - start).days)]
    f = _day_factors(days)

    weights = np.array([spec.category_weights()[c] for c in CATS])
    for c in categories:
        weights[CATS.index(c)] *= 4  # what they told us they shop for dominates
    weights /= weights.sum()

    prices = np.array([p.price for p in PRODUCTS])
    prod_cat = np.array([CATS.index(p.category) for p in PRODUCTS])
    cat_sorted = [np.where(prod_cat == k)[0][np.argsort(prices[prod_cat == k])] for k in range(len(CATS))]
    hour_p = HOUR_WEIGHTS / HOUR_WEIGHTS.sum()
    rate = spec.visit_rate * FREQUENCY_MULT.get(frequency, 0.9) * base_visit
    if customer.persona == "loyal_vip":
        # self-declared weekly quality shoppers are the store's best customers; ×1.2 keeps them at real-VIP
        # volume (~6 orders a quarter), anything far beyond that is outside what the uplift model has seen
        rate *= 1.2
    quiet_from = len(days) - int(rng.integers(62, 80)) if customer.persona == "at_risk_regular" else len(days)
    can_buy = customer.persona != "window_shopper"
    # no generated purchase in the last few days: a fresh one would trip the post-purchase cooling-off rule
    # and silence the welcome the user just asked for
    last_buy_day = len(days) - MIN_DAYS_SINCE_PURCHASE

    cid = customer.id
    events: list[dict] = []
    orders: list[dict] = []
    ledger: list[dict] = []

    def event(typ: str, ts: datetime, cat=None, item=None, value=None, **meta) -> None:
        events.append(
            dict(
                id=f"E{cid}-{len(events) + 1:05d}",
                customer_id=cid,
                type=typ,
                ts=ts,
                category=cat,
                item=item,
                value=value,
                meta={"src": "onboarding", **meta},
            )
        )

    def session(t: int, sid: str, force: bool = False, browse_only: bool = False) -> None:
        conv = base_conv * f["conv"][t] * (1 + spec.festival_sensitivity * (f["fest_conv"][t] - 1))
        day_w = weights * f["catmult"][t]
        ts = datetime.combine(days[t], time(int(rng.choice(24, p=hour_p)), int(rng.integers(60))), IST)
        ts += timedelta(seconds=int(rng.integers(60)))
        event("session", ts, sid=sid)
        k = int(rng.choice(len(CATS), p=day_w / day_w.sum()))
        target = np.exp(
            np.log(CATEGORIES[CATS[k]].aov_median * spec.aov_mult * f["fest_aov"][t])
            + CATEGORIES[CATS[k]].aov_sigma * rng.standard_normal(1)
        )
        prod, qty = _match_products(target, np.array([k]), cat_sorted, prices, rng)
        product, qty = PRODUCTS[int(prod[0])], int(qty[0])
        for _ in range(1 + rng.poisson(1.8)):
            seen = PRODUCTS[k * 12 + int(rng.integers(12))]
            ts += timedelta(seconds=int(rng.integers(20, 180)))
            event("view", ts, CATS[k], seen.name, seen.price, sid=sid)
        if browse_only or (not force and rng.random() >= min(spec.p_cart * conv, 0.95)):
            return
        ts += timedelta(seconds=60)
        event("add_to_cart", ts, CATS[k], product.name, product.price * qty, sid=sid)
        if not can_buy or (not force and rng.random() >= spec.p_checkout * 0.92):
            return
        ts += timedelta(minutes=3)
        event("checkout_started", ts, CATS[k], product.name, product.price * qty, sid=sid)
        if t >= last_buy_day or (not force and rng.random() >= spec.p_purchase):
            return
        ts += timedelta(minutes=2)
        _order(customer, product, qty, ts, sid, spec, rng, clock, event, orders, ledger)

    for t in range(len(days)):
        lam = rate * f["visit"][t] * (1 + spec.festival_sensitivity * (f["fest_visit"][t] - 1))
        lapsed = t >= quiet_from
        if lapsed:
            # a lapsing regular stops buying but still browses: the win-back-able at-risk customer
            lam *= AT_RISK_BROWSE_SHARE
        for s in range(rng.poisson(lam)):
            session(t, f"{t}-{s}", browse_only=lapsed)

    # a short history can come out empty by chance; top up so the profile matches the answers
    shortfall = MIN_ORDERS.get(customer.persona, 2) - len(orders)
    lo, hi = (0, quiet_from) if quiet_from < len(days) else (max(len(days) - 40, 0), last_buy_day)
    hi = min(hi, last_buy_day)
    for n in range(max(shortfall, 0)):
        session(int(rng.integers(lo, max(hi, lo + 1))), f"top-{n}", force=True)

    # someone who says they shop weekly / monthly has bought something lately
    within = RECENT_PURCHASE_DAYS.get(frequency)
    if within and customer.persona not in ("at_risk_regular", "window_shopper", "new_user"):
        recent_from = clock - timedelta(days=within)
        if not any(o["ts"] >= recent_from for o in orders):
            first = max(len(days) - within + 1, 0)  # +1: any hour of that day stays inside the window
            session(int(rng.integers(first, max(last_buy_day, first + 1))), "recent", force=True)

    if (
        customer.persona == "cart_abandoner"
    ):  # a fresh open cart, so the first decision has something to act on
        product = PRODUCTS[
            CATS.index(categories[0] if categories else "fashion") * 12 + int(rng.integers(12))
        ]
        ts = clock - timedelta(minutes=int(rng.integers(40, 120)))
        event("session", ts, sid="open")
        event("view", ts + timedelta(seconds=40), product.category, product.name, product.price, sid="open")
        event(
            "add_to_cart",
            ts + timedelta(seconds=90),
            product.category,
            product.name,
            product.price,
            sid="open",
        )
    return events, orders, ledger


def _order(customer, product, qty, ts, sid, spec, rng, clock, event, orders, ledger) -> None:
    cid = customer.id
    value = product.price * qty
    oid = f"O{cid}-{len(orders) + 1:04d}"
    # same response-type trace as the generator: persuadables buy on coupons, sure-things pay full price
    coupon_p = min(spec.discount_usage * RESPONSE_COUPON_MULT[customer.response_type], 0.95)
    pct = int(rng.choice([5, 10, 15])) if rng.random() < coupon_p else 0
    return_at = ts + timedelta(days=int(rng.integers(3, 13)))
    returned = (
        rng.random() < CATEGORIES[product.category].return_rate * spec.return_mult and return_at < clock
    )
    orders.append(
        dict(
            id=oid,
            customer_id=cid,
            ts=ts,
            category=product.category,
            items=qty,
            value=value,
            discount=value * pct // 100,
            coupon_code=f"SAVE{pct}" if pct else None,
            payment_method=customer.preferred_payment,
            returned=returned,
        )
    )
    event("purchase", ts, product.category, product.name, value, sid=sid, order_id=oid)
    if returned:
        event("return", return_at, product.category, product.name, value, order_id=oid)
    elif value >= 100:
        ledger.append(
            dict(
                customer_id=cid,
                ts=ts,
                delta=value // 100,
                reason=f"onboarding:earn:{oid}",
                expires_on=ts.date() + timedelta(days=POINTS_EXPIRY_DAYS),
            )
        )


# ------------------------------------------------------------------ persistence
def _tier(orders: list[dict], today: date) -> str:
    spend = sum(
        o["value"] for o in orders if not o["returned"] and o["ts"].date() > today - timedelta(days=365)
    )
    return (
        "Platinum"
        if spend >= 75000
        else "Gold"
        if spend >= 30000
        else "Silver"
        if spend >= 10000
        else "Bronze"
    )


def _save(customer: Customer, state: str, answers: dict, events, orders, ledger, clock: datetime) -> None:
    cid = customer.id
    balance = sum(p["delta"] for p in ledger if p["expires_on"] > clock.date())
    with Session(db.engine) as s:
        row = s.get(CustomerRow, cid) or CustomerRow(**customer.model_dump())
        for field in (
            "first_name",
            "city",
            "city_tier",
            "signup_date",
            "channel",
            "device",
            "preferred_payment",
            "persona",
            "response_type",
            "telegram_chat_id",
            "opt_in_festivals",
            "is_holdout",
        ):
            setattr(row, field, getattr(customer, field))
        row.points_balance = balance
        row.tier = _tier(orders, clock.date())
        row.attrs = {**(row.attrs or {}), "state": state, "onboarding": answers, "synthetic_history": True}
        s.add(row)
        s.flush()  # the customer row must exist before its history (foreign keys on Postgres)
        s.execute(delete(EventRow).where(EventRow.id.like(f"E{cid}-%")))
        s.execute(delete(OrderRow).where(OrderRow.id.like(f"O{cid}-%")))
        s.execute(
            delete(PointsLedgerRow).where(
                PointsLedgerRow.customer_id == cid, PointsLedgerRow.reason.like("onboarding:%")
            )
        )
        for model, rows in ((EventRow, events), (OrderRow, orders), (PointsLedgerRow, ledger)):
            if rows:
                s.execute(model.__table__.insert(), rows)
        s.commit()
