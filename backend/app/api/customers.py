"""Customers, the decision Playground and campaign dry-runs."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app import db, decision_store, ports
from app.api.deps import not_found, require_admin
from app.config import now
from app.contracts import CustomerProfile, Decision, DecisionLight, Event, TriggerType
from app.models import CustomerRow, EventRow

router = APIRouter(prefix="/api", tags=["customers"])

MAX_SCAN = 600  # rows scanned per request when filtering by a computed policy
# a profile is ~5 round trips on Neon, so a sequential policy scan could pass Render's proxy timeout (502)
SCAN_CHUNK = 24
SCAN_WORKERS = 6  # stays inside the engine's pool (5 + 5 overflow) next to the bot
PROFILE_TTL_S = 300
_profile_cache: dict[str, tuple[float, CustomerProfile]] = {}
_cache_lock = threading.Lock()


class SimulateIn(BaseModel):
    trigger: TriggerType
    meta: dict = Field(default_factory=dict)


class PlaygroundIn(SimulateIn):
    customer_id: str
    now: datetime | None = None


class CampaignIn(BaseModel):
    policy: str | None = None
    festival: str | None = None
    offer_ids: list[str] | None = None
    budget: int = 50_000
    limit: int = Field(default=100, ge=1, le=200)


def _rows(q: str | None, after: str | None, limit: int) -> list[CustomerRow]:
    stmt = select(CustomerRow).order_by(CustomerRow.id)
    if q:
        stmt = stmt.where(CustomerRow.id.contains(q) | CustomerRow.first_name.contains(q))
    if after:
        stmt = stmt.where(CustomerRow.id > after)
    with Session(db.engine) as s:
        return list(s.exec(stmt.limit(limit)).all())


def _cached_profile(customer_id: str, at: datetime) -> CustomerProfile:
    clock = time.monotonic()
    with _cache_lock:
        hit = _profile_cache.get(customer_id)
    if hit and clock - hit[0] < PROFILE_TTL_S:
        return hit[1]
    profile = ports.build_profile(customer_id, at)
    with _cache_lock:
        _profile_cache[customer_id] = (clock, profile)
    return profile


def _profiles(q: str | None, policy: str | None, cursor: str | None, limit: int) -> tuple[list, str | None]:
    at = now()
    rows = _rows(q, cursor, limit if not policy else MAX_SCAN)
    out: list[CustomerProfile] = []
    last = cursor
    with ThreadPoolExecutor(max_workers=SCAN_WORKERS) as pool:
        for start in range(0, len(rows), SCAN_CHUNK):
            chunk = rows[start : start + SCAN_CHUNK]
            for row, p in zip(chunk, pool.map(lambda r: _cached_profile(r.id, at), chunk), strict=True):
                last = row.id
                if not policy or p.policy == policy:
                    out.append(p)
                if len(out) == limit:
                    return out, last
    return out, None


@router.get("/customers")
def list_customers(
    q: str | None = None, policy: str | None = None, limit: int = 25, cursor: str | None = None
) -> dict:
    items, nxt = _profiles(q, policy, cursor, max(1, min(limit, 100)))
    return {"items": items, "next": nxt}


@router.get("/customers/{customer_id}")
def get_customer(customer_id: str) -> dict:
    with Session(db.engine) as s:
        row = s.get(CustomerRow, customer_id)
        if row is None:
            raise not_found("Customer")
        events = s.exec(
            select(EventRow).where(EventRow.customer_id == customer_id).order_by(EventRow.ts.desc()).limit(50)
        ).all()
    return {
        "profile": ports.build_profile(customer_id, now()),
        "events": [Event.model_validate(e.model_dump()) for e in events],
        "decisions": decision_store.light(decision_store.query(customer_id=customer_id, limit=20)),
    }


@router.post("/customers/{customer_id}/simulate", dependencies=[Depends(require_admin)])
def simulate(customer_id: str, body: SimulateIn) -> Decision:
    """Runs the real pipeline, not a dry run. The harness stores but never sends, so (as in the scheduler) a
    SENT offer is delivered here; synthetic customers have no chat, so deliver skips them."""
    decision = ports.decide(customer_id, body.trigger, {**body.meta, "initiated_by": "admin"})
    if decision.status == "SENT" and decision.channel == "dm":
        ports.deliver(decision, "dm")
    return decision


@router.post("/playground/run")
def playground(body: PlaygroundIn) -> Decision:
    """Dry run: nothing is stored or sent, so it is open to anyone browsing the dashboard."""
    return ports.decide(body.customer_id, body.trigger, body.meta, dry_run=True, now=body.now)


@router.post("/campaigns/dry-run")
def campaign_dry_run(body: CampaignIn) -> dict:
    profiles, _ = _profiles(None, body.policy, None, body.limit)
    meta = {"festival": body.festival, "offer_ids": body.offer_ids}
    rows: list[DecisionLight] = []
    totals = {
        "customers": 0,
        "would_send": 0,
        "no_offer": 0,
        "blocked": 0,
        "over_budget": 0,
        "cost": 0,
        "expected_incremental_profit": 0,
    }
    batch = ports.decide_batch([(p.customer_id, "campaign", meta) for p in profiles], dry_run=True)
    for d in batch:
        totals["customers"] += 1
        if d.final_offer_id and totals["cost"] + d.cost > body.budget:
            totals["over_budget"] += 1
            continue
        if d.final_offer_id:
            totals["would_send"] += 1
            totals["cost"] += d.cost
            totals["expected_incremental_profit"] += d.expected_incremental_profit
        elif d.status == "BLOCKED":
            totals["blocked"] += 1
        else:
            totals["no_offer"] += 1
        rows.append(DecisionLight.from_decision(d))
    return {"rows": rows, "totals": totals}
