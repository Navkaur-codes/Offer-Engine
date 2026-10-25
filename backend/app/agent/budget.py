"""LLM budget guard: keeps the agent inside the Groq free tier by counting tokens per model per IST day.

Degrade chain: 70B until 80% of its budget is used → 8B for the agent too → rules once both are spent.
Counters live in the runtime settings table under `llm_usage:<YYYY-MM-DD>`, so a new IST day starts at zero.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Literal

from sqlalchemy.exc import SQLAlchemyError

from app import runtime
from app.config import IST, settings
from app.config import now as clock

log = logging.getLogger(__name__)

Kind = Literal["agent", "fast"]
Mode = Literal["70b", "8b", "rules"]
SWITCH_AT = 0.8  # share of the 70B budget after which the agent drops to 8B
EXHAUSTED_REASON = "llm_budget_exhausted"


def _key(now: datetime) -> str:
    return f"llm_usage:{now.astimezone(IST):%Y-%m-%d}"


def limits() -> dict[Kind, int]:
    return {"agent": settings.llm_daily_tokens_agent, "fast": settings.llm_daily_tokens_fast}


def usage(now: datetime | None = None) -> dict[Kind, int]:
    try:
        stored = runtime.get_setting(_key(now or clock()), {})
    except SQLAlchemyError:
        log.warning("settings table not readable; assuming no LLM tokens used today")
        stored = {}
    return {"agent": int(stored.get("agent", 0)), "fast": int(stored.get("fast", 0))}


def record(kind: Kind, tokens: int, now: datetime | None = None) -> None:
    if tokens <= 0:
        return
    now = now or clock()
    used = usage(now)
    used[kind] += tokens
    try:
        runtime.set_setting(_key(now), used)
    except SQLAlchemyError:
        log.exception("could not record %d %s tokens", tokens, kind)


def mode(now: datetime | None = None) -> Mode:
    used, cap = usage(now), limits()
    if used["agent"] < SWITCH_AT * cap["agent"]:
        return "70b"
    if used["fast"] < cap["fast"]:
        return "8b"
    if used["agent"] < cap["agent"]:
        return "70b"
    return "rules"


def model_for(m: Mode) -> tuple[Kind, str] | None:
    """(budget kind to charge, Groq model id) for a mode, or None when the rules must decide."""
    if m == "70b":
        return "agent", settings.groq_model_agent
    if m == "8b":
        return "fast", settings.groq_model_fast
    return None


def status(now: datetime | None = None) -> dict:
    """For the dashboard's LLM budget meter and /health."""
    used, cap = usage(now), limits()
    return {
        "agent": {"used": used["agent"], "limit": cap["agent"], "model": settings.groq_model_agent},
        "fast": {"used": used["fast"], "limit": cap["fast"], "model": settings.groq_model_fast},
        "mode": mode(now),
    }
