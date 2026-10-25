"""ExperimentStats for the Experiments page: does the engine create value we wouldn't get anyway?

Two randomised sources per date range, each its own *stratum*:
  - every past campaign (campaign_history): its treated customers vs its own random 10% control, revenue in
    the campaign's own response window;
  - live decisions: SENT vs HELD_OUT (the 10% holdout), revenue = purchases within 7 days.
Treated and control are only ever compared inside a stratum (pooling strata with different seasons, offers and
control shares invites Simpson's paradox). Incremental revenue of a cell = (treated − control conversion) ×
treated customers × the stratum's average basket per buyer. The headline, the ROI table and uplift by policy
are all sums of the same (stratum × offer type) cells, so they always agree. A stratum with fewer than
MIN_CONTROL control customers isn't measured; its treated customers are reported as `unmeasured_n`.
"Margin saved on sure-things" is what a blanket offer pays people who'd have bought anyway: per stratum,
coupon cost × (control conversion ÷ treated conversion), the non-incremental share of redemptions.
Cached for 10 minutes per date range.
"""

from __future__ import annotations

import time as _time
from collections import defaultdict
from datetime import date, datetime, time, timedelta

import pandas as pd
from sqlmodel import Session, select

from app import db
from app.config import IST
from app.contracts import ExperimentStats
from app.data.catalog import CATEGORIES
from app.data.festivals import FESTIVALS, festival_key
from app.data.generator import CAMPAIGNS
from app.models import CampaignHistoryRow, CustomerRow, DecisionRow, EventRow, OfferRow, OrderRow
from app.scoring import uplift

CACHE_TTL_S = 600
CONVERSION_WINDOW_DAYS = 7
MIN_CONTROL = 20  # control customers a stratum needs before its treated customers count as measured
# hidden personas are reported under the policy they usually land in
PERSONA_POLICY = {
    "loyal_vip": "vip",
    "deal_hunter": "deal_hunter",
    "at_risk_regular": "at_risk",
    "new_user": "new_user",
    "dormant": "dormant",
    "window_shopper": "window_shopper",
    "cart_abandoner": "cart_abandoner",
    "festive_gifter": "default",
    "high_returner": "high_returner",
}
SHOWN_FESTIVALS = {
    "navratri",
    "karwa_chauth",
    "dhanteras",
    "diwali",
    "black_friday",
    "gurpurab",
    "lohri",
    "christmas",
}
_cache: dict = {}


def reset_cache() -> None:
    _cache.clear()


def compute(start: date, end: date) -> ExperimentStats:
    key = (id(db.engine), start, end)
    hit = _cache.get(key)
    if hit and _time.monotonic() - hit[0] < CACHE_TTL_S:
        return hit[1]
    lo = datetime.combine(start, time(0), IST)
    hi = datetime.combine(end + timedelta(days=1), time(0), IST)
    with Session(db.engine) as s:
        rows = _campaign_rows(s, lo, hi) + _decision_rows(s, lo, hi)
        orders = pd.DataFrame(
            s.exec(
                select(OrderRow.ts, OrderRow.category, OrderRow.value).where(
                    OrderRow.ts >= lo, OrderRow.ts < hi
                )
            ).all(),
            columns=["ts", "category", "value"],
        )
    result = _stats(pd.DataFrame(rows, columns=_COLUMNS), orders, start, end)
    _cache[key] = (_time.monotonic(), result)
    return result


_COLUMNS = [
    "stratum",
    "customer_id",
    "treated",
    "converted",
    "revenue",
    "cost",
    "offer_type",
    "policy",
]


def _campaign_rows(s: Session, lo: datetime, hi: datetime) -> list[tuple]:
    hist = s.exec(
        select(CampaignHistoryRow, CustomerRow.persona)
        .join(CustomerRow, CustomerRow.id == CampaignHistoryRow.customer_id)
        .where(CampaignHistoryRow.sent_at >= lo, CampaignHistoryRow.sent_at < hi)
    ).all()
    if not hist:
        return []
    coupons = {c.coupon: c.id for c in CAMPAIGNS}
    spent: dict[tuple[str, str], int] = defaultdict(int)
    for cid, code, discount in s.exec(
        select(OrderRow.customer_id, OrderRow.coupon_code, OrderRow.discount).where(
            OrderRow.coupon_code.in_(list(coupons))
        )
    ).all():
        spent[(coupons[code], cid)] += discount
    out = []
    for r, persona in hist:
        cost = 0 if r.is_control else spent.get((r.campaign_id, r.customer_id), 0)
        out.append(
            (
                r.campaign_id,
                r.customer_id,
                not r.is_control,
                r.converted,
                r.revenue,
                cost,
                r.offer_type,
                PERSONA_POLICY.get(persona, "default"),
            )
        )
    return out


