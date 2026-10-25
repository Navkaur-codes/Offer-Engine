"""Uplift T-learner + impact: offers go where they change behaviour, not to people who'd buy anyway."""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime

import pytest
from sqlmodel import Session, select

from app import config, db, ports
from app.config import IST
from app.data.generator import DEFAULT_END
from app.data.seed import run
from app.models import CustomerRow
from app.scoring import impact, profile
from app.scoring.uplift_model import MODEL

NOW = datetime(2026, 10, 25, 12, 0, tzinfo=IST)
PAID = [("pct_off", {"pct": 10}), ("free_shipping", {}), ("bonus_points", {"multiplier": 2})]


@pytest.fixture(scope="module")
def by_type(tmp_path_factory):
    """Expected profit per hidden response type × offer, over a fresh 600-customer world."""
    engine = db.make_engine(f"sqlite:///{tmp_path_factory.mktemp('uplift') / 'u.db'}")
    run(600, 21, end=DEFAULT_END, engine=engine)
    original = db.engine
    db.engine = engine
    profile.reset_cache()
    config.set_time_override(NOW)
    try:
        with Session(engine) as s:
            rows = s.exec(
                select(CustomerRow.id, CustomerRow.response_type).where(CustomerRow.id.like("C%"))
            ).all()
        out: dict[tuple[str, str], list[int]] = defaultdict(list)
        for cid, resp in rows:
            p = profile.build_profile(cid, NOW)
            for offer_type, params in PAID:
                out[(resp, offer_type)].append(impact.estimate(p, offer_type, params, None)[1])
        return out
    finally:
        db.engine = original
        config.set_time_override(None)
        profile.reset_cache()


def _mean(by_type, resp, offer_type) -> float:
    return statistics.mean(by_type[(resp, offer_type)])


def test_model_is_trained_and_beats_random():
    assert set(MODEL["families"]) == {"discount", "points"}
    for fam, report in MODEL["report"].items():
        assert report["qini_gain_over_random"] > 0, fam
        assert report["n_control"] > 500 and report["n_treated"] > 500
    q = MODEL["qini"]
    assert q[0]["targeted"] == 0 and q[-1]["targeted"] == 1
    assert sum(p["model"] for p in q) > sum(p["random"] for p in q)  # the curve sits above the diagonal


def test_uplift_ranks_hidden_types_sensibly():
    disc = MODEL["report"]["discount"]["mean_uplift_by_response_type"]
    pts = MODEL["report"]["points"]["mean_uplift_by_response_type"]
    assert disc["persuadable"] > disc["sure_thing"] and disc["persuadable"] > disc["sleeping_dog"]
    assert pts["persuadable"] > 0 > pts["sure_thing"] and pts["sleeping_dog"] < 0


def test_persuadables_pay_and_sure_things_do_not(by_type):
    assert max(_mean(by_type, "persuadable", t) for t, _ in PAID) > 0
    for offer_type, _ in PAID:
        assert _mean(by_type, "persuadable", offer_type) > _mean(by_type, "sure_thing", offer_type), (
            offer_type
        )
        assert _mean(by_type, "sure_thing", offer_type) <= 0, offer_type
        assert _mean(by_type, "sleeping_dog", offer_type) <= 0, offer_type


def _profile(**kw):
    from tests.data.test_profile_policy import _p

    return _p(**kw)


def test_impact_cost_models():
    p = _profile(aov=2000, category_affinity={"fashion": 1.0})
    zero_cost, _ = impact.estimate(p, "cart_nudge", {}, "fashion")
    assert zero_cost == 0
    c10, _ = impact.estimate(p, "pct_off", {"pct": 10}, "fashion")
    c20, _ = impact.estimate(p, "pct_off", {"pct": 20}, "fashion")
    assert 0 < c10 < c20  # cost grows with the discount
    ship, _ = impact.estimate(p, "free_shipping", {}, "fashion")
    express, _ = impact.estimate(p, "free_express", {}, "fashion")
    assert 0 < ship < express <= 120  # shipping cost × P(buy), never more than the full fee
    basket, _ = impact.estimate(p, "pct_off", {"pct": 10, "min_basket": 5000}, "fashion")
    assert basket > c10  # a higher minimum basket means a bigger discount in ₹


def test_ports_are_real():
    ports.reset_cache()
    status = ports.status()
    assert status["uplift_predict"] == "real" and status["impact_estimate"] == "real"
