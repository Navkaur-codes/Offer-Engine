"""The agent's whitelisted, read-only tools (PLAN §3). Nothing here writes; the harness is the only writer.

Results are compact JSON to save tokens. The hidden ground truth (`response_type`) never appears: the agent
only ever sees CustomerProfile fields, which don't carry it.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from app.contracts import Context, CustomerProfile, EffectivePolicy, Offer, OfferCandidate, Rule
from app.rules.engine import evaluate
from app.rules.rule_types import estimate_offer

log = logging.getLogger(__name__)

MAX_CHECKS = 1  # single-call design: at most one check_offer before answering


# ---------------------------------------------------------------- compact summaries, shared with the prompt
def profile_summary(p: CustomerProfile) -> dict:
    top = sorted(p.category_affinity, key=lambda c: -p.category_affinity[c])[:3]
    cart = p.open_cart or None
    return {
        "policy": p.policy,
        "persona": p.persona,
        "segment": p.rfm.get("segment"),
        "city_tier": p.city_tier,
        "recency_days": p.recency_days,
        "orders_90d": p.orders_90d,
        "aov": p.aov,
        "churn_risk": round(p.churn_risk, 2),
        "price_sensitivity": round(p.price_sensitivity, 2),
        "discount_usage": round(p.discount_usage_rate, 2),
        "points": p.points_balance,
        "points_expiring": p.points_expiring,
        "tier": p.tier,
        "top_categories": top,
        "open_cart": {k: cart.get(k) for k in ("category", "item", "value")} if cart else None,
        "uplift": {k: round(v, 3) for k, v in p.uplift.items()},
    }


def candidate_summary(c: OfferCandidate) -> dict:
    return {
        "offer_id": c.offer_id,
        "type": c.type,
        "category": c.category,
        "params": c.allowed_params,
        "cost": c.est_cost,
        "profit": c.est_incremental_profit,
    }


def context_summary(ctx: Context, greeting: str | None) -> dict:
    return {
        "now": f"{ctx.now:%a %d %b %H:%M}",
        "festival": ctx.festival,
        "phase": ctx.festival_phase,
        "days_to_festival": ctx.days_to_festival,
        "hero_categories": ctx.hero_categories,
        "greeting": greeting,
        "payday_window": ctx.is_payday_window,
        "budget_left_today": ctx.budget_left_today,
    }


def recent_events(customer_id: str, now: datetime, hours: int = 72) -> dict:
    from app.db import engine as db_engine
    from app.models import EventRow

    since = now - timedelta(hours=hours)
    try:
        with Session(db_engine) as s:
            rows = s.exec(
                select(EventRow)
                .where(EventRow.customer_id == customer_id, EventRow.ts >= since, EventRow.ts <= now)
                .order_by(EventRow.ts.desc())
                .limit(50)
            ).all()
    except SQLAlchemyError:
        return {"hours": hours, "counts": {}, "latest": []}
    latest = [{"type": r.type, "category": r.category, "item": r.item, "value": r.value} for r in rows[:5]]
    return {"hours": hours, "counts": dict(Counter(r.type for r in rows)), "latest": latest}


# ---------------------------------------------------------------- tool schemas
def _fn(
    name: str, description: str, properties: dict | None = None, required: list[str] | None = None
) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties or {}, "required": required or []},
        },
    }


_OFFER_ARGS = {"offer_id": {"type": "string"}, "params": {"type": "object"}}
TOOL_SCHEMAS = [
    _fn("get_profile", "Customer scores (already in the facts)."),
    _fn("get_recent_events", "Recent activity.", {"hours": {"type": "integer"}}),
    _fn("get_effective_policy", "Merged rules and limits."),
    _fn("list_allowed_offers", "Allowed offers with param ranges, cost and profit."),
    _fn("estimate_impact", "Cost and incremental profit for an offer and params.", _OFFER_ARGS, ["offer_id"]),
    _fn(
        "check_offer",
        "Dry-run the rules on your final pick. Use at most once.",
        {**_OFFER_ARGS, "message": {"type": "string"}},
        ["offer_id", "params"],
    ),
    _fn("get_context", "Date, festival, payday, budget."),
]


@dataclass
class ToolBox:
    """The tools for one decision, bound to data the harness already loaded."""

    profile: CustomerProfile
    context: Context
    policy: EffectivePolicy
    candidates: list[OfferCandidate]
    rules: list[Rule]
    catalogue: list[Offer]
    greeting: str | None
    checks_used: int = 0

    def run(self, name: str, raw_args: str | dict | None) -> str:
        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) and raw_args else dict(raw_args or {})
        except json.JSONDecodeError:
            return json.dumps({"error": "arguments must be a JSON object"})
        handler = getattr(self, f"_{name}", None)
        if name not in {t["function"]["name"] for t in TOOL_SCHEMAS} or handler is None:
            return json.dumps({"error": f"unknown tool {name}"})
        try:
            return json.dumps(handler(args), ensure_ascii=False, default=str)
        except (TypeError, ValueError) as exc:
            return json.dumps({"error": f"bad arguments: {exc}"})

    def _get_profile(self, args: dict) -> dict:
        return profile_summary(self.profile)

    def _get_recent_events(self, args: dict) -> dict:
        hours = max(1, min(int(args.get("hours", 72)), 24 * 14))
        return recent_events(self.profile.customer_id, self.context.now, hours)

    def _get_effective_policy(self, args: dict) -> dict:
        return {"rules": self.policy.summary, "limits": self.policy.limits}

    def _list_allowed_offers(self, args: dict) -> list[dict]:
        return [candidate_summary(c) for c in self.candidates]

    def _estimate_impact(self, args: dict) -> dict:
        offer = next((o for o in self.catalogue if o.id == args.get("offer_id")), None)
        if offer is None:
            return {"error": "unknown offer"}
        params = args.get("params") or {}
        cand = next((c for c in self.candidates if c.offer_id == offer.id), None)
        cost, profit = estimate_offer(
            self.profile, offer.type, params, params.get("category", cand and cand.category)
        )
        return {"cost": cost, "profit": profit}

    def _check_offer(self, args: dict) -> dict:
        if self.checks_used >= MAX_CHECKS:
            return {"error": "check_offer already used; answer now"}
        self.checks_used += 1
        ctx = self.context.model_copy(update={"greeting": self.greeting})
        res = evaluate(
            self.profile,
            ctx,
            args.get("offer_id"),
            args.get("params") or {},
            args.get("message"),
            rules=self.rules,
            catalogue=self.catalogue,
        )
        return {"ok": res.ok, "violations": [f"{v.rule_id}: {v.detail}" for v in res.violations]}

    def _get_context(self, args: dict) -> dict:
        return context_summary(self.context, self.greeting)
