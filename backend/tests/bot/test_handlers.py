"""Onboarding flow, commands and buttons against mocked Telegram objects and the stub ports."""

from __future__ import annotations

from datetime import datetime

from app.bot import app as bot_app
from app.bot import commands, onboarding, store
from app.config import IST
from app.models import CustomerRow


def _labels(markup) -> list[str]:
    return [b.text for row in markup.inline_keyboard for b in row]


async def _onboard(chat, festivals=("diwali",)):
    await onboarding.start(chat.message_update(), chat.context())
    for data in ["ob:consent:yes", "ob:cat:fashion", "ob:cat:beauty", "ob:cat_done", "ob:freq:monthly",
                 "ob:style:deal", *[f"ob:fest:{f}" for f in festivals], "ob:fest_done"]:
        await onboarding.on_button(chat.button_update(data), chat.context())


async def test_full_onboarding_creates_customer_and_sends_welcome_card(chat):
    await _onboard(chat)
    row = store.get_customer("TG55512345")
    assert row is not None and row.telegram_chat_id == 55512345
    assert row.opt_in_festivals == ["diwali"] and not row.opted_out
    assert row.attrs["onboarding"] == {
        "categories": ["fashion", "beauty"], "frequency": "monthly", "style": "deal", "festivals": ["diwali"]
    }
    edits = [t for k, t, _ in chat.sent if k == "edit"]
    assert edits[-1].startswith("<b>All set ✓</b>") and "Fashion, Beauty" in edits[-1]
    kind, card, keyboard = chat.sent[-1]
    assert kind == "send" and "<code>" in card
    assert _labels(keyboard) == ["✅ Claim", "⏰ Remind me tonight", "🙅 Not for me", "❓ Why this?"]
    assert "onboarding" not in chat.user_data


async def test_consent_first_and_declining_stops(chat):
    await onboarding.start(chat.message_update(), chat.context())
    assert "synthetic" in chat.last_text
    assert _labels(chat.sent[-1][2]) == ["✅ Sounds good, let's go", "Not now"]
    await onboarding.on_button(chat.button_update("ob:consent:no"), chat.context())
    assert "/start" in chat.last_text and store.get_customer("TG55512345") is None


async def test_category_toggle_marks_choice(chat):
    await onboarding.start(chat.message_update(), chat.context())
    await onboarding.on_button(chat.button_update("ob:consent:yes"), chat.context())
    await onboarding.on_button(chat.button_update("ob:cat:kitchen"), chat.context())
    labels = _labels(chat.sent[-1][2])
    assert "✓ Kitchen" in labels and "Next → (1 picked)" in labels
    await onboarding.on_button(chat.button_update("ob:cat:kitchen"), chat.context())
    assert "Skip →" in _labels(chat.sent[-1][2])


async def test_festival_none_clears_opt_ins(chat):
    await onboarding.start(chat.message_update(), chat.context())
    for data in ["ob:consent:yes", "ob:cat_done", "ob:freq:weekly", "ob:style:quality", "ob:fest:lohri",
                 "ob:fest_none"]:
        await onboarding.on_button(chat.button_update(data), chat.context())
    assert store.get_customer("TG55512345").opt_in_festivals == []


async def test_expired_menu_asks_to_restart(chat):
    await onboarding.on_button(chat.button_update("ob:cat:fashion"), chat.context())
    assert chat.last_text == onboarding.EXPIRED_TEXT


async def test_name_is_escaped(chat):
    chat.user.first_name = "<b>Eve</b>"
    await onboarding.start(chat.message_update(), chat.context())
    assert "&lt;b&gt;Eve&lt;/b&gt;" in chat.last_text


async def test_stop_then_start_resubscribes(chat):
    await _onboard(chat)
    await commands.stop_cmd(chat.message_update("/stop"), chat.context())
    assert store.get_customer("TG55512345").opted_out
    await _onboard(chat)
    assert not store.get_customer("TG55512345").opted_out


async def test_pause_and_resume(chat):
    await _onboard(chat)
    await commands.pause_cmd(chat.message_update("/pause 3"), chat.context(["3"]))
    row = store.get_customer("TG55512345")
    assert row.paused_until is not None and "Paused till" in chat.last_text
    await commands.resume_cmd(chat.message_update("/resume"), chat.context())
    assert store.get_customer("TG55512345").paused_until is None


async def test_commands_before_start_say_not_registered(chat):
    for cmd in (commands.profile_cmd, commands.pause_cmd):
        await cmd(chat.message_update(), chat.context())
        assert chat.last_text == commands.NOT_REGISTERED


async def test_profile_in_plain_words(chat):
    await _onboard(chat)
    await commands.profile_cmd(chat.message_update("/profile"), chat.context())
    text = chat.last_text
    assert "Shopper type" in text and "Festival greetings: Diwali" in text and "Status: Active" in text
    assert "response_type" not in text and "persuadable" not in text


async def test_offers_and_why_after_welcome(chat):
    await _onboard(chat)
    await commands.offers_cmd(chat.message_update("/offers"), chat.context())
    assert "Your active offers" in chat.last_text and "<code>" in chat.last_text
    await commands.why_cmd(chat.message_update("/why"), chat.context())
    assert "Why you got this" in chat.last_text


async def test_offers_empty_before_any_decision(chat):
    await commands.offers_cmd(chat.message_update("/offers"), chat.context())
    assert chat.last_text.startswith("No active offers")


async def test_offer_buttons_respond(chat):
    await _onboard(chat)
    decision_id = chat.sent[-1][2].inline_keyboard[0][0].callback_data.split(":", 2)[2]
    ctx = chat.context()
    await commands.on_offer_button(chat.button_update(f"o:claim:{decision_id}"), ctx)
    assert chat.last_text.startswith("✅ Saved! Use code <code>")
    await commands.on_offer_button(chat.button_update(f"o:why:{decision_id}"), ctx)
    assert "Why you got this" in chat.last_text
    update = chat.button_update(f"o:remind:{decision_id}")
    await commands.on_offer_button(update, ctx)
    ctx.job_queue.run_once.assert_called_once()
    assert "remind you at 19:00" in update.callback_query.answer.call_args.args[0]
    update = chat.button_update("o:claim:D-unknown")
    await commands.on_offer_button(update, ctx)
    assert update.callback_query.answer.call_args.kwargs["show_alert"] is True


def test_next_evening():
    assert commands.next_evening(datetime(2026, 10, 24, 10, 0, tzinfo=IST)).day == 24
    assert commands.next_evening(datetime(2026, 10, 24, 19, 30, tzinfo=IST)).day == 25


async def test_error_handler_replies_and_never_raises(chat):
    ctx = chat.context()
    ctx.error = ValueError("boom")
    await bot_app.on_error(None, ctx)  # non-Update: just logs
    chat.bot.send_message.side_effect = RuntimeError("telegram down")
    from telegram import Update

    message = {"message_id": 1, "date": 0, "chat": {"id": 7, "type": "private"}, "text": "hi"}
    update = Update.de_json({"update_id": 9, "message": message}, None)
    await bot_app.on_error(update, ctx)  # send fails, handler still returns


def test_register_handlers_without_token():
    from telegram.ext import ApplicationBuilder

    application = ApplicationBuilder().token("123:TEST").build()
    bot_app.register_handlers(application)
    assert sum(len(h) for h in application.handlers.values()) >= 10
    assert application.error_handlers


def test_customer_row_shape_matches_contract():
    needed = {"opted_out", "paused_until", "opt_in_festivals", "telegram_chat_id"}
    assert needed <= set(CustomerRow.model_fields)
