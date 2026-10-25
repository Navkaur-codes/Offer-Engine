"""Customer Lab rounds: a Lab Shopper bot acts as a customer, the Offer bot replies, the customer reacts.

Bots can't see each other's group messages, so the backend drives all three messages of a round. Rotation
state lives in the `settings` table so every persona gets a turn before anyone repeats, across restarts.
"""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack

from telegram import Bot, Message, ReplyParameters
from telegram.constants import ChatType, ParseMode
from telegram.error import TelegramError

from app import ports, runtime
from app.bot import commands, resilience, sender, store
from app.bot.render import FOOTER, escape, inr, render_decision, render_why
from app.config import now, settings
from app.contracts import Decision
from app.lab import scripts
from app.lab.registry import (
    BY_ID,
    LAB_CUSTOMERS,
    LabCustomer,
    ensure_lab_customers,
    remember_voices,
    tokens,
    voice_index,
)

log = logging.getLogger(__name__)

ROTATION = "lab_rotation"
BATCH_FROM = 5  # runs longer than this go through decide_batch (agent for the top 5 only)
OFFER_STATUSES = {"SENT", "QUEUED"}

# hidden response type → (reaction, weight). Sure-things claim offers they'd have used anyway: wasted margin.
REACTIONS: dict[str, list[tuple[str, float]]] = {
    "persuadable": [("claim", 0.6), ("why", 0.15), ("ignore", 0.15), ("decline", 0.1)],
    "sure_thing": [("claim", 0.55), ("ignore", 0.35), ("why", 0.1)],
    "lost_cause": [("ignore", 0.6), ("decline", 0.3), ("why", 0.1)],
    "sleeping_dog": [("decline", 0.6), ("ignore", 0.3), ("claim", 0.1)],
}
LINES: dict[str, list[str]] = {
    "claim": ["Claimed ✅ perfect timing!", "Ooh, saving this one ✅", "Claimed ✅ ordering tonight"],
    "claim_sure_thing": ["Claimed ✅ (was going to buy it anyway 🤫)"],
    "decline": ["Not for me, thanks 🙅", "Nah, I'm good 🙅"],
    "decline_sleeping_dog": ["Please stop sending me these 🙅", "I was happy without the spam, honestly 🙅"],
    "ignore": ["<i>(seen ✓✓, no reply)</i>"],
    "why": ["Why am I getting this? ❓", "Hmm, why me? ❓"],
}
OUTCOMES = {
    "claim": ("claimed", "offer_claimed"),
    "decline": ("declined", "offer_declined"),
    "ignore": ("ignored", None),
}

_running = False


class LabError(RuntimeError):
    """A friendly reason the Lab can't run; the message is shown in the group as-is."""


async def _pause() -> None:
    await asyncio.sleep(random.uniform(2, 4))  # readable pacing, well inside Telegram's group limits


def react(decision: Decision, customer: LabCustomer) -> str:
    rng = random.Random(decision.id)  # stable per decision, varied across decisions
    options, weights = zip(*REACTIONS.get(customer.response_type, REACTIONS["persuadable"]), strict=True)
    return rng.choices(options, weights)[0]


def reaction_line(reaction: str, customer: LabCustomer, decision: Decision) -> str:
    pool = LINES.get(f"{reaction}_{customer.response_type}") or LINES[reaction]
    return f"<b>{escape(customer.name)}</b>: {random.Random(decision.id + reaction).choice(pool)}"


def offer_reply(decision: Decision, customer: LabCustomer) -> str:
    name = escape(customer.name)
    e = decision.explanation
    trail = f"\n<i>{escape(e.decided_by_line)} · {escape(e.rules_line)}</i>"
    if decision.status in OFFER_STATUSES and decision.final_offer_id:
        card = render_decision(decision).text.removesuffix(FOOTER).rstrip()
        return f"📨 <b>For {name}</b>\n{card}{trail}"
    if decision.status == "BLOCKED":
        return f"✗ <b>Blocked for {name}</b>: {escape(e.why_offer or e.telegram_text)}{trail}"
    if decision.status == "HELD_OUT":
        return (
            f"➖ <b>{name} is in the holdout group</b>: nothing sent, so we can measure true uplift.{trail}"
        )
    saved = max((c.est_cost for c in decision.candidates), default=0)
    margin = f" Margin protected: {inr(saved)}." if saved > 0 else ""
    return f"➖ <b>No offer for {name}</b>: {escape(e.why_offer or e.telegram_text)}{margin}{trail}"


