"""GATE-4: a judge who taps through /start must get a welcome, whatever they answer.

Runs the real harness (dry run, rules fallback, no LLM) over every frequency × style answer. The at-risk
persona (monthly + balanced) is checked for its uplift signal only: whether it then gets an offer is decided
by the at-risk winback rule (min uplift) and the festival hero-category rule, owned by the rules engine.
"""

from __future__ import annotations

import itertools
from datetime import datetime, timedelta

import pytest
from sqlmodel import Session, select

from app import config, db, ports
from app.config import IST
from app.data.generator import DEFAULT_END
from app.data.onboarding import RECENT_PURCHASE_DAYS, create_profile_from_answers
from app.data.seed import run
from app.models import OrderRow
from app.scoring import profile

NOW = datetime(2026, 10, 26, 14, 0, tzinfo=IST)
ANSWERS = list(
    itertools.product(["weekly", "monthly", "occasionally", "rarely"], ["deal", "quality", "balanced"])
)


@pytest.fixture(scope="module")
def onboarded(tmp_path_factory):
    engine = db.make_engine(f"sqlite:///{tmp_path_factory.mktemp('welcome') / 'w.db'}")
    run(300, 7, end=DEFAULT_END, engine=engine)
    original = db.engine
    db.engine = engine
    profile.reset_cache()
    config.set_time_override(NOW)
    try:
        out = []
        for i, (freq, style) in enumerate(ANSWERS):
            for j, cat in enumerate(("fashion", "home_decor")):
                tid = 9_100_000_000 + i * 10 + j
                answers = {"categories": [cat], "frequency": freq, "style": style, "festivals": []}
                customer = create_profile_from_answers(tid, "Judge", answers)
                decision = ports.decide(
                    customer.id, "welcome", {"initiated_by": "customer"}, dry_run=True, now=NOW
                )
                with Session(engine) as s:
                    last = max(
                        s.exec(select(OrderRow.ts).where(OrderRow.customer_id == customer.id)).all(),
                        default=None,
                    )
                out.append((freq, style, customer, decision, last))
        yield out
    finally:
        db.engine = original
        config.set_time_override(None)
        profile.reset_cache()


def _aware(ts):
    return ts.replace(tzinfo=IST) if ts.tzinfo is None else ts.astimezone(IST)


def test_no_new_user_is_a_sleeping_dog(onboarded):
    assert all(d.profile_snapshot.policy != "sleeping_dog" for *_, d, _ in onboarded)
    assert all(c.response_type != "sleeping_dog" for _, _, c, _, _ in onboarded)


def test_generated_history_never_trips_the_post_purchase_rule(onboarded):
    for *_, last in onboarded:
        assert last is None or NOW - _aware(last) >= timedelta(days=3)


def test_stated_frequency_shows_in_recency(onboarded):
    for freq, _, c, _, last in onboarded:
        within = RECENT_PURCHASE_DAYS.get(freq)
        if within and c.persona not in ("at_risk_regular", "window_shopper", "new_user"):
            assert last is not None and NOW - _aware(last) <= timedelta(days=within), (freq, c.persona)


def test_every_new_user_outside_at_risk_gets_a_welcome(onboarded):
    misses = [
        (freq, style, d.profile_snapshot.policy, d.fallback_reason)
        for freq, style, _, d, _ in onboarded
        if d.profile_snapshot.policy != "at_risk" and d.status != "DRY_RUN"
    ]
    assert not misses


def test_at_risk_new_users_carry_a_winback_signal(onboarded):
    at_risk = [d.profile_snapshot for f, s, _, d, _ in onboarded if (f, s) == ("monthly", "balanced")]
    assert at_risk and all(p.policy == "at_risk" for p in at_risk)
    # still browsing after they stopped buying: the win-back-able kind, with a positive discount uplift
    assert all(p.rfm["days_since_active"] < p.recency_days for p in at_risk)
    assert sum(p.uplift["pct_off"] > 0 for p in at_risk) >= len(at_risk) // 2
