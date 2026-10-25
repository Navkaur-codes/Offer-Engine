"""ExperimentStats for the Experiments page: does the engine create value we wouldn't get anyway?

Two randomised sources, pooled per date range:
  - past campaigns (campaign_history): treated vs the random 10% control;
  - live decisions: SENT vs HELD_OUT (the 10% holdout), converted = a purchase within 7 days.
"Margin saved on sure-things" is what a blanket campaign pays people who'd have bought anyway: coupon cost ×
(control conversion ÷ treated conversion), i.e. the non-incremental share of redemptions that targeting skips.
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


_COLUMNS = ["source", "customer_id", "treated", "converted", "revenue", "cost", "offer_type", "policy"]


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
                "campaign",
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


def _incremental(t: dict, c: dict) -> int:
    if not t["n"] or not c["n"]:
        return 0
    return int((t["revenue_per_customer"] - c["revenue_per_customer"]) * t["n"])


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
    t, c = _arm(df[df["treated"]]), _arm(df[~df["treated"]])
    inc_rev = _incremental(t, c)
    non_incremental = min(c["conv_rate"] / t["conv_rate"], 1.0) if t["conv_rate"] else 0.0
    return ExperimentStats(
        treatment=t,
        control=c,
        incremental_revenue=inc_rev,
        incremental_profit=int(inc_rev * margin - t["cost"]),
        margin_saved_sure_things=int(t["cost"] * non_incremental),
        uplift_by_policy=_by(df, "policy", margin),
        roi_by_offer_type=_roi(df, margin),
        qini=uplift.qini(),
        festival_vs_baseline=_festivals(orders, start, end),
    )


def _by(df: pd.DataFrame, col: str, margin: float) -> list[dict]:
    out = []
    for value, g in df.groupby(col):
        t, c = g[g["treated"]], g[~g["treated"]]
        if len(t) < 20 or len(c) < 5:
            continue
        out.append(
            {
                "policy": value,
                "n_treated": int(len(t)),
                "n_control": int(len(c)),
                "treated_conv": round(float(t["converted"].mean()), 4),
                "control_conv": round(float(c["converted"].mean()), 4),
                "uplift": round(float(t["converted"].mean() - c["converted"].mean()), 4),
            }
        )
    return sorted(out, key=lambda r: -r["uplift"])


def _roi(df: pd.DataFrame, margin: float) -> list[dict]:
    """Each offer type is compared with the control customers of the same campaigns / the live holdout."""
    out = []
    control = df[~df["treated"]]
    for offer_type, t in df[df["treated"]].groupby("offer_type"):
        if offer_type == "none" or len(t) < 20:
            continue
        same = control[control["offer_type"] == offer_type]
        c = same if len(same) >= 20 else control
        tt, cc = _arm(t), _arm(c)
        inc = _incremental(tt, cc)
        profit = inc * margin - tt["cost"]
        out.append(
            {
                "type": offer_type,
                "n": tt["n"],
                "incremental_revenue": inc,
                "cost": tt["cost"],
                "incremental_profit": int(profit),
                "roi": round(profit / tt["cost"], 2) if tt["cost"] else None,
            }
        )
    return sorted(out, key=lambda r: -(r["incremental_profit"]))


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
