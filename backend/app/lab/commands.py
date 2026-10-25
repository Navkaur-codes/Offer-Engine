"""Group commands for the Customer Lab: /lab here | run [n] | who | persona <name> <state> | date | reset,
and reply-/why on any Lab message. /lab is admin-only (ADMIN_TELEGRAM_IDS)."""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from app import runtime
from app.bot import store
from app.bot.render import escape, render_why
from app.config import now, set_time_override, settings
from app.lab import registry, runner

log = logging.getLogger(__name__)

USAGE = (
    "<b>Customer Lab</b>\n"
    "/lab here · make this group the Lab\n"
    "/lab run [n] · play n rounds (default 3, max 10)\n"
    "/lab who · the 10 Lab customers and their voices\n"
    "/lab persona &lt;name&gt; inactive [days] | cart | purchase | next\n"
    "/lab date YYYY-MM-DD | off · time-travel the engine's clock\n"
    "/lab reset · rebuild all 10 customers, clear the clock and rotation\n"
    "Reply /why to any Lab message for its explanation."
)
STATES = ("inactive", "cart", "purchase", "next")


async def _say(update: Update, text: str) -> None:
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


def _is_admin(update: Update) -> bool:
    return update.effective_user is not None and update.effective_user.id in settings.admin_ids


async def lab_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not settings.admin_ids:
        await _say(update, "The Lab needs ADMIN_TELEGRAM_IDS set on the server first.")
        return
    if not _is_admin(update):
        await _say(update, "Only Lab admins can run /lab.")
        return
    sub, *args = context.args or ["help"]
    handler = {
        "here": _here,
        "run": _run,
        "who": _who,
        "persona": _persona,
        "date": _date,
        "reset": _reset,
    }.get(sub.lower())
    if handler is None:
        await _say(update, USAGE)
        return
    await handler(update, context, args)


async def _here(update: Update, context: ContextTypes.DEFAULT_TYPE, args: list[str]) -> None:
    chat = update.effective_chat
    await asyncio.to_thread(runtime.set_lab_group, chat.id, chat.title)
    await _say(update, "✅ This group is now the Customer Lab")


async def _run(update: Update, context: ContextTypes.DEFAULT_TYPE, args: list[str]) -> None:
    lab_chat = await asyncio.to_thread(runtime.lab_group_chat_id)
    if lab_chat is None or lab_chat != update.effective_chat.id:
        await _say(update, "Type /lab here first.")
        return
    if not registry.tokens():
        await _say(update, "No Lab Shopper bots configured.")
        return
    try:
        n = max(1, min(int(args[0]), 10)) if args else 3
    except ValueError:
        n = 3
    await _say(update, f"▶️ Running {n} Lab round{'s' if n > 1 else ''}…")
    # Rounds take ~10 s each; run them in the background so the webhook request returns at once.
    context.application.create_task(_play(context, lab_chat, n))


async def _play(context: ContextTypes.DEFAULT_TYPE, chat_id: int, n: int) -> None:
    try:
        decisions = await runner.run_rounds_async(context.bot, chat_id, n)
    except runner.LabError as exc:
        await context.bot.send_message(chat_id, f"⚠️ {escape(str(exc))}", parse_mode=ParseMode.HTML)
        return
    except Exception as exc:  # never leave the group hanging mid-demo
        log.exception("lab run failed")
        await context.bot.send_message(chat_id, f"⚠️ Lab run stopped ({type(exc).__name__}).")
        return
    sent = sum(d.status == "SENT" for d in decisions)
    await context.bot.send_message(
        chat_id, f"🏁 Done: {len(decisions)} rounds, {sent} offers sent, {len(decisions) - sent} held back."
    )


