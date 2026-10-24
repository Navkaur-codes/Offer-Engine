"""Realism statistics over event/order frames shaped like the DB tables (also reused by scoring.realism).

`events` needs customer_id, type, ts, sid; `orders` needs customer_id, ts, category, value, returned.
Duplicate session beacons are deduped on (customer, session, type) before counting a funnel.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

# target ranges the generator is tuned to; each with the public benchmark it imitates
BENCHMARKS: dict[str, tuple[float, float]] = {
    "pareto_top20_share": (0.65, 0.80),  # Pareto 80/20 rule; repeat-buyer concentration in Indian e-com
    "cart_abandon_rate": (0.65, 0.75),  # Baymard Institute average ≈ 70%
    "view_to_purchase": (0.02, 0.04),  # typical e-commerce conversion 2–4%
    "fashion_return_rate": (0.20, 0.30),  # Indian fashion e-commerce returns ≈ 25%
    "diwali_week_ratio": (1.8, 4.0),  # festive week GMV ≈ 2–3× a normal week (RedSeer festive reports)
    "evening_session_share": (0.35, 0.55),  # evening peak 19:00–23:59 IST
}


def _funnel_events(events: pd.DataFrame) -> pd.DataFrame:
    linked = events[events["sid"].notna()]
    return linked.drop_duplicates(["customer_id", "sid", "type"])


def funnel(events: pd.DataFrame) -> dict[str, int]:
    """Distinct sessions reaching each step, plus raw product views."""
    ev = _funnel_events(events)
    steps = {
        t: int((ev["type"] == t).sum()) for t in ("session", "add_to_cart", "checkout_started", "purchase")
    }
    steps["view"] = int((events["type"] == "view").sum())
    return steps


def cart_abandon_rate(events: pd.DataFrame) -> float:
    ev = _funnel_events(events)
    carted = set(ev.loc[ev["type"] == "add_to_cart", "sid"])
    bought = set(ev.loc[ev["type"] == "purchase", "sid"])
    return 1 - len(carted & bought) / max(len(carted), 1)


def view_to_purchase(events: pd.DataFrame) -> float:
    f = funnel(events)
    return f["purchase"] / max(f["view"], 1)


def pareto_top20_share(orders: pd.DataFrame) -> float:
    """Share of revenue from the top 20% of buyers (customers with at least one order)."""
    spend = orders.groupby("customer_id")["value"].sum().sort_values(ascending=False)
    top = max(1, int(round(len(spend) * 0.2)))
    return float(spend.iloc[:top].sum() / spend.sum())


def return_rate_by_category(orders: pd.DataFrame) -> dict[str, float]:
    return {k: round(float(v), 4) for k, v in orders.groupby("category")["returned"].mean().items()}


def aov_by_category(orders: pd.DataFrame) -> dict[str, int]:
    return {k: int(v) for k, v in orders.groupby("category")["value"].mean().items()}


def evening_session_share(events: pd.DataFrame, start_hour: int = 19) -> float:
    s = events[events["type"] == "session"]
    return float((s["ts"].dt.hour >= start_hour).mean())


def weekly_revenue(orders: pd.DataFrame) -> pd.Series:
    day = orders["ts"].dt.tz_localize(None).dt.normalize()
    return orders.groupby(day)["value"].sum().resample("7D").sum()


def festival_week_ratio(orders: pd.DataFrame, festival_day: date) -> float:
    """Revenue in the 7 days ending on the festival, divided by the median 7-day revenue."""
    day = orders["ts"].dt.date
    week = orders[(day > festival_day - timedelta(days=7)) & (day <= festival_day)]["value"].sum()
    daily = orders.groupby(day)["value"].sum()
    rolling = daily.rolling(7).sum().dropna()
    return float(week / rolling.median())


def daily_revenue(orders: pd.DataFrame) -> list[dict]:
    daily = orders.groupby(orders["ts"].dt.date)["value"].sum()
    return [{"date": d.isoformat(), "revenue": int(v)} for d, v in daily.items()]


def retention_cohorts(orders: pd.DataFrame, months: int = 6) -> list[dict]:
    """Share of each first-purchase-month cohort that buys again in month k after."""
    o = orders.assign(month=orders["ts"].dt.tz_localize(None).dt.to_period("M"))
    first = o.groupby("customer_id")["month"].min().rename("cohort")
    o = o.join(first, on="customer_id")
    o["k"] = (o["month"] - o["cohort"]).apply(lambda x: x.n)
    out = []
    for cohort, grp in o.groupby("cohort"):
        size = grp["customer_id"].nunique()
        row = {"cohort": str(cohort), "size": int(size)}
        for k in range(1, months + 1):
            row[f"m{k}"] = round(grp.loc[grp["k"] == k, "customer_id"].nunique() / size, 3)
        out.append(row)
    return out
