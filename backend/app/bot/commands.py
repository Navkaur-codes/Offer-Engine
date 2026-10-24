"""Customer commands (/profile /help /offers /why /pause /resume /stop) and the offer-card buttons."""

from __future__ import annotations

import asyncio
from datetime import datetime, time, timedelta

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from app import ports
from app.bot import sender, store
from app.bot.onboarding import FESTIVALS
from app.bot.render import CATEGORY_LABELS, escape, inr, offer_value, render_why
from app.config import IST, now
from app.contracts import Decision

NOT_REGISTERED = "You're not set up yet. Tap /start, it takes 20 seconds."
HELP_TEXT = (
    "<b>Offer Engine</b> · a student demo with synthetic offers\n\n"
    "/start · set up or change your preferences\n"
    "/offers · your active offers\n"
    "/why · why you got the last message\n"
    "/profile · what we know about you, in plain words\n"
    "/pause · no offers for 7 days (/pause 3 for 3 days)\n"
    "/resume · start offers again\n"
    "/stop · unsubscribe completely\n\n"
    "<i>We send at most a few offers a week, never between 9 pm and 9 am.</i>"
)
UNKNOWN_TEXT = "I work with buttons and commands, not chat. Try /help."

PERSONA_LABELS = {
    "loyal_vip": "Loyal regular",
    "deal_hunter": "Deal hunter",
    "at_risk_regular": "Regular we haven't seen lately",
    "new_user": "New shopper",
    "dormant": "Quiet for a while",
    "window_shopper": "Window shopper",
    "cart_abandoner": "Saves things in the cart for later",
    "festive_gifter": "Festive gifter",
    "high_returner": "Tries things on, returns often",
}
POLICY_LABELS = {
    "vip": "Perks and early access; you don't need discounts",
    "deal_hunter": "Small, capped discounts",
    "at_risk": "Win-back offers to welcome you back",
    "new_user": "Welcome offers for your next order",
    "cart_abandoner": "The smallest nudge to finish checkout",
    "window_shopper": "Ideas first, offers only when you're clearly interested",
    "high_returner": "Offers that fit first time",
    "sleeping_dog": "We leave you in peace; you're happy as you are",
    "dormant": "An occasional gentle hello",
    "default": "Occasional offers",
}


def _level(x: float) -> str:
    return "High" if x >= 0.6 else "Medium" if x >= 0.3 else "Low"


def _customer_id(update: Update) -> str:
    return store.customer_id_for(update.effective_user.id)


async def _reply(update: Update, text: str) -> None:
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _reply(update, HELP_TEXT)


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _reply(update, UNKNOWN_TEXT)  # customer text is data: never parsed, never sent to the LLM


def _status_line(row) -> str:
    if row.opted_out:
        return "Unsubscribed (/start to come back)"
    if row.paused_until and row.paused_until.replace(tzinfo=row.paused_until.tzinfo or IST) > now():
        return f"Paused till {row.paused_until:%d %b} (/resume)"
    return "Active"


def profile_text(row, profile) -> str:
    top = sorted(profile.category_affinity.items(), key=lambda kv: kv[1], reverse=True)[:3]
    cats = ", ".join(CATEGORY_LABELS.get(c, c) for c, _ in top) or "Still learning"
    fests = ", ".join(FESTIVALS.get(f, f) for f in (row.opt_in_festivals or [])) or "Off"
    return (
        f"<b>Your profile, {escape(profile.first_name)}</b>\n"
        f"👤 Shopper type: {PERSONA_LABELS.get(profile.persona, profile.persona)}\n"
        f"🎯 How we treat you: {POLICY_LABELS.get(profile.policy, profile.policy)}\n"
        f"❤️ Top categories: {cats}\n"
        f"💸 Price sensitivity: {_level(profile.price_sensitivity)}\n"
        f"📉 Chance you drift away: {_level(profile.churn_risk)}\n"
        f"⭐ {profile.tier} tier · {profile.points_balance:,} points · usual basket {inr(profile.aov)}\n"
        f"🎉 Festival greetings: {fests}\n"
        f"🔔 Status: {_status_line(row)}\n\n"
        "<i>Built from synthetic demo data and your /start answers.</i>"
    )


async def profile_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cid = _customer_id(update)
    row = await asyncio.to_thread(store.get_customer, cid)
    if row is None:
        await _reply(update, NOT_REGISTERED)
        return
    profile = await asyncio.to_thread(ports.build_profile, cid, now())
    await _reply(update, profile_text(row, profile))


