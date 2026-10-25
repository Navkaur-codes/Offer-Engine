"""Runs the proactive jobs inside the web process (one Render instance, so no double runs)."""

from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot

from app.config import IST, settings
from app.scheduler import jobs

log = logging.getLogger(__name__)

SCHEDULE = {  # job -> APScheduler trigger kwargs (IST)
    "cart_abandonment": {"trigger": "interval", "minutes": 5},
    "flush_quiet_queue": {"trigger": "cron", "hour": 9, "minute": 5},
    "points_expiry": {"trigger": "cron", "hour": 10, "minute": 0},
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
        log.info("scheduler %s", summary)
        return summary
    except Exception as exc:  # a broken job must not stop the others
        log.exception("scheduler job %s failed: %s", name, type(exc).__name__)
        return {"job": name, "error": type(exc).__name__}


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
