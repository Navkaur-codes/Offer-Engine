from __future__ import annotations

from datetime import datetime

from app import stubs
from app.config import IST
from app.contracts import Context, CustomerProfile, Offer, Rule
from app.rules.seed_rules import SEED_RULES

NOW = datetime(2026, 10, 24, 14, 0, tzinfo=IST)  # a Saturday afternoon, outside quiet hours

CATALOGUE: list[Offer] = [
    *stubs.CATALOGUE,
    Offer(
        id="OF_FLAT",
        type="flat_off",
        name="Flat ₹ off",
        description="Flat rupees off",
        param_schema={"amount": {"min": 50, "max": 1000}, "min_basket": {"min": 0}},
        base_cost_model="amount*p_redeem",
    ),
    Offer(
        id="OF_ELEC",
        type="pct_off",
        name="% off electronics",
        description="Electronics only",
        categories=["electronics"],
        param_schema={"pct": {"min": 5, "max": 30}},
        base_cost_model="pct*aov*p_redeem",
    ),
    Offer(
        id="OF_NUDGE",
        type="cart_nudge",
        name="Cart reminder",
        description="Reminder, no discount",
        param_schema={},
        base_cost_model="zero",
    ),
    Offer(
        id="OF_OFF",
        type="pct_off",
        name="Switched off",
        description="Disabled",
        param_schema={"pct": {"min": 5, "max": 30}},
        base_cost_model="pct*aov*p_redeem",
        enabled=False,
    ),
]


def make_profile(customer_id: str = "C000001", **update) -> CustomerProfile:
    base = stubs.PROFILES[customer_id] if customer_id in stubs.PROFILES else stubs.PROFILES["C000001"]
    data = {"customer_id": customer_id, "as_of": NOW, **update}
    return base.model_copy(update=data)


def make_context(**update) -> Context:
    base = dict(now=NOW, is_quiet_hours=False, is_payday_window=False, budget_left_today=50000)
    return Context(**{**base, **update})


def rule_by_id(rid: str) -> Rule:
    return next(r for r in SEED_RULES if r.id == rid)
