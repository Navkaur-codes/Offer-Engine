"""daily(day): a 5-line digest of the day's decisions for marketers.

Every number is computed here from the decision log. The fast model only rewrites the lines; if it is off,
out of budget, or invents a number, the template version is used. Suggestions are for a human to approve.
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter, defaultdict
from datetime import date, datetime, time

from sqlalchemy.exc import SQLAlchemyError

from app import decision_store
from app.agent import budget
from app.agent.llm import LLMClient, LLMError
from app.config import IST, settings
from app.rules.rule_types import POLICY_LABELS, inr

log = logging.getLogger(__name__)

CLAIMED = {"claimed", "redeemed"}
MIN_SENDS_FOR_SEGMENT = 3
DIGEST_TIMEOUT_S = 15.0
SYSTEM = (
    "You write a 5-line daily digest for an e-commerce marketing team. Use ONLY the facts given; "
    "every number you write must appear in the facts. Keep each line under 160 characters, plain and "
    "specific. Line 5 is a suggestion for a human to approve. "
    'Answer JSON only: {"lines": [5 strings]}.'
)


# ---------------------------------------------------------------- stats (code, not the LLM)
def _block_reason(payload: dict) -> str:
    """The rule id that held a decision back; pre-gate switches have no rule, so name the switch."""
    violations = (payload.get("validation") or {}).get("violations") or []
    if violations:
        return violations[0]["rule_id"]
    reason = payload.get("fallback_reason") or ""
    if "kill switch" in reason:
        return "KILL_SWITCH"
    if "opted out" in reason or "paused" in reason:
        return "CONSENT"
    return "NO_CANDIDATES"


def stats(day: date) -> dict:
    try:
        rows = decision_store.day_rows(day)
    except SQLAlchemyError:
        rows = []
    status = Counter(r.status for r in rows)
    by = Counter(r.decided_by for r in rows)
    sent = [r for r in rows if r.status in {"SENT", "QUEUED"}]
    blocked_rules: Counter = Counter()
    for r in rows:
        if r.status in {"BLOCKED", "NO_OFFER"}:
            blocked_rules[_block_reason(r.payload or {})] += 1
    seg: dict = defaultdict(lambda: {"sent": 0, "claimed": 0})
    for r in sent:
        seg[r.policy]["sent"] += 1
        seg[r.policy]["claimed"] += r.outcome in CLAIMED
    zero_cost = sum(1 for r in sent if r.cost == 0)
    festival = None
    if rows:
        ctx = (rows[0].payload or {}).get("context") or {}
        festival = (
            {"id": ctx.get("festival"), "phase": ctx.get("festival_phase")} if ctx.get("festival") else None
        )
    return {
        "day": f"{day:%d %b}",
        "total": len(rows),
        "status": dict(status),
        "decided_by": dict(by),
        "cost": sum(r.cost for r in sent),
        "expected_profit": sum(r.expected_incremental_profit for r in sent),
        "zero_cost_sent": zero_cost,
        "top_blocks": blocked_rules.most_common(3),
        "segments": {k: v for k, v in seg.items()},
        "festival": festival,
    }


def _segment_line(s: dict) -> str:
    segs = {k: v for k, v in s["segments"].items() if v["sent"] >= MIN_SENDS_FOR_SEGMENT}
    if not segs:
        segs = s["segments"]
    if not segs:
        return "Segments: no offers went out, so there is no segment comparison yet."

    def rate(v: dict) -> float:
        return v["claimed"] / v["sent"] if v["sent"] else 0.0

    best = max(segs, key=lambda k: (rate(segs[k]), segs[k]["sent"]))
    worst = min(segs, key=lambda k: (rate(segs[k]), -segs[k]["sent"]))
    b, w = segs[best], segs[worst]
    label = lambda k: POLICY_LABELS.get(k, k)  # noqa: E731
    return (
        f"Best segment: {label(best)} ({b['claimed']} of {b['sent']} claimed); "
        f"weakest: {label(worst)} ({w['claimed']} of {w['sent']} claimed)."
    )


def _suggestion(s: dict) -> str:
    blocked = s["status"].get("BLOCKED", 0) + s["status"].get("NO_OFFER", 0)
    if s["top_blocks"] and blocked and s["top_blocks"][0][1] * 2 >= blocked:
        rule_id, n = s["top_blocks"][0]
        return (
            f"Suggestion (needs your approval): review {rule_id}; "
            f"it stopped {n} of {blocked} held-back decisions."
        )
    fallback = s["decided_by"].get("RULES_FALLBACK", 0)
    if s["total"] and fallback * 2 > s["total"]:
        return (
            f"Suggestion (needs your approval): {fallback} of {s['total']} decisions used the rules "
            "fallback; "
            "check the LLM budget and errors on /health."
        )
    return "Suggestion: no rule changes needed today."


def template(s: dict) -> list[str]:
    st = s["status"]
    line1 = (
        f"{s['day']}: {s['total']} decisions. {st.get('SENT', 0)} sent, {st.get('QUEUED', 0)} queued, "
        f"{st.get('NO_OFFER', 0)} no offer, {st.get('BLOCKED', 0)} blocked, {st.get('HELD_OUT', 0)} held out."
    )
    blocks = ", ".join(f"{rid} ×{n}" for rid, n in s["top_blocks"]) or "none"
    line2 = (
        f"Spend {inr(s['cost'])} for {inr(s['expected_profit'])} expected incremental profit; "
        f"{s['zero_cost_sent']} offers were free perks. Top blocks: {blocks}."
    )
    fest = s["festival"]
    if fest:
        name = fest["id"].rsplit("_", 1)[0].replace("_", " ").title()
        line4 = f"Festival: {name} ({(fest['phase'] or '').replace('_', ' ')})."
    else:
        line4 = "Festival: no festival window today."
    return [line1, line2, _segment_line(s), line4, _suggestion(s)]


# ---------------------------------------------------------------- the LLM rewrite (optional)
def _numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text)}


def _rewrite(llm: LLMClient, s: dict, draft: list[str]) -> tuple[list[str], int]:
    messages = [
        {"role": "system", "content": SYSTEM},
        {
            "role": "user",
            "content": json.dumps({"facts": s, "draft": draft}, ensure_ascii=False, default=str),
        },
    ]
    resp = llm.chat(messages, None, DIGEST_TIMEOUT_S)
    lines = json.loads(resp.content).get("lines")
    if not (
        isinstance(lines, list) and len(lines) == 5 and all(isinstance(x, str) and x.strip() for x in lines)
    ):
        raise ValueError("digest must be 5 lines")
    allowed = _numbers(json.dumps(s, default=str) + " ".join(draft))
    invented = _numbers(" ".join(lines)) - allowed
    if invented:
        raise ValueError(f"digest invented numbers: {sorted(invented)}")
    return [x.strip()[:200] for x in lines], resp.tokens


def daily(day: date, *, llm: LLMClient | None = None) -> str:
    s = stats(day)
    draft = template(s)
    now = datetime.combine(day, time(21, 0), IST)
    kind = "fast"
    if llm is None and settings.groq_api_key and not settings.force_llm_fail and budget.mode(now) != "rules":
        from app.agent.groq_client import GroqClient

        llm = GroqClient(settings.groq_model_fast)
    if llm is None:
        return "\n".join(draft)
    try:
        lines, tokens = _rewrite(llm, s, draft)
    except (LLMError, ValueError, json.JSONDecodeError, AttributeError) as exc:
        log.info("digest falls back to the template: %s", exc)
        return "\n".join(draft)
    budget.record(kind, tokens, now)
    return "\n".join(lines)
