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
from app.agent import budget, fallback, prompts, tools
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
from app.rules.rule_types import NO_COUPON_TYPES, estimate_offer, offer_expiry

log = logging.getLogger(__name__)

AGENT_TIMEOUT_S = 20.0
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I
DRY_RUN_CODE = "PREVIEW"
NOTHING_PAYS = "no allowed offer is expected to pay for itself"
WELCOME_GUARANTEE = "welcome guarantee: a first-time customer always gets a free perk"


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


def is_first_decision(customer_id: str) -> bool:
    try:
        return not decision_store.query(customer_id=customer_id, limit=1)
    except SQLAlchemyError:
        return True


def pick_llm(now: datetime) -> tuple[LLMClient | None, budget.Kind | None, str | None]:
    """(client, budget kind to charge, why there is none). The budget guard picks 70B → 8B → rules."""
    if settings.force_llm_fail:
        return None, None, "the LLM is forced off (FORCE_LLM_FAIL)"
    if not settings.groq_api_key:
        return None, None, "no LLM is configured"
    target = budget.model_for(budget.mode(now))
    if target is None:
        return None, None, budget.EXHAUSTED_REASON
    kind, model = target
    from app.agent.groq_client import GroqClient

    return GroqClient(model), kind, None


# ---------------------------------------------------------------- small helpers
def new_decision_id(now: datetime) -> str:
    return f"D{now.astimezone(IST):%Y%m%d}-{secrets.token_hex(3).upper()}"


def coupon_code(offer_type: str, first_name: str) -> str:
    letters = re.sub(r"[^A-Z]", "", first_name.upper())
    name3 = (letters + "XXX")[:3]
    tail = "".join(secrets.choice(CODE_ALPHABET) for _ in range(4))
    return f"{fallback.coupon_prefix(offer_type)}{name3}{tail}"


def fill_code(message: str, offer_type: str, code: str | None) -> str:
    if offer_type in NO_COUPON_TYPES or code is None:
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
MAX_TOOL_STEPS = 3  # single-call design: normally 0 tools; at most one check_offer, hard cap 3 steps


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


def facts_for(
    profile: CustomerProfile,
    ctx: Context,
    trigger: TriggerType,
    meta: dict,
    policy_summary: list[str],
    candidates: list[OfferCandidate],
    expires_at: datetime,
    greeting: str | None,
) -> dict:
    """Everything the agent needs, pre-computed, so a normal decision is one LLM call."""
    return {
        "trigger": trigger,
        "trigger_meta": {
            k: v for k, v in meta.items() if k in {"category", "item", "value", "minutes", "days"}
        },
        "customer": tools.profile_summary(profile),
        "recent_events": tools.recent_events(profile.customer_id, ctx.now),
        "context": tools.context_summary(ctx, greeting),
        "policy": policy_summary,
        "candidates": [tools.candidate_summary(c) for c in candidates],
        "expiry": f"{expires_at.astimezone(IST):%d %b}",
    }


def parse_output(content: str) -> AgentOutput:
    """Strict JSON, but tolerate a ```json fence or a sentence around the object."""
    text = content.strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end < start:
        raise ValueError("no JSON object")
    return AgentOutput.model_validate_json(text[start : end + 1])


def _ask(llm: LLMClient, messages: list[dict], box: tools.ToolBox, result: AgentResult, attempt: int):
    """One answer from the model, after at most MAX_TOOL_STEPS read-only tool calls. None on failure."""
    for step in range(MAX_TOOL_STEPS + 1):
        offered = tools.TOOL_SCHEMAS if step < MAX_TOOL_STEPS else None  # the last step must answer
        started = timer.perf_counter()
        try:
            resp = llm.chat(messages, offered, AGENT_TIMEOUT_S)
        except LLMTimeout:
            result.failure = "the agent timed out"
        except LLMRateLimited:
            result.failure = "the LLM rate limit was hit (429)"
        except LLMError as exc:
            result.failure = f"the LLM call failed ({exc.__class__.__name__})"
        ms = int((timer.perf_counter() - started) * 1000)
        args = {"attempt": attempt, "step": step + 1}
        if result.failure:
            result.trace.append(ToolCall(name="llm", args=args, result_summary=result.failure, ms=ms))
            return None
        result.tokens += resp.tokens
        if not resp.tool_calls:
            result.trace.append(ToolCall(name="llm", args=args, result_summary="answered", ms=ms))
            return resp
        names = ", ".join(c["name"] for c in resp.tool_calls)
        result.trace.append(ToolCall(name="llm", args=args, result_summary=f"asked for {names}", ms=ms))
        messages.append(
            {
                "role": "assistant",
                "content": resp.content or "",
                "tool_calls": [
                    {
                        "id": c["id"],
                        "type": "function",
                        "function": {"name": c["name"], "arguments": c["arguments"]},
                    }
                    for c in resp.tool_calls
                ],
            }
        )
        for call in resp.tool_calls:
            t0 = timer.perf_counter()
            out = box.run(call["name"], call["arguments"])
            result.trace.append(
                ToolCall(
                    name=call["name"],
                    args={"raw": str(call["arguments"])[:200]},
                    result_summary=out[:200],
                    ms=int((timer.perf_counter() - t0) * 1000),
                )
            )
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": out})
    result.failure = "the agent kept calling tools instead of answering"
    return None


