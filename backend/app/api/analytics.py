"""KPIs, experiments, realism and the daily AI digest."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter

from app import decision_store, ports
from app.api.rules import daily_cap
from app.config import now
from app.contracts import ExperimentStats, Kpis, RealismStats

router = APIRouter(prefix="/api", tags=["analytics"])

AGENT = {"AGENT", "AGENT_RETRY"}
CLAIMED = {"claimed", "redeemed"}


def _day_numbers(day: date) -> dict:
    rows = decision_store.day_rows(day)
    sent = [r for r in rows if r.status == "SENT"]
    n = len(sent)
    return {
        "sent": n,
        "claim_rate": sum(r.outcome in CLAIMED for r in sent) / n if n else 0.0,
        "blocked": sum(r.status == "BLOCKED" for r in rows),
        "agent_share": sum(r.decided_by in AGENT for r in sent) / n if n else 0.0,
        "fallback_share": sum(r.decided_by == "RULES_FALLBACK" for r in sent) / n if n else 0.0,
        "spent": sum(r.cost for r in sent),
    }


@router.get("/kpis")
def kpis(day: date | None = None) -> Kpis:
    day = day or now().date()
    today, yday = _day_numbers(day), _day_numbers(day - timedelta(days=1))
    exp = ports.experiments_compute(day - timedelta(days=30), day)
    cap = daily_cap()
    return Kpis(
        sent_today=today["sent"],
        claim_rate=round(today["claim_rate"], 4),
        incremental_revenue=exp.incremental_revenue,
        budget_used_pct=round(today["spent"] / cap, 4) if cap else 0.0,
        blocked_by_rules=today["blocked"],
        agent_share=round(today["agent_share"], 4),
        fallback_share=round(today["fallback_share"], 4),
        margin_saved=exp.margin_saved_sure_things,
        deltas={k: round(today[k] - yday[k], 4) for k in ("sent", "claim_rate", "blocked")},
    )


@router.get("/experiments")
def experiments(start: date | None = None, end: date | None = None) -> ExperimentStats:
    end = end or now().date()
    return ports.experiments_compute(start or end - timedelta(days=30), end)


@router.get("/realism")
def realism() -> RealismStats:
    return ports.realism_compute()


@router.get("/digest")
def digest(day: date | None = None) -> dict:
    day = day or now().date()
    return {
        "day": day.isoformat(),
        "text": ports.daily_digest(day),
        "generated_by": ports.status()["daily_digest"],
    }
