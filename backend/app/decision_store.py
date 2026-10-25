"""Shared persistence for decisions (owned by Main; used by the harness, the bot and the API).

`DecisionRow` keeps filterable columns plus the full `contracts.Decision` JSON in `payload`.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlmodel import Session, func, select

from app import db
from app.config import IST
from app.contracts import Decision, DecisionLight, Outcome
from app.models import DecisionRow


def aware(ts: datetime) -> datetime:
    """SQLite hands back naive IST wall time; Postgres hands back aware UTC. Normalise to aware IST."""
    return ts.replace(tzinfo=IST) if ts.tzinfo is None else ts.astimezone(IST)


def _session() -> Session:
    return Session(db.engine, expire_on_commit=False)


def _columns(d: Decision) -> dict:
    return dict(
        ts=d.ts, customer_id=d.customer_id, policy=d.profile_snapshot.policy, trigger=d.trigger,
        decided_by=d.decided_by, status=d.status, final_offer_id=d.final_offer_id, coupon_code=d.coupon_code,
        cost=d.cost, expected_incremental_profit=d.expected_incremental_profit, channel=d.channel,
        is_holdout=d.is_holdout, outcome=d.outcome, outcome_at=d.outcome_at, revenue=d.revenue,
        payload=d.model_dump(mode="json"),
    )


def save(decision: Decision) -> None:
    """Insert or replace one decision. Dry runs are never stored."""
    if decision.status == "DRY_RUN":
        return
    with _session() as s:
        row = s.get(DecisionRow, decision.id)
        if row is None:
            row = DecisionRow(id=decision.id, **_columns(decision))
        else:
            for k, v in _columns(decision).items():
                setattr(row, k, v)
        s.add(row)
        s.commit()


def get(decision_id: str) -> Decision | None:
    with _session() as s:
        row = s.get(DecisionRow, decision_id)
    return Decision.model_validate(row.payload) if row else None


def set_outcome(decision_id: str, outcome: Outcome, at: datetime, revenue: int | None = None) -> bool:
    with _session() as s:
        row = s.get(DecisionRow, decision_id)
        if row is None:
            return False
        row.outcome, row.outcome_at = outcome, at
        if revenue is not None:
            row.revenue = revenue
        payload = dict(row.payload)
        payload.update(outcome=outcome, outcome_at=at.isoformat(), revenue=row.revenue)
        row.payload = payload
        s.add(row)
        s.commit()
        return True


def query(*, status: str | None = None, decided_by: str | None = None, policy: str | None = None,
          trigger: str | None = None, customer_id: str | None = None, q: str | None = None,
          festival: str | None = None, before: datetime | None = None, after: datetime | None = None,
          limit: int = 50) -> list[Decision]:
    """Newest first. `before` pages backwards; `after` returns only rows newer than it (live stream)."""
    stmt = select(DecisionRow)
    if festival:  # active at decision time, any trigger (CR-D2); "diwali" or "diwali_2026"
        active = DecisionRow.payload["context"]["festival"].as_string()
        stmt = stmt.where((active == festival) | active.startswith(f"{festival}_"))
    for col, val in ((DecisionRow.status, status), (DecisionRow.decided_by, decided_by),
                     (DecisionRow.policy, policy), (DecisionRow.trigger, trigger),
                     (DecisionRow.customer_id, customer_id)):
        if val:
            stmt = stmt.where(col == val)
    if q:
        stmt = stmt.where(DecisionRow.id.contains(q) | DecisionRow.customer_id.contains(q)
                          | DecisionRow.coupon_code.contains(q))
    if before:
        stmt = stmt.where(DecisionRow.ts < before)
    if after:
        stmt = stmt.where(DecisionRow.ts > after)
    stmt = stmt.order_by(DecisionRow.ts.desc()).limit(limit)
    with _session() as s:
        rows = s.exec(stmt).all()
    return [Decision.model_validate(r.payload) for r in rows]


def light(decisions: list[Decision]) -> list[DecisionLight]:
    return [DecisionLight.from_decision(d) for d in decisions]


def day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, IST)
    return start, start + timedelta(days=1)


def day_rows(day: date) -> list[DecisionRow]:
    start, end = day_bounds(day)
    with _session() as s:
        return list(s.exec(select(DecisionRow).where(DecisionRow.ts >= start, DecisionRow.ts < end)).all())


def spent_on(day: date) -> int:
    """₹ committed by sent offers that day — the budget meter and the harness's pacing both read this."""
    start, end = day_bounds(day)
    with _session() as s:
        total = s.exec(select(func.coalesce(func.sum(DecisionRow.cost), 0)).where(
            DecisionRow.ts >= start, DecisionRow.ts < end, DecisionRow.status == "SENT")).one()
    return int(total or 0)
