"""Admin commands: /summary, /killswitch, /campaign run, /impersonate (stub ports + in-memory DB)."""

from __future__ import annotations

from datetime import date

import pytest
from sqlmodel import Session
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler

from app import decision_store, runtime, stubs
from app.bot import admin, commands, store
from app.bot import app as bot_app
from app.config import settings
from app.models import CustomerRow

from .test_handlers import _onboard


@pytest.fixture(autouse=True)
def as_admin(monkeypatch, chat):
    monkeypatch.setattr(settings, "admin_telegram_ids", str(chat.user.id))
    commands.IMPERSONATING.clear()
    yield
    commands.IMPERSONATING.clear()


def _customer(engine, cid: str, **kw) -> None:
    with Session(engine) as s:
        s.add(
            CustomerRow(
                id=cid,
                first_name=kw.pop("name", "Test"),
                city="Pune",
                city_tier=1,
                signup_date=date(2026, 1, 1),
                channel="organic",
                device="android",
                preferred_payment="upi",
                persona="cart_abandoner",
                response_type="persuadable",
                **kw,
            )
        )
        s.commit()


async def test_non_admin_is_refused(chat, monkeypatch):
    monkeypatch.setattr(settings, "admin_telegram_ids", "1")
    await admin.killswitch_cmd(chat.message_update("/killswitch on"), chat.context(["on"]))
    assert chat.last_text == "That command is for Offer Engine admins." and not runtime.killswitch_on()


async def test_killswitch_on_off_and_status(chat):
    await admin.killswitch_cmd(chat.message_update(), chat.context(["on"]))
    assert runtime.killswitch_on() and "Kill switch ON" in chat.last_text
    await admin.killswitch_cmd(chat.message_update(), chat.context([]))
    assert "is ON" in chat.last_text
    await admin.killswitch_cmd(chat.message_update(), chat.context(["off"]))
    assert not runtime.killswitch_on() and "off" in chat.last_text


async def test_summary_counts_today(chat):
    decision_store.save(stubs.decide("C000001", "lab"))  # SENT
    decision_store.save(stubs.decide("C000003", "lab"))  # NO_OFFER
    decision_store.save(stubs.decide("C000004", "manual"))  # BLOCKED
    await admin.summary_cmd(chat.message_update("/summary"), chat.context())
    text = chat.last_text
    assert (
        "Sent <code>1</code>" in text
        and "No offer <code>1</code>" in text
        and "blocked <code>1</code>" in text
    )
    assert "Digest for" in text  # the daily_digest port


def test_campaign_targets_synthetic_only(memory_db):
    for cid in ("C000101", "C000102", "C000103", "C000104"):
        _customer(memory_db, cid)
    _customer(memory_db, "C900001", is_lab_bot=True)
    _customer(memory_db, "C000105", opted_out=True)
    _customer(memory_db, "TG123456", telegram_chat_id=123456)
    targets = admin.campaign_targets("cart_abandoner", 10)  # stub profiles are all cart abandoners
    assert sorted(targets) == ["C000101", "C000102", "C000103", "C000104"]
    assert admin.campaign_targets("vip", 10) == []


def test_run_campaign_reports_batch(memory_db):
    for cid in ("C000101", "C000102", "C000103"):
        _customer(memory_db, cid)
    text = admin.run_campaign("cart_abandoner", 2)
    assert "Campaign · cart_abandoner</b> · 2 synthetic customers" in text and "Sent <code>2</code>" in text
    assert "No synthetic customers" in admin.run_campaign("dormant", 2)


async def test_campaign_command_runs_in_background(chat):
    ctx = chat.context(["run", "deal_hunter", "5"])
    from unittest.mock import MagicMock

    ctx.application = MagicMock()
    await admin.campaign_cmd(chat.message_update(), ctx)
    assert "deal_hunter campaign on up to 5" in chat.last_text
    ctx.application.create_task.assert_called_once()
    ctx.application.create_task.call_args.args[0].close()
    await admin.campaign_cmd(chat.message_update(), chat.context(["run", "wizards"]))
    assert chat.last_text.startswith("Usage: /campaign run")


async def test_impersonate_reads_as_customer_but_consent_stays_own(chat, memory_db):
    await _onboard(chat)  # the admin's own TG customer
    _customer(memory_db, "C000101", name="Kavya")
    await admin.impersonate_cmd(chat.message_update(), chat.context(["c000101"]))
    assert commands.IMPERSONATING[chat.user.id] == "C000101" and "You are now <b>Kavya</b>" in chat.last_text
    await commands.profile_cmd(chat.message_update("/profile"), chat.context())
    assert "Your profile" in chat.last_text
    await commands.stop_cmd(chat.message_update("/stop"), chat.context())
    assert store.get_customer("TG55512345").opted_out and not store.get_customer("C000101").opted_out
    await admin.impersonate_cmd(chat.message_update(), chat.context(["off"]))
    assert chat.last_text == "🎭 Stopped impersonating C000101." and not commands.IMPERSONATING


async def test_impersonate_unknown_customer(chat):
    await admin.impersonate_cmd(chat.message_update(), chat.context(["C999999"]))
    assert chat.last_text == "No customer C999999."


def test_admin_commands_registered_before_catch_all():
    application = ApplicationBuilder().token("123:TEST").build()
    bot_app.register_handlers(application)
    handlers = application.handlers[0]
    catch_all = next(i for i, h in enumerate(handlers) if isinstance(h, MessageHandler))
    admin_idx = [
        i for i, h in enumerate(handlers) if isinstance(h, CommandHandler) and "summary" in h.commands
    ]
    assert admin_idx and admin_idx[0] < catch_all
