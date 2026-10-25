"""RealismStats for the dashboard's Realism page: how closely the synthetic world matches Indian e-commerce.

Reads the live DB (so it describes whatever was seeded) with a few aggregate queries plus the small orders
table, and caches the result for an hour; a reseed is picked up on the next refresh.
"""

from __future__ import annotations

import time as _time
from datetime import date

import pandas as pd
from sqlalchemy import func
from sqlmodel import Session, select

from app import db
from app.config import IST
from app.contracts import RealismStats
from app.data import stats
from app.models import EventRow, OrderRow

CACHE_TTL_S = 3600
DIWALI_2025 = date(2025, 10, 20)

SOURCES: dict[str, str] = {
    "pareto_top20_share": "Pareto 80/20 rule; repeat-buyer revenue concentration in Indian e-commerce",
    "cart_abandon_rate": "Baymard Institute, average documented cart abandonment ≈ 70%",
    "view_to_purchase": "Typical e-commerce conversion of product views to orders, 2–4%",
    "fashion_return_rate": "Indian fashion e-commerce return rates ≈ 25% (industry reports)",
    "diwali_week_ratio": "Festive-week GMV ≈ 2–3× a normal week (RedSeer festive season reports)",
    "evening_session_share": "Indian mobile shopping peaks 19:00–23:59 IST",
}
_cache: dict = {}


def _ist(ts: pd.Series) -> pd.Series:
    ts = pd.to_datetime(ts)
    return ts.dt.tz_localize(IST) if ts.dt.tz is None else ts.dt.tz_convert(IST)


def _frames(s: Session) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    orders = pd.DataFrame(
        s.exec(
            select(OrderRow.customer_id, OrderRow.ts, OrderRow.category, OrderRow.value, OrderRow.returned)
        ).all(),
        columns=["customer_id", "ts", "category", "value", "returned"],
    )
    sessions = pd.DataFrame(
        s.exec(select(EventRow.ts).where(EventRow.type == "session")).all(), columns=["ts"]
    )
    counts = dict(s.exec(select(EventRow.type, func.count()).group_by(EventRow.type)).all())
    if len(orders):
        orders["ts"] = _ist(orders["ts"])
    if len(sessions):
        sessions["ts"] = _ist(sessions["ts"])
        sessions["type"] = "session"
    return orders, sessions, counts


def _benchmark(key: str, value: float) -> dict:
    lo, hi = stats.BENCHMARKS[key]
    return {"min": lo, "max": hi, "value": round(value, 4), "ok": lo <= value <= hi, "source": SOURCES[key]}


def compute() -> RealismStats:
    key = id(db.engine)
    hit = _cache.get(key)
    if hit and _time.monotonic() - hit[0] < CACHE_TTL_S:
        return hit[1]
    with Session(db.engine) as s:
        orders, sessions, counts = _frames(s)
    result = _compute(orders, sessions, counts)
    _cache[key] = (_time.monotonic(), result)
    return result


def reset_cache() -> None:
    _cache.clear()


def _compute(orders: pd.DataFrame, sessions: pd.DataFrame, counts: dict[str, int]) -> RealismStats:
    funnel = {
        t: int(counts.get(t, 0)) for t in ("session", "view", "add_to_cart", "checkout_started", "purchase")
    }
    carts = funnel["add_to_cart"]
    # every simulated purchase follows a cart in the same session, so counts give the abandonment rate
    abandon = 1 - funnel["purchase"] / carts if carts else 0.0
    v2p = funnel["purchase"] / funnel["view"] if funnel["view"] else 0.0
    if orders.empty:
        return RealismStats(
            pareto_top20_share=0.0,
            cart_abandon_rate=round(abandon, 4),
            funnel=funnel,
            retention_cohorts=[],
            aov_by_category={},
            return_rate_by_category={},
            seasonality_daily=[],
            benchmarks={},
        )
    pareto = stats.pareto_top20_share(orders)
    returns = stats.return_rate_by_category(orders)
    benchmarks = {
        "pareto_top20_share": _benchmark("pareto_top20_share", pareto),
        "cart_abandon_rate": _benchmark("cart_abandon_rate", abandon),
        "view_to_purchase": _benchmark("view_to_purchase", v2p),
        "fashion_return_rate": _benchmark("fashion_return_rate", returns.get("fashion", 0.0)),
        "evening_session_share": _benchmark(
            "evening_session_share", stats.evening_session_share(sessions) if len(sessions) else 0.0
        ),
    }
    if orders["ts"].dt.date.min() <= DIWALI_2025:
        benchmarks["diwali_week_ratio"] = _benchmark(
            "diwali_week_ratio", stats.festival_week_ratio(orders, DIWALI_2025)
        )
    return RealismStats(
        pareto_top20_share=round(pareto, 4),
        cart_abandon_rate=round(abandon, 4),
        funnel=funnel,
        retention_cohorts=stats.retention_cohorts(orders),
        aov_by_category=stats.aov_by_category(orders),
        return_rate_by_category=returns,
        seasonality_daily=stats.daily_revenue(orders),
        benchmarks=benchmarks,
    )
