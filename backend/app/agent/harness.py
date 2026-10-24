"""decide(): the one decision pipeline (context-2 Phase 2, CLAUDE.md §3).

pre-gate → effective policy → candidates → agent (≤ 1 retry) → evaluate() → rules fallback → coupon → log.

The harness is the only writer: it persists every decision, including blocked, held-out and no-offer ones.
It never sends anything — the bot (or the scheduler, for queued ones) delivers the returned Decision.
"""

from __future__ import annotations

import json
import logging
import re
import secrets
import time as timer
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from app import decision_store, ports, runtime
from app.agent import fallback, prompts
from app.agent.context import festival_key, get_context
from app.agent.explainer import explain, placeholder
from app.agent.llm import LLMClient, LLMError, LLMRateLimited, LLMTimeout
from app.config import IST, settings
from app.config import now as clock
from app.contracts import (
    AgentOutput,
    Context,
    CustomerProfile,
    Decision,
    DecisionStatus,
    Offer,
    OfferCandidate,
    Rule,
    ToolCall,
    TriggerType,
    ValidationResult,
)
from app.rules.engine import effective_policy, evaluate, load_rules, screen_offers
from app.rules.offers import load_offers

log = logging.getLogger(__name__)

AGENT_TIMEOUT_S = 20.0
EXPIRY_DAYS = 2
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I
DRY_RUN_CODE = "PREVIEW"
NOTHING_PAYS = "no allowed offer is expected to pay for itself"


# ---------------------------------------------------------------- reads (the harness's only DB inputs)
@dataclass
class CustomerFlags:
    opted_out: bool = False
    paused_until: datetime | None = None
    is_holdout: bool = False
    is_lab_bot: bool = False
    telegram_chat_id: int | None = None
    opt_in_festivals: list[str] = field(default_factory=list)


def customer_flags(customer_id: str) -> CustomerFlags:
    from app.db import engine as db_engine
    from app.models import CustomerRow

    try:
        with Session(db_engine) as s:
            row = s.get(CustomerRow, customer_id)
    except SQLAlchemyError:
        log.warning("customers table not readable; treating %s as a default customer", customer_id)
        return CustomerFlags()
    if row is None:
        return CustomerFlags()
    paused = row.paused_until
    if paused is not None and paused.tzinfo is None:
        paused = paused.replace(tzinfo=IST)
    return CustomerFlags(
        opted_out=row.opted_out,
        paused_until=paused,
        is_holdout=row.is_holdout,
        is_lab_bot=row.is_lab_bot,
        telegram_chat_id=row.telegram_chat_id,
        opt_in_festivals=list(row.opt_in_festivals or []),
    )


def default_llm() -> LLMClient | None:
    """Phase 2 has no real model: decisions go to the rules fallback unless a client is passed in."""
    return None


# ---------------------------------------------------------------- small helpers
def new_decision_id(now: datetime) -> str:
    return f"D{now.astimezone(IST):%Y%m%d}-{secrets.token_hex(3).upper()}"


def coupon_code(offer_type: str, first_name: str) -> str:
    letters = re.sub(r"[^A-Z]", "", first_name.upper())
    name3 = (letters + "XXX")[:3]
    tail = "".join(secrets.choice(CODE_ALPHABET) for _ in range(4))
    return f"{fallback.coupon_prefix(offer_type)}{name3}{tail}"


def fill_code(message: str, offer_type: str, code: str | None) -> str:
    if offer_type in fallback.NO_COUPON_TYPES or code is None:
        return message.replace(" Code {CODE}.", "").replace("{CODE}", "").strip()
    if "{CODE}" in message:
        return message.replace("{CODE}", code)
    return f"{message.rstrip()} Code {code}."


def next_send_time(now: datetime, rules: list[Rule]) -> datetime:
    quiet = next((r for r in rules if r.enabled and r.type == "quiet_hours" and not r.conditions), None)
    end = time.fromisoformat((quiet.params if quiet else {}).get("end", "09:00"))
    local = now.astimezone(IST)
    send = datetime.combine(local.date(), end, IST)
    return send if send > local else send + timedelta(days=1)


def expiry(send_at: datetime, ctx: Context) -> datetime:
    local = send_at.astimezone(IST)
    expires = datetime.combine(local.date() + timedelta(days=EXPIRY_DAYS), time(23, 59), IST)
    # before a festival, an offer that can't arrive in time shouldn't outlive the delivery cutoff
    cutoff = ctx.delivery_cutoff
    if cutoff and ctx.festival_phase in {"build_up", "last_minute"} and cutoff > local.date():
        expires = min(expires, datetime.combine(cutoff, time(23, 59), IST))
    return expires


