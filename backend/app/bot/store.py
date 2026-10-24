"""The bot's DB reads/writes (customers' consent + preferences, decision lookups).

Sync functions: handlers call them via `asyncio.to_thread` so a slow Neon round-trip never blocks the loop.
"""

from __future__ import annotations

import logging
from datetime import datetime

from sqlmodel import Session, select

from app import db
from app.contracts import Customer, Decision
from app.models import CustomerRow, DecisionRow

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
