"""Profiles from real DB rows, live policy membership, RFM, churn and onboarding."""

from __future__ import annotations

import time
from datetime import datetime, timedelta

import pytest
from sqlmodel import Session, select

from app import config, db
from app.config import IST
from app.contracts import CustomerProfile
from app.data.generator import DEFAULT_END
from app.data.onboarding import create_profile_from_answers, persona_for
from app.data.seed import run
from app.models import CustomerRow, EventRow
from app.scoring import churn, profile, rfm
from app.scoring.profile import assign_policy, build_profile

NOW = datetime(2026, 10, 24, 19, 0, tzinfo=IST)


@pytest.fixture(scope="module")
def engine(tmp_path_factory):
    eng = db.make_engine(f"sqlite:///{tmp_path_factory.mktemp('profile') / 'p.db'}")
    run(400, 5, end=DEFAULT_END, engine=eng)
    return eng


@pytest.fixture(autouse=True)
def use_engine(engine, monkeypatch):
    monkeypatch.setattr(db, "engine", engine)
    profile.reset_cache()
    config.set_time_override(NOW)
    yield
    config.set_time_override(None)


def _ids(engine) -> list[str]:
    with Session(engine) as s:
        return list(s.exec(select(CustomerRow.id).where(CustomerRow.id.like("C%"))))


def _add_event(engine, cid: str, typ: str, ts: datetime, **kw) -> None:
    with Session(engine) as s:
        s.add(EventRow(id=f"T-{cid}-{typ}-{ts.timestamp():.0f}", customer_id=cid, type=typ, ts=ts, **kw))
        s.commit()


# ------------------------------------------------------------------ assign_policy, one test per policy
def _p(**kw) -> CustomerProfile:
    rfm_extra = kw.pop("rfm", {})
    base = dict(
        customer_id="X",
        first_name="Asha",
        city_tier=2,
        persona="new_user",
        policy="default",
        rfm={
            "r": 3,
            "f": 3,
            "m": 3,
            "segment": "Potential",
            "orders_total": 4,
            "views_90d": 6,
            "days_since_active": 5,
            "tenure_days": 300,
            "spend_365d": 9000,
            "vip_spend_365d": 40000,
            **rfm_extra,
        },
        recency_days=12,
        orders_90d=1,
        aov=1500,
        ltv=9000,
        churn_risk=0.3,
        uplift={"pct_off": 0.05, "free_shipping": 0.04},
        price_sensitivity=0.4,
        category_affinity={"fashion": 1.0},
        return_rate=0.1,
        discount_usage_rate=0.2,
        points_balance=0,
        points_expiring=0,
        tier="Silver",
        as_of=NOW,
    )
    base.update(kw)
    return CustomerProfile(**base)


@pytest.mark.parametrize(
    ("expected", "profile_kw"),
    [
        ("default", {}),
        ("high_returner", {"return_rate": 0.5}),
        ("sleeping_dog", {"uplift": {"pct_off": -0.02, "free_shipping": -0.01}}),
        ("vip", {"rfm": {"spend_365d": 52000}, "recency_days": 4}),
        ("dormant", {"rfm": {"days_since_active": 150}, "recency_days": 150}),
        ("at_risk", {"recency_days": 61, "rfm": {"days_since_active": 61}}),
        ("at_risk", {"churn_risk": 0.7, "recency_days": 35}),
        (
            "cart_abandoner",
            {"open_cart": {"category": "fashion", "item": "Cotton Kurta", "value": 1450, "minutes": 45}},
        ),
        ("new_user", {"rfm": {"tenure_days": 10, "orders_total": 1}}),
        ("deal_hunter", {"discount_usage_rate": 0.75}),
        ("window_shopper", {"rfm": {"orders_total": 0, "views_90d": 20}, "ltv": 0}),
    ],
)
def test_assign_policy(expected, profile_kw):
    assert assign_policy(_p(**profile_kw)) == expected


def test_policy_priority_protects_margin_first():
    vip_with_cart = _p(
        rfm={"spend_365d": 52000},
        recency_days=2,
        open_cart={"category": "fashion", "item": "x", "value": 999, "minutes": 50},
    )
    assert assign_policy(vip_with_cart) == "vip"
    assert assign_policy(_p(return_rate=0.6, discount_usage_rate=0.9)) == "high_returner"
    fresh_cart = _p(open_cart={"category": "fashion", "item": "x", "value": 999, "minutes": 10})
    assert assign_policy(fresh_cart) == "default"
    lapsed_with_cart = _p(
        recency_days=70, open_cart={"category": "fashion", "item": "x", "value": 999, "minutes": 40}
    )
    assert assign_policy(lapsed_with_cart) == "cart_abandoner"


