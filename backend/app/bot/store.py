"""The bot's DB reads/writes (customers' consent + preferences, decision lookups).

Sync functions: handlers call them via `asyncio.to_thread` so a slow Neon round-trip never blocks the loop.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from uuid import uuid4

from sqlmodel import Session, select

from app import config, db, decision_store
from app.contracts import Customer, Decision
from app.models import CustomerRow, DecisionRow, EventRow, OrderRow, PointsLedgerRow, ProductRow

log = logging.getLogger(__name__)


def customer_id_for(telegram_id: int) -> str:
    return f"TG{telegram_id}"


def _session() -> Session:
    # expire_on_commit=False: rows stay readable after the session closes
    return Session(db.engine, expire_on_commit=False)


def get_customer(customer_id: str) -> CustomerRow | None:
    with _session() as s:
        return s.get(CustomerRow, customer_id)


def save_customer(customer: Customer, answers: dict) -> CustomerRow:
    """Upsert after onboarding. Re-running /start is fresh consent, so it clears opt-out and pause."""
    with _session() as s:
        row = s.get(CustomerRow, customer.id)
        if row is None:
            row = CustomerRow(**customer.model_dump())
        row.first_name = customer.first_name
        row.telegram_chat_id = customer.telegram_chat_id
        row.opt_in_festivals = list(customer.opt_in_festivals)
        row.opted_out = False
        row.paused_until = None
        row.attrs = {**(row.attrs or {}), "onboarding": answers}
        s.add(row)
        s.commit()
        return row


def set_opted_out(customer_id: str, opted_out: bool) -> bool:
    with _session() as s:
        row = s.get(CustomerRow, customer_id)
        if row is None:
            return False
        row.opted_out = opted_out
        s.add(row)
        s.commit()
        return True


def set_paused_until(customer_id: str, until: datetime | None) -> bool:
    with _session() as s:
        row = s.get(CustomerRow, customer_id)
        if row is None:
            return False
        row.paused_until = until
        s.add(row)
        s.commit()
        return True


def _parse(row: DecisionRow) -> Decision | None:
    try:
        return Decision.model_validate(row.payload)
    except ValueError:
        log.warning("decision %s has an unreadable payload", row.id)
        return None


def find_decision(decision_id: str) -> Decision | None:
    with _session() as s:
        row = s.get(DecisionRow, decision_id)
        return _parse(row) if row else None


def recent_decisions(customer_id: str, limit: int = 10) -> list[Decision]:
    with _session() as s:
        rows = s.exec(
            select(DecisionRow)
            .where(DecisionRow.customer_id == customer_id)
            .order_by(DecisionRow.ts.desc())
            .limit(limit)
        ).all()
    return [d for d in map(_parse, rows) if d]


def set_message_id(decision_id: str, message_id: int) -> None:
    with _session() as s:
        row = s.get(DecisionRow, decision_id)
        if row is not None:  # the harness writes the row; the stub doesn't
            row.telegram_message_id = message_id
            s.add(row)
            s.commit()


# ---------------------------------------------------------------- simulation + outcomes (Phase 2)
FALLBACK_PRODUCTS: dict[str, list[tuple[str, int]]] = {  # only used when the products table is empty
    "fashion": [("Cotton Kurta", 1450), ("Slim Fit Denim Jeans", 1699)],
    "ethnic_wear": [("Silk Saree", 3499), ("Embroidered Lehenga", 6999)],
    "electronics": [("Wireless Earbuds", 2499), ("Smart Watch", 4999)],
    "beauty": [("Vitamin C Serum", 599), ("Matte Lipstick Set", 899)],
    "home_decor": [("Brass Diya Set", 799), ("Cotton Cushion Covers", 649)],
    "kitchen": [("Non-stick Kadai", 1299), ("Steel Tiffin Box", 549)],
    "grocery": [("Dry Fruits Gift Box", 999), ("Basmati Rice 5 kg", 749)],
    "jewellery": [("Silver Jhumkas", 1899), ("Gold-plated Bangles", 2499)],
    "gifting": [("Festive Hamper", 1499), ("Scented Candle Set", 699)],
    "winter_wear": [("Wool Shawl", 1999), ("Puffer Jacket", 3499)],
}


def new_id(prefix: str) -> str:
    return f"{prefix}{uuid4().hex[:12].upper()}"


def pick_product(category: str, seed: str) -> tuple[str, int]:
    """A real catalogue product in that category; stable per seed so repeated demos look consistent."""
    with _session() as s:
        rows = s.exec(select(ProductRow).where(ProductRow.category == category).order_by(ProductRow.id)).all()
    items = [(r.name, r.price) for r in rows] or FALLBACK_PRODUCTS[category]
    return items[sum(map(ord, seed)) % len(items)]


def add_events(customer_id: str, events: list[dict]) -> None:
    with _session() as s:
        for e in events:
            s.add(EventRow(id=new_id("E"), customer_id=customer_id, **e))
        s.commit()


def add_order(customer_id: str, category: str, item: str, value: int, ts: datetime) -> None:
    with _session() as s:
        s.add(OrderRow(id=new_id("O"), customer_id=customer_id, ts=ts, category=category, value=value))
        s.add(
            EventRow(
                id=new_id("E"), customer_id=customer_id, type="purchase", ts=ts,
                category=category, item=item, value=value,
            )
        )
        s.commit()


def open_cart(customer_id: str) -> EventRow | None:
    """The latest add_to_cart with no purchase after it."""
    with _session() as s:
        cart = s.exec(
            select(EventRow)
            .where(EventRow.customer_id == customer_id, EventRow.type == "add_to_cart")
            .order_by(EventRow.ts.desc())
        ).first()
        if cart is None:
            return None
        bought = s.exec(
            select(EventRow).where(
                EventRow.customer_id == customer_id, EventRow.type == "purchase", EventRow.ts >= cart.ts
            )
        ).first()
        return None if bought else cart


def shift_activity(customer_id: str, days: int) -> int:
    """Move the customer's whole history `days` into the past, so the newest activity is `days` old."""
    delta = timedelta(days=days)
    with _session() as s:
        rows = [
            *s.exec(select(EventRow).where(EventRow.customer_id == customer_id)).all(),
            *s.exec(select(OrderRow).where(OrderRow.customer_id == customer_id)).all(),
        ]
        newest = max((r.ts for r in rows), default=None)
        if newest is not None:
            back = delta - (_aware(config.now()) - _aware(newest))
            for r in rows:
                r.ts = _aware(r.ts) - back
                s.add(r)
        customer = s.get(CustomerRow, customer_id)
        if customer is not None:
            customer.signup_date = min(customer.signup_date, (config.now() - delta).date())
            s.add(customer)
        s.commit()
        return len(rows)


