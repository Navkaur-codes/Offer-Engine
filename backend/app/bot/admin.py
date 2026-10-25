"""Admin commands (ADMIN_TELEGRAM_IDS only): /summary, /killswitch, /campaign run, /impersonate.

Campaigns target synthetic customers only (never classmates' TG accounts, T19) and go through
`decide_batch`, so caps, quiet hours and the top-5 agent rule (T26) all apply.
"""

from __future__ import annotations

import asyncio
import random
from collections import Counter
from typing import get_args

from sqlmodel import Session, select
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from app import db, decision_store, ports, runtime
from app.bot import commands, store
from app.bot.render import escape, inr
from app.config import now, settings
from app.contracts import PolicyName
from app.models import CustomerRow

CAMPAIGN_DEFAULT, CAMPAIGN_MAX, SCAN_LIMIT = 10, 25, 300
POLICIES: tuple[str, ...] = get_args(PolicyName)


async def _say(update: Update, text: str) -> None:
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


def admin_only(handler):
    async def guarded(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_user is None or update.effective_user.id not in settings.admin_ids:
            await _say(update, "That command is for Offer Engine admins.")
            return
        await handler(update, context)

    guarded.__name__ = handler.__name__
    return guarded


# ---------------------------------------------------------------- /summary
def summary_text() -> str:
    today = now().date()
    rows = decision_store.day_rows(today)
    status = Counter(r.status for r in rows)
    by = Counter(r.decided_by for r in rows)
    claimed = sum(r.outcome in ("claimed", "redeemed") for r in rows)
    sent = status["SENT"]
    cost = sum(r.cost for r in rows if r.status == "SENT")
    profit = sum(r.expected_incremental_profit for r in rows if r.status == "SENT")
    claim_rate = f"{claimed / sent:.0%}" if sent else "n/a"
    agent = by["AGENT"] + by["AGENT_RETRY"]
    lines = [
        f"<b>Today · {today:%a %d %b}</b>",
        f"✅ Sent <code>{sent}</code> · claimed <code>{claimed}</code> ({claim_rate})",
        f"➖ No offer <code>{status['NO_OFFER']}</code> · ✗ blocked <code>{status['BLOCKED']}</code>"
        f" · held out <code>{status['HELD_OUT']}</code> · queued <code>{status['QUEUED']}</code>",
        f"🧠 Agent <code>{agent}</code> · rules fallback <code>{by['RULES_FALLBACK']}</code>",
        f"💸 Offer cost <code>{inr(cost)}</code> · expected incremental profit <code>{inr(profit)}</code>",
        f"🛑 Kill switch: {'ON, all sends paused' if runtime.killswitch_on() else 'off'}",
    ]
    digest = ports.daily_digest(today)
    if digest:
        lines += ["", escape(digest)]
    return "\n".join(lines)


@admin_only
async def summary_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _say(update, await asyncio.to_thread(summary_text))


# ---------------------------------------------------------------- /killswitch
@admin_only
async def killswitch_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    arg = context.args[0].lower() if context.args else ""
    if arg not in ("on", "off"):
        state = "ON (all sends paused)" if await asyncio.to_thread(runtime.killswitch_on) else "off"
        await _say(update, f"🛑 Kill switch is {state}. Use /killswitch on or /killswitch off.")
        return
    await asyncio.to_thread(runtime.set_killswitch, arg == "on", f"telegram:{update.effective_user.id}")
    if arg == "on":
        await _say(update, "🛑 Kill switch ON. Every send is paused; decisions are still logged as blocked.")
    else:
        await _say(update, "▶️ Kill switch off. Sends resume, within every rule and cap.")


# ---------------------------------------------------------------- /campaign run
def campaign_targets(policy: str, n: int) -> list[str]:
    """Synthetic, non-Lab customers whose live policy matches, scanned in a random-but-daily-stable order."""
    with Session(db.engine) as s:
        ids = list(
            s.exec(
                select(CustomerRow.id).where(
                    CustomerRow.id.like("C%"),
                    CustomerRow.is_lab_bot == False,  # noqa: E712
                    CustomerRow.opted_out == False,  # noqa: E712
                )
            ).all()
        )
    random.Random(now().date().isoformat() + policy).shuffle(ids)
    at, picked = now(), []
    for cid in ids[:SCAN_LIMIT]:
        if ports.build_profile(cid, at).policy == policy:
            picked.append(cid)
            if len(picked) == n:
                break
    return picked


def run_campaign(policy: str, n: int) -> str:
    targets = campaign_targets(policy, n)
    if not targets:
        return f"No synthetic customers with policy <b>{escape(policy)}</b> right now."
    meta = {"campaign": f"telegram:{policy}", "policy": policy}
    decisions = ports.decide_batch([(cid, "campaign", meta) for cid in targets], dry_run=False)
    status = Counter(d.status for d in decisions)
    offers = Counter(d.final_offer_id for d in decisions if d.status == "SENT")
    cost = sum(d.cost for d in decisions if d.status == "SENT")
    profit = sum(d.expected_incremental_profit for d in decisions if d.status == "SENT")
    top = ", ".join(f"{escape(o)} ×{c}" for o, c in offers.most_common(3)) or "none"
    return (
        f"📣 <b>Campaign · {escape(policy)}</b> · {len(decisions)} synthetic customers\n"
        f"✅ Sent <code>{status['SENT']}</code> · ⏰ queued <code>{status['QUEUED']}</code> · "
        f"➖ no offer <code>{status['NO_OFFER']}</code> · ✗ blocked <code>{status['BLOCKED']}</code> · "
        f"held out <code>{status['HELD_OUT']}</code>\n"
        f"🎟 Top offers: {top}\n"
        f"💸 Cost <code>{inr(cost)}</code> · expected incremental profit <code>{inr(profit)}</code>\n"
        "<i>Agent for the top 5, rules fallback for the rest. Every decision is in the dashboard log.</i>"
    )


@admin_only
async def campaign_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = [a.lower() for a in context.args or []]
    if len(args) < 2 or args[0] != "run" or args[1] not in POLICIES:
        await _say(
            update,
            f"Usage: /campaign run &lt;policy&gt; [n ≤ {CAMPAIGN_MAX}]\nPolicies: {', '.join(POLICIES)}",
        )
        return
    try:
        n = max(1, min(int(args[2]), CAMPAIGN_MAX)) if len(args) > 2 else CAMPAIGN_DEFAULT
    except ValueError:
        n = CAMPAIGN_DEFAULT
    await _say(update, f"📣 Running a {args[1]} campaign on up to {n} synthetic customers…")
    # can take ~30 s (profile scan + agent calls): run in the background so the webhook returns at once
    context.application.create_task(_campaign(update, args[1], n))


async def _campaign(update: Update, policy: str, n: int) -> None:
    try:
        text = await asyncio.to_thread(run_campaign, policy, n)
    except Exception as exc:  # report, never leave the admin waiting
        text = f"⚠️ Campaign stopped ({type(exc).__name__})."
    await _say(update, text)


# ---------------------------------------------------------------- /impersonate
@admin_only
async def impersonate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    arg = context.args[0] if context.args else ""
    if arg.lower() in ("", "off", "stop"):
        was = commands.IMPERSONATING.pop(uid, None)
        await _say(
            update, f"🎭 Stopped impersonating {escape(was)}." if was else "Usage: /impersonate C000123 | off"
        )
        return
    row = await asyncio.to_thread(store.get_customer, arg.upper())
    if row is None:
        await _say(update, f"No customer {escape(arg)}.")
        return
    commands.IMPERSONATING[uid] = row.id
    profile = await asyncio.to_thread(ports.build_profile, row.id, now())
    await _say(
        update,
        f"🎭 You are now <b>{escape(row.first_name)}</b> (<code>{row.id}</code>). "
        "/profile, /simulate, /offers, /why and /history act as them; cards come to this chat. "
        "/impersonate off to stop.\n\n"
        + commands.profile_text(row, profile),
    )
