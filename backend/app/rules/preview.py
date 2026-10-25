"""impact(rule): what a rule edit would change, before the marketer saves it.

Re-screens a fixed sample of customers with the current rules and with the edited rule, and compares what
the rules fallback would send each of them (the same deterministic scorer the harness falls back to).
"""

from __future__ import annotations

import logging
import random
import time as timer
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from app import ports
from app.config import now as clock
from app.contracts import CustomerProfile, Rule
from app.rules.engine import load_rules, screen_offers
from app.rules.offers import load_offers

log = logging.getLogger(__name__)

SAMPLE_SIZE = 500
SAMPLE_SEED = 42
CACHE_SECONDS = 600
MAX_EXAMPLES = 3

_cache: dict = {"at": 0.0, "day": None, "profiles": []}


def sample_profiles(now: datetime, size: int = SAMPLE_SIZE) -> list[CustomerProfile]:
    """A fixed random sample of synthetic customers (same ids every time), built once per 10 minutes."""
    if (
        _cache["profiles"]
        and _cache["day"] == now.date()
        and timer.monotonic() - _cache["at"] < CACHE_SECONDS
    ):
        return _cache["profiles"]
    from app.db import engine as db_engine
    from app.models import CustomerRow

    try:
        with Session(db_engine) as s:
            query = select(CustomerRow.id).where(CustomerRow.is_lab_bot == False)  # noqa: E712
            ids = sorted(s.exec(query).all())
    except SQLAlchemyError:
        ids = []
    picked = random.Random(SAMPLE_SEED).sample(ids, min(size, len(ids)))
    profiles = []
    for cid in picked:
        try:
            profiles.append(ports.build_profile(cid, now))
        except Exception:  # one broken history row shouldn't sink the whole preview
            log.exception("preview: could not build profile %s", cid)
    _cache.update(at=timer.monotonic(), day=now.date(), profiles=profiles)
    return profiles


def _with_edit(rules: list[Rule], edited: Rule) -> list[Rule]:
    return [r for r in rules if r.id != edited.id] + [edited]


def _view(profile: CustomerProfile, ctx, rules: list[Rule], catalogue) -> tuple[tuple, int, str]:
    """(what the rules allow this customer, the most we could spend on them, a one-line description)."""
    from app.agent import fallback
    from app.rules.rule_types import worst_case_params

    cands, _ = screen_offers(profile, ctx, catalogue, rules=rules)
    allowed = tuple(sorted((c.offer_id, repr(c.allowed_params)) for c in cands))
    if not cands:
        return allowed, 0, "no offer allowed"
    top = max(cands, key=lambda c: (c.est_cost, c.offer_id))
    most = fallback.offer_value(top.type, {**worst_case_params(top.allowed_params), "category": top.category})
    n = len(cands)
    return allowed, top.est_cost, f"{n} offer{'s' * (n != 1)} allowed, up to {most}"


def impact(rule: Rule, *, profiles: list[CustomerProfile] | None = None, now: datetime | None = None) -> dict:
    """{"customers_affected", "budget_delta", "examples", "sample_size"} over the sample.

    A customer is affected when the offers or ranges the rules allow them change. `budget_delta` is the change
    in the most the rules would let us spend on these customers (each one's most expensive allowed offer), so
    tightening a cap shows a saving even when today's cheapest pick stays the same.
    """
    from app.agent.context import get_context

    now = now or clock()
    current = load_rules()
    edited = _with_edit(current, rule)
    catalogue = load_offers()
    ctx = get_context(now, rules=current)
    profiles = sample_profiles(now) if profiles is None else profiles

    affected, delta, examples = 0, 0, []
    for p in profiles:
        allowed_before, cost_before, before = _view(p, ctx, current, catalogue)
        allowed_after, cost_after, after = _view(p, ctx, edited, catalogue)
        if allowed_before == allowed_after:
            continue
        affected += 1
        delta += cost_after - cost_before
        if len(examples) < MAX_EXAMPLES:
            examples.append(
                {"customer_id": p.customer_id, "first_name": p.first_name, "before": before, "after": after}
            )
    return {
        "customers_affected": affected,
        "budget_delta": delta,
        "examples": examples,
        "sample_size": len(profiles),
    }