def add_points(customer_id: str, points: int, expires_on: date, ts: datetime) -> None:
    with _session() as s:
        s.add(
            PointsLedgerRow(
                customer_id=customer_id, ts=ts, delta=points, reason="demo bonus", expires_on=expires_on
            )
        )
        customer = s.get(CustomerRow, customer_id)
        if customer is not None:
            customer.points_balance += points
            s.add(customer)
        s.commit()


def set_persona(customer_id: str, persona: str) -> bool:
    with _session() as s:
        row = s.get(CustomerRow, customer_id)
        if row is None:
            return False
        row.persona = persona
        s.add(row)
        s.commit()
        return True


def record_outcome(decision: Decision, outcome: str, at: datetime) -> bool:
    """Writes the outcome on the logged decision. False if it was already final (claimed/declined)."""
    logged = decision_store.get(decision.id)
    if logged is None:  # stub phase: the harness hasn't logged it, events still record the action
        return True
    if logged.outcome in ("claimed", "declined", "redeemed"):
        return False
    decision_store.set_outcome(decision.id, outcome, at)
    return True


def suppress_category(customer_id: str, category: str, until: datetime) -> None:
    with _session() as s:
        row = s.get(CustomerRow, customer_id)
        if row is not None:
            row.suppressed = {**(row.suppressed or {}), category: until.isoformat()}
            s.add(row)
            s.commit()


def _aware(ts: datetime) -> datetime:
    return ts if ts.tzinfo else ts.replace(tzinfo=config.IST)  # SQLite hands back naive IST wall times
