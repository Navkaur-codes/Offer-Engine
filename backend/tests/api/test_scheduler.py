from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel

import app.models as m
from app import config, db, decision_store, main, ports, stubs
from app.config import IST, settings
from app.db import make_engine
from app.scheduler import jobs

NOW = datetime(2026, 10, 25, 14, 0, tzinfo=IST)


@pytest.fixture
def env(monkeypatch, tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'sched.db'}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db, "engine", engine)
    config.set_time_override(NOW)
    delivered = []

    def decide_and_store(cid, trigger, meta=None, **kw):
        d = stubs.decide(cid, trigger, meta, now=config.now())
        decision_store.save(d)
        return d

    monkeypatch.setattr(ports, "decide", decide_and_store)
    monkeypatch.setattr(ports, "deliver", lambda d, ch: delivered.append((d.customer_id, d.trigger)))
    yield delivered
    config.set_time_override(None)


def _customer(cid: str, chat: int | None) -> None:
    with Session(db.engine) as s:
        s.add(
            m.CustomerRow(
                id=cid,
                first_name="Navpreet",
                city="Ludhiana",
                city_tier=2,
                signup_date=date(2026, 1, 1),
                channel="telegram",
                device="mobile",
                preferred_payment="upi",
                persona="cart_abandoner",
                response_type="persuadable",
                telegram_chat_id=chat,
            )
        )
        s.commit()


def _event(eid: str, cid: str, kind: str, minutes_ago: int) -> None:
    with Session(db.engine) as s:
        s.add(
            m.EventRow(
                id=eid,
                customer_id=cid,
                type=kind,
                ts=NOW - timedelta(minutes=minutes_ago),
                category="fashion",
                item="Cotton Kurta",
                value=1450,
            )
        )
        s.commit()


def test_abandoned_cart_is_nudged_once(env):
    _customer("TG7123456789", 7123456789)
    _event("E1", "TG7123456789", "add_to_cart", 40)
    first = jobs.cart_abandonment()
    assert [d.trigger_meta["source"] for d in first] == ["scheduler"]
    assert first[0].trigger_meta["minutes"] == 40 and env == [("TG7123456789", "cart_abandoned")]
    assert jobs.cart_abandonment() == []  # already nudged after this cart


@pytest.mark.parametrize("minutes_ago,then", [(10, None), (40, "purchase"), (400, None)])
def test_fresh_bought_or_old_carts_are_left_alone(env, minutes_ago, then):
    _customer("TG1", 1)
    _event("E1", "TG1", "add_to_cart", minutes_ago)
    if then:
        _event("E2", "TG1", then, 5)
    assert jobs.cart_abandonment() == []


def test_synthetic_customers_are_never_nudged(env):
    _customer("C000001", None)
    _event("E1", "C000001", "add_to_cart", 40)
    assert jobs.cart_abandonment() == [] and env == []


def test_quiet_queue_is_rerun_exactly_once(env):
    held = stubs.decide("C000001", "campaign", {}, now=NOW - timedelta(hours=8))
    decision_store.save(held.model_copy(update={"status": "QUEUED"}))
    rerun = jobs.flush_quiet_queue()
    assert len(rerun) == 1 and rerun[0].trigger_meta["requeued_from"] == held.id
    assert jobs.flush_quiet_queue() == []


def test_points_expiry_only_when_points_expire_soon(env, monkeypatch):
    _customer("TG2", 2)
    base = stubs.PROFILES["C000001"].model_copy(update={"customer_id": "TG2"})
    monkeypatch.setattr(ports, "build_profile", lambda cid, at: base)
    assert jobs.points_expiry() == []
    soon = base.model_copy(
        update={"points_expiring": 300, "points_expiry_date": NOW.date() + timedelta(days=2)}
    )
    monkeypatch.setattr(ports, "build_profile", lambda cid, at: soon)
    assert [d.trigger for d in jobs.points_expiry()] == ["points_expiry"]
    assert jobs.points_expiry() == []  # once per 3 days


def test_scheduler_api(env, monkeypatch):
    monkeypatch.setattr(settings, "telegram_bot_token", "")
    monkeypatch.setattr(settings, "admin_passcode", "pw")
    with TestClient(main.app) as c:
        assert c.get("/api/scheduler").json()["running"] is False  # no bot, no scheduler
        assert c.post("/api/scheduler/run/cart_abandonment").status_code == 401
        body = c.post("/api/scheduler/run/cart_abandonment", headers={"X-Admin-Passcode": "pw"}).json()
        assert body == {"job": "cart_abandonment", "decisions": 0, "sent": 0, "queued": 0}
        assert c.post("/api/scheduler/run/nope", headers={"X-Admin-Passcode": "pw"}).status_code == 404
