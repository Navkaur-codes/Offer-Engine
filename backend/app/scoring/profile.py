"""CustomerProfile from live DB rows, plus dynamic policy membership.

`build_profile` reads only rows with ts ≤ `now`, so demo time-travel and freshly inserted `/simulate` events
are reflected immediately (no cache per customer). Four indexed queries; target < 50 ms.

Policy thresholds live in `POLICY_THRESHOLDS` (one config dict, PLAN §4). Activity facts that the contract
has no field for (orders_total, views_90d, days_since_active, tenure_days) travel inside `profile.rfm`,
so `assign_policy(profile)` needs nothing but the profile.
"""

from __future__ import annotations

import time as _time
from datetime import date, datetime, timedelta
from typing import get_args

from sqlalchemy import func
from sqlmodel import Session, select

from app import db
from app.config import IST
from app.contracts import Category, CustomerProfile, OfferType, PolicyName
from app.data.catalog import CATEGORIES
from app.models import CustomerRow, DecisionRow, EventRow, OrderRow, PointsLedgerRow
from app.scoring import churn, rfm

POLICY_THRESHOLDS: dict = {
    "high_returner": {"min_return_rate": 0.40, "min_orders": 3},
    # every offer type must be predicted to *hurt*, by a margin above model noise
    "sleeping_dog": {"max_uplift_below": -0.005},
    "vip": {"ltv_percentile": 90, "max_recency_days": 30, "min_orders": 3},
    "dormant": {"min_days_inactive": 120},
    # churn ≥ 0.6 alone catches most active buyers (the 60-day base rate is ~65%), so the churn path
    # also needs a month of silence; 60+ days of silence qualifies on its own
    "at_risk": {
        "min_churn_risk": 0.60,
        "churn_min_recency_days": 30,
        "or_min_recency_days": 60,
        "min_orders": 2,
        "min_ltv": 2500,
    },
    "cart_abandoner": {"min_cart_age_minutes": 30, "max_cart_age_hours": 72},
    "new_user": {"max_tenure_days": 30, "max_orders": 1},
    "deal_hunter": {"min_discount_usage": 0.60, "min_orders": 2},
    "window_shopper": {"min_views_90d": 8, "max_orders": 0},
}
CATEGORY_VALUES: tuple[str, ...] = get_args(Category)
OFFER_TYPE_VALUES: tuple[str, ...] = get_args(OfferType)
POPULATION_TTL_S = 3600
OFFERS_LOOKBACK_DAYS = 7
POINTS_EXPIRY_WINDOW_DAYS = 30

# Prior incremental-conversion lift per offer type, before personalisation. Replaced by the T-learner
# (scoring.uplift) in Phase 3; until then uplift = prior × price sensitivity × (1 − P(buys anyway)).
_UPLIFT_PRIOR: dict[str, float] = {
    "pct_off": 0.12,
    "flat_off": 0.10,
    "free_shipping": 0.09,
    "free_express": 0.06,
    "bonus_points": 0.04,
    "points_reminder": 0.03,
    "cart_nudge": 0.05,
    "early_access": 0.02,
    "bundle": 0.07,
    "gift_card": 0.05,
    "birthday": 0.04,
}


# ------------------------------------------------------------------ population stats (cached)
_population: dict = {}


def reset_cache() -> None:
    _population.clear()


def _population_stats(s: Session, now: datetime) -> dict:
    key = id(db.engine)
    hit = _population.get(key)
    if hit and _time.monotonic() - hit["at"] < POPULATION_TTL_S:
        return hit
    since = now - timedelta(days=365)
    rows = s.exec(
        select(OrderRow.customer_id, func.count(), func.sum(OrderRow.value), func.max(OrderRow.ts))
        .where(OrderRow.ts >= since, OrderRow.ts <= now)
        .group_by(OrderRow.customer_id)
    ).all()
    recency = [max((now - _aware(r[3])).days, 0) for r in rows]
    freq = [int(r[1]) for r in rows]
    spend = [int(r[2] or 0) for r in rows]
    cp = rfm.cutpoints(recency, freq, spend)
    spend_sorted = sorted(spend)
    pct = POLICY_THRESHOLDS["vip"]["ltv_percentile"] / 100
    vip_spend = spend_sorted[int(len(spend_sorted) * pct)] if len(spend_sorted) >= 25 else 30000
    hit = {"at": _time.monotonic(), "cutpoints": cp, "vip_spend_365d": vip_spend}
    _population[key] = hit
    return hit