def _decision_rows(s: Session, lo: datetime, hi: datetime) -> list[tuple]:
    decisions = s.exec(
        select(
            DecisionRow.customer_id,
            DecisionRow.ts,
            DecisionRow.status,
            DecisionRow.final_offer_id,
            DecisionRow.cost,
            DecisionRow.outcome,
            DecisionRow.policy,
        ).where(DecisionRow.ts >= lo, DecisionRow.ts < hi, DecisionRow.status.in_(["SENT", "HELD_OUT"]))
    ).all()
    if not decisions:
        return []
    offer_type = dict(s.exec(select(OfferRow.id, OfferRow.type)).all())
    ids = list({d[0] for d in decisions})
    buys: dict[str, list[tuple[datetime, int]]] = defaultdict(list)
    for cid, ts, value in s.exec(
        select(EventRow.customer_id, EventRow.ts, EventRow.value).where(
            EventRow.type == "purchase", EventRow.customer_id.in_(ids), EventRow.ts >= lo
        )
    ).all():
        buys[cid].append((_aware(ts), value or 0))
    out = []
    for cid, ts, status, offer_id, cost, outcome, policy in decisions:
        t0 = _aware(ts)
        window = [v for t, v in buys.get(cid, ()) if t0 <= t < t0 + timedelta(days=CONVERSION_WINDOW_DAYS)]
        treated = status == "SENT"
        paid = cost if treated and outcome in ("claimed", "redeemed") else 0
        out.append(
            ("live", cid, treated, bool(window), sum(window), paid, offer_type.get(offer_id, "none"), policy)
        )
    return out


def _aware(ts: datetime) -> datetime:
    return ts.replace(tzinfo=IST) if ts.tzinfo is None else ts.astimezone(IST)


# ------------------------------------------------------------------ aggregation
def _arm(df: pd.DataFrame) -> dict:
    n = int(len(df))
    return {
        "n": n,
        "conv_rate": round(float(df["converted"].mean()), 4) if n else 0.0,
        "revenue": int(df["revenue"].sum()),
        "cost": int(df["cost"].sum()),
        "revenue_per_customer": round(float(df["revenue"].mean()), 1) if n else 0.0,
    }


def _margin(orders: pd.DataFrame) -> float:
    if orders.empty:
        return 0.35
    m = orders["category"].map(lambda c: CATEGORIES[c].margin if c in CATEGORIES else 0.35)
    return float((orders["value"] * m).sum() / max(orders["value"].sum(), 1))


def _cells(df: pd.DataFrame, margin: float) -> pd.DataFrame:
    """One row per (stratum, offer type): its treated customers measured against the stratum's own control.
    Every cost is a treated customer's own coupon spend, so it is subtracted exactly once."""
    rows = []
    for stratum, g in df.groupby("stratum"):
        control = g[~g["treated"]]
        measured = len(control) >= MIN_CONTROL
        c_conv = float(control["converted"].mean()) if len(control) else 0.0
        # extra buyers × the stratum's typical basket: per-customer revenue is heavy-tailed (one ₹19k gold
        # coin in a 26-person control swings a raw revenue comparison by lakhs), conversion isn't
        buyers = g[g["converted"]]
        basket = float(buyers["revenue"].sum() / len(buyers)) if len(buyers) else 0.0
        for offer_type, t in g[g["treated"]].groupby("offer_type"):
            t_conv = float(t["converted"].mean())
            inc = (t_conv - c_conv) * len(t) * basket if measured else 0.0
            cost = float(t["cost"].sum())
            rows.append(
                {
                    "stratum": stratum,
                    "offer_type": offer_type,
                    "n": len(t),
                    "measured": measured,
                    "incremental_revenue": inc,
                    "cost": cost,
                    "incremental_profit": inc * margin - cost if measured else 0.0,
                    "saved": cost * min(c_conv / t_conv, 1.0) if measured and t_conv else 0.0,
                }
            )
    cols = [
        "stratum",
        "offer_type",
        "n",
        "measured",
        "incremental_revenue",
        "cost",
        "incremental_profit",
        "saved",
    ]
    return pd.DataFrame(rows, columns=cols)