def _decisions_for(cid: str, from_db: list[Decision]) -> list[Decision]:
    seen = {d.id: d for d in from_db}
    for d in sender.all_for(cid):
        seen.setdefault(d.id, d)
    return sorted(seen.values(), key=lambda d: d.ts, reverse=True)


def active_offers(decisions: list[Decision], at: datetime) -> list[Decision]:
    return [
        d
        for d in decisions
        if d.status == "SENT"
        and d.coupon_code
        and d.outcome in ("pending", "claimed", "remind_later")
        and (d.expires_at is None or d.expires_at > at)
    ]


async def offers_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cid = _customer_id(update)
    decisions = _decisions_for(cid, await asyncio.to_thread(store.recent_decisions, cid))
    active = active_offers(decisions, now())
    if not active:
        await _reply(
            update,
            "No active offers right now. We'll message you when something genuinely useful comes up.",
        )
        return
    lines = ["<b>Your active offers</b>"]
    for d in active[:5]:
        till = f" · till {d.expires_at:%d %b}" if d.expires_at else ""
        lines.append(f"🎟 {escape(offer_value(d))}{till}\n    <code>{escape(d.coupon_code)}</code>")
    await _reply(update, "\n".join(lines))


async def _find(decision_id: str) -> Decision | None:
    return sender.recent(decision_id) or await asyncio.to_thread(store.find_decision, decision_id)


async def why_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cid = _customer_id(update)
    decisions = _decisions_for(cid, await asyncio.to_thread(store.recent_decisions, cid, 1))
    if not decisions:
        await _reply(update, "Nothing to explain yet. Tap /start to get your welcome offer.")
        return
    await _reply(update, render_why(decisions[0]))


async def pause_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        days = int(context.args[0]) if context.args else 7
    except ValueError:
        days = 7
    days = max(1, min(days, 90))
    until = now() + timedelta(days=days)
    if not await asyncio.to_thread(store.set_paused_until, _customer_id(update), until):
        await _reply(update, NOT_REGISTERED)
        return
    await _reply(update, f"⏸ Paused till {until:%d %b}. No offers until then. /resume to restart sooner.")


async def resume_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cid = _customer_id(update)
    if not await asyncio.to_thread(store.set_paused_until, cid, None):
        await _reply(update, NOT_REGISTERED)
        return
    await asyncio.to_thread(store.set_opted_out, cid, False)
    await _reply(update, "▶️ You're back. We'll only message you when an offer genuinely fits.")


async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await asyncio.to_thread(store.set_opted_out, _customer_id(update), True)
    await _reply(
        update,
        "✋ Unsubscribed. You won't get any more offers.\nChanged your mind? Tap /start any time.",
    )


def next_evening(at: datetime) -> datetime:
    """19:00 IST today, or tomorrow if that has passed (21:00–09:00 is quiet hours)."""
    at = at.astimezone(IST)
    target = datetime.combine(at.date(), time(19, 0), IST)
    return target if target > at else target + timedelta(days=1)


async def _remind(context: ContextTypes.DEFAULT_TYPE) -> None:
    decision: Decision = context.job.data
    till = f" It's valid till {decision.expires_at:%d %b}." if decision.expires_at else ""
    code = escape(decision.coupon_code or "")
    await context.bot.send_message(
        context.job.chat_id,
        f"⏰ Reminder: {escape(offer_value(decision))}, code <code>{code}</code>.{till}",
        parse_mode=ParseMode.HTML,
    )


async def on_offer_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Phase 1: buttons respond. Phase 2 records claims/declines as events and outcomes."""
    query = update.callback_query
    _, action, decision_id = query.data.split(":", 2)
    decision = await _find(decision_id)
    if decision is None:
        await query.answer("This offer has expired.", show_alert=True)
        return
    if action == "why":
        await query.answer()
        await update.effective_message.reply_text(render_why(decision), parse_mode=ParseMode.HTML)
    elif action == "claim":
        await query.answer("Saved! ✅")
        await update.effective_message.reply_text(
            f"✅ Saved! Use code <code>{escape(decision.coupon_code or '')}</code> at checkout "
            "<i>(demo: no real purchase)</i>.",
            parse_mode=ParseMode.HTML,
        )
    elif action == "remind":
        when = next_evening(now())
        if context.job_queue is not None:
            context.job_queue.run_once(
                _remind, when, chat_id=update.effective_chat.id, data=decision, name=f"remind:{decision_id}"
            )
        await query.answer(f"⏰ I'll remind you at {when:%H:%M} on {when:%d %b}.")
    elif action == "decline":
        await query.answer("Got it, thanks for telling us. 🙏")
    else:
        await query.answer()
