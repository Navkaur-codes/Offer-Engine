"""The only way one session's code calls another's (CLAUDE.md §4).

Each port resolves lazily: if the owning session's real module + attribute exist, it is used; otherwise the
fixture-based stub in `app.stubs` answers. A real module that exists but fails to import raises — we never
silently hide a broken implementation behind a stub.
"""

from __future__ import annotations

import importlib
import logging
from collections.abc import Callable
from datetime import date, datetime
from functools import cache
from typing import Any

from app import stubs
from app.contracts import (
    Channel,
    Context,
    Customer,
    CustomerProfile,
    Decision,
    EffectivePolicy,
    ExperimentStats,
    Explanation,
    Festival,
    Offer,
    OfferCandidate,
    OfferType,
    PolicyName,
    RealismStats,
    Rule,
    TriggerType,
    ValidationResult,
)

log = logging.getLogger(__name__)

# port name -> (module, attribute, stub)
_PORTS: dict[str, tuple[str, str, Any]] = {
    # Session A — data & scoring
    "seed_run": ("app.data.seed", "run", stubs.seed_run),
    "festivals": ("app.data.festivals", "FESTIVALS", stubs.FESTIVALS),
    "create_profile_from_answers": (
        "app.data.onboarding",
        "create_profile_from_answers",
        stubs.create_profile_from_answers,
    ),
    "build_profile": ("app.scoring.profile", "build_profile", stubs.build_profile),
    "assign_policy": ("app.scoring.profile", "assign_policy", stubs.assign_policy),
    "uplift_predict": ("app.scoring.uplift", "predict", stubs.uplift_predict),
    "impact_estimate": ("app.scoring.impact", "estimate", stubs.impact_estimate),
    "realism_compute": ("app.scoring.realism", "compute", stubs.realism_compute),
    "experiments_compute": ("app.scoring.experiments", "compute", stubs.experiments_compute),
    # Session B — decision core
    "effective_policy": ("app.rules.engine", "effective_policy", stubs.effective_policy),
    "allowed_offers": ("app.rules.engine", "allowed_offers", stubs.allowed_offers),
    "evaluate": ("app.rules.engine", "evaluate", stubs.evaluate),
    "describe_rule": ("app.rules.describe", "describe", stubs.describe_rule),
    "ensure_rules_seeded": ("app.rules.seed_rules", "ensure_seeded", stubs.ensure_rules_seeded),
    "rule_impact": ("app.rules.preview", "impact", stubs.rule_impact),
    "get_context": ("app.agent.context", "get_context", stubs.get_context),
    "decide": ("app.agent.harness", "decide", stubs.decide),
    "explain": ("app.agent.explainer", "explain", stubs.explain),
    "daily_digest": ("app.agent.digest", "daily", stubs.daily_digest),
    # Session C — telegram & lab
    "deliver": ("app.bot.sender", "deliver", stubs.deliver),
    "build_application": ("app.bot.app", "build_application", stubs.build_application),
    "set_bot_commands": ("app.bot.app", "set_commands", stubs.set_bot_commands),
    "run_rounds": ("app.lab.runner", "run_rounds", stubs.run_rounds),
}


@cache
def _resolve(name: str) -> tuple[Any, bool]:
    module_name, attr, stub = _PORTS[name]
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name:  # the module simply isn't written yet
            return stub, False
        raise
    if hasattr(module, attr):
        return getattr(module, attr), True
    return stub, False


def _call(name: str) -> Callable[..., Any]:
    return _resolve(name)[0]


def status() -> dict[str, str]:
    """{"decide": "real" | "stub", ...} — shown in /health and used at phase gates."""
    return {name: ("real" if _resolve(name)[1] else "stub") for name in _PORTS}


def reset_cache() -> None:
    _resolve.cache_clear()


# ---------------------------------------------------------------- Session A
def seed_run(n_customers: int = 5000, seed: int = 42) -> None:
    return _call("seed_run")(n_customers=n_customers, seed=seed)


def festivals() -> list[Festival]:
    return _call("festivals")


def create_profile_from_answers(telegram_id: int, first_name: str, answers: dict) -> Customer:
    return _call("create_profile_from_answers")(telegram_id, first_name, answers)


def build_profile(customer_id: str, now: datetime) -> CustomerProfile:
    return _call("build_profile")(customer_id, now)


def assign_policy(profile: CustomerProfile) -> PolicyName:
    return _call("assign_policy")(profile)


def uplift_predict(profile: CustomerProfile, offer_type: OfferType) -> float:
    return _call("uplift_predict")(profile, offer_type)


def impact_estimate(
    profile: CustomerProfile, offer_type: OfferType, params: dict, category: str | None
) -> tuple[int, int]:
    return _call("impact_estimate")(profile, offer_type, params, category)


def realism_compute() -> RealismStats:
    return _call("realism_compute")()


def experiments_compute(start: date, end: date) -> ExperimentStats:
    return _call("experiments_compute")(start, end)


# ---------------------------------------------------------------- Session B
def effective_policy(profile: CustomerProfile, context: Context) -> EffectivePolicy:
    return _call("effective_policy")(profile, context)


def allowed_offers(
    profile: CustomerProfile, context: Context, catalogue: list[Offer]
) -> list[OfferCandidate]:
    return _call("allowed_offers")(profile, context, catalogue)


def evaluate(
    profile: CustomerProfile, context: Context, offer_id: str | None, params: dict, message: str | None = None
) -> ValidationResult:
    return _call("evaluate")(profile, context, offer_id, params, message)


def describe_rule(rule: Rule) -> str:
    return _call("describe_rule")(rule)


def ensure_rules_seeded() -> int:
    """Insert missing seed rules into the `rules` table (never overwrites a marketer's edit)."""
    return _call("ensure_rules_seeded")()


def rule_impact(rule: Rule) -> dict:
    return _call("rule_impact")(rule)


def get_context(now: datetime) -> Context:
    return _call("get_context")(now)


def decide(
    customer_id: str,
    trigger: TriggerType,
    trigger_meta: dict | None = None,
    *,
    dry_run: bool = False,
    now: datetime | None = None,
) -> Decision:
    return _call("decide")(customer_id, trigger, trigger_meta or {}, dry_run=dry_run, now=now)


def explain(decision: Decision) -> Explanation:
    return _call("explain")(decision)


def daily_digest(day: date) -> str:
    return _call("daily_digest")(day)


# ---------------------------------------------------------------- Session C
def deliver(decision: Decision, channel: Channel) -> None:
    return _call("deliver")(decision, channel)


def build_application():
    return _call("build_application")()


async def set_bot_commands(application) -> None:
    """Fills the bot's "/" menu; post_init only runs under polling, so the webhook boot calls this."""
    await _call("set_bot_commands")(application)


def run_rounds(n: int) -> list[Decision]:
    return _call("run_rounds")(n)
