"""Proactive triggers (owned by Main). Each job is a plain sync function so it can be tested and run by hand.

The harness decides and stores; jobs only find who is due, call `ports.decide`, and hand SENT decisions to the
bot through `ports.deliver`. Jobs never DM synthetic customers (they have no Telegram chat); personal
picks for the 10 Lab customers are posted in the Lab group, the bots' own stage.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from sqlmodel import Session, select

from app import db, decision_store, ports, runtime
from app.config import now
from app.contracts import Decision, TriggerType
from app.models import CustomerRow, DecisionRow, EventRow

log = logging.getLogger(__name__)

CART_IDLE = timedelta(minutes=30)  # a cart counts as abandoned after this long
CART_LOOKBACK = timedelta(hours=6)  # older carts are left alone
POINTS_REPEAT = timedelta(days=3)  # one points-expiry reminder per 3 days
FLUSHED = "queue_flushed"  # settings key: ids of QUEUED decisions already re-run
PICKS = "personal_picks"
PICKS_AGENT_TOP_N = 5


def _telegram_customers(s: Session) -> list[CustomerRow]:
    return list(s.exec(select(CustomerRow).where(CustomerRow.telegram_chat_id.is_not(None))).all())


def _last_decision_at(s: Session, customer_id: str, trigger: str):
    row = s.exec(
        select(DecisionRow.ts)
        .where(DecisionRow.customer_id == customer_id, DecisionRow.trigger == trigger)
        .order_by(DecisionRow.ts.desc())
    ).first()
    return decision_store.aware(row) if row else None


def _decide_and_deliver(customer_id: str, trigger: TriggerType, meta: dict) -> Decision:
    decision = ports.decide(customer_id, trigger, {**meta, "source": "scheduler"})
    if decision.status == "SENT" and decision.channel == "dm":
        ports.deliver(decision, "dm")
    return decision


def cart_abandonment() -> list[Decision]:
    """Every 5 min: a Telegram customer's newest cart is 30 min – 6 h old, unbought and not yet nudged."""
    at = now()
    out: list[Decision] = []
    with Session(db.engine) as s:
        for cust in _telegram_customers(s):
            cart = s.exec(
                select(EventRow)
                .where(
                    EventRow.customer_id == cust.id,
                    EventRow.type == "add_to_cart",
                    EventRow.ts >= at - CART_LOOKBACK,
                )
                .order_by(EventRow.ts.desc())
            ).first()
            if cart is None:
                continue
            cart_ts = decision_store.aware(cart.ts)
            if at - cart_ts < CART_IDLE:
                continue
            closed = s.exec(
                select(EventRow.id).where(
                    EventRow.customer_id == cust.id,
                    EventRow.ts > cart.ts,
                    EventRow.type.in_(["purchase", "checkout_started"]),
                )
            ).first()
            nudged = _last_decision_at(s, cust.id, "cart_abandoned")
            if closed or (nudged and nudged > cart_ts):
                continue
            meta = {
                "category": cart.category,
                "item": cart.item,
                "value": cart.value,
                "minutes": int((at - cart_ts).total_seconds() // 60),
                "cart_event_id": cart.id,
            }
            out.append((cust.id, meta))
    return [_decide_and_deliver(cid, "cart_abandoned", meta) for cid, meta in out]


def flush_quiet_queue() -> list[Decision]:
    """09:05 IST: re-run every offer that quiet hours held overnight, so today's rules and consent decide."""
    at = now()
    done = set(runtime.get_setting(FLUSHED).get("ids", []))
    queued = [
        d
        for d in decision_store.query(status="QUEUED", after=at - timedelta(hours=24), limit=500)
        if d.id not in done
    ]
    out = []
    for d in reversed(queued):  # oldest first
        meta = {k: v for k, v in d.trigger_meta.items() if k != "source"}
        out.append(_decide_and_deliver(d.customer_id, d.trigger, {**meta, "requeued_from": d.id}))
        done.add(d.id)
    if queued:
        runtime.set_setting(FLUSHED, {"ids": sorted(done)[-1000:], "last_run": at.isoformat()})
    return out


def points_expiry() -> list[Decision]:
    """10:00 IST: remind Telegram customers whose points expire within 3 days (at most once per 3 days)."""
    at = now()
    due = []
    with Session(db.engine) as s:
        for cust in _telegram_customers(s):
            last = _last_decision_at(s, cust.id, "points_expiry")
            if last and at - last < POINTS_REPEAT:
                continue
            due.append(cust.id)
    out = []
    for cid in due:
        profile = ports.build_profile(cid, at)
        if (
            profile.points_expiring > 0
            and profile.points_expiry_date
            and (profile.points_expiry_date - at.date()).days <= 3
        ):
            out.append(_decide_and_deliver(cid, "points_expiry", {"points": profile.points_expiring}))
    return out


def _pick_meta(customer_id: str, at) -> dict:
    """What the pick is built on: the customer's strongest category (60% spend share + 40% browsing share)."""
    affinity = ports.build_profile(customer_id, at).category_affinity
    meta: dict = {"campaign": PICKS, "source": "scheduler"}
    if affinity:
        top = max(affinity, key=affinity.get)
        meta.update(category=top, category_share=round(affinity[top], 2))
    return meta


def personal_picks() -> list[Decision]:
    """11:00 and 18:00 IST: one profile-based pick for every Telegram customer (DM, quiet hours apply) and
    every Lab customer (posted in the Lab group). One batch, so only the top 5 by expected profit use the
    agent (T26); every pick still goes through the full pipeline and every limit, and every outcome is
    logged."""
    at = now()
    with Session(db.engine) as s:
        telegram = [c.id for c in _telegram_customers(s) if not c.is_lab_bot]
        lab = list(s.exec(select(CustomerRow.id).where(CustomerRow.is_lab_bot)).all())
    items: list[tuple[str, TriggerType, dict]] = [(cid, "campaign", _pick_meta(cid, at)) for cid in telegram]
    items += [(cid, "lab", _pick_meta(cid, at)) for cid in sorted(lab)]
    if not items:
        return []
    decisions = ports.decide_batch(items, dry_run=False, agent_top_n=PICKS_AGENT_TOP_N)
    for d in decisions:
        if d.status == "SENT" and d.channel == "dm":
            ports.deliver(d, "dm")
    return decisions


def daily_digest_text() -> str:
    """21:00 IST: the day's digest (sent to admins by the runner)."""
    return ports.daily_digest(now().date())


JOBS = {
    "cart_abandonment": cart_abandonment,
    "flush_quiet_queue": flush_quiet_queue,
    "points_expiry": points_expiry,
    PICKS: personal_picks,
}