def run_agent(
    llm: LLMClient,
    profile: CustomerProfile,
    ctx_eval: Context,
    facts: dict,
    candidates: list[OfferCandidate],
    box: tools.ToolBox,
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
        resp = _ask(llm, messages, box, result, attempt)
        if resp is None:
            return result
        try:
            out = parse_output(resp.content)
        except (ValueError, ValidationError):
            result.trace.append(ToolCall(name="parse", args={}, result_summary="invalid JSON", ms=0))
            result.failure = "the agent returned invalid JSON"
            return result
        result.output = out
        if out.decision == "NO_OFFER":
            result.decided_by = "AGENT" if attempt == 1 else "AGENT_RETRY"
            return result
        cand = by_id.get(out.offer_id or "")
        otype = cand.type if cand else next((o.type for o in catalogue if o.id == out.offer_id), "pct_off")
        code = DRY_RUN_CODE if dry_run else coupon_code(otype, profile.first_name)
        message = fill_code(out.message, otype, code)
        res = evaluate(profile, ctx_eval, out.offer_id, out.params, message, rules=rules, catalogue=catalogue)
        result.validation = res
        summary = f"{out.offer_id} {json.dumps(out.params)}: {'ok' if res.ok else 'rejected'}"
        result.trace.append(
            ToolCall(name="validate", args={"attempt": attempt}, result_summary=summary, ms=0)
        )
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
    use_agent: bool = True,
) -> Decision:
    started = timer.perf_counter()
    now = now or clock()
    meta = dict(trigger_meta or {})
    all_rules = load_rules()
    catalogue = load_offers()
    profile = with_trigger(ports.build_profile(customer_id, now), trigger, meta, now)
    ctx = get_context(now, rules=all_rules)
    # quiet hours guard proactive sends only; a reply to something the customer just did goes out now
    rules = (
        all_rules
        if runtime.quiet_hours_apply(trigger, meta)
        else [r for r in all_rules if r.type != "quiet_hours"]
    )
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

    expires_at = offer_expiry(send_at, ctx_eval)
    welcome_guaranteed = trigger == "welcome" and is_first_decision(customer_id)
    opted = ctx.festival and festival_key(ctx.festival) in flags.opt_in_festivals
    greeting = ctx.greeting if opted else None
    ctx_eval = ctx_eval.model_copy(update={"greeting": greeting})  # the validator allows only this greeting

    def sent_fields(
        cand: OfferCandidate, params: dict, headline: str, message: str, code: str | None
    ) -> dict:
        cost, profit = estimate_offer(profile, cand.type, params, params.get("category", cand.category))
        if flags.is_holdout:
            status, channel, code = "HELD_OUT", "none", None
        elif dry_run:
            status, channel, code = "DRY_RUN", "none", None
        else:
            status = "QUEUED" if queued else "SENT"
            channel = "lab_group" if flags.is_lab_bot else ("dm" if flags.telegram_chat_id else "none")
        return dict(
            status=status,
            channel=channel,
            final_offer_id=cand.offer_id,
            final_params=params,
            coupon_code=code if cand.type not in NO_COUPON_TYPES else None,
            expires_at=expires_at if cand.type not in NO_COUPON_TYPES else None,
            headline=headline,
            message=message,
            cost=cost,
            expected_incremental_profit=profit,
        )

    def use_fallback(reason: str, extra: dict) -> Decision:
        choice = fallback.choose(candidates)
        if choice is None and welcome_guaranteed:
            choice = fallback.welcome_perk(candidates)
            if choice is not None:
                reason = f"{reason}; {WELCOME_GUARANTEE}"
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

    # 4. agent → evaluate → retry once → fallback (the budget guard may hand it to the rules up front)
    kind: budget.Kind | None = "agent"
    if not use_agent:
        return use_fallback("batch rule: only the top 5 by expected profit go to the agent", {})
    if llm is None:
        llm, kind, why = pick_llm(now)
        if llm is None:
            return use_fallback(why, {})
    facts = facts_for(profile, ctx_eval, trigger, meta, policy.summary, candidates, expires_at, greeting)
    box = tools.ToolBox(profile, ctx_eval, policy, candidates, rules, catalogue, greeting)
    agent = run_agent(llm, profile, ctx_eval, facts, candidates, box, rules, catalogue, dry_run=dry_run)
    if kind is not None:
        budget.record(kind, agent.tokens, now)
    extra = {"agent_trace": agent.trace, "agent_output": agent.output, "llm_tokens": agent.tokens}
    if agent.decided_by and agent.offer is None and welcome_guaranteed:
        return use_fallback(f"the agent chose no offer; {WELCOME_GUARANTEE}", extra)
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


def decide_batch(
    items: list[tuple[str, TriggerType, dict]],
    *,
    dry_run: bool = False,
    now: datetime | None = None,
    agent_top_n: int = 5,
) -> list[Decision]:
    """Campaign dry-runs and Lab rounds (detective T26): the agent only for the top N customers by expected
    incremental profit; the rules fallback scores everyone else, so a batch can't drain the LLM budget."""
    now = now or clock()
    rules, catalogue = load_rules(), load_offers()
    ctx = get_context(now, rules=rules)

    def best_profit(item: tuple[str, TriggerType, dict]) -> int:
        cid, trigger, meta = item
        profile = with_trigger(ports.build_profile(cid, now), trigger, dict(meta), now)
        cands, _ = screen_offers(profile, ctx, catalogue, rules=rules)
        return max((c.est_incremental_profit for c in cands), default=-(10**9))

    ranked = sorted(range(len(items)), key=lambda i: -best_profit(items[i]))
    to_agent = set(ranked[:agent_top_n])
    return [
        decide(cid, trigger, meta, dry_run=dry_run, now=now, use_agent=i in to_agent)
        for i, (cid, trigger, meta) in enumerate(items)
    ]
