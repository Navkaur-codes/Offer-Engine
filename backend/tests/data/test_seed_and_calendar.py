from __future__ import annotations

from datetime import date

from sqlmodel import Session, func, select

from app.data.catalog import CATEGORIES, PRODUCTS
from app.data.festivals import FESTIVALS, OPT_IN_KEYS, festival_key, lifts, phase_on
from app.data.generator import DEFAULT_END
from app.data.personas import PERSONAS
from app.data.seed import run
from app.db import make_engine
from app.models import (
    CampaignHistoryRow,
    CustomerRow,
    EventRow,
    FestivalRow,
    OrderRow,
    PointsLedgerRow,
    ProductRow,
)


def _count(s: Session, model) -> int:
    return s.exec(select(func.count()).select_from(model)).one()


def test_seed_runs_from_scratch_and_reruns_cleanly(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'seed.db'}")
    run(200, 1, end=DEFAULT_END, engine=engine)
    with Session(engine) as s:
        counts = {
            m.__tablename__: _count(s, m)
            for m in (
                CustomerRow,
                ProductRow,
                EventRow,
                OrderRow,
                PointsLedgerRow,
                CampaignHistoryRow,
                FestivalRow,
            )
        }
        s.add(
            CustomerRow(
                id="TG42",
                first_name="Real",
                city="Ludhiana",
                city_tier=2,
                signup_date=date(2026, 10, 24),
                channel="telegram",
                device="mobile",
                preferred_payment="upi",
                persona="new_user",
                response_type="persuadable",
            )
        )
        s.commit()
    assert counts["customers"] == 200 and counts["products"] == len(PRODUCTS)
    assert counts["events"] > counts["orders"] > 0 and counts["campaign_history"] > 0
    assert counts["festivals"] == len(FESTIVALS)

    run(200, 1, end=DEFAULT_END, engine=engine)
    with Session(engine) as s:
        assert _count(s, CustomerRow) == 201  # the real Telegram user survives a re-seed
        assert _count(s, EventRow) == counts["events"]
        purchase = s.exec(select(EventRow).where(EventRow.type == "purchase")).first()
        assert purchase.meta["order_id"].startswith("O")


def test_festival_dates_verified_for_2026():
    by_id = {f.id: f for f in FESTIVALS}
    assert by_id["karwa_chauth_2026"].date == date(2026, 10, 29)
    assert by_id["dhanteras_2026"].date == date(2026, 11, 6)
    assert by_id["diwali_2026"].date == date(2026, 11, 8)
    assert by_id["bhai_dooj_2026"].date == date(2026, 11, 11)
    assert by_id["gurpurab_2026"].date == date(2026, 11, 24)
    assert by_id["diwali_2025"].date == date(2025, 10, 20)


def test_festival_rows_are_complete_and_safe():
    assert min(f.date for f in FESTIVALS) <= date(2025, 10, 31) and max(f.date for f in FESTIVALS) >= date(
        2027, 1, 1
    )
    for f in FESTIVALS:
        assert f.hero_categories and set(f.hero_categories) <= set(CATEGORIES)
        assert set(f.phases) == {"teaser", "build_up", "last_minute", "post"}
        assert f.budget > 0 and set(f.delivery_days_by_tier) == {1, 2, 3}
        assert f.needs_opt_in == (f.greeting is not None)  # every greeting needs an opt-in
        assert set(lifts(f)) == set(f.phases)
    gurpurab = next(f for f in FESTIVALS if f.id == "gurpurab_2026")
    assert "alcohol" in gurpurab.restricted_promos and "meat" in gurpurab.restricted_promos
    assert phase_on(gurpurab, date(2026, 11, 23)) == "last_minute"
    assert festival_key("karwa_chauth_2026") == "karwa_chauth" and "diwali" in OPT_IN_KEYS


def test_personas_and_catalogue():
    assert len(PERSONAS) == 9
    for p in PERSONAS.values():
        assert abs(sum(p.response_mix.values()) - 1) < 1e-9
        assert abs(sum(p.category_weights().values()) - 1) < 1e-9
    assert PERSONAS["deal_hunter"].response_mix["persuadable"] == 0.50
    assert len(CATEGORIES) == 10 and 100 <= len(PRODUCTS) <= 140
    assert CATEGORIES["electronics"].margin < CATEGORIES["grocery"].margin < CATEGORIES["fashion"].margin
    assert len({p.id for p in PRODUCTS}) == len(PRODUCTS)