def test_thresholds_are_config_not_code(monkeypatch):
    monkeypatch.setitem(profile.POLICY_THRESHOLDS["deal_hunter"], "min_discount_usage", 0.9)
    assert assign_policy(_p(discount_usage_rate=0.75)) == "default"


# ------------------------------------------------------------------ build_profile from the DB
def test_build_profile_is_valid_and_fast(engine):
    ids = _ids(engine)[:60]
    build_profile(ids[0], NOW)  # warm the population cache
    start = time.perf_counter()
    profiles = [build_profile(cid, NOW) for cid in ids]
    per_call_ms = (time.perf_counter() - start) * 1000 / len(ids)
    assert per_call_ms < 50, f"{per_call_ms:.1f} ms per profile"
    for p in profiles:
        assert p.as_of == NOW and 0 <= p.churn_risk <= 1 and p.rfm["segment"] in rfm.SEGMENTS
        assert p.policy == assign_policy(p)
        assert abs(sum(p.category_affinity.values()) - 1) < 0.05 or not p.category_affinity
    assert len({p.policy for p in profiles}) >= 4


def test_unknown_customer_raises():
    with pytest.raises(KeyError):
        build_profile("C999999", NOW)


def test_simulated_purchase_sets_recency_to_zero(engine):
    cid = next(c for c in _ids(engine) if build_profile(c, NOW).recency_days > 5)
    before = build_profile(cid, NOW)
    _add_event(
        engine, cid, "purchase", NOW - timedelta(minutes=1), category="beauty", item="Nykaa Kajal", value=199
    )
    after = build_profile(cid, NOW)
    assert after.recency_days == 0
    assert after.orders_90d == before.orders_90d + 1


def test_inactivity_flips_policy_to_at_risk(engine):
    candidates = (build_profile(c, NOW) for c in _ids(engine))
    regular = next(
        p
        for p in candidates
        if p.policy in ("default", "vip", "deal_hunter")
        and p.recency_days < 20
        and p.rfm["orders_total"] >= 2
        and p.ltv >= profile.POLICY_THRESHOLDS["at_risk"]["min_ltv"]
    )
    later = build_profile(regular.customer_id, NOW + timedelta(days=61))
    assert later.recency_days >= 60
    assert later.policy == "at_risk"


def test_open_cart_makes_a_cart_abandoner(engine):
    cid = next(
        p.customer_id
        for p in (build_profile(c, NOW) for c in _ids(engine))
        if p.policy in ("default", "new_user", "window_shopper")
        and p.recency_days > 1  # no purchase after the cart
    )
    _add_event(
        engine,
        cid,
        "add_to_cart",
        NOW - timedelta(minutes=45),
        category="fashion",
        item="Cotton Kurta",
        value=1450,
    )
    p = build_profile(cid, NOW)
    assert p.open_cart["item"] == "Cotton Kurta" and p.open_cart["minutes"] == 45
    assert p.policy == "cart_abandoner"


def test_suppression_and_time_travel_ignore_future_rows(engine):
    cid = _ids(engine)[3]
    with Session(engine) as s:
        row = s.get(CustomerRow, cid)
        row.suppressed = {
            "fashion": (NOW + timedelta(days=14)).isoformat(),
            "beauty": (NOW - timedelta(days=1)).isoformat(),
        }
        s.add(row)
        s.commit()
    assert build_profile(cid, NOW).suppressed_categories == ["fashion"]
    past = build_profile(cid, NOW - timedelta(days=200))
    assert past.as_of < NOW and past.rfm["orders_total"] <= build_profile(cid, NOW).rfm["orders_total"]


# ------------------------------------------------------------------ rfm + churn
def test_rfm_scores_and_segments():
    cp = rfm.DEFAULT_CUTPOINTS
    assert rfm.score(3, 12, 60000, cp) == {"r": 5, "f": 5, "m": 5}
    assert rfm.score(None, 0, 0, cp) == {"r": 1, "f": 1, "m": 1}
    seg = rfm.segment
    assert seg(5, 5, 5, orders_total=12, tenure_days=400, days_since_active=1) == "Champions"
    assert seg(1, 4, 4, orders_total=6, tenure_days=400, days_since_active=200) == "At Risk"
    assert seg(1, 1, 1, orders_total=1, tenure_days=10, days_since_active=1) == "New"
    assert seg(1, 1, 1, orders_total=0, tenure_days=200, days_since_active=150) == "Lost"


