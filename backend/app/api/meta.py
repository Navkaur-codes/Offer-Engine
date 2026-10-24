"""Meta, kill switch and budget: the top bar of the dashboard."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app import decision_store, ports, runtime
from app.api.deps import require_admin
from app.api.rules import daily_cap
from app.config import now, settings, time_override

router = APIRouter(prefix="/api", tags=["meta"])

BOT_USERNAME = "navpreet_offers_bot"


class KillSwitchIn(BaseModel):
    on: bool


@router.get("/meta")
def meta() -> dict:
    override = time_override()
    return {
        "bot_username": BOT_USERNAME,
        "bot_link": f"https://t.me/{BOT_USERNAME}",
        "lab_group_link": None,
        "now": now().isoformat(),
        "demo_time_override": override.isoformat() if override else None,
        "ports": ports.status(),
        "public_base_url": settings.public_base_url or None,
    }


@router.get("/settings/killswitch")
def get_killswitch() -> dict:
    value = runtime.get_setting(runtime.KILLSWITCH, {"on": False})
    return {"on": bool(value.get("on")), "changed_at": value.get("changed_at")}


@router.post("/settings/killswitch", dependencies=[Depends(require_admin)])
def set_killswitch(body: KillSwitchIn) -> dict:
    value = runtime.set_killswitch(body.on)
    return {"on": value["on"], "changed_at": value["changed_at"]}


@router.get("/budget")
def budget() -> dict:
    today = now().date()
    cap = daily_cap()
    used = decision_store.spent_on(today)
    ctx = ports.get_context(now())
    return {
        "today_used": used,
        "today_cap": cap,
        "today_used_pct": round(used / cap, 4) if cap else 0.0,
        "festival": {
            "name": ctx.festival,
            "phase": ctx.festival_phase,
            "days_to": ctx.days_to_festival,
            "budget_left": ctx.budget_left_festival,
        }
        if ctx.festival
        else None,
    }