def with_trigger(
    profile: CustomerProfile, trigger: TriggerType, meta: dict, now: datetime
) -> CustomerProfile:
    """A cart trigger carries the cart; show it on the profile even if events haven't been scored yet."""
    if trigger != "cart_abandoned" or profile.open_cart is not None or not meta.get("item"):
        return profile
    minutes = int(meta.get("minutes", 30))
    cart = {
        "category": meta.get("category"),
        "item": meta["item"],
        "value": int(meta.get("value", 0)),
        "since": (now - timedelta(minutes=minutes)).isoformat(),
    }
    return profile.model_copy(update={"open_cart": cart})


def _rule_types(rules: list[Rule]) -> dict[str, str]:
    return {r.id: r.type for r in rules}


# ---------------------------------------------------------------- the agent step
@dataclass
class AgentResult:
    output: AgentOutput | None = None
    offer: OfferCandidate | None = None
    params: dict = field(default_factory=dict)
    message: str = ""
    code: str | None = None
    validation: ValidationResult | None = None
    decided_by: str | None = None
    failure: str | None = None
    trace: list[ToolCall] = field(default_factory=list)
    tokens: int = 0


def _facts(
    profile: CustomerProfile,
    ctx: Context,
    trigger: TriggerType,
    meta: dict,
    policy_summary: list[str],
    candidates: list[OfferCandidate],
    expires_at: datetime,
    greeting: str | None,
) -> dict:
    top = sorted(profile.category_affinity, key=lambda c: -profile.category_affinity[c])[:3]
    cart = profile.open_cart or None
    return {
        "trigger": trigger,
        "trigger_meta": {
            k: v for k, v in meta.items() if k in {"category", "item", "value", "minutes", "days"}
        },
        "customer": {
            "policy": profile.policy,
            "persona": profile.persona,
            "segment": profile.rfm.get("segment"),
            "city_tier": profile.city_tier,
            "recency_days": profile.recency_days,
            "orders_90d": profile.orders_90d,
            "aov": profile.aov,
            "churn_risk": round(profile.churn_risk, 2),
            "price_sensitivity": round(profile.price_sensitivity, 2),
            "points_balance": profile.points_balance,
            "tier": profile.tier,
            "top_categories": top,
            "open_cart": {k: cart.get(k) for k in ("category", "item", "value")} if cart else None,
            "uplift": {k: round(v, 3) for k, v in profile.uplift.items()},
        },
        "context": {
            "festival": ctx.festival,
            "phase": ctx.festival_phase,
            "days_to_festival": ctx.days_to_festival,
            "hero_categories": ctx.hero_categories,
            "greeting": greeting,  # only when the customer opted in; otherwise say "festive season" at most
            "payday_window": ctx.is_payday_window,
        },
        "policy": policy_summary,
        "candidates": [c.model_dump(mode="json") for c in candidates],
        "expiry": f"{expires_at.astimezone(IST):%d %b}",
    }