# ------------------------------------------------------------------ helpers
def _aware(ts: datetime) -> datetime:
    """SQLite hands back naive IST wall time; Postgres hands back aware UTC. Normalise to aware IST."""
    return ts.replace(tzinfo=IST) if ts.tzinfo is None else ts.astimezone(IST)


def _epoch(ts: datetime) -> float:
    return _aware(ts).timestamp()


def _normalise(weights: dict[str, float]) -> dict[str, float]:
    total = sum(weights.values())
    if total <= 0:
        return {}
    return {
        c: round(w / total, 3) for c, w in sorted(weights.items(), key=lambda kv: -kv[1]) if w / total >= 0.01
    }


def _suppressed(raw: dict | list | None, now: datetime) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, list):  # tolerate a plain list of categories
        return [c for c in raw if c in CATEGORY_VALUES]
    out = []
    for cat, until in raw.items():
        try:
            active = until is None or _aware(datetime.fromisoformat(str(until))) > now
        except ValueError:
            active = True
        if active and cat in CATEGORY_VALUES:
            out.append(cat)
    return out


# ------------------------------------------------------------------ build_profile
def build_profile(customer_id: str, now: datetime) -> CustomerProfile:
    now = _aware(now)
    with Session(db.engine) as s:
        cust = s.get(CustomerRow, customer_id)
        if cust is None:
            raise KeyError(f"unknown customer {customer_id}")
        events = s.exec(
            select(EventRow.type, EventRow.ts, EventRow.category, EventRow.item, EventRow.value)
            .where(EventRow.customer_id == customer_id, EventRow.ts <= now)
            .order_by(EventRow.ts)
        ).all()
        discounts = s.exec(
            select(OrderRow.discount).where(OrderRow.customer_id == customer_id, OrderRow.ts <= now)
        ).all()
        ledger = s.exec(
            select(PointsLedgerRow.ts, PointsLedgerRow.delta, PointsLedgerRow.expires_on).where(
                PointsLedgerRow.customer_id == customer_id
            )
        ).all()
        sent = (
            s.exec(
                select(DecisionRow.ts, DecisionRow.coupon_code, DecisionRow.outcome, DecisionRow.payload)
                .where(
                    DecisionRow.customer_id == customer_id,
                    DecisionRow.status == "SENT",
                    DecisionRow.ts <= now,
                )
                .order_by(DecisionRow.ts.desc())
                .limit(5)
            ).all()
            if _has_decisions(s)
            else []
        )
        pop = _population_stats(s, now)
    return _assemble(cust, events, discounts, ledger, sent, pop, now)


_decisions_seen: dict[int, bool] = {}


def _has_decisions(s: Session) -> bool:
    # payload JSON is heavy; skip the query entirely while no decision has ever been logged
    key = id(db.engine)
    if not _decisions_seen.get(key):
        _decisions_seen[key] = s.exec(select(DecisionRow.id).limit(1)).first() is not None
    return _decisions_seen[key]


