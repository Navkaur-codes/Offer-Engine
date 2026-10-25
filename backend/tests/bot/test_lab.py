"""Customer Lab: registry, rotation, rounds with fake bots, and the /lab group commands."""

from __future__ import annotations

from collections import Counter
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlmodel import Session, func, select

from app import config, ports, runtime, stubs
from app.config import settings
from app.lab import commands as lab
from app.lab import registry, runner
from app.models import CustomerRow, EventRow, OrderRow

GROUP = -100777
ADMIN = 55512345


class FakeBot:
    """Records every message across all bots in one shared log."""

    def __init__(self, username: str, log: list, chat_type: str = "supergroup"):
        self.username, self.log, self.chat_type = username, log, chat_type

    async def get_chat(self, chat_id):
        return SimpleNamespace(type=self.chat_type)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def send_message(self, chat_id, text, parse_mode=None, reply_parameters=None, **kw):
        message_id = len(self.log) + 1
        reply_to = reply_parameters.message_id if reply_parameters else None
        self.log.append(
            SimpleNamespace(bot=self.username, chat=chat_id, text=text, reply_to=reply_to, id=message_id)
        )
        return SimpleNamespace(message_id=message_id)


@pytest.fixture
def four_bots(monkeypatch):
    monkeypatch.setattr(
        settings, "customer_bot_tokens", '[{"token":"t1"},{"token":"t2"},{"token":"t3"},{"token":"t4"}]'
    )
    log: list = []
    factory = {f"t{i}": FakeBot(f"lab_shopper_{i}_bot", log) for i in range(1, 5)}
    return log, factory


async def _no_pause():
    return None


async def _run(log, factory, n, chat_type="supergroup"):
    offer = FakeBot("offer_bot", log, chat_type)
    return await runner.run_rounds_async(offer, GROUP, n, bot_factory=factory.__getitem__, pause=_no_pause)


# ---------------------------------------------------------------- registry
def test_ensure_lab_customers_is_idempotent(memory_db):
    assert registry.ensure_lab_customers() == 10
    assert registry.ensure_lab_customers() == 0
    with Session(memory_db) as s:
        rows = s.exec(select(CustomerRow).where(CustomerRow.id.like("C9000%"))).all()
        assert len(rows) == 10 and all(r.is_lab_bot and not r.is_holdout for r in rows)
        arjun_orders = s.exec(
            select(func.count()).select_from(OrderRow).where(OrderRow.customer_id == "C900001")
        ).one()
    assert arjun_orders == 10
    assert {r.id: r.opt_in_festivals for r in rows}["C900010"] == ["diwali", "karwa_chauth"]
    assert registry.ensure_lab_customers(force=True) == 10


def test_ensure_repairs_wiped_history(memory_db):
    registry.ensure_lab_customers()
    with Session(memory_db) as s:  # what a re-seed does to C… history
        for row in s.exec(select(OrderRow).where(OrderRow.customer_id == "C900002")).all():
            s.delete(row)
        s.commit()
    assert registry.ensure_lab_customers() == 1


def test_round_robin_voices_any_bot_count():
    for n, expected in ((4, [3, 3, 2, 2]), (1, [10]), (10, [1] * 10), (3, [4, 3, 3])):
        counts = Counter(registry.voice_index(c, n) for c in registry.LAB_CUSTOMERS)
        assert [counts[i] for i in range(n)] == expected


def test_tokens_accept_old_format_and_skip_blanks(monkeypatch):
    monkeypatch.setattr(
        settings,
        "customer_bot_tokens",
        '[{"token":"a","customer_id":"C1","persona":"vip"},{"persona":"x"},{"token":"b"}]',
    )
    assert registry.tokens() == ["a", "b"]


def test_find_by_name_or_id():
    assert registry.find("priya").id == "C900002" and registry.find("C900009").name == "Karan"
    assert registry.find("nobody") is None


# ---------------------------------------------------------------- rotation
def test_rotation_plays_all_ten_before_repeating():
    first = [c.id for c, _ in runner.next_customers(10)]
    assert len(set(first)) == 10
    assert runner.next_customers(1)[0][0].id == first[0]


def test_queued_customer_goes_first():
    runner.next_customers(2)
    runner.queue_next("C900009")
    picked = [c.id for c, _ in runner.next_customers(2)]
    assert picked == ["C900009", "C900003"]


