from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel

import app.models  # noqa: F401
from app import db, decision_store, main, ports
from app.config import IST, settings
from app.db import make_engine
from app.models import CustomerRow

NOW = datetime(2026, 10, 24, 12, 0, tzinfo=IST)
ADMIN = {"X-Admin-Passcode": "test-pass"}


@pytest.fixture
def client(monkeypatch, tmp_path):
    # a file DB: in-memory SQLite is per-connection, and the test client runs on another thread
    engine = make_engine(f"sqlite:///{tmp_path / 'api.db'}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(settings, "telegram_bot_token", "")
    monkeypatch.setattr(settings, "admin_passcode", "test-pass")
    with TestClient(main.app) as c:
        yield c


def _customer(cid: str, name: str) -> None:
    from datetime import date

    from sqlmodel import Session

    with Session(db.engine) as s:
        s.add(
            CustomerRow(
                id=cid,
                first_name=name,
                city="Ludhiana",
                city_tier=2,
                signup_date=date(2026, 1, 1),
                channel="organic",
                device="android",
                preferred_payment="upi",
                persona="deal_hunter",
                response_type="persuadable",
            )
        )
        s.commit()


def test_meta_and_killswitch_guard(client):
    assert client.get("/api/meta").json()["bot_username"] == "navpreet_offers_bot"
    assert client.get("/api/settings/killswitch").json()["on"] is False
    assert client.post("/api/settings/killswitch", json={"on": True}).status_code == 401
    assert client.post("/api/settings/killswitch", json={"on": True}, headers=ADMIN).json()["on"] is True
    assert client.get("/api/settings/killswitch").json()["on"] is True


def test_rules_seeded_edit_version_and_revert(client):
    rules = client.get("/api/rules").json()
    assert rules and {r["layer"] for r in rules} >= {"global", "persona"}
    target = next(r for r in rules if r["id"] == "G_BUDGET")
    assert client.patch("/api/rules/G_BUDGET", json={"params": {"daily_cap": 40000}}).status_code == 401
    edited = client.patch("/api/rules/G_BUDGET", json={"params": {"daily_cap": 40000}}, headers=ADMIN).json()
    assert edited["params"]["daily_cap"] == 40000 and edited["version"] == target["version"] + 1
    assert "40,000" in edited["description"]
    assert client.get("/api/budget").json()["today_cap"] == 40000
    versions = client.get("/api/rules/G_BUDGET/versions").json()
    assert [v["version"] for v in versions] == [target["version"] + 1, target["version"]]
    reverted = client.post(f"/api/rules/G_BUDGET/revert/{target['version']}", headers=ADMIN).json()
    assert reverted["params"]["daily_cap"] == target["params"]["daily_cap"]


def test_offers_and_festivals(client):
    offers = client.get("/api/offers").json()
    assert any(o["id"] == "OF_FREE_SHIP" for o in offers)
    assert client.get("/api/festivals").json()


def test_decisions_list_detail_and_filters(client):
    for cid, trig in [("C000001", "cart_abandoned"), ("C000003", "browse_interest"), ("C000002", "manual")]:
        decision_store.save(ports.decide(cid, trig, now=NOW))
    body = client.get("/api/decisions").json()
    assert len(body["items"]) == 3 and body["next"] is None
    assert [d["status"] for d in client.get("/api/decisions?status=BLOCKED").json()["items"]] == ["BLOCKED"]
    one = body["items"][0]["id"]
    assert client.get(f"/api/decisions/{one}").json()["explanation"]["title"]
    assert client.get("/api/decisions/nope").status_code == 404
    page = client.get("/api/decisions?limit=2").json()
    assert len(page["items"]) == 2 and page["next"]


def test_festival_filter_and_light_field(client):
    base = ports.decide("C000001", "cart_abandoned", now=NOW)
    diwali = base.model_copy(
        update={
            "id": "D-diwali",
            "context": base.context.model_copy(
                update={"festival": "diwali_2026", "festival_phase": "build_up"}
            ),
        }
    )
    decision_store.save(base)
    decision_store.save(diwali)
    for key in ("diwali", "diwali_2026"):
        items = client.get(f"/api/decisions?festival={key}").json()["items"]
        assert [d["id"] for d in items] == ["D-diwali"] and items[0]["festival"] == "diwali_2026"
    assert client.get("/api/decisions?festival=lohri").json()["items"] == []


def test_customers_playground_and_campaign(client):
    _customer("C000002", "Priya")
    listed = client.get("/api/customers").json()
    assert listed["items"][0]["customer_id"] == "C000002"
    detail = client.get("/api/customers/C000002").json()
    assert detail["profile"]["customer_id"] == "C000002" and detail["events"] == []
    run = client.post(
        "/api/playground/run", json={"customer_id": "C000001", "trigger": "cart_abandoned"}
    ).json()
    assert run["status"] == "DRY_RUN" and run["coupon_code"] is None
    assert decision_store.query() == []  # dry runs are never stored
    camp = client.post("/api/campaigns/dry-run", json={"budget": 100000, "limit": 5}).json()
    assert camp["totals"]["customers"] == 1
    assert client.post("/api/customers/C000002/simulate", json={"trigger": "manual"}).status_code == 401


def test_analytics(client):
    decision_store.save(ports.decide("C000001", "cart_abandoned"))
    k = client.get("/api/kpis").json()
    assert k["sent_today"] == 1 and 0 <= k["budget_used_pct"] <= 1
    # CR-D1: one delta per KPI tile, as a fractional change; None when yesterday had nothing
    assert set(k["deltas"]) == {
        "sent_today",
        "claim_rate",
        "incremental_revenue",
        "budget_used_pct",
        "blocked_by_rules",
        "margin_saved",
    }
    assert k["deltas"]["sent_today"] is None and k["deltas"]["incremental_revenue"] == 0.0
    assert client.get("/api/experiments").json()["treatment"]
    assert client.get("/api/realism").json()["benchmarks"]
    assert client.get("/api/digest").json()["text"]
