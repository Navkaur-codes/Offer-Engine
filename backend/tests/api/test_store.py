from datetime import datetime

import pytest
from sqlmodel import SQLModel

import app.models  # noqa: F401
from app import db, decision_store, ports, runtime
from app.config import IST
from app.db import make_engine

NOW = datetime(2026, 10, 24, 12, 0, tzinfo=IST)


@pytest.fixture(autouse=True)
def fresh_db(monkeypatch):
    engine = make_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db, "engine", engine)


def test_save_get_and_query():
    d = ports.decide("C000001", "cart_abandoned", now=NOW)
    decision_store.save(d)
    assert decision_store.get(d.id) == d
    assert [x.id for x in decision_store.query(status="SENT")] == [d.id]
    assert decision_store.query(status="BLOCKED") == []
    assert decision_store.spent_on(NOW.date()) == d.cost


def test_dry_runs_are_not_stored():
    d = ports.decide("C000004", "inactivity", dry_run=True, now=NOW)
    decision_store.save(d)
    assert decision_store.get(d.id) is None


def test_outcome_updates_row_and_payload():
    d = ports.decide("C000001", "cart_abandoned", now=NOW)
    decision_store.save(d)
    assert decision_store.set_outcome(d.id, "claimed", NOW, revenue=1450)
    got = decision_store.get(d.id)
    assert got.outcome == "claimed" and got.revenue == 1450
    assert decision_store.set_outcome("missing", "claimed", NOW) is False


def test_lab_group_saved_by_lab_here():
    assert runtime.lab_group_chat_id() is None
    runtime.set_lab_group(-1001234567890, "Customer Lab")
    assert runtime.lab_group_chat_id() == -1001234567890


def test_quiet_hours_only_for_proactive_triggers():
    assert runtime.quiet_hours_apply("campaign", {}) is True
    assert runtime.quiet_hours_apply("cart_abandoned", None) is True
    assert runtime.quiet_hours_apply("cart_abandoned", {"initiated_by": "customer"}) is False
    assert runtime.quiet_hours_apply("manual", {"initiated_by": "admin"}) is False
    assert runtime.quiet_hours_apply("lab", {}) is False


def test_killswitch_roundtrip():
    assert runtime.killswitch_on() is False
    runtime.set_killswitch(True)
    assert runtime.killswitch_on() is True
    runtime.set_killswitch(False)
    assert runtime.killswitch_on() is False
