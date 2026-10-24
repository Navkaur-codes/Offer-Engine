"""/simulate: write realistic events for the user's own TG customer → decide → card, status line first.

Every action runs through `run()` so the command and the button menu behave identically. Arguments are
matched against fixed lists (categories, personas, festivals); free text never reaches the decision path.
"""

from __future__ import annotations

import asyncio
import time
from datetime import date, datetime, timedelta
from typing import get_args

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from app import ports
from app.bot import sender, store
from app.bot.commands import NOT_REGISTERED, PERSONA_LABELS
from app.bot.render import CATEGORY_LABELS, escape, inr
from app.config import now
from app.contracts import Festival, FestivalPhase, Persona

RATE_LIMIT_S = 10
CART_MINUTES = 35
ACTIONS = ("cart", "browse", "purchase", "inactive", "points_expiry", "festival", "payday", "persona")
PHASES: tuple[str, ...] = get_args(FestivalPhase)
PHASE_LABELS = {"teaser": "teaser", "build_up": "build-up", "last_minute": "last minute", "post": "after"}

MENU_TEXT = (
    "🧪 <b>Simulation console</b>\n"
    "Pretend you just did something in the shop, and watch the engine decide in real time.\n"
    "<i>Or type it: /simulate cart fashion · /simulate inactive 60 · /simulate festival diwali</i>"
)
USAGE = {
    "browse": "Which category? e.g. /simulate browse beauty",
    "persona": "Which persona? e.g. /simulate persona deal_hunter\nOptions: {options}",
    "festival": "Which festival? e.g. /simulate festival diwali build_up",
}


def menu_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [("🛒 Abandon a cart", "cart"), ("👀 Browse", "browse")],
        [("✅ Buy something", "purchase"), ("💤 Go quiet 60 days", "inactive")],
        [("⭐ Points expiring", "points_expiry"), ("🎉 Next festival", "festival")],
        [("💰 Payday", "payday")],
    ]
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(label, callback_data=f"sim:{key}") for label, key in row] for row in rows]
    )


def _category(arg: str | None) -> str | None:
    if not arg:
        return None
    key = arg.lower().replace(" ", "_").replace("-", "_")
    if key in CATEGORY_LABELS:
        return key
    return next((k for k, label in CATEGORY_LABELS.items() if label.lower() == arg.lower()), None)


def _favourite_category(row) -> str:
    picked = (row.attrs or {}).get("onboarding", {}).get("categories") or []
    return picked[0] if picked else "fashion"


def find_festival(festivals: list[Festival], name: str | None, today: date) -> Festival | None:
    """By key/name, or the nearest upcoming one; for repeats (Diwali 2025/2026) the nearest upcoming wins."""
    upcoming = sorted((f for f in festivals if f.date >= today), key=lambda f: f.date)
    past = sorted((f for f in festivals if f.date < today), key=lambda f: f.date, reverse=True)
    ordered = upcoming + past
    if not name:
        return upcoming[0] if upcoming else None
    key = name.lower().replace(" ", "_").replace("-", "_")
    return next((f for f in ordered if f.id.rsplit("_", 1)[0] == key or f.name.lower() == name.lower()), None)


def festival_phase(festival: Festival, today: date) -> str:
    offset = (today - festival.date).days
    for phase, (start, end) in festival.phases.items():
        if start <= offset <= end:
            return phase
    return "build_up"


def check_rate_limit(user_data: dict, clock: float | None = None) -> int:
    """Seconds left to wait (0 = go). Stamps the time when allowed."""
    t = time.monotonic() if clock is None else clock
    wait = RATE_LIMIT_S - (t - user_data.get("last_simulate", -RATE_LIMIT_S))
    if wait > 0:
        return int(wait + 0.999)
    user_data["last_simulate"] = t
    return 0


async def simulate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.effective_message.reply_text(
            MENU_TEXT, parse_mode=ParseMode.HTML, reply_markup=menu_keyboard()
        )
        return
    action, *args = context.args
    action = action.lower()
    if action not in ACTIONS:
        await update.effective_message.reply_text(
            "I don't know that one. Try /simulate for the menu.", parse_mode=ParseMode.HTML
        )
        return
    await run(update, context, action, args)


async def on_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    action = update.callback_query.data.split(":", 1)[1]
    if action not in ACTIONS:
        await update.callback_query.answer()
        return
    await update.callback_query.answer()
    await run(update, context, action, ["60"] if action == "inactive" else [])


async def _say(update: Update, text: str) -> None:
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


