"""Sending decisions to Telegram.

- `send_decision(bot, chat_id, decision)`: async, used by handlers that answer a user action (onboarding,
  /simulate). Renders every status, including NO_OFFER/BLOCKED, because the user asked.
- `deliver(decision, channel)`: the sync port (contracts §3) for proactive sends (scheduler, campaigns).
  It only ever sends real offers: a proactive "no offer" message would be spam.
"""

from __future__ import annotations

import asyncio
import logging
from collections import OrderedDict

from telegram import Bot, Message
from telegram.constants import ParseMode
from telegram.error import TelegramError

from app.bot import store
from app.bot.render import render_decision
from app.config import settings
from app.contracts import Channel, Decision

log = logging.getLogger(__name__)

# Recently rendered decisions, so buttons and /why work even before the harness logs to the DB (stub phase).
_RECENT: OrderedDict[str, Decision] = OrderedDict()
_RECENT_MAX = 500
_TASKS: set[asyncio.Task] = set()


def remember(decision: Decision) -> None:
    _RECENT[decision.id] = decision
    _RECENT.move_to_end(decision.id)
    while len(_RECENT) > _RECENT_MAX:
        _RECENT.popitem(last=False)


def recent(decision_id: str) -> Decision | None:
    return _RECENT.get(decision_id)


def last_for(customer_id: str) -> Decision | None:
    for d in reversed(_RECENT.values()):
        if d.customer_id == customer_id:
            return d
    return None


def all_for(customer_id: str) -> list[Decision]:
    return [d for d in reversed(_RECENT.values()) if d.customer_id == customer_id]


async def send_decision(bot: Bot, chat_id: int, decision: Decision) -> Message:
    card = render_decision(decision)
    message = await bot.send_message(
        chat_id,
        card.text,
        parse_mode=ParseMode.HTML,
        reply_markup=card.keyboard,
    )
    remember(decision)
    await asyncio.to_thread(store.set_message_id, decision.id, message.message_id)
    return message


def _chat_id(decision: Decision) -> int | None:
    if decision.customer_id.startswith("TG"):
        return int(decision.customer_id[2:])
    row = store.get_customer(decision.customer_id)
    return row.telegram_chat_id if row else None


async def _send_with_fresh_bot(chat_id: int, decision: Decision) -> None:
    async with Bot(settings.telegram_bot_token) as bot:
        await send_decision(bot, chat_id, decision)


def deliver(decision: Decision, channel: Channel) -> None:
    if channel != "dm":
        log.info("deliver %s: channel %s not handled yet", decision.id, channel)
        return
    if decision.status != "SENT" or not decision.final_offer_id:
        log.info("deliver %s: status %s, nothing to send", decision.id, decision.status)
        return
    chat_id = _chat_id(decision)
    if chat_id is None or not settings.telegram_bot_token:
        log.info("deliver %s: no chat or no bot token, skipped", decision.id)
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:  # called from a worker thread (scheduler) with no loop of its own
        loop = None
    if loop is None:
        try:
            asyncio.run(_send_with_fresh_bot(chat_id, decision))
        except TelegramError as exc:
            log.warning("deliver %s failed: %s", decision.id, type(exc).__name__)
        return
    task = loop.create_task(_send_with_fresh_bot(chat_id, decision))
    _TASKS.add(task)  # keep a reference so the task isn't garbage-collected mid-send
    task.add_done_callback(_TASKS.discard)