def run_agent(
    llm: LLMClient,
    profile: CustomerProfile,
    ctx_eval: Context,
    facts: dict,
    candidates: list[OfferCandidate],
    rules: list[Rule],
    catalogue: list[Offer],
    *,
    dry_run: bool,
) -> AgentResult:
    result = AgentResult()
    messages = [
        {"role": "system", "content": prompts.SYSTEM_PROMPT},
        {"role": "user", "content": prompts.user_message(facts, {"first_name": profile.first_name})},
    ]
    by_id = {c.offer_id: c for c in candidates}
    for attempt in (1, 2):
        started = timer.perf_counter()
        try:
            resp = llm.chat(messages, None, AGENT_TIMEOUT_S)
        except LLMTimeout:
            result.failure = "the agent timed out"
        except LLMRateLimited:
            result.failure = "the LLM rate limit was hit (429)"
        except LLMError as exc:
            result.failure = f"the LLM call failed ({exc.__class__.__name__})"
        ms = int((timer.perf_counter() - started) * 1000)
        if result.failure:
            result.trace.append(
                ToolCall(name="llm", args={"attempt": attempt}, result_summary=result.failure, ms=ms)
            )
            return result
        result.tokens += resp.tokens
        try:
            out = AgentOutput.model_validate_json(resp.content)
        except ValidationError:
            result.trace.append(
                ToolCall(name="llm", args={"attempt": attempt}, result_summary="invalid JSON", ms=ms)
            )
            result.failure = "the agent returned invalid JSON"
            return result
        result.output = out
        summary = f"{out.decision} {out.offer_id or ''} {json.dumps(out.params)}".strip()
        result.trace.append(ToolCall(name="llm", args={"attempt": attempt}, result_summary=summary, ms=ms))

        if out.decision == "NO_OFFER":
            result.decided_by = "AGENT" if attempt == 1 else "AGENT_RETRY"
            return result
        cand = by_id.get(out.offer_id or "")
        otype = cand.type if cand else next((o.type for o in catalogue if o.id == out.offer_id), "pct_off")
        code = DRY_RUN_CODE if dry_run else coupon_code(otype, profile.first_name)
        message = fill_code(out.message, otype, code)
        res = evaluate(profile, ctx_eval, out.offer_id, out.params, message, rules=rules, catalogue=catalogue)
        result.validation = res
        if res.ok and cand is not None:
            result.offer, result.params, result.message, result.code = cand, out.params, message, code
            result.decided_by = "AGENT" if attempt == 1 else "AGENT_RETRY"
            return result
        problems = [f"{v.rule_id}: {v.detail}" for v in res.violations] or [
            "offer is not in the candidate list"
        ]
        if attempt == 1:
            messages += [
                {"role": "assistant", "content": resp.content},
                {"role": "user", "content": prompts.retry_message(problems)},
            ]
        else:
            result.failure = f"the agent's offer was rejected twice ({problems[0]})"
    return result