async def run(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, args: list[str]) -> None:
    cid = store.customer_id_for(update.effective_user.id)
    row = await asyncio.to_thread(store.get_customer, cid)
    if row is None:
        await _say(update, NOT_REGISTERED)
        return
    wait = check_rate_limit(context.user_data)
    if wait:
        await _say(update, f"⏳ One simulation at a time. Try again in {wait} s.")
        return

    plan = await asyncio.to_thread(_prepare, action, args, cid, row, now())
    if isinstance(plan, str):  # usage / validation message, nothing written
        context.user_data.pop("last_simulate", None)
        await _say(update, plan)
        return
    status, trigger, meta = plan
    await _say(update, f"🧪 Simulated: {status}")
    if trigger is None:
        return
    meta = {**meta, "initiated_by": "customer"}  # customer asked: answered even in quiet hours
    decision = await asyncio.to_thread(ports.decide, cid, trigger, meta)
    await sender.send_decision(context.bot, update.effective_chat.id, decision)


def _prepare(action: str, args: list[str], cid: str, row, at: datetime):
    """Writes the events for one action. Returns (status line, trigger | None, meta) or a usage string."""
    arg = args[0] if args else None
    if action == "cart":
        category = _category(arg) or _favourite_category(row)
        item, value = store.pick_product(category, f"{cid}{at:%Y%m%d%H%M}")
        added = at - timedelta(minutes=CART_MINUTES)
        store.add_events(
            cid,
            [
                {"type": "session", "ts": added - timedelta(minutes=6), "category": category},
                {
                    "type": "view",
                    "ts": added - timedelta(minutes=4),
                    "category": category,
                    "item": item,
                    "value": value,
                },
                {"type": "add_to_cart", "ts": added, "category": category, "item": item, "value": value},
            ],
        )
        meta = {"category": category, "item": item, "value": value, "minutes": CART_MINUTES}
        return f"added {escape(item)} {inr(value)} to cart, {CART_MINUTES} min ago", "cart_abandoned", meta

    if action == "browse":
        category = _category(arg) or (None if args else _favourite_category(row))
        if category is None:
            return USAGE["browse"]
        views = [store.pick_product(category, f"{cid}{i}") for i in range(3)]
        store.add_events(
            cid,
            [
                {
                    "type": "view",
                    "ts": at - timedelta(minutes=12 - 4 * i),
                    "category": category,
                    "item": n,
                    "value": v,
                }
                for i, (n, v) in enumerate(views)
            ],
        )
        label = CATEGORY_LABELS[category]
        meta = {"category": category, "views": len(views)}
        return f"browsed {len(views)} {label.lower()} items in the last 12 min", "browse_interest", meta

    if action == "purchase":
        cart = store.open_cart(cid)
        if cart is not None:
            category, item, value = cart.category, cart.item, cart.value
        else:
            category = _category(arg) or _favourite_category(row)
            item, value = store.pick_product(category, f"{cid}{at:%Y%m%d%H}buy")
        store.add_order(cid, category, item, value, at)
        return f"bought {escape(item)} for {inr(value)} just now. No offer needed after a purchase.", None, {}

    if action == "inactive":
        try:
            days = max(7, min(int(arg), 365)) if arg else 30
        except ValueError:
            return "How many days? e.g. /simulate inactive 60"
        moved = store.shift_activity(cid, days)
        detail = f" ({moved} past events moved back)" if moved else ""
        return f"no visits or orders for {days} days{detail}", "inactivity", {"days": days}

    if action == "points_expiry":
        points, expires = 500, (at + timedelta(days=3)).date()
        store.add_points(cid, points, expires, at - timedelta(days=87))
        meta = {"points": points, "expires_on": expires.isoformat()}
        return f"{points} reward points expire on {expires:%d %b}", "points_expiry", meta

    if action == "festival":
        festival = find_festival(ports.festivals(), arg, at.date())
        if festival is None:
            return USAGE["festival"]
        phase = (
            args[1].lower()
            if len(args) > 1 and args[1].lower() in PHASES
            else festival_phase(festival, at.date())
        )
        days = (festival.date - at.date()).days
        when = f"{days} days away" if days > 0 else "today" if days == 0 else f"{-days} days ago"
        meta = {"festival": festival.id, "phase": phase, "days_to_festival": days}
        return f"{festival.name} season, {PHASE_LABELS[phase]} phase ({when})", "festival", meta

    if action == "payday":
        return "it's payday (1st of the month), salaries just landed", "payday", {"day": 1}

    if action == "persona":
        options = get_args(Persona)
        if arg not in options:
            return USAGE["persona"].format(options=", ".join(options))
        store.set_persona(cid, arg)
        label = PERSONA_LABELS.get(arg, arg)
        return f"you now shop like: {label}. Try /simulate cart to see the difference.", None, {}

    return "Try /simulate for the menu."
