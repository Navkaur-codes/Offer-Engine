"""Telegram resilience: retry 429/5xx with backoff, mark blocked customers unreachable, dedupe updates."""

from __future__ import annotations

import asyncio
import logging
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from datetime import timedelta

from telegram import Bot, Message, Update
from telegram.error import BadRequest, Forbidden, NetworkError, RetryAfter
from telegram.ext import ApplicationHandlerStop, ContextTypes

from app.bot import store

log = logging.getLogger(__name__)

MAX_TRIES = 3
MAX_WAIT_S = 30.0
_SEEN: OrderedDict[int, None] = OrderedDict()
_SEEN_MAX = 5000


def _wait(exc: Exception, attempt: int) -> float:
    if isinstance(exc, RetryAfter):
        after = exc.retry_after
        secs = after.total_seconds() if isinstance(after, timedelta) else float(after)
        return min(secs + 0.5, MAX_WAIT_S)
    return float(2**attempt)  # 1 s, 2 s, 4 s for timeouts / 5xx


async def send(
    bot: Bot,
    chat_id: int,
    text: str,
    *,
    customer_chat: bool = True,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    **kwargs,
) -> Message | None:
    """send_message with retries. A 403 on a customer's chat (they blocked the bot) marks them unreachable
    and returns None instead of raising; in group chats (`customer_chat=False`) it raises."""
    return await _retrying(lambda: bot.send_message(chat_id, text, **kwargs), chat_id, customer_chat, sleep)


async def send_photo(
    bot: Bot,
    chat_id: int,
    photo: bytes,
    caption: str,
    *,
    customer_chat: bool = True,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    **kwargs,
) -> Message | None:
    """send_photo with the same retry and 403 handling as `send`."""
    return await _retrying(
        lambda: bot.send_photo(chat_id, photo=photo, caption=caption, **kwargs), chat_id, customer_chat, sleep
    )


async def _retrying(
    call: Callable[[], Awaitable[Message]],
    chat_id: int,
    customer_chat: bool,
    sleep: Callable[[float], Awaitable[None]],
) -> Message | None:
    for attempt in range(MAX_TRIES):
        try:
            return await call()
        except Forbidden:
            if not customer_chat:
                raise
            log.warning("chat %s blocked the bot; marking unreachable", chat_id)
            await asyncio.to_thread(store.mark_unreachable, chat_id)
            return None
        except BadRequest:
            raise  # our fault (bad HTML, unknown chat): retrying won't help
        except (RetryAfter, NetworkError) as exc:
            if attempt == MAX_TRIES - 1:
                raise
            wait = _wait(exc, attempt)
            log.info("telegram %s, retry %d in %.1fs", type(exc).__name__, attempt + 1, wait)
            await sleep(wait)
    return None


async def drop_duplicates(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Group -1 handler: Telegram re-delivers a webhook update when our reply is slow; handle it once."""
    if not isinstance(update, Update):
        return
    if update.update_id in _SEEN:
        log.info("duplicate update %s dropped", update.update_id)
        raise ApplicationHandlerStop
    _SEEN[update.update_id] = None
    while len(_SEEN) > _SEEN_MAX:
        _SEEN.popitem(last=False)
