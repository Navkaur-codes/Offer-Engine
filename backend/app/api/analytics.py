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


HERO_WINDOW_DAYS = 365  # 30 days often holds no campaign with enough holdout customers, so the hero read ₹0


def _kpi_values(day: date, cap: int) -> dict:
    n = _day_numbers(day)
    exp = ports.experiments_compute(day - timedelta(days=HERO_WINDOW_DAYS), day)
    return {
        "sent_today": n["sent"],
        "claim_rate": round(n["claim_rate"], 4),
        "incremental_revenue": exp.incremental_revenue,
        "budget_used_pct": round(n["spent"] / cap, 4) if cap else 0.0,
        "blocked_by_rules": n["blocked"],
        "agent_share": round(n["agent_share"], 4),
        "fallback_share": round(n["fallback_share"], 4),
        "margin_saved": exp.margin_saved_sure_things,
    }


def _relative(now_v: float, then_v: float) -> float | None:
    """Fractional change vs yesterday (0.12 = +12%); None when yesterday was 0, so the UI shows no arrow."""
    return round((now_v - then_v) / then_v, 4) if then_v else None


DELTA_KEYS = (
    "sent_today",
    "claim_rate",
    "incremental_revenue",
    "budget_used_pct",
    "blocked_by_rules",
    "margin_saved",
)


@router.get("/kpis")
def kpis(day: date | None = None) -> Kpis:
    day = day or now().date()
    cap = daily_cap()
    today, yday = _kpi_values(day, cap), _kpi_values(day - timedelta(days=1), cap)
    return Kpis(**today, deltas={k: _relative(today[k], yday[k]) for k in DELTA_KEYS})


@router.get("/today")
def today(day: date | None = None) -> dict:
    """Today's money in and out of offers, live from the decision log (the KPIs' 12-month figures only move
    when a randomised control group can measure them). `margin_kept` is what the offers the engine chose not
    to send would have cost: per NO_OFFER decision, its costliest allowed candidate (as the Lab says)."""
    rows = decision_store.day_rows(day or now().date())
    sent = [r for r in rows if r.status == "SENT"]
    skipped = [r for r in rows if r.status == "NO_OFFER"]
    kept = sum(
        max((c.get("est_cost", 0) for c in r.payload.get("candidates", [])), default=0) for r in skipped
    )
    return {
        "decisions": len(rows),
        "sent": len(sent),
        "spent": sum(r.cost for r in sent),
        "expected_incremental_profit": sum(r.expected_incremental_profit for r in sent),
        "no_offer": len(skipped),
        "margin_kept": int(max(kept, 0)),
        "blocked": sum(r.status == "BLOCKED" for r in rows),
        "held_out": sum(r.status == "HELD_OUT" for r in rows),
    }


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