def test_churn_model_is_trained_and_sensible():
    from app.scoring.churn_model import MODEL

    assert MODEL["features"] == churn.FEATURES and MODEL["auc"] >= 0.70
    now_ts, day = NOW.timestamp(), 86400
    signup = now_ts - 400 * day
    active = churn.features(
        [now_ts - d * day for d in (3, 20, 41, 70)],
        [1500] * 4,
        [now_ts - d * day for d in range(1, 60, 3)],
        0,
        signup,
        now_ts,
    )
    lapsed = churn.features(
        [now_ts - d * day for d in (95, 140, 200)],
        [1500] * 3,
        [now_ts - d * day for d in (80, 120)],
        0,
        signup,
        now_ts,
    )
    assert churn.predict(lapsed) > 0.6 > churn.predict(active)


# ------------------------------------------------------------------ onboarding
ANSWERS = {
    "categories": ["fashion", "beauty"],
    "frequency": "weekly",
    "style": "balanced",
    "festivals": ["diwali", "gurpurab", "not_a_festival"],
}


def test_onboarding_creates_customer_with_history(engine):
    customer = create_profile_from_answers(555001, "Navpreet", ANSWERS)
    assert customer.id == "TG555001" and customer.telegram_chat_id == 555001
    assert customer.persona == "cart_abandoner" and not customer.is_holdout
    assert customer.opt_in_festivals == ["diwali", "gurpurab"]
    p = build_profile(customer.id, NOW)
    assert p.rfm["tenure_days"] >= 170 and p.rfm["orders_total"] >= 1
    assert set(p.category_affinity) & {"fashion", "beauty"}
    assert p.policy == "cart_abandoner" and p.open_cart is not None


def test_onboarding_rerun_replaces_history_but_keeps_simulated_events(engine):
    first = create_profile_from_answers(555002, "Simran", ANSWERS)
    _add_event(engine, first.id, "session", NOW - timedelta(minutes=5))
    with Session(engine) as s:
        n_before = len(s.exec(select(EventRow.id).where(EventRow.customer_id == first.id)).all())
    create_profile_from_answers(555002, "Simran", ANSWERS)
    with Session(engine) as s:
        ids = s.exec(select(EventRow.id).where(EventRow.customer_id == first.id)).all()
    assert len(ids) == n_before and any(i.startswith("T-") for i in ids)


@pytest.mark.parametrize(
    ("answers", "persona"),
    [
        ({"frequency": "weekly", "style": "quality"}, "loyal_vip"),
        ({"frequency": "monthly", "style": "deal"}, "deal_hunter"),
        ({"frequency": "monthly", "style": "balanced"}, "at_risk_regular"),
        ({"frequency": "occasionally", "style": "quality", "festivals": ["diwali"]}, "festive_gifter"),
        ({"frequency": "occasionally", "style": "balanced"}, "window_shopper"),
        ({"frequency": "rarely", "style": "deal"}, "new_user"),
    ],
)
def test_answers_pick_a_persona(answers, persona):
    assert persona_for(answers) == persona


@pytest.mark.parametrize(
    ("answers", "policy"),
    [
        ({"frequency": "weekly", "style": "quality"}, "vip"),
        ({"frequency": "weekly", "style": "balanced"}, "cart_abandoner"),
        ({"frequency": "monthly", "style": "balanced"}, "at_risk"),
        ({"frequency": "occasionally", "style": "balanced"}, "window_shopper"),
        ({"frequency": "rarely", "style": "deal"}, "new_user"),
    ],
)
def test_onboarded_policies_match_the_answers(engine, answers, policy):
    """Most classmates who give these answers land in the intended policy (history is random per user)."""
    hits = 0
    for i in range(8):
        customer = create_profile_from_answers(
            557000 + i * 7919, "Guest", {"categories": ["fashion"], **answers}
        )
        hits += build_profile(customer.id, NOW).policy == policy
    assert hits >= 6, f"{hits}/8 onboarded users landed in {policy}"