# ---------------------------------------------------------------- decide
def decide(
    customer_id: str,
    trigger: TriggerType,
    trigger_meta: dict | None = None,
    *,
    dry_run: bool = False,
    now: datetime | None = None,
    llm: LLMClient | None = None,
) -> Decision:
    started = timer.perf_counter()
    now = now or clock()
    meta = dict(trigger_meta or {})
    rules = load_rules()
    catalogue = load_offers()
    profile = with_trigger(ports.build_profile(customer_id, now), trigger, meta, now)
    ctx = get_context(now, rules=rules)
    flags = customer_flags(customer_id)
    policy = effective_policy(profile, ctx, rules=rules)
    base = dict(
        id=new_decision_id(now),
        ts=now,
        customer_id=customer_id,
        trigger=trigger,
        trigger_meta=meta,
        profile_snapshot=profile,
        context=ctx,
        effective_policy=policy,
        is_holdout=flags.is_holdout,
        explanation=placeholder(now),
    )

    def finish(**fields) -> Decision:
        d = Decision(**base, **fields)
        d = d.model_copy(update={"latency_ms": int((timer.perf_counter() - started) * 1000)})
        d = d.model_copy(update={"explanation": explain(d)})
        if not dry_run:
            try:
                decision_store.save(d)  # the one shared writer; every status is logged
            except SQLAlchemyError:
                log.exception("could not log decision %s", d.id)
        log.info("decision %s %s %s %s", d.id, d.customer_id, d.status, d.decided_by)
        return d

    def stop(status: DecisionStatus, reason: str, validation: ValidationResult | None = None) -> Decision:
        return finish(
            decided_by="BLOCKED_PREGATE", status=status, fallback_reason=reason, validation=validation
        )

    # 1. pre-gate: switches and consent first, then the same evaluate() everything else uses
    if runtime.killswitch_on():
        return stop("BLOCKED", "the kill switch is on, so all sends are paused")
    if flags.opted_out:
        return stop("BLOCKED", "the customer opted out with /stop")
    if flags.paused_until and flags.paused_until > now:
        return stop("BLOCKED", f"the customer paused offers until {flags.paused_until.astimezone(IST):%d %b}")
    gate = evaluate(profile, ctx, None, {}, rules=rules, catalogue=catalogue)
    types = _rule_types(rules)
    hard = [v for v in gate.violations if v.severity == "hard"]
    queued = bool(hard) and all(types.get(v.rule_id) == "quiet_hours" for v in hard)
    if hard and not queued:
        blocking = next((v for v in hard if types.get(v.rule_id) != "quiet_hours"), hard[0])
        status = "NO_OFFER" if types.get(blocking.rule_id) == "exclusion" else "BLOCKED"
        return stop(status, blocking.detail, gate)

    send_at, ctx_eval = now, ctx
    if queued:
        send_at = next_send_time(now, rules)
        ctx_eval = get_context(send_at, rules=rules)
        later = evaluate(profile, ctx_eval, None, {}, rules=rules, catalogue=catalogue)
        if not later.ok:
            v = next(v for v in later.violations if v.severity == "hard")
            return stop("BLOCKED", v.detail, later)

    # 2. policy → candidates
    candidates, _ = screen_offers(profile, ctx_eval, catalogue, rules=rules)
    base["candidates"] = candidates
    if not candidates:
        return finish(
            decided_by="RULES_FALLBACK",
            status="NO_OFFER",
            fallback_reason="no offer passes this customer's rules",
            validation=gate,
        )

    expires_at = expiry(send_at, ctx_eval)
    opted = ctx.festival and festival_key(ctx.festival) in flags.opt_in_festivals
    greeting = ctx.greeting if opted else None

    def sent_fields(
        cand: OfferCandidate, params: dict, headline: str, message: str, code: str | None
    ) -> dict:
        cost, profit = ports.impact_estimate(
            profile, cand.type, params, params.get("category", cand.category)
        )
        if flags.is_holdout:
            status, channel, code = "HELD_OUT", "none", None
        elif dry_run:
            status, channel, code = "DRY_RUN", "none", None
        else:
            status = "QUEUED" if queued else "SENT"
            channel = (
                "lab_group" if flags.is_lab_bot else ("dm" if flags.telegram_chat_id else "shadow_channel")
            )
        return dict(
            status=status,
            channel=channel,
            final_offer_id=cand.offer_id,
            final_params=params,
            coupon_code=code if cand.type not in fallback.NO_COUPON_TYPES else None,
            expires_at=expires_at if cand.type not in fallback.NO_COUPON_TYPES else None,
            headline=headline,
            message=message,
            cost=cost,
            expected_incremental_profit=profit,
        )

    def use_fallback(reason: str, extra: dict) -> Decision:
        choice = fallback.choose(candidates)
        decided_by = "HOLDOUT" if flags.is_holdout else "RULES_FALLBACK"
        if choice is None:
            status = "HELD_OUT" if flags.is_holdout else "NO_OFFER"
            return finish(
                decided_by=decided_by,
                status=status,
                validation=gate,
                **extra,
                fallback_reason=f"{reason}; {NOTHING_PAYS}",
            )
        cand, params = choice.candidate, choice.params
        headline, text = fallback.template(profile, trigger, cand.type, params, expires_at, greeting)
        code = DRY_RUN_CODE if (dry_run or flags.is_holdout) else coupon_code(cand.type, profile.first_name)
        message = fill_code(text, cand.type, code)
        res = evaluate(profile, ctx_eval, cand.offer_id, params, message, rules=rules, catalogue=catalogue)
        if not res.ok:  # should be impossible (property-tested); never send it anyway
            log.error(
                "fallback offer %s failed validation: %s", cand.offer_id, [v.rule_id for v in res.violations]
            )
            return finish(
                decided_by=decided_by,
                status="NO_OFFER",
                validation=res,
                **extra,
                fallback_reason=f"{reason}; the fallback offer failed validation",
            )
        return finish(
            decided_by=decided_by,
            validation=res,
            fallback_reason=reason,
            **extra,
            **sent_fields(cand, params, headline, message, code),
        )

    # 3. holdout: decide like the fallback would, log it, send nothing
    if flags.is_holdout:
        return use_fallback("holdout group (control): logged, not sent", {})

    # 4. agent → evaluate → retry once → fallback
    llm = llm if llm is not None else default_llm()
    if llm is None or settings.force_llm_fail:
        why = (
            "the LLM is forced off (FORCE_LLM_FAIL)"
            if settings.force_llm_fail
            else "no LLM is configured yet"
        )
        return use_fallback(why, {})
    facts = _facts(profile, ctx_eval, trigger, meta, policy.summary, candidates, expires_at, greeting)
    agent = run_agent(llm, profile, ctx_eval, facts, candidates, rules, catalogue, dry_run=dry_run)
    extra = {"agent_trace": agent.trace, "agent_output": agent.output, "llm_tokens": agent.tokens}
    if agent.decided_by and agent.offer is None:
        return finish(
            decided_by=agent.decided_by,
            status="NO_OFFER",
            validation=gate,
            **extra,
            fallback_reason="the agent judged that no offer is worth its cost",
        )
    if agent.decided_by:
        out = agent.output
        return finish(
            decided_by=agent.decided_by,
            validation=agent.validation,
            **extra,
            **sent_fields(agent.offer, agent.params, out.headline, agent.message, agent.code),
        )
    return use_fallback(agent.failure or "the agent gave no usable answer", extra)