# ---------------------------------------------------------------- rotation
def queue_next(customer_id: str) -> None:
    state = runtime.get_setting(ROTATION, {"pos": 0, "turn": 0, "queue": []})
    state["queue"] = [customer_id, *[q for q in state.get("queue", []) if q != customer_id]]
    runtime.set_setting(ROTATION, state)


def reset_rotation() -> None:
    runtime.set_setting(ROTATION, {"pos": 0, "turn": 0, "queue": []})


def next_customers(n: int) -> list[tuple[LabCustomer, int]]:
    """Queued customers first (from /lab persona), then round-robin, so all 10 play before anyone repeats."""
    state = runtime.get_setting(ROTATION, {"pos": 0, "turn": 0, "queue": []})
    picked: list[tuple[LabCustomer, int]] = []
    queue = [q for q in state.get("queue", []) if q in BY_ID]
    pos, turn = state.get("pos", 0), state.get("turn", 0)
    while len(picked) < n:
        if queue:
            customer = BY_ID[queue.pop(0)]
        else:
            customer = LAB_CUSTOMERS[pos % len(LAB_CUSTOMERS)]
            pos += 1
        picked.append((customer, turn))
        turn += 1
    runtime.set_setting(ROTATION, {"pos": pos % len(LAB_CUSTOMERS), "turn": turn, "queue": queue})
    return picked


# ---------------------------------------------------------------- rounds
async def _post(bot: Bot, chat_id: int, text: str, **kwargs) -> Message:
    return await resilience.send(bot, chat_id, text, customer_chat=False, parse_mode=ParseMode.HTML, **kwargs)


async def _reply(bot: Bot, chat_id: int, text: str, to: Message | None) -> Message:
    if to is None:
        return await _post(bot, chat_id, text)
    replying = ReplyParameters(message_id=to.message_id, allow_sending_without_reply=True)
    return await _post(bot, chat_id, text, reply_parameters=replying)


async def shared_message_ids(bot: Bot, chat_id: int) -> bool:
    """Only supergroups share message ids between bots. In a basic group each bot numbers messages itself, so
    a Lab Shopper's message_id points at some other message for the Offer bot: there we don't reply-link."""
    try:
        return (await bot.get_chat(chat_id)).type == ChatType.SUPERGROUP
    except TelegramError:
        return False


async def play_round(
    offer_bot: Bot,
    voice: Bot,
    chat_id: int,
    customer: LabCustomer,
    turn: int,
    pause: Callable[[], Awaitable[None]] = _pause,
    prepared: tuple[scripts.Activity, Decision] | None = None,
    threaded: bool = False,
) -> Decision:
    """One round. `prepared` = (activity already written, decision already made) for batched runs.
    `threaded` = reply-link across bots (supergroups only); otherwise the name headers carry the thread."""

    def link(message: Message) -> Message | None:
        return message if threaded else None

    act = prepared[0] if prepared else await asyncio.to_thread(scripts.activity, customer, now(), turn)
    header = f"👤 <b>{escape(customer.name)}</b> · {escape(customer.label)}"
    post = await _post(voice, chat_id, f"{header}\n{act.line}")
    if act.events and not prepared:
        await asyncio.to_thread(store.add_events, customer.id, act.events)
    await pause()

    if prepared:
        decision = prepared[1]
    else:
        decision = await asyncio.to_thread(ports.decide, customer.id, "lab", act.meta)
    answer = await _reply(offer_bot, chat_id, offer_reply(decision, customer), link(post))
    sender.remember(decision)
    await asyncio.to_thread(store.set_message_id, decision.id, answer.message_id)
    remember_message(answer.message_id, decision.id)  # the Offer bot's own id: right for reply-/why anywhere
    if threaded:
        remember_message(post.message_id, decision.id)
    if decision.status not in OFFER_STATUSES or not decision.final_offer_id:
        return decision

    reaction = react(decision, customer)
    await pause()
    said = await _reply(voice, chat_id, reaction_line(reaction, customer, decision), link(answer))
    if threaded:
        remember_message(said.message_id, decision.id)
    if reaction == "why":
        await pause()
        why = await _reply(offer_bot, chat_id, render_why(decision), link(said))
        remember_message(why.message_id, decision.id)
        return decision
    outcome, event = OUTCOMES[reaction]
    await commands._record(decision, outcome, event)
    return decision