# ---------------------------------------------------------------- rounds
async def test_rounds_post_reply_and_react(four_bots, memory_db):
    log, factory = four_bots
    decisions = await _run(log, factory, 3)
    assert [d.customer_id for d in decisions] == ["C900001", "C900002", "C900003"]
    posts = [m for m in log if m.bot.startswith("lab_shopper")]
    assert posts[0].text.startswith("👤 <b>Arjun</b> · VIP\n") and posts[0].bot == "lab_shopper_1_bot"
    assert any(
        m.text.startswith("👤 <b>Priya</b> · Deal hunter") and m.bot == "lab_shopper_2_bot" for m in posts
    )
    offers = [m for m in log if m.bot == "offer_bot"]
    assert offers[0].reply_to == posts[0].id and "<b>For Arjun</b>" in offers[0].text
    assert all("/stop" not in m.text for m in offers)  # customer footer is not for the group
    reactions = [m for m in posts if m.reply_to]
    assert reactions and all(m.text.startswith("<b>") for m in reactions)
    with Session(memory_db) as s:
        voice = s.get(CustomerRow, "C900005").attrs["lab_voice"]
        lab_events = s.exec(
            select(EventRow).where(EventRow.customer_id == "C900002", EventRow.ts >= decisions[0].ts)
        ).all()
    assert voice == "lab_shopper_1_bot"  # customer 5 → bot 5 mod 4 = bot 1
    assert lab_events


async def test_no_offer_round_says_margin_protected(four_bots, monkeypatch):
    log, factory = four_bots

    def decide(cid, trigger, meta, **kw):
        d = stubs.decide("C000003", trigger, meta)  # stub NO_OFFER (VIP)
        return d.model_copy(update={"customer_id": cid})

    monkeypatch.setattr(ports, "decide", decide)
    await _run(log, factory, 1)
    reply = next(m for m in log if m.bot == "offer_bot")
    assert reply.text.startswith("➖ <b>No offer for Arjun</b>")
    assert len(log) == 2  # no customer reaction to "no offer"


async def test_claim_is_recorded(four_bots, memory_db, monkeypatch):
    log, factory = four_bots
    monkeypatch.setattr(runner, "react", lambda d, c: "claim")
    decisions = await _run(log, factory, 1)
    with Session(memory_db) as s:
        claimed = s.exec(select(EventRow).where(EventRow.type == "offer_claimed")).all()
    assert len(claimed) == 1 and claimed[0].meta["decision_id"] == decisions[0].id
    assert "Claimed ✅ (was going to buy it anyway" in log[-1].text  # Arjun is a sure thing


async def test_why_reaction_gets_explanation(four_bots, monkeypatch):
    log, factory = four_bots
    monkeypatch.setattr(runner, "react", lambda d, c: "why")
    await _run(log, factory, 1)
    assert log[-1].bot == "offer_bot" and "Why you got this" in log[-1].text


async def test_no_bots_configured(monkeypatch):
    monkeypatch.setattr(settings, "customer_bot_tokens", "[]")
    with pytest.raises(runner.LabError, match="No Lab Shopper bots"):
        await runner.run_rounds_async(FakeBot("offer", []), GROUP, 1, pause=_no_pause)


def test_reactions_follow_hidden_response_type():
    d = stubs.decide("C000001", "lab")
    meera = registry.find("Meera")
    picks = Counter(runner.react(d.model_copy(update={"id": f"D{i}"}), meera) for i in range(300))
    assert picks["decline"] > picks["claim"] * 3


# ---------------------------------------------------------------- /lab commands
def _update(text: str, user_id: int = ADMIN, reply_to: int | None = None):
    sent: list[str] = []

    async def reply_text(t, **kw):
        sent.append(t)

    message = SimpleNamespace(
        reply_text=reply_text, reply_to_message=SimpleNamespace(message_id=reply_to) if reply_to else None
    )
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        effective_chat=SimpleNamespace(id=GROUP, title="Customer Lab"),
        effective_message=message,
    )
    args = text.split()[1:]
    context = SimpleNamespace(args=args, bot=MagicMock(), application=MagicMock())
    return update, context, sent


@pytest.fixture
def admin(monkeypatch):
    monkeypatch.setattr(settings, "admin_telegram_ids", str(ADMIN))


async def test_lab_is_admin_only(admin):
    update, context, sent = _update("/lab here", user_id=1)
    await lab.lab_cmd(update, context)
    assert sent == ["Only Lab admins can run /lab."] and runtime.lab_group_chat_id() is None


async def test_lab_here_then_run(admin, four_bots):
    update, context, sent = _update("/lab run 2")
    await lab.lab_cmd(update, context)
    assert sent[-1] == "Type /lab here first."
    update, context, sent = _update("/lab here")
    await lab.lab_cmd(update, context)
    assert sent[-1] == "✅ This group is now the Customer Lab" and runtime.lab_group_chat_id() == GROUP
    update, context, sent = _update("/lab run 2")
    await lab.lab_cmd(update, context)
    assert sent[-1] == "▶️ Running 2 Lab rounds…"
    context.application.create_task.assert_called_once()
    context.application.create_task.call_args.args[0].close()  # not awaited in this unit test


async def test_lab_who_lists_ten(admin, four_bots):
    update, context, sent = _update("/lab who")
    await lab.lab_cmd(update, context)
    lines = sent[-1].splitlines()
    assert "4 Lab Shopper bots" in lines[0] and len(lines) == 11
    assert lines[1] == "👤 <b>Arjun</b> · VIP → Lab Shopper 1"


