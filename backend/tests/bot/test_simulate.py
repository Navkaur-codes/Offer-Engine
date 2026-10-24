"""/simulate actions, rate limit, recorded buttons and /history (stub ports + in-memory DB)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from sqlmodel import Session, select

from app import decision_store, ports, stubs
from app.bot import commands, sender, simulate, store
from app.config import IST
from app.models import DecisionRow, EventRow, OrderRow, PointsLedgerRow, ProductRow

from .test_handlers import _onboard

CID = "TG55512345"


@pytest.fixture
async def member(chat):
    await _onboard(chat)  # likes fashion + beauty
    chat.sent.clear()
    return chat


def _events(engine, type_: str | None = None) -> list[EventRow]:
    with Session(engine) as s:
        q = select(EventRow).where(EventRow.customer_id == CID)
        if type_:
            q = q.where(EventRow.type == type_)
        return list(s.exec(q).all())


async def _sim(chat, *args):
    chat.user_data.pop("last_simulate", None)  # tests skip the 10 s wait
    await simulate.simulate_cmd(chat.message_update("/simulate " + " ".join(args)), chat.context(list(args)))


async def test_no_args_shows_button_menu(member):
    await simulate.simulate_cmd(member.message_update("/simulate"), member.context())
    kind, text, keyboard = member.sent[-1]
    assert "Simulation console" in text
    assert all(b.callback_data.startswith("sim:") for row in keyboard.inline_keyboard for b in row)


async def test_cart_writes_funnel_events_status_first_then_card(member, memory_db, monkeypatch):
    calls = []
    real = ports.decide
    monkeypatch.setattr(ports, "decide", lambda *a, **k: calls.append(a) or real(*a, **k))
    await _sim(member, "cart", "ethnic_wear")
    assert [e.type for e in sorted(_events(memory_db), key=lambda e: e.ts)] == [
        "session",
        "view",
        "add_to_cart",
    ]
    cart = _events(memory_db, "add_to_cart")[0]
    assert cart.category == "ethnic_wear" and cart.value > 0
    (_, status, _), (kind, card, _) = member.sent[-2], member.sent[-1]
    assert status.startswith("🧪 Simulated: added ") and "to cart, 35 min ago" in status and "₹" in status
    assert kind == "send" and "<b>" in card
    assert calls == [
        (
            CID,
            "cart_abandoned",
            {"category": "ethnic_wear", "item": cart.item, "value": cart.value, "minutes": 35},
        )
    ]


async def test_cart_uses_catalogue_products_when_seeded(member, memory_db):
    with Session(memory_db) as s:
        s.add(ProductRow(id="P900", name="Linen Shirt", category="fashion", price=1299, margin=0.5))
        s.commit()
    await _sim(member, "cart")  # no category → first onboarding pick (fashion)
    assert _events(memory_db, "add_to_cart")[0].item == "Linen Shirt"


async def test_purchase_closes_open_cart_and_makes_no_decision(member, memory_db, monkeypatch):
    await _sim(member, "cart", "beauty")
    item = _events(memory_db, "add_to_cart")[0].item
    monkeypatch.setattr(ports, "decide", lambda *a, **k: pytest.fail("purchase must not decide"))
    await _sim(member, "purchase")
    assert f"bought {item}" in member.last_text
    assert store.open_cart(CID) is None
    with Session(memory_db) as s:
        assert len(s.exec(select(OrderRow)).all()) == 1


async def test_purchase_then_cart_shows_no_offer_reason(member, monkeypatch):
    """Done-when wiring: whatever reason the harness gives (e.g. bought <48 h ago) reaches the user."""
    await _sim(member, "purchase")

    def harness(cid, trigger, meta, **kw):
        d = stubs.decide("C000003", trigger, meta)  # stub NO_OFFER fixture
        expl = d.explanation.model_copy(update={"telegram_text": "No offer: you bought something <48 h ago."})
        return d.model_copy(update={"customer_id": cid, "explanation": expl})

    monkeypatch.setattr(ports, "decide", harness)
    await _sim(member, "cart")
    assert "No offer right now" in member.last_text and "bought something &lt;48 h ago" in member.last_text


async def test_inactive_moves_history_back(member, memory_db, monkeypatch):
    seen = {}
    monkeypatch.setattr(
        ports, "decide", lambda cid, t, m, **k: seen.update(t=t, m=m) or stubs.decide(cid, t, m)
    )
    await _sim(member, "cart")
    await _sim(member, "inactive", "60")
    newest = max(e.ts for e in _events(memory_db))
    assert timedelta(days=59) < datetime.now() - newest < timedelta(days=61)  # SQLite: naive IST
    assert seen == {"t": "inactivity", "m": {"days": 60}}
    assert "no visits or orders for 60 days" in member.sent[-2][1]


async def test_points_expiry(member, memory_db):
    await _sim(member, "points_expiry")
    with Session(memory_db) as s:
        entry = s.exec(select(PointsLedgerRow)).one()
    assert entry.delta == 500 and entry.expires_on > date.today()
    assert store.get_customer(CID).points_balance >= 500


async def test_festival_by_name_and_phase(member, monkeypatch):
    seen = {}
    monkeypatch.setattr(
        ports, "decide", lambda cid, t, m, **k: seen.update(t=t, m=m) or stubs.decide(cid, t, m)
    )
    await _sim(member, "festival", "diwali", "last_minute")
    assert seen["t"] == "festival" and seen["m"]["festival"].startswith("diwali_")
    assert seen["m"]["phase"] == "last_minute"
    assert "season, last minute phase" in member.sent[-2][1]


def test_find_festival_prefers_nearest_upcoming():
    fests = [
        f.model_copy(update={"id": "diwali_2025", "date": date(2025, 10, 20)}) for f in stubs.FESTIVALS[1:]
    ]
    fests += stubs.FESTIVALS
    found = simulate.find_festival(fests, "Diwali", date(2026, 10, 24))
    assert found.id == "diwali_2026"
    assert simulate.find_festival(fests, None, date(2026, 10, 24)).id == "karwa_chauth_2026"
    assert simulate.festival_phase(stubs.FESTIVALS[1], date(2026, 11, 3)) == "build_up"


async def test_payday_and_persona(member):
    await _sim(member, "persona", "deal_hunter")
    assert store.get_customer(CID).persona == "deal_hunter" and "Deal hunter" in member.last_text
    await _sim(member, "persona", "wizard")
    assert "Options:" in member.last_text and store.get_customer(CID).persona == "deal_hunter"
    await _sim(member, "payday")
    assert "payday" in member.sent[-2][1]


async def test_unknown_category_and_action(member):
    await _sim(member, "browse", "spaceships")
    assert member.last_text == simulate.USAGE["browse"]
    await _sim(member, "teleport")
    assert "Try /simulate" in member.last_text


async def test_requires_onboarding(chat):
    await _sim(chat, "cart")
    assert chat.last_text == commands.NOT_REGISTERED


async def test_rate_limit(member):
    ud: dict = {}
    assert simulate.check_rate_limit(ud, clock=100.0) == 0
    assert simulate.check_rate_limit(ud, clock=104.2) == 6
    assert simulate.check_rate_limit(ud, clock=110.0) == 0
    member.user_data.pop("last_simulate", None)
    await simulate.simulate_cmd(member.message_update(), member.context(["payday"]))
    await simulate.simulate_cmd(member.message_update(), member.context(["payday"]))
    assert member.last_text.startswith("⏳ One simulation at a time")


async def test_menu_button_runs_action(member, memory_db):
    member.user_data.pop("last_simulate", None)
    await simulate.on_menu_button(member.button_update("sim:browse"), member.context())
    assert len(_events(memory_db, "view")) == 3


# ---------------------------------------------------------------- recorded buttons
async def _card(member, memory_db, log=True):
    await _sim(member, "cart", "fashion")
    decision_id = member.sent[-1][2].inline_keyboard[0][0].callback_data.split(":", 2)[2]
    decision = sender.recent(decision_id)
    if log:
        decision_store.save(decision)  # what the real harness does
    return decision


async def test_claim_records_event_and_outcome_once(member, memory_db):
    d = await _card(member, memory_db)
    ctx = member.context()
    await commands.on_offer_button(member.button_update(f"o:claim:{d.id}"), ctx)
    assert member.last_text.startswith("✅ Saved! Use code")
    claimed = _events(memory_db, "offer_claimed")
    assert len(claimed) == 1 and claimed[0].meta["decision_id"] == d.id
    with Session(memory_db) as s:
        row = s.get(DecisionRow, d.id)
        assert row.outcome == "claimed" and row.payload["outcome"] == "claimed"
    update = member.button_update(f"o:claim:{d.id}")
    await commands.on_offer_button(update, ctx)
    assert "Already handled" in update.callback_query.answer.call_args.args[0]
    assert len(_events(memory_db, "offer_claimed")) == 1


async def test_decline_suppresses_category_14_days(member, memory_db):
    d = await _card(member, memory_db, log=False)  # stub phase: no decision row, still recorded
    update = member.button_update(f"o:decline:{d.id}")
    await commands.on_offer_button(update, member.context())
    assert "No Fashion offers for 14 days" in update.callback_query.answer.call_args.args[0]
    until = datetime.fromisoformat(store.get_customer(CID).suppressed["fashion"])
    assert timedelta(days=13) < until - datetime.now(IST) <= timedelta(days=14)
    assert len(_events(memory_db, "offer_declined")) == 1


async def test_remind_records_outcome_and_schedules_once(member, memory_db):
    d = await _card(member, memory_db)
    ctx = member.context()
    await commands.on_offer_button(member.button_update(f"o:remind:{d.id}"), ctx)
    ctx.job_queue.run_once.assert_called_once()
    when = ctx.job_queue.run_once.call_args.args[1]
    assert (when.hour, when.minute) == (19, 0)
    with Session(memory_db) as s:
        assert s.get(DecisionRow, d.id).outcome == "remind_later"
    await commands.on_offer_button(member.button_update(f"o:claim:{d.id}"), ctx)  # remind isn't final
    assert member.last_text.startswith("✅ Saved!")


async def test_history_lists_all_statuses(member, memory_db, monkeypatch):
    await _sim(member, "cart")
    later = datetime.now(IST) + timedelta(seconds=5)  # stub ids are per-second; the real harness's aren't
    monkeypatch.setattr(ports, "decide", lambda cid, t, m, **k: stubs.decide(cid, "manual", m, now=later))
    await _sim(member, "payday")
    await commands.history_cmd(member.message_update("/history"), member.context())
    text = member.last_text
    assert text.startswith("<b>Your last decisions</b>")
    assert "✅" in text and "✗" in text and "cart abandoned" in text


def test_history_hides_holdout():
    d = stubs.decide("C000001", "welcome").model_copy(update={"status": "HELD_OUT"})
    d = d.model_copy(update={"explanation": d.explanation.model_copy(update={"title": "Held out (control)"})})
    assert "Held out" not in commands.history_line(d)