def _stats(df: pd.DataFrame, orders: pd.DataFrame, start: date, end: date) -> ExperimentStats:
    margin = _margin(orders)
    if df.empty:
        return ExperimentStats(
            treatment=_arm(df),
            control=_arm(df),
            incremental_revenue=0,
            incremental_profit=0,
            margin_saved_sure_things=0,
            uplift_by_policy=[],
            roi_by_offer_type=[],
            qini=uplift.qini(),
            festival_vs_baseline=_festivals(orders, start, end),
        )
    cells = _cells(df, margin)
    measured = cells[cells["measured"]]
    t = _arm(df[df["treated"]])
    t.update(
        measured_n=int(measured["n"].sum()),
        unmeasured_n=int(cells.loc[~cells["measured"], "n"].sum()),
        method="extra buyers × typical basket; each campaign vs its own control, live vs the holdout; summed",
    )
    return ExperimentStats(
        treatment=t,
        control=_arm(df[~df["treated"]]),
        incremental_revenue=int(round(measured["incremental_revenue"].sum())),
        incremental_profit=int(round(measured["incremental_profit"].sum())),
        margin_saved_sure_things=int(round(measured["saved"].sum())),
        uplift_by_policy=_by_policy(df),
        roi_by_offer_type=_roi(measured),
        qini=uplift.qini(),
        festival_vs_baseline=_festivals(orders, start, end),
    )


def _by_policy(df: pd.DataFrame) -> list[dict]:
    """Conversion uplift per policy, measured inside each stratum and weighted by treated customers."""
    acc: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for _, g in df.groupby("stratum"):
        for policy, p in g.groupby("policy"):
            t, c = p[p["treated"]], p[~p["treated"]]
            if not len(t) or len(c) < 3:
                continue
            a = acc[policy]
            a["n_t"] += len(t)
            a["n_c"] += len(c)
            a["t_conv"] += float(t["converted"].mean()) * len(t)
            a["c_conv"] += float(c["converted"].mean()) * len(t)
    out = []
    for policy, a in acc.items():
        if a["n_t"] < 20:
            continue
        t_conv, c_conv = a["t_conv"] / a["n_t"], a["c_conv"] / a["n_t"]
        out.append(
            {
                "policy": policy,
                "n_treated": int(a["n_t"]),
                "n_control": int(a["n_c"]),
                "treated_conv": round(t_conv, 4),
                "control_conv": round(c_conv, 4),
                "uplift": round(t_conv - c_conv, 4),
            }
        )
    return sorted(out, key=lambda r: -r["uplift"])


def _roi(measured: pd.DataFrame) -> list[dict]:
    """Sums of the same cells as the headline, so the rows always add up to it."""
    out = []
    for offer_type, g in measured.groupby("offer_type"):
        profit, cost = float(g["incremental_profit"].sum()), float(g["cost"].sum())
        out.append(
            {
                "type": offer_type,
                "n": int(g["n"].sum()),
                "incremental_revenue": int(round(g["incremental_revenue"].sum())),
                "cost": int(round(cost)),
                "incremental_profit": int(round(profit)),
                "roi": round(profit / cost, 2) if cost else None,
            }
        )
    return sorted(out, key=lambda r: -r["incremental_profit"])


def _festivals(orders: pd.DataFrame, start: date, end: date) -> list[dict]:
    if orders.empty:
        return []
    ts = pd.to_datetime(orders["ts"])
    ts = ts.dt.tz_localize(IST) if ts.dt.tz is None else ts.dt.tz_convert(IST)
    daily = orders.groupby(ts.dt.date)["value"].sum()
    baseline = float(daily.median()) if len(daily) else 0.0
    out = []
    for f in FESTIVALS:
        if festival_key(f.id) not in SHOWN_FESTIVALS or not start <= f.date <= end:
            continue
        lo, _ = f.phases["build_up"]
        days = [f.date + timedelta(days=d) for d in range(lo, f.phases["last_minute"][1] + 1)]
        per_day = float(daily.reindex(days).fillna(0).mean())
        out.append(
            {
                "festival": f.name,
                "id": f.id,
                "date": f.date.isoformat(),
                "revenue_per_day": int(per_day),
                "baseline_per_day": int(baseline),
                "lift": round(per_day / baseline, 2) if baseline else None,
            }
        )
    return out