async def test_lab_persona_queues_customer(admin, memory_db):
    update, context, sent = _update("/lab persona Karan cart")
    await lab.lab_cmd(update, context)
    assert "Karan left" in sent[-1]
    assert runner.next_customers(1)[0][0].name == "Karan"
    update, context, sent = _update("/lab persona Karan dance")
    await lab.lab_cmd(update, context)
    assert sent[-1].startswith("Usage:")


async def test_lab_date_and_reset(admin):
    try:
        update, context, sent = _update("/lab date 2026-11-06")
        await lab.lab_cmd(update, context)
        assert config.now().date().isoformat() == "2026-11-06" and "06 Nov 2026" in sent[-1]
        update, context, sent = _update("/lab reset")
        await lab.lab_cmd(update, context)
        assert sent[-1].startswith("🔄 Rebuilt 10 Lab customers")
    finally:
        config.set_time_override(None)


async def test_reply_why_in_group(four_bots):
    log, factory = four_bots
    await _run(log, factory, 1)
    offer_msg = next(m for m in log if m.bot == "offer_bot")
    update, context, sent = _update("/why", reply_to=offer_msg.id)
    await lab.why_in_group(update, context)
    assert "Why you got this" in sent[-1]
    update, context, sent = _update("/why")
    await lab.why_in_group(update, context)
    assert sent[-1].startswith("Reply /why")


async def test_voices_written_as_customer_bot_rows(four_bots, memory_db):
    log, factory = four_bots
    await _run(log, factory, 1)
    await _run(log, factory, 1)  # second run upserts, no duplicate-key error
    from app.models import CustomerBotRow

    with Session(memory_db) as s:
        rows = {r.customer_id: r for r in s.exec(select(CustomerBotRow)).all()}
    assert len(rows) == 10
    assert rows["C900005"].username == "lab_shopper_1_bot" and rows["C900002"].persona == "deal_hunter"


async def test_big_runs_use_one_decide_batch(four_bots, monkeypatch):
    log, factory = four_bots
    calls = []
    real = ports.decide_batch

    def batch(items, **kw):
        calls.append(items)
        return real(items, **kw)

    monkeypatch.setattr(ports, "decide", lambda *a, **k: pytest.fail("big runs must not decide one by one"))
    monkeypatch.setattr(ports, "decide_batch", batch)
    decisions = await _run(log, factory, 7)
    assert len(calls) == 1 and len(calls[0]) == 7 and all(t == "lab" for _, t, _ in calls[0])
    assert [d.customer_id for d in decisions] == [c.id for c in registry.LAB_CUSTOMERS[:7]]
    assert sum(m.text.startswith("👤") for m in log) == 7


async def test_basic_group_never_reply_links_across_bots(four_bots, monkeypatch):
    """Basic groups number messages per bot, so a cross-bot reply would land on an unrelated message."""
    log, factory = four_bots
    monkeypatch.setattr(runner, "react", lambda d, c: "why")
    await _run(log, factory, 2, chat_type="group")
    assert all(m.reply_to is None for m in log)
    offers = [m for m in log if m.bot == "offer_bot"]
    assert offers[0].text.startswith("📨 <b>For Arjun</b>")
    update, context, sent = _update("/why", reply_to=offers[0].id)  # reply-/why still finds the decision
    await lab.why_in_group(update, context)
    assert "Why you got this" in sent[-1]


def test_meera_is_a_long_standing_full_price_regular():
    meera = registry.find("Meera")
    assert meera.response_type == "sleeping_dog" and len(meera.orders) == 9
    assert all(o.discount_pct == 0 and not o.returned for o in meera.orders)
    assert meera.orders[0].days_ago >= 14  # not a fresh buyer


async def test_lab_offer_reply_is_the_card_image(four_bots, monkeypatch):
    log, factory = four_bots
    photos = []

    async def send_photo(self, chat_id, photo, caption, **kw):
        photos.append(caption)
        return await self.send_message(chat_id, caption, **kw)

    monkeypatch.setattr(FakeBot, "send_photo", send_photo, raising=False)
    await _run(log, factory, 1)
    assert len(photos) == 1 and photos[0].startswith("📨 <b>For Arjun</b>")


def test_meera_has_declined_past_offers(memory_db):
    registry.ensure_lab_customers()
    with Session(memory_db) as s:
        types = [e.type for e in s.exec(select(EventRow).where(EventRow.customer_id == "C900008")).all()]
    assert types.count("offer_received") == 2 and types.count("offer_declined") == 2


def test_deployed_meera_without_declines_is_repaired(memory_db):
    """Production's Meera already has 9 orders; the missing declines alone must trigger a rebuild."""
    registry.ensure_lab_customers()
    with Session(memory_db) as s:
        for e in s.exec(select(EventRow).where(EventRow.type == "offer_declined")).all():
            s.delete(e)
        s.commit()
    assert registry.ensure_lab_customers() == 1
