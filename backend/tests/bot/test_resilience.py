"""Retries on 429/5xx, 403 → unreachable, duplicate update_id dropped."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telegram import Update
from telegram.error import BadRequest, Forbidden, NetworkError, RetryAfter, TimedOut
from telegram.ext import ApplicationHandlerStop

from app import stubs
from app.bot import resilience, sender, store

from .test_handlers import _onboard


def _bot(*outcomes):
    """send_message raises/returns each outcome in turn."""
    calls = []

    async def send_message(chat_id, text, **kw):
        calls.append(text)
        out = outcomes[len(calls) - 1]
        if isinstance(out, Exception):
            raise out
        return out

    return SimpleNamespace(send_message=send_message, calls=calls)


async def test_retry_after_is_honoured():
    sleep = AsyncMock()
    ok = SimpleNamespace(message_id=7)
    msg = await resilience.send(_bot(RetryAfter(5), ok), 1, "hi", sleep=sleep)
    assert msg is ok and sleep.await_args.args[0] == 5.5


async def test_network_errors_back_off_then_succeed():
    sleep = AsyncMock()
    bot = _bot(TimedOut(), NetworkError("Bad Gateway"), SimpleNamespace(message_id=1))
    assert (await resilience.send(bot, 1, "hi", sleep=sleep)).message_id == 1
    assert [c.args[0] for c in sleep.await_args_list] == [1.0, 2.0]


async def test_gives_up_after_three_tries():
    with pytest.raises(NetworkError):
        await resilience.send(_bot(TimedOut(), TimedOut(), TimedOut()), 1, "hi", sleep=AsyncMock())


async def test_bad_request_is_not_retried():
    sleep = AsyncMock()
    bot = _bot(BadRequest("can't parse entities"))
    with pytest.raises(BadRequest):
        await resilience.send(bot, 1, "<b>", sleep=sleep)
    assert len(bot.calls) == 1 and not sleep.await_count


async def test_blocked_customer_marked_unreachable_until_start(chat):
    await _onboard(chat)
    assert await resilience.send(_bot(Forbidden("bot was blocked by the user")), chat.user.id, "hi") is None
    assert store.is_unreachable("TG55512345")
    await _onboard(chat)  # coming back via /start makes them reachable again
    assert not store.is_unreachable("TG55512345")


async def test_group_403_raises():
    with pytest.raises(Forbidden):
        await resilience.send(_bot(Forbidden("kicked")), -100, "hi", customer_chat=False)


async def test_send_decision_survives_block(chat):
    await _onboard(chat)
    decision = stubs.decide("TG55512345", "lab")
    assert await sender.send_decision(_bot(Forbidden("blocked")), chat.user.id, decision) is None


async def test_deliver_skips_unreachable(chat, monkeypatch):
    await _onboard(chat)
    store.mark_unreachable(chat.user.id)
    monkeypatch.setattr(sender.settings, "telegram_bot_token", "123:TEST")
    monkeypatch.setattr(sender, "_send_with_fresh_bot", lambda *a: pytest.fail("must not send"))
    sender.deliver(stubs.decide("TG55512345", "inactivity"), "dm")


async def test_duplicate_updates_dropped():
    update = Update(update_id=424242)
    await resilience.drop_duplicates(update, None)
    with pytest.raises(ApplicationHandlerStop):
        await resilience.drop_duplicates(Update(update_id=424242), None)
    await resilience.drop_duplicates("not an update", None)
