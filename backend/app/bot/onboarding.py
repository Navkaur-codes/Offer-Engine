"""/start: consent → categories → frequency → deal vs quality → optional festival greetings → welcome offer.

Inline buttons only (no free text), one message edited in place. State lives in `user_data["onboarding"]`;
if it's gone (bot restarted) the user is asked to /start again.
"""

from __future__ import annotations

import asyncio
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from app import ports
from app.bot import sender, store
from app.bot.render import CATEGORY_LABELS, escape, short_name

log = logging.getLogger(__name__)

FREQUENCIES = {
    "weekly": "Every week",
    "monthly": "A few times a month",
    "occasionally": "Once in a while",
    "rarely": "Only for big occasions",
}
STYLES = {"deal": "💸 Best deal", "quality": "💎 Best quality", "balanced": "⚖️ A bit of both"}
# Opt-in only (CLAUDE.md §2.9): we never infer festivals from a name. Keys match festival ids minus the year.
FESTIVALS = {
    "diwali": "Diwali",
    "gurpurab": "Gurpurab",
    "lohri": "Lohri",
    "karwa_chauth": "Karwa Chauth",
    "christmas": "Christmas",
}

CONSENT_TEXT = (
    "👋 Hi {name}! I'm <b>Offer Engine</b>. I pick the one offer that actually helps you, "
    "and stay quiet when you don't need one.\n\n"
    "<b>Heads up:</b> this is a student demo. Every offer and code is synthetic; nothing can be bought "
    "and no real shopping data is used.\n\n"
    "You can /pause or /stop at any time."
)
CATEGORY_TEXT = "<b>Step 1 of 4</b> · What do you like shopping for?\n<i>Pick as many as you like.</i>"
FREQUENCY_TEXT = "<b>Step 2 of 4</b> · How often do you shop online?"
STYLE_TEXT = "<b>Step 3 of 4</b> · When you shop, what matters more?"
FESTIVAL_TEXT = (
    "<b>Step 4 of 4</b> · Festival greetings <i>(optional)</i>\n"
    "Want a greeting and festive picks for any of these? We only send them if you choose here."
)
EXPIRED_TEXT = "That menu has expired. Tap /start to begin again."


def _state(context: ContextTypes.DEFAULT_TYPE) -> dict | None:
    return context.user_data.get("onboarding")


def _toggle_keyboard(
    options: dict[str, str], chosen: list[str], prefix: str, done_label: str, extra: list | None = None
) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(("✓ " if key in chosen else "") + label, callback_data=f"ob:{prefix}:{key}")
        for key, label in options.items()
    ]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    rows.extend(extra or [])
    rows.append([InlineKeyboardButton(done_label, callback_data=f"ob:{prefix}_done")])
    return InlineKeyboardMarkup(rows)


def _choice_keyboard(options: dict[str, str], prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(label, callback_data=f"ob:{prefix}:{key}")] for key, label in options.items()]
    )


def category_keyboard(chosen: list[str]) -> InlineKeyboardMarkup:
    done = f"Next → ({len(chosen)} picked)" if chosen else "Skip →"
    return _toggle_keyboard(CATEGORY_LABELS, chosen, "cat", done)


def festival_keyboard(chosen: list[str]) -> InlineKeyboardMarkup:
    none = [[InlineKeyboardButton("🙅 None, thanks", callback_data="ob:fest_none")]]
    return _toggle_keyboard(FESTIVALS, chosen, "fest", "Finish ✓", extra=none)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["onboarding"] = {"categories": [], "festivals": []}
    name = escape(short_name(update.effective_user.first_name))
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Sounds good, let's go", callback_data="ob:consent:yes")],
            [InlineKeyboardButton("Not now", callback_data="ob:consent:no")],
        ]
    )
    await update.effective_message.reply_text(
        CONSENT_TEXT.format(name=name), parse_mode=ParseMode.HTML, reply_markup=keyboard
    )


async def _edit(update: Update, text: str, keyboard: InlineKeyboardMarkup | None = None) -> None:
    await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    state = _state(context)
    if state is None:
        await _edit(update, EXPIRED_TEXT)
        return
    _, step, *rest = query.data.split(":", 2)
    value = rest[0] if rest else ""

    if step == "consent":
        if value != "yes":
            context.user_data.pop("onboarding", None)
            await _edit(update, "No problem. Tap /start whenever you'd like to join. 👋")
            return
        await _edit(update, CATEGORY_TEXT, category_keyboard(state["categories"]))
    elif step == "cat" and value in CATEGORY_LABELS:
        _toggle(state["categories"], value)
        await query.edit_message_reply_markup(category_keyboard(state["categories"]))
    elif step == "cat_done":
        await _edit(update, FREQUENCY_TEXT, _choice_keyboard(FREQUENCIES, "freq"))
    elif step == "freq" and value in FREQUENCIES:
        state["frequency"] = value
        await _edit(update, STYLE_TEXT, _choice_keyboard(STYLES, "style"))
    elif step == "style" and value in STYLES:
        state["style"] = value
        await _edit(update, FESTIVAL_TEXT, festival_keyboard(state["festivals"]))
    elif step == "fest" and value in FESTIVALS:
        _toggle(state["festivals"], value)
        await query.edit_message_reply_markup(festival_keyboard(state["festivals"]))
    elif step == "fest_none":
        state["festivals"] = []
        await finish(update, context)
    elif step == "fest_done":
        await finish(update, context)


def _toggle(items: list[str], value: str) -> None:
    if value in items:
        items.remove(value)
    else:
        items.append(value)


def answers_from(state: dict) -> dict:
    return {
        "categories": list(state.get("categories", [])),
        "frequency": state.get("frequency", "occasionally"),
        "style": state.get("style", "balanced"),
        "festivals": list(state.get("festivals", [])),
    }


def summary_text(answers: dict) -> str:
    cats = ", ".join(CATEGORY_LABELS[c] for c in answers["categories"]) or "Anything"
    fests = ", ".join(FESTIVALS[f] for f in answers["festivals"]) or "None"
    return (
        "<b>All set ✓</b>\n"
        f"❤️ Likes: {cats}\n"
        f"🛍 Shops: {FREQUENCIES[answers['frequency']]}\n"
        f"🎯 Prefers: {STYLES[answers['style']]}\n"
        f"🎉 Festival greetings: {fests}\n\n"
        "<i>Change these any time with /start. See your profile with /profile.</i>"
    )


async def finish(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = context.user_data.pop("onboarding")
    answers = answers_from(state)
    user = update.effective_user
    customer = await asyncio.to_thread(
        ports.create_profile_from_answers, user.id, user.first_name or "there", answers
    )
    await asyncio.to_thread(store.save_customer, customer, answers)
    await _edit(update, summary_text(answers))
    meta = {"source": "onboarding", "initiated_by": "customer"}  # customer asked: exempt from quiet hours
    decision = await asyncio.to_thread(ports.decide, customer.id, "welcome", meta)
    await sender.send_decision(context.bot, update.effective_chat.id, decision)
    log.info("onboarded %s → welcome decision %s (%s)", customer.id, decision.id, decision.status)