async def run_rounds_async(
    offer_bot: Bot,
    chat_id: int,
    n: int,
    *,
    bot_factory: Callable[[str], Bot] = Bot,
    pause: Callable[[], Awaitable[None]] = _pause,
) -> list[Decision]:
    global _running
    voices_tokens = tokens()
    if not voices_tokens:
        raise LabError("No Lab Shopper bots configured (CUSTOMER_BOT_TOKENS is empty).")
    if _running:
        raise LabError("A Lab run is already going. Give it a minute.")
    _running = True
    try:
        await asyncio.to_thread(ensure_lab_customers)
        decisions: list[Decision] = []
        async with AsyncExitStack() as stack:
            voices = [await stack.enter_async_context(bot_factory(t)) for t in voices_tokens]
            await asyncio.to_thread(remember_voices, [v.username for v in voices])
            threaded = await shared_message_ids(offer_bot, chat_id)
            cast = await asyncio.to_thread(next_customers, n)
            prepared = await asyncio.to_thread(_prepare_batch, cast) if n > BATCH_FROM else [None] * len(cast)
            for (customer, turn), ready in zip(cast, prepared, strict=True):
                voice = voices[voice_index(customer, len(voices))]
                decisions.append(
                    await play_round(offer_bot, voice, chat_id, customer, turn, pause, ready, threaded)
                )
                await pause()
        return decisions
    finally:
        _running = False


def _prepare_batch(cast: list[tuple[LabCustomer, int]]) -> list[tuple[scripts.Activity, Decision]]:
    """Big runs: write every activity first, then one `decide_batch` so only the top 5 use the agent (T26)."""
    at = now()
    acts = [scripts.activity(customer, at, turn) for customer, turn in cast]
    for (customer, _), act in zip(cast, acts, strict=True):
        if act.events:
            store.add_events(customer.id, act.events)
    items = [(customer.id, "lab", act.meta) for (customer, _), act in zip(cast, acts, strict=True)]
    return list(zip(acts, ports.decide_batch(items, dry_run=False), strict=True))


def run_rounds(n: int) -> list[Decision]:
    """The sync port (contracts §3), for the API/scheduler: posts into the registered Lab group."""
    chat_id = runtime.lab_group_chat_id()
    if chat_id is None:
        raise LabError("No Lab group yet. Type /lab here in the group first.")

    async def go() -> list[Decision]:
        async with Bot(settings.telegram_bot_token) as bot:
            return await run_rounds_async(bot, chat_id, n)

    return asyncio.run(go())


# ---------------------------------------------------------------- reply-/why lookup
_BY_MESSAGE: dict[int, str] = {}


def remember_message(message_id: int, decision_id: str) -> None:
    _BY_MESSAGE[message_id] = decision_id
    if len(_BY_MESSAGE) > 2000:
        _BY_MESSAGE.pop(next(iter(_BY_MESSAGE)))


def decision_for_message(message_id: int) -> Decision | None:
    decision_id = _BY_MESSAGE.get(message_id)
    if decision_id:
        return sender.recent(decision_id) or store.find_decision(decision_id)
    return store.decision_by_message(message_id)
