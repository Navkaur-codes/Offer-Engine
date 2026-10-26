"""Runs the proactive jobs inside the web process (one Render instance, so no double runs)."""

from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot

from app import ports
from app.config import IST, settings
from app.contracts import Decision
from app.scheduler import jobs

log = logging.getLogger(__name__)
_TASKS: set[asyncio.Task] = set()  # background Lab posts; referenced so they aren't garbage-collected

SCHEDULE = {  # job -> APScheduler trigger kwargs (IST)
    "cart_abandonment": {"trigger": "interval", "minutes": 5},
    "flush_quiet_queue": {"trigger": "cron", "hour": 9, "minute": 5},
    "points_expiry": {"trigger": "cron", "hour": 10, "minute": 0},
    "personal_picks": {"trigger": "cron", "hour": "11,18", "minute": 0},
    "daily_digest": {"trigger": "cron", "hour": 21, "minute": 0},
}


async def run_job(name: str) -> dict:
    """Runs one job off the event loop; failures are logged, never raised into the scheduler."""
    try:
        if name == "daily_digest":
            text = await asyncio.to_thread(jobs.daily_digest_text)
            sent = await send_to_admins(f"📊 <b>Daily digest</b>\n{text}")
            return {"job": name, "admins_messaged": sent}
        decisions = await asyncio.to_thread(jobs.JOBS[name])
        summary = {
            "job": name,
            "decisions": len(decisions),
            "sent": sum(d.status == "SENT" for d in decisions),
            "queued": sum(d.status == "QUEUED" for d in decisions),
        }
        if name == jobs.PICKS:
            summary.update(_picks_summary(decisions))
        log.info("scheduler %s", summary)
        return summary
    except Exception as exc:  # a broken job must not stop the others
        log.exception("scheduler job %s failed: %s", name, type(exc).__name__)
        return {"job": name, "error": type(exc).__name__}


def pick_row(d: Decision) -> dict:
    """One line of the dashboard's run report: who, what it was based on, what happened and why."""
    e = d.explanation
    return {
        "decision_id": d.id,
        "customer_id": d.customer_id,
        "first_name": d.profile_snapshot.first_name,
        "where": "lab" if d.channel == "lab_group" or d.trigger == "lab" else "telegram",
        "policy": d.profile_snapshot.policy,
        "category": d.trigger_meta.get("category"),
        "category_share": d.trigger_meta.get("category_share"),
        "status": d.status,
        "title": e.title,
        "offer_id": d.final_offer_id,
        "decided_by": d.decided_by,
        "cost": d.cost,
        "expected_incremental_profit": d.expected_incremental_profit,
    }


def _picks_summary(decisions: list[Decision]) -> dict:
    """Run report for the dashboard, plus the Lab posts, which run in the background so the response is quick
    (each Lab round takes a few seconds of readable pacing in the group)."""
    lab = [d for d in decisions if d.trigger == "lab"]
    if lab:
        task = asyncio.get_running_loop().create_task(_post_lab(lab))
        _TASKS.add(task)
        task.add_done_callback(_TASKS.discard)
    return {
        "blocked": sum(d.status == "BLOCKED" for d in decisions),
        "no_offer": sum(d.status == "NO_OFFER" for d in decisions),
        "spent": sum(d.cost for d in decisions if d.status == "SENT"),
        "lab_posting": len(lab),
        "rows": [pick_row(d) for d in decisions],
    }


async def _post_lab(decisions: list[Decision]) -> None:
    try:
        posted = await asyncio.to_thread(ports.post_lab_picks, decisions)
        log.info("personal picks: %d posted in the Lab group", posted)
    except Exception as exc:  # the decisions are already logged; a failed post must not crash the scheduler
        log.warning("personal picks Lab post failed: %s", type(exc).__name__)


async def send_to_admins(html: str) -> int:
    if not settings.telegram_bot_token or not settings.admin_ids:
        return 0
    sent = 0
    async with Bot(settings.telegram_bot_token) as bot:
        for chat_id in settings.admin_ids:
            try:
                await bot.send_message(chat_id, html[:4000], parse_mode="HTML")
                sent += 1
            except Exception as exc:
                log.warning("digest to admin failed: %s", type(exc).__name__)
    return sent


def start() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=IST)
    for name, trigger in SCHEDULE.items():
        scheduler.add_job(
            run_job, args=[name], id=name, coalesce=True, max_instances=1, misfire_grace_time=600, **trigger
        )
    scheduler.start()
    log.info("scheduler started: %s", ", ".join(SCHEDULE))
    return scheduler