def _assemble(
    cust: CustomerRow, events, discounts, ledger, sent, pop: dict, now: datetime
) -> CustomerProfile:
    now_ts = now.timestamp()
    signup_ts = datetime.combine(cust.signup_date, datetime.min.time(), IST).timestamp()
    purchase_ts, purchase_val, session_ts = [], [], []
    returns, returned_value, views_90d = 0, 0, 0
    last_active = signup_ts
    spend_by_cat: dict[str, float] = {}
    views_by_cat: dict[str, float] = {}
    last_cart, last_purchase_ts = None, 0.0
    offer_ts: list[float] = []
    declines = sum(r[2] == "declined" for r in sent)  # "Not for me" taps on logged decisions
    for typ, ts, cat, item, value in events:
        t = _epoch(ts)
        last_active = max(last_active, t)
        if typ == "session":
            session_ts.append(t)
        elif typ == "view":
            if now_ts - t <= 90 * 86400:
                views_90d += 1
                if cat:
                    views_by_cat[cat] = views_by_cat.get(cat, 0) + 1
        elif typ == "purchase":
            purchase_ts.append(t)
            purchase_val.append(value or 0)
            last_purchase_ts = t
            if cat:
                spend_by_cat[cat] = spend_by_cat.get(cat, 0) + (value or 0)
        elif typ == "return":
            returns += 1
            returned_value += value or 0
        elif typ == "add_to_cart":
            last_cart = (t, cat, item, value)
        elif typ == "offer_received":
            offer_ts.append(t)
        elif typ == "offer_declined":
            declines += 1

    orders_total = len(purchase_ts)
    day = 86400
    recency_days = (
        int((now_ts - last_purchase_ts) // day) if orders_total else int((now_ts - signup_ts) // day)
    )
    orders_90d = sum(now_ts - t <= 90 * day for t in purchase_ts)
    orders_365 = [(t, v) for t, v in zip(purchase_ts, purchase_val, strict=True) if now_ts - t <= 365 * day]
    aov = int(sum(purchase_val) / orders_total) if orders_total else 0
    ltv = int(sum(purchase_val) - returned_value)
    return_rate = round(returns / orders_total, 3) if orders_total else 0.0
    discount_usage = round(sum(d > 0 for d in discounts) / len(discounts), 3) if discounts else 0.0
    tenure_days = max(int((now_ts - signup_ts) // day), 0)
    days_since_active = int((now_ts - last_active) // day)

    x = churn.features(purchase_ts, purchase_val, session_ts, returns, signup_ts, now_ts)
    churn_risk = (
        round(churn.predict(x), 3) if orders_total else round(min(0.9, 0.3 + days_since_active / 120), 3)
    )

    scores = rfm.score(
        recency_days if orders_total else None,
        len(orders_365),
        sum(v for _, v in orders_365),
        pop["cutpoints"],
    )
    scores["segment"] = rfm.segment(
        scores["r"],
        scores["f"],
        scores["m"],
        orders_total=orders_total,
        tenure_days=tenure_days,
        days_since_active=days_since_active,
    )
    scores.update(
        orders_total=orders_total,
        views_90d=views_90d,
        days_since_active=days_since_active,
        tenure_days=tenure_days,
        spend_365d=int(sum(v for _, v in orders_365)),
        vip_spend_365d=int(pop["vip_spend_365d"]),
        offers_received=len(offer_ts) + len(sent),
        offers_declined=declines,
    )

    affinity = _normalise(
        {
            c: 0.6 * spend_by_cat.get(c, 0) / max(sum(spend_by_cat.values()), 1)
            + 0.4 * views_by_cat.get(c, 0) / max(sum(views_by_cat.values()), 1)
            for c in CATEGORY_VALUES
        }
    )
    cheap = sum(
        v < CATEGORIES[c].aov_median
        for (typ, _, c, _, v) in events
        if typ == "purchase" and c in CATEGORIES and v
    )
    price_sensitivity = round(
        min(1.0, 0.7 * discount_usage + 0.3 * (cheap / orders_total if orders_total else 0.5)), 3
    )

    open_cart = None
    th = POLICY_THRESHOLDS["cart_abandoner"]
    if (
        last_cart
        and last_cart[0] > last_purchase_ts
        and now_ts - last_cart[0] <= th["max_cart_age_hours"] * 3600
    ):
        t, cat, item, value = last_cart
        open_cart = {
            "category": cat,
            "item": item,
            "value": int(value or 0),
            "since": datetime.fromtimestamp(t, IST).isoformat(),
            "minutes": int((now_ts - t) // 60),
        }

    points_balance, points_expiring, expiry_date = _points(ledger, now, cust.points_balance)
    last_offer_at, offers_7d, active_coupon = _offers(sent, offer_ts, now)

    p_anyway = min(0.9, orders_90d / 6)
    uplift = {
        t: round(prior * (0.4 + price_sensitivity) * (1 - p_anyway), 4) for t, prior in _UPLIFT_PRIOR.items()
    }
    assert set(uplift) == set(OFFER_TYPE_VALUES)

    profile = CustomerProfile(
        customer_id=cust.id,
        first_name=cust.first_name,
        city_tier=cust.city_tier,
        persona=cust.persona,
        policy="default",
        rfm=scores,
        recency_days=recency_days,
        orders_90d=orders_90d,
        aov=aov,
        ltv=ltv,
        churn_risk=churn_risk,
        uplift=uplift,
        price_sensitivity=price_sensitivity,
        category_affinity=affinity,
        return_rate=return_rate,
        discount_usage_rate=discount_usage,
        points_balance=points_balance,
        points_expiring=points_expiring,
        points_expiry_date=expiry_date,
        tier=cust.tier,
        open_cart=open_cart,
        last_offer_at=last_offer_at,
        offers_7d=offers_7d,
        active_coupon=active_coupon,
        suppressed_categories=_suppressed(cust.suppressed, now),
        as_of=now,
    )
    from app.scoring import uplift as uplift_model  # lazy: uplift's trainer imports this module

    if uplift_model.family_probabilities(profile):  # the trained T-learner replaces the prior
        profile = profile.model_copy(update={"uplift": uplift_model.predict_all(profile)})
    return profile.model_copy(update={"policy": assign_policy(profile)})


def _points(ledger, now: datetime, fallback_balance: int) -> tuple[int, int, date | None]:
    if not ledger:
        return fallback_balance, 0, None
    today = now.date()
    balance, expiring, first_expiry = 0, 0, None
    for ts, delta, expires_on in ledger:
        if _aware(ts) > now:
            continue
        balance += delta
        if (
            delta > 0
            and expires_on
            and today < expires_on <= today + timedelta(days=POINTS_EXPIRY_WINDOW_DAYS)
        ):
            expiring += delta
            first_expiry = min(first_expiry or expires_on, expires_on)
    return max(balance, 0), expiring, first_expiry


def _offers(sent, offer_ts: list[float], now: datetime) -> tuple[datetime | None, int, str | None]:
    week_ago = now - timedelta(days=OFFERS_LOOKBACK_DAYS)
    times = [_aware(r[0]) for r in sent] + [datetime.fromtimestamp(t, IST) for t in offer_ts]
    last = max(times, default=None)
    offers_7d = sum(t >= week_ago for t in times)
    coupon = None
    for _, code, outcome, payload in sent:  # newest first
        if not code or outcome in ("redeemed", "declined", "ignored"):
            continue
        expires = (payload or {}).get("expires_at")
        if expires and _aware(datetime.fromisoformat(expires)) > now:
            coupon = code
            break
    return last, offers_7d, coupon


# ------------------------------------------------------------------ assign_policy
def assign_policy(profile: CustomerProfile) -> PolicyName:
    """First matching policy wins; the order puts margin protection (returns, sleeping dogs, VIPs) first."""
    th, r = POLICY_THRESHOLDS, profile.rfm
    orders = r.get("orders_total", profile.orders_90d)
    inactive = r.get("days_since_active", profile.recency_days)

    t = th["high_returner"]
    if profile.return_rate > t["min_return_rate"] and orders >= t["min_orders"]:
        return "high_returner"
    if profile.uplift and max(profile.uplift.values()) < th["sleeping_dog"]["max_uplift_below"]:
        return "sleeping_dog"
    t = th["vip"]
    vip_spend = r.get("vip_spend_365d", 30000)
    if (
        r.get("spend_365d", profile.ltv) >= vip_spend
        and profile.recency_days < t["max_recency_days"]
        and orders >= t["min_orders"]
    ):
        return "vip"
    t = th["cart_abandoner"]
    if profile.open_cart and profile.open_cart.get("minutes", 0) >= t["min_cart_age_minutes"]:
        return "cart_abandoner"  # a live cart is the strongest signal; it outranks past silence
    if inactive >= th["dormant"]["min_days_inactive"]:
        return "dormant"
    t = th["at_risk"]
    if (
        orders >= t["min_orders"]
        and profile.ltv >= t["min_ltv"]
        and (
            (
                profile.churn_risk >= t["min_churn_risk"]
                and profile.recency_days >= t["churn_min_recency_days"]
            )
            or profile.recency_days >= t["or_min_recency_days"]
        )
    ):
        return "at_risk"
    t = th["new_user"]
    if r.get("tenure_days", 999) <= t["max_tenure_days"] and orders <= t["max_orders"]:
        return "new_user"
    t = th["deal_hunter"]
    if profile.discount_usage_rate > t["min_discount_usage"] and orders >= t["min_orders"]:
        return "deal_hunter"
    t = th["window_shopper"]
    if orders <= t["max_orders"] and r.get("views_90d", 0) >= t["min_views_90d"]:
        return "window_shopper"
    return "default"