async def _who(update: Update, context: ContextTypes.DEFAULT_TYPE, args: list[str]) -> None:
    n = len(registry.tokens())
    lines = [f"<b>Customer Lab</b> · 10 customers, {n} Lab Shopper bot{'s' if n != 1 else ''}"]
    for c in registry.LAB_CUSTOMERS:
        row = await asyncio.to_thread(store.get_customer, c.id)
        voice = (row.attrs or {}).get("lab_voice") if row else None
        if voice:
            who = f"@{escape(voice)}"
        else:
            who = f"Lab Shopper {registry.voice_index(c, n) + 1}" if n else "no bot"
        lines.append(f"👤 <b>{escape(c.name)}</b> · {escape(c.label)} → {who}")
    await _say(update, "\n".join(lines))


async def _persona(update: Update, context: ContextTypes.DEFAULT_TYPE, args: list[str]) -> None:
    customer = registry.find(args[0]) if args else None
    state = args[1].lower() if len(args) > 1 else ""
    if customer is None or state not in STATES:
        names = ", ".join(c.name for c in registry.LAB_CUSTOMERS)
        await _say(update, f"Usage: /lab persona &lt;name&gt; {' | '.join(STATES)}\nNames: {names}")
        return
    await asyncio.to_thread(registry.ensure_lab_customers)
    at = now()
    if state == "inactive":
        try:
            days = max(7, min(int(args[2]), 365)) if len(args) > 2 else 90
        except ValueError:
            days = 90
        await asyncio.to_thread(store.shift_activity, customer.id, days)
        done = f"{escape(customer.name)} has now been inactive for {days} days"
    elif state == "cart":
        item, value = store.pick_product(customer.favourite, f"{customer.id}{at:%H%M}")
        since = at - timedelta(minutes=45)
        event = {
            "type": "add_to_cart",
            "ts": since,
            "category": customer.favourite,
            "item": item,
            "value": value,
        }
        await asyncio.to_thread(store.add_events, customer.id, [event])
        done = f"{escape(customer.name)} left {escape(item)} in the cart 45 min ago"
    elif state == "purchase":
        item, value = store.pick_product(customer.favourite, f"{customer.id}{at:%H%M}buy")
        await asyncio.to_thread(store.add_order, customer.id, customer.favourite, item, value, at)
        done = f"{escape(customer.name)} just bought {escape(item)}"
    else:
        done = f"{escape(customer.name)} is up next"
    await asyncio.to_thread(runner.queue_next, customer.id)
    await _say(update, f"🎭 {done}. They play the next round: /lab run 1")


async def _date(update: Update, context: ContextTypes.DEFAULT_TYPE, args: list[str]) -> None:
    if not args:
        await _say(update, f"🕰 Engine clock: {now():%a %d %b %Y, %H:%M}. Usage: /lab date 2026-11-06 | off")
        return
    if args[0].lower() in ("off", "reset", "now"):
        set_time_override(None)
        await _say(update, f"🕰 Back to real time: {now():%a %d %b %Y, %H:%M}.")
        return
    try:
        day = date.fromisoformat(args[0])
    except ValueError:
        await _say(update, "Use a date like /lab date 2026-11-06.")
        return
    set_time_override(day.isoformat())
    await _say(
        update,
        f"🕰 Engine clock set to {now():%a %d %b %Y}. Run /lab reset so the customers' history lines up.",
    )


async def _reset(update: Update, context: ContextTypes.DEFAULT_TYPE, args: list[str]) -> None:
    rebuilt = await asyncio.to_thread(registry.ensure_lab_customers, True)
    await asyncio.to_thread(runner.reset_rotation)
    await _say(
        update, f"🔄 Rebuilt {rebuilt} Lab customers and reset the rotation (clock: {now():%d %b %Y})."
    )


async def why_in_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    replied = update.effective_message.reply_to_message
    if replied is None:
        await _say(update, "Reply /why to a Lab message to see why the engine did that.")
        return
    decision = await asyncio.to_thread(runner.decision_for_message, replied.message_id)
    if decision is None:
        await _say(update, "I can't find a decision for that message.")
        return
    await _say(update, render_why(decision))
