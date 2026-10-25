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
from app.contracts import CustomerProfile, OfferCandidate, Rule
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


def _allowed(profile: CustomerProfile, ctx, rules: list[Rule], catalogue) -> dict[str, OfferCandidate]:
    cands, _ = screen_offers(profile, ctx, catalogue, rules=rules)
    return {c.offer_id: c for c in cands}


def _label(cand: OfferCandidate | None) -> str:
    """'up to 10% off ethnic wear' for an allowed offer, 'not allowed' when the rules remove it."""
    if cand is None:
        return "not allowed"
    from app.agent import fallback
    from app.rules.rule_types import worst_case_params

    params = {**worst_case_params(cand.allowed_params), "category": cand.category}
    return f"up to {fallback.offer_value(cand.type, params)}"


def impact(rule: Rule, *, profiles: list[CustomerProfile] | None = None, now: datetime | None = None) -> dict:
    """{"customers_affected", "budget_delta", "examples", "sample_size"} over the sample.

    A customer is affected when any offer or range the rules allow them changes. `budget_delta` is the change
    in worst-case spend headroom: the summed most-generous cost of every allowed offer, after minus before.
    A removed offer subtracts its cost and a narrowed range subtracts the difference, so tightening a cap
    shows up as a saving (negative ₹) even when another offer is still the most expensive one.
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
        before = _allowed(p, ctx, current, catalogue)
        after = _allowed(p, ctx, edited, catalogue)
        changed = sorted(
            oid
            for oid in before.keys() | after.keys()
            if (before.get(oid) and before[oid].allowed_params)
            != (after.get(oid) and after[oid].allowed_params)
        )
        if not changed:
            continue
        affected += 1
        delta += sum(c.est_cost for c in after.values()) - sum(c.est_cost for c in before.values())
        if len(examples) < MAX_EXAMPLES:
            oid = changed[0]
            name = next((o.name for o in catalogue if o.id == oid), oid)
            examples.append(
                {
                    "customer_id": p.customer_id,
                    "first_name": p.first_name,
                    "offer": name,
                    "before": _label(before.get(oid)),
                    "after": _label(after.get(oid)),
                }
            )
    return {
        "customers_affected": affected,
        "budget_delta": delta,
        "examples": examples,
        "sample_size": len(profiles),
    }
