"""get_context(now): the facts about *the moment* that every decision shares (not about the customer)."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from sqlalchemy.exc import SQLAlchemyError

from app import decision_store, ports
from app.config import IST
from app.contracts import Context, Festival, FestivalPhase, Rule
from app.rules.engine import load_rules
from app.rules.rule_types import QuietHours

log = logging.getLogger(__name__)

DEFAULT_DAILY_CAP = 50000
PACING_STARTS_AT = 0.8  # share of a budget used before caps start shrinking (PLAN §4)
PACING_FLOOR = 0.5  # caps never shrink below half while any budget is left


def festival_key(festival_id: str) -> str:
    """'diwali_2026' → 'diwali' (same rule as app.data.festivals.festival_key; customers opt in to keys)."""
    return festival_id.rsplit("_", 1)[0]


def phase_on(festival: Festival, day: date) -> FestivalPhase | None:
    offset = (day - festival.date).days
    for phase, (lo, hi) in festival.phases.items():
        if lo <= offset <= hi:
            return phase
    return None


def active_festival(day: date) -> tuple[Festival, FestivalPhase] | None:
    """Phases of neighbouring festivals overlap (Dhanteras/Diwali/Bhai Dooj): the nearest date wins."""
    live = [(f, p) for f in ports.festivals() if (p := phase_on(f, day)) is not None]
    if not live:
        return None
    return min(live, key=lambda fp: (abs((fp[0].date - day).days), fp[0].date))


def pacing_factor(used: int, cap: int) -> float:
    if cap <= 0:
        return PACING_FLOOR
    share = used / cap
    if share <= PACING_STARTS_AT:
        return 1.0
    shrink = (share - PACING_STARTS_AT) / (1 - PACING_STARTS_AT)
    return round(max(PACING_FLOOR, 1 - shrink * (1 - PACING_FLOOR)), 3)


def _rule_of_type(rules: list[Rule], rtype: str) -> Rule | None:
    return next(
        (r for r in rules if r.enabled and r.layer == "global" and r.type == rtype and not r.conditions), None
    )


def spent_between(first: date, last: date) -> int:
    """₹ already sent on the days first..last (inclusive), from the shared decision store."""
    try:
        return sum(decision_store.spent_on(first + timedelta(days=i)) for i in range((last - first).days + 1))
    except SQLAlchemyError:
        log.warning("decisions table not readable; assuming nothing spent")
        return 0


def get_context(now: datetime, *, rules: list[Rule] | None = None) -> Context:
    now = now if now.tzinfo else now.replace(tzinfo=IST)
    local = now.astimezone(IST)
    rules = load_rules() if rules is None else rules

    quiet_rule = _rule_of_type(rules, "quiet_hours")
    is_quiet = QuietHours(quiet_rule).is_quiet(now) if quiet_rule else False
    budget_rule = _rule_of_type(rules, "budget")
    cap = int((budget_rule.params.get("daily_cap") if budget_rule else None) or DEFAULT_DAILY_CAP)

    used_today = spent_between(local.date(), local.date())
    pf = pacing_factor(used_today, cap)

    festival = phase = days_to = cutoff = greeting = left_fest = None
    heroes: list = []
    found = active_festival(local.date())
    if found:
        fest, phase = found
        festival, days_to, heroes, greeting = (
            fest.id,
            (fest.date - local.date()).days,
            fest.hero_categories,
            fest.greeting,
        )
        slowest = max(fest.delivery_days_by_tier.values(), default=0)
        cutoff = fest.date - timedelta(days=slowest)
        window_start = fest.date + timedelta(days=min(lo for lo, _ in fest.phases.values()))
        used_fest = spent_between(window_start, local.date())
        left_fest = max(0, fest.budget - used_fest)
        pf = min(pf, pacing_factor(used_fest, fest.budget))

    return Context(
        now=now,
        is_quiet_hours=is_quiet,
        is_payday_window=local.day <= 5,
        festival=festival,
        festival_phase=phase,
        days_to_festival=days_to,
        hero_categories=heroes,
        delivery_cutoff=cutoff,
        greeting=greeting,
        budget_left_today=max(0, cap - used_today),
        budget_left_festival=left_fest,
        pacing_factor=pf,
    )
