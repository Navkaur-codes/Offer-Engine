"""Edge cases judges will hit: a brand-new Telegram user, 0 orders, missing age, time travel."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from sqlmodel import Session, select

from app import config, db
from app.config import IST
from app.data.generator import DEFAULT_END
from app.data.seed import run
from app.models import CustomerRow, EventRow
from app.scoring import impact, profile
from app.scoring.uplift import FAMILY

NOW = datetime(2026, 10, 25, 12, 0, tzinfo=IST)
PARAMS = {"pct": 10, "amount": 100, "multiplier": 2}


@pytest.fixture(scope="module")
def engine(tmp_path_factory):
    eng = db.make_engine(f"sqlite:///{tmp_path_factory.mktemp('edge') / 'e.db'}")
    run(150, 2, end=DEFAULT_END, engine=eng)
    with Session(eng) as s:
        s.add(
            CustomerRow(
                id="TG1",
                first_name="Brand New",
                city="Ludhiana",
                city_tier=2,
                signup_date=NOW.date(),
                channel="telegram",
                device="mobile",
                preferred_payment="upi",
                persona="new_user",
                response_type="persuadable",
                telegram_chat_id=1,
            )
        )
        s.add(
            CustomerRow(
                id="TG2",
                first_name="Looker",
                city="Moga",
                city_tier=3,
                signup_date=date(2026, 9, 1),
                channel="telegram",
                device="mobile",
                preferred_payment="cod",
                persona="window_shopper",
                response_type="lost_cause",
            )
        )
        s.flush()
        for i in range(12):
            s.add(
                EventRow(
                    id=f"EDGE-V{i}",
                    customer_id="TG2",
                    type="view",
                    ts=NOW - timedelta(days=i + 1),
                    category="electronics",
                    item="Noise Smartwatch",
                    value=2999,
                )
            )
        s.commit()
    return eng


@pytest.fixture(autouse=True)
def use_engine(engine, monkeypatch):
    monkeypatch.setattr(db, "engine", engine)
    profile.reset_cache()
    config.set_time_override(NOW)
    yield
    config.set_time_override(None)


def _every_offer_type_scores(p) -> None:
    for offer_type in FAMILY:
        cost, profit = impact.estimate(p, offer_type, PARAMS, None)
        assert cost >= 0 and isinstance(profit, int), offer_type


def test_brand_new_telegram_user_with_no_rows_at_all():
    p = profile.build_profile("TG1", NOW)
    assert p.policy == "new_user" and p.rfm["segment"] == "New"
    assert p.rfm["orders_total"] == 0 and p.recency_days == 0 and p.aov == 0 and p.ltv == 0
    assert p.points_balance == 0 and p.open_cart is None and p.last_offer_at is None
    assert set(p.uplift) == set(FAMILY)
    _every_offer_type_scores(p)


def test_zero_orders_but_browsing_is_a_window_shopper():
    p = profile.build_profile("TG2", NOW)
    assert p.policy == "window_shopper" and p.rfm["views_90d"] == 12
    assert p.category_affinity == {"electronics": 1.0}
    _every_offer_type_scores(p)


def test_missing_age_is_fine(engine):
    with Session(engine) as s:
        cid = s.exec(select(CustomerRow.id).where(CustomerRow.age.is_(None))).first()
    assert cid is not None  # the generator leaves ~3% of ages empty on purpose
    _every_offer_type_scores(profile.build_profile(cid, NOW))


@pytest.mark.parametrize("when", [NOW - timedelta(days=30), datetime(2023, 1, 1, tzinfo=IST)])
def test_time_travel_before_signup_never_goes_negative(when):
    for cid in ("TG1", "C000001"):
        p = profile.build_profile(cid, when)
        assert p.recency_days >= 0 and p.rfm["days_since_active"] >= 0 and p.rfm["tenure_days"] >= 0
        _every_offer_type_scores(p)
