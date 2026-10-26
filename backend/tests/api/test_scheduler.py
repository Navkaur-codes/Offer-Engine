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


def _customer(cid: str, chat: int | None, lab: bool = False) -> None:
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
                is_lab_bot=lab,
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


@pytest.fixture
def picks(env, monkeypatch):
    """Telegram, Lab and plain synthetic customers; decide_batch records what it was asked."""
    _customer("TG3", 3)
    _customer("C900002", None, lab=True)
    _customer("C000001", None)
    affinity = {"fashion": 0.6, "beauty": 0.4}
    profile = stubs.PROFILES["C000001"].model_copy(update={"category_affinity": affinity})
    monkeypatch.setattr(ports, "build_profile", lambda cid, at: profile)
    calls = []

    def batch(items, **kw):
        calls.append((items, kw))
        return [
            ports.decide(cid, trigger, meta).model_copy(
                update={"channel": "lab_group" if trigger == "lab" else "dm"}
            )
            for cid, trigger, meta in items
        ]

    monkeypatch.setattr(ports, "decide_batch", batch)
    return calls


def test_personal_picks_cover_telegram_and_lab_customers_only(env, picks):
    decisions = jobs.personal_picks()
    items, kw = picks[0]
    assert [(cid, trigger) for cid, trigger, _ in items] == [("TG3", "campaign"), ("C900002", "lab")]
    assert kw == {"dry_run": False, "agent_top_n": 5}  # one batch: the agent only for the top 5 (T26)
    assert items[0][2] == {
        "campaign": "personal_picks", "source": "scheduler", "category": "fashion", "category_share": 0.6
    }
    assert "initiated_by" not in items[0][2]  # proactive: quiet hours still hold DMs to real people
    assert env == [("TG3", "campaign")]  # only Telegram gets a DM; the runner posts the Lab pick
    assert len(decisions) == 2


def test_personal_picks_run_report_and_lab_post(env, picks, monkeypatch):
    posted = []
    monkeypatch.setattr(
        ports, "post_lab_picks", lambda ds: posted.append([d.customer_id for d in ds]) or len(ds)
    )
    monkeypatch.setattr(settings, "telegram_bot_token", "")
    monkeypatch.setattr(settings, "admin_passcode", "pw")
    with TestClient(main.app) as c:
        body = c.post("/api/scheduler/run/personal_picks", headers={"X-Admin-Passcode": "pw"}).json()
    assert body["job"] == "personal_picks" and body["decisions"] == 2 and body["lab_posting"] == 1
    rows = {r["customer_id"]: r for r in body["rows"]}
    assert rows["TG3"]["where"] == "telegram" and rows["C900002"]["where"] == "lab"
    assert rows["TG3"]["category"] == "fashion" and rows["TG3"]["title"]
    assert body["spent"] == sum(r["cost"] for r in body["rows"] if r["status"] == "SENT")
    assert posted == [["C900002"]]


def test_personal_picks_with_nobody_to_pick(env, monkeypatch):
    monkeypatch.setattr(ports, "decide_batch", lambda *a, **k: pytest.fail("no customers, no batch"))
    assert jobs.personal_picks() == []


def test_today_numbers_follow_the_decision_log(env):
    sent = stubs.decide("C000001", "campaign", {}, now=NOW)
    skipped = stubs.decide("C000003", "campaign", {}, now=NOW)  # stub VIP: NO_OFFER
    assert sent.status == "SENT" and skipped.status == "NO_OFFER"
    decision_store.save(sent)
    decision_store.save(skipped)
    with TestClient(main.app) as c:
        today = c.get("/api/today").json()
    assert today["sent"] == 1 and today["spent"] == sent.cost and today["no_offer"] == 1
    assert today["margin_kept"] == max((x.est_cost for x in skipped.candidates), default=0)
    assert today["decisions"] == 2
