from datetime import date, datetime

from sqlmodel import Session, SQLModel, select

import app.models as m
from app import config
from app.db import _normalise_url, make_engine


def test_now_is_ist_and_overridable():
    assert config.now().utcoffset().total_seconds() == 5.5 * 3600
    config.set_time_override("2026-11-06")
    try:
        assert config.now().date() == date(2026, 11, 6)
    finally:
        config.set_time_override(None)
    assert config.time_override() is None or config.settings.demo_time_override


def test_blank_env_values_mean_unset(monkeypatch):
    monkeypatch.setenv("LAB_GROUP_CHAT_ID", "")
    s = config.Settings(_env_file=None)
    assert s.lab_group_chat_id is None


def test_httpx_logs_are_quiet():
    import logging

    import app.main  # noqa: F401

    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING


def test_neon_url_gets_psycopg_driver():
    assert _normalise_url("postgresql://u:p@h/db").startswith("postgresql+psycopg://")
    assert _normalise_url("sqlite:///x.db") == "sqlite:///x.db"


def test_tables_create_and_roundtrip():
    engine = make_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(
            m.CustomerRow(
                id="C1",
                first_name="Priya",
                city="Ludhiana",
                city_tier=2,
                signup_date=date(2026, 1, 5),
                channel="organic",
                device="android",
                preferred_payment="upi",
                persona="deal_hunter",
                response_type="persuadable",
                opt_in_festivals=["diwali"],
            )
        )
        s.add(m.SettingRow(key="killswitch", value={"on": False}, updated_at=datetime(2026, 10, 22)))
        s.commit()
        row = s.exec(select(m.CustomerRow)).one()
        assert row.opt_in_festivals == ["diwali"]


def test_telegram_ids_are_bigint():
    """Telegram ids pass 2^31; Postgres INTEGER would raise DataError at the end of onboarding."""
    from sqlalchemy import BigInteger

    assert isinstance(m.CustomerRow.__table__.c.telegram_chat_id.type, BigInteger)
    assert isinstance(m.DecisionRow.__table__.c.telegram_message_id.type, BigInteger)
    engine = make_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(
            m.CustomerRow(
                id="TG7123456789",
                first_name="Navpreet",
                city="Ludhiana",
                city_tier=2,
                signup_date=date(2026, 10, 24),
                channel="telegram",
                device="mobile",
                preferred_payment="upi",
                persona="new_user",
                response_type="persuadable",
                telegram_chat_id=7_123_456_789,
            )
        )
        s.commit()
        assert s.get(m.CustomerRow, "TG7123456789").telegram_chat_id == 7_123_456_789
