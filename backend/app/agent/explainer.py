"""explain(decision): a plain-English Explanation built only from Decision fields. No LLM, so it's instant and
can't drift from what actually happened."""

from __future__ import annotations

from datetime import datetime

from app.agent.fallback import offer_value
from app.config import IST
from app.contracts import Decision, Explanation
from app.rules.engine import screen_offers
from app.rules.offers import load_offers
from app.rules.rule_types import OFFER_LABELS, POLICY_LABELS, inr

MAX_REJECTED = 4


def _offer_type(d: Decision) -> str | None:
    if d.final_offer_id is None:
        return None
    for c in d.candidates:
        if c.offer_id == d.final_offer_id:
            return c.type
    return next((o.type for o in load_offers() if o.id == d.final_offer_id), None)


def _value(d: Decision) -> str:
    otype = _offer_type(d)
    return offer_value(otype, d.final_params) if otype else (d.final_offer_id or "offer")


def _business_reason(d: Decision) -> str:
    """fallback_reason reads "<why the fallback ran>; <why no offer>"; titles need only the last part."""
    return (d.fallback_reason or "nothing worth its cost").split("; ")[-1]


def _first_violation(d: Decision) -> str:
    if d.validation and d.validation.violations:
        v = d.validation.violations[0]
        return v.detail or v.description
    return d.fallback_reason or "a rule stopped this send"


def _title(d: Decision) -> str:
    exp = f" (exp. {d.expires_at.astimezone(IST):%d %b})" if d.expires_at else ""
    name = d.profile_snapshot.first_name
    if d.status == "SENT":
        return f"Sent: {_value(d)}{exp}"
    if d.status == "QUEUED":
        return f"Queued for 09:00: {_value(d)}{exp}"
    if d.status == "DRY_RUN":
        return f"Dry run: would send {_value(d)}{exp}"
    if d.status == "HELD_OUT":
        what = _value(d) if d.final_offer_id else "no offer"
        return f"Held out: would send {what} to {name}"
    if d.status == "NO_OFFER":
        return f"No offer for {name}: {_business_reason(d)}"
    return f"Blocked: {_first_violation(d)}"


def _why_customer(d: Decision) -> str:
    p = d.profile_snapshot
    bits = [f"{POLICY_LABELS.get(p.policy, p.policy)} policy"]
    cart = p.open_cart or {}
    if cart.get("value"):
        bits.append(f"cart {inr(cart['value'])} open ({cart.get('item', 'items')})")
    bits.append(f"last order {p.recency_days} days ago")
    bits.append(f"churn risk {p.churn_risk:.2f}")
    otype = _offer_type(d)
    if otype and otype in p.uplift:
        bits.append(f"uplift {p.uplift[otype]:.2f} for {OFFER_LABELS.get(otype, otype)}")
    return f"Trigger {d.trigger.replace('_', ' ')}: " + "; ".join(bits) + "."


def _why_offer(d: Decision) -> str:
    if d.final_offer_id is None:
        if d.agent_output and d.decided_by in {"AGENT", "AGENT_RETRY"}:
            return d.agent_output.reasoning.why_offer
        return _business_reason(d).capitalize() + "."
    numbers = (
        f"{inr(d.cost)} expected cost vs {inr(d.expected_incremental_profit)} expected incremental profit."
    )
    if d.agent_output and d.decided_by in {"AGENT", "AGENT_RETRY"}:
        return f"{d.agent_output.reasoning.why_offer.rstrip('.')}. {numbers}"
    n = len(d.candidates)
    return f"{_value(d)} has the best expected incremental profit among {n} allowed offers: {numbers}"


def _rejected(d: Decision) -> list[str]:
    names = {o.id: o.name for o in load_offers()}
    out: list[str] = []
    if d.agent_output and d.decided_by in {"AGENT", "AGENT_RETRY"}:
        for alt in d.agent_output.reasoning.alternatives_rejected:
            oid = alt.get("offer_id")
            out.append(f"{names.get(oid, oid)}: {alt.get('reason', 'not chosen')}")
    if d.decided_by not in {"BLOCKED_PREGATE"}:
        _, rejected = screen_offers(
            d.profile_snapshot, d.context, load_offers(), rules=d.effective_policy.rules
        )
        by_reason: dict[str, list[str]] = {}
        for r in rejected:
            by_reason.setdefault(r["reason"], []).append(names.get(r["offer_id"], r["offer_id"]))
        out += [f"{', '.join(offers)}: {reason}" for reason, offers in by_reason.items()]
    return out[:MAX_REJECTED]


def _rules_line(d: Decision) -> str:
    policy = POLICY_LABELS.get(d.profile_snapshot.policy, d.profile_snapshot.policy)
    version = d.effective_policy.version_hash[:6]
    if d.validation is None:
        return f"{len(d.effective_policy.rules)} rules in force · policy {policy} ({version})"
    passed = sum(c.passed for c in d.validation.checks)
    failed = len(d.validation.violations)
    return f"{passed} passed · {failed} violations · policy {policy} ({version})"


def _decided_by_line(d: Decision) -> str:
    secs = f"{d.latency_ms / 1000:.1f} s"
    calls = sum(1 for t in d.agent_trace if t.name == "llm")
    if d.decided_by == "AGENT":
        return f"Agent ({calls} LLM call{'s' * (calls != 1)}, {secs})"
    if d.decided_by == "AGENT_RETRY":
        return f"Agent after one retry ({calls} LLM calls, {secs})"
    if d.decided_by == "RULES_FALLBACK":
        return f"Rules fallback — {d.fallback_reason or 'no agent answer'}"
    if d.decided_by == "HOLDOUT":
        return "Holdout group: logged for measurement, nothing sent"
    return "Pre-gate (no AI call)"


def _telegram_text(d: Decision) -> str:
    checks = len(d.validation.checks) if d.validation else len(d.effective_policy.rules)
    if d.status in {"SENT", "QUEUED", "DRY_RUN"} and d.final_offer_id:
        cart = (d.profile_snapshot.open_cart or {}).get("item")
        if d.trigger == "cart_abandoned" and cart:
            why = (
                f"your {cart} is still in your cart, so {_value(d).lower()} is the smallest nudge that helps"
            )
        else:
            why = f"{_value(d).lower()} is the offer most likely to help, at the lowest cost"
        return f"Why you got this: {why}. {checks} rules checked ✓"
    if d.status == "NO_OFFER":
        return f"No offer this time: {_business_reason(d)}. {checks} rules checked ✓"
    if d.status == "HELD_OUT":
        return (
            "You're in our comparison group this time, so no offer was sent. Thanks for helping us measure!"
        )
    return f"No new offer right now: {_first_violation(d)}."


def explain(decision: Decision) -> Explanation:
    return Explanation(
        title=_title(decision),
        why_customer=_why_customer(decision),
        why_offer=_why_offer(decision),
        rejected=_rejected(decision),
        rules_line=_rules_line(decision),
        decided_by_line=_decided_by_line(decision),
        telegram_text=_telegram_text(decision),
    )


def placeholder(now: datetime) -> Explanation:
    """Decision requires an explanation at construction; the harness replaces this with explain()."""
    return Explanation(
        title="",
        why_customer="",
        why_offer="",
        rules_line="",
        decided_by_line="",
        telegram_text=f"{now:%H:%M}",
    )
