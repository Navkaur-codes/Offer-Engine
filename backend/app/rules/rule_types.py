"""Rule types: a Rule row is data; its RuleType class gives it behaviour (CLAUDE.md §9).

Each type answers four questions for the engine:
  applies   — does this rule cover this customer right now? (from `conditions`)
  constrain — narrow an offer candidate's param ranges, or drop the candidate (None)
  check     — does one concrete decision pass?
  describe  — the plain-English sentence a marketer reads

`constrain` and `check` must agree: any params inside the ranges `constrain` leaves must pass `check`.
The property tests in tests/core hold both sides to that.
"""

from __future__ import annotations

import logging
import math
import re
from datetime import datetime, time, timedelta
from typing import Any, ClassVar, Literal, get_args

from app import ports
from app.config import IST
from app.contracts import (
    Category,
    Context,
    CustomerProfile,
    Offer,
    OfferCandidate,
    OfferType,
    Rule,
    RuleCheck,
    RuleType,
)

log = logging.getLogger(__name__)

CATEGORIES: tuple[str, ...] = get_args(Category)
DISCOUNT_TYPES = frozenset({"pct_off", "flat_off"})
VALUE_KEYS = ("pct", "amount", "multiplier")  # params that make an offer more generous as they grow
ZERO_COST_TYPES = frozenset({"cart_nudge", "early_access", "points_reminder"})  # free perks
NO_COUPON_TYPES = frozenset({"cart_nudge", "points_reminder"})  # nothing to redeem, so no code or expiry
EXPIRY_DAYS = 2

POLICY_LABELS = {
    "vip": "VIP customers",
    "deal_hunter": "Deal hunters",
    "at_risk": "At-risk customers",
    "new_user": "New users",
    "cart_abandoner": "Cart abandoners",
    "window_shopper": "Window shoppers",
    "high_returner": "High returners",
    "sleeping_dog": "Sleeping dogs (offers put them off)",
    "dormant": "Dormant customers",
    "default": "Other customers",
}
OFFER_LABELS = {
    "pct_off": "% off",
    "flat_off": "flat ₹ off",
    "free_shipping": "free shipping",
    "free_express": "free express delivery",
    "bonus_points": "bonus points",
    "points_reminder": "points reminders",
    "cart_nudge": "cart reminders",
    "early_access": "early access",
    "bundle": "bundles",
    "gift_card": "gift cards",
    "birthday": "birthday treats",
}
PHASE_LABELS = {
    "teaser": "teaser week",
    "build_up": "build-up",
    "last_minute": "last-minute days",
    "post": "post-festival days",
}


# ---------------------------------------------------------------- small helpers
def inr(amount: float) -> str:
    return f"₹{int(amount):,}"


def as_list(value: Any) -> list:
    return value if isinstance(value, list) else [value]


def num(params: dict, key: str) -> float | None:
    """A numeric param, or None when absent or not a real number (bools are not numbers here)."""
    v = params.get(key)
    if isinstance(v, bool) or not isinstance(v, int | float) or not math.isfinite(v):
        return None
    return v


def fmt_hours(hours: float) -> str:
    if hours < 1:
        return f"{round(hours * 60)} min"
    if hours < 48 or hours % 24:
        return f"{hours:g} h"
    return f"{int(hours // 24)} days"


def join_words(words: list[str]) -> str:
    if len(words) <= 1:
        return "".join(words)
    return ", ".join(words[:-1]) + " or " + words[-1]


def offer_labels(types: list[str]) -> str:
    return join_words([OFFER_LABELS.get(t, t) for t in types])


def category_label(cat: str | None) -> str:
    return (cat or "any category").replace("_", " ")


def offer_category(offer: Offer, params: dict, profile: CustomerProfile) -> Category | None:
    """The one category an offer is scoped to. A coupon always targets one category (or none for non-category
    perks), chosen in the same way by allowed_offers and evaluate so they agree."""
    cat = params.get("category")
    if isinstance(cat, str):
        return cat
    if offer.categories and len(offer.categories) == 1:
        return offer.categories[0]
    pool = set(offer.categories or CATEGORIES) - set(profile.suppressed_categories)
    cart_cat = (profile.open_cart or {}).get("category")
    if cart_cat in pool:
        return cart_cat
    ranked = sorted(
        (c for c in profile.category_affinity if c in pool), key=lambda c: -profile.category_affinity[c]
    )
    return ranked[0] if ranked else None


def worst_case_params(allowed: dict) -> dict:
    """The most generous point inside the allowed ranges; used for conservative cost estimates."""
    out = {}
    for key, rng in allowed.items():
        if not isinstance(rng, dict):
            continue
        lo, hi = rng.get("min"), rng.get("max")
        if key in VALUE_KEYS:
            out[key] = hi if hi is not None else lo
        else:
            out[key] = lo if lo is not None else hi
    return {k: v for k, v in out.items() if v is not None}


def estimate_offer(
    profile: CustomerProfile, offer_type: str, params: dict, category: str | None
) -> tuple[int, int]:
    """(cost, incremental profit). A reminder or early access gives no money away, so it costs ₹0 by
    definition and its profit is what the nudge earns, never below zero."""
    cost, profit = ports.impact_estimate(profile, offer_type, params, category)
    if offer_type in ZERO_COST_TYPES:
        return 0, max(0, profit + cost)
    return cost, profit


def estimate_candidate(profile: CustomerProfile, cand: OfferCandidate) -> tuple[int, int]:
    return estimate_offer(profile, cand.type, worst_case_params(cand.allowed_params), cand.category)


def narrow(
    cand: OfferCandidate, key: str, note: str, *, lo: float | None = None, hi: float | None = None
) -> OfferCandidate | None:
    """Tighten one param range. None if the range becomes empty; the same candidate if nothing changed."""
    rng = cand.allowed_params.get(key)
    if rng is None:
        if key != "min_basket" or lo is None:
            return cand  # the offer has no such knob
        rng = {"min": 0}
    cur_lo, cur_hi = rng.get("min"), rng.get("max")
    new_lo = cur_lo if lo is None else (lo if cur_lo is None else max(cur_lo, lo))
    new_hi = cur_hi if hi is None else (hi if cur_hi is None else min(cur_hi, hi))
    if (new_lo, new_hi) == (cur_lo, cur_hi):
        return cand
    if new_lo is not None and new_hi is not None and new_lo > new_hi:
        return None
    new_rng = {**rng, "min": new_lo, "max": new_hi}
    new_rng = {k: v for k, v in new_rng.items() if v is not None}
    return cand.model_copy(
        update={
            "allowed_params": {**cand.allowed_params, key: new_rng},
            "rule_notes": [*cand.rule_notes, note],
        }
    )


# ---------------------------------------------------------------- conditions
def _festival_match(wanted: Any, festival: str | None) -> bool:
    if festival is None:
        return False
    return any(w == "*" or festival == w or festival.startswith(f"{w}_") for w in as_list(wanted))


def matches(conditions: dict, profile: CustomerProfile, context: Context) -> bool:
    for key, want in conditions.items():
        if key == "policy":
            ok = profile.policy in as_list(want)
        elif key == "persona":
            ok = profile.persona in as_list(want)
        elif key == "customer_id":
            ok = profile.customer_id in as_list(want)
        elif key == "festival":
            ok = _festival_match(want, context.festival)
        elif key == "phase":
            ok = context.festival_phase in as_list(want)
        elif key == "city_tier":
            ok = profile.city_tier in as_list(want)
        elif key == "payday":
            ok = context.is_payday_window == bool(want)
        else:
            log.warning("rule condition %r is unknown; the rule is skipped", key)
            return False
        if not ok:
            return False
    return True


def _festival_name(wanted: Any) -> str:
    names = [w for w in as_list(wanted) if w != "*"]
    if not names:
        return "any festival"
    return join_words([re.sub(r"_\d{4}$", "", n).replace("_", " ").title() for n in names])


def lead_and_subject(conditions: dict) -> tuple[str, str]:
    """("During Diwali last-minute days, ", "deal hunters") style pieces for describe()."""
    lead = ""
    if "festival" in conditions:
        fest = _festival_name(conditions["festival"])
        if "phase" in conditions:
            phases = join_words([PHASE_LABELS.get(p, p) for p in as_list(conditions["phase"])])
            lead = f"During the {phases} of {fest}, "
        else:
            lead = f"During {fest}, "
    if "customer_id" in conditions:
        subject = "customer " + join_words(as_list(conditions["customer_id"]))
    elif "policy" in conditions:
        subject = join_words([POLICY_LABELS.get(p, p) for p in as_list(conditions["policy"])])
    elif "persona" in conditions:
        subject = join_words([p.replace("_", " ") for p in as_list(conditions["persona"])]) + " customers"
    else:
        subject = "customers"
    if "city_tier" in conditions:
        subject += " in tier-" + join_words([str(t) for t in as_list(conditions["city_tier"])]) + " cities"
    return lead, subject


def sentence(lead: str, rest: str) -> str:
    text = (lead + rest).strip()
    return text[0].upper() + text[1:]


# ---------------------------------------------------------------- base class
class RuleSpec:
    type: ClassVar[RuleType]
    # customer: may we contact this person at all? offer: is this one offer fine? message: is the text fine?
    scope: ClassVar[Literal["customer", "offer", "message"]] = "offer"

    def __init__(self, rule: Rule):
        self.rule = rule
        self.p = rule.params

    def applies(self, profile: CustomerProfile, context: Context) -> bool:
        return matches(self.rule.conditions, profile, context)

    def limits(self, profile: CustomerProfile, context: Context) -> dict:
        return {}

    def constrain(
        self, cand: OfferCandidate, offer: Offer, profile: CustomerProfile, context: Context
    ) -> OfferCandidate | None:
        return cand

    def check(
        self,
        profile: CustomerProfile,
        context: Context,
        offer: Offer | None,
        params: dict,
        message: str | None,
    ) -> RuleCheck:
        passed, detail = self._check(profile, context, offer, params, message)
        return RuleCheck(
            rule_id=self.rule.id,
            description=self.describe(),
            passed=passed,
            severity=self.rule.severity,
            detail=detail,
        )

    def _check(
        self,
        profile: CustomerProfile,
        context: Context,
        offer: Offer | None,
        params: dict,
        message: str | None,
    ) -> tuple[bool, str]:
        return True, ""

    def describe(self) -> str:
        raise NotImplementedError

    def _parts(self) -> tuple[str, str]:
        return lead_and_subject(self.rule.conditions)


# ---------------------------------------------------------------- the 11 rule types
class MarginGuard(RuleSpec):
    """params: buffer_pct, margins {category: pct}, default_margin (optional; else the lowest margin)."""

    type = "margin_guard"

    def cap_pct(self, category: str | None) -> int:
        margins: dict = self.p.get("margins", {})
        default = self.p.get("default_margin", min(margins.values()) if margins else 0)
        margin = margins.get(category, default) if category else default
        return max(0, int(margin) - int(self.p.get("buffer_pct", 0)))

    def amount_cap(self, category: str | None, min_basket: float, profile: CustomerProfile) -> int:
        # flat ₹ off is judged against the smallest basket it can apply to (or the usual order size)
        return math.floor(self.cap_pct(category) / 100 * max(min_basket, profile.aov))

    def limits(self, profile, context):
        return {"min_margin_buffer_pct": self.p.get("buffer_pct", 0)}

    def constrain(self, cand, offer, profile, context):
        cap = self.cap_pct(cand.category)
        note = f"capped at {cap}% by the margin guard ({category_label(cand.category)})"
        cand = narrow(cand, "pct", note, hi=cap)
        if cand is None:
            return None
        basket_lo = cand.allowed_params.get("min_basket", {}).get("min", 0) or 0
        amt = self.amount_cap(cand.category, basket_lo, profile)
        return narrow(cand, "amount", f"flat discount capped at {inr(amt)} by the margin guard", hi=amt)

    def _check(self, profile, context, offer, params, message):
        if offer is None:
            return True, "no offer to check"
        cat = offer_category(offer, params, profile)
        cap = self.cap_pct(cat)
        pct = num(params, "pct")
        if pct is not None and pct > cap:
            return False, f"{pct:g}% off on {category_label(cat)} is over the {cap}% margin limit"
        amount = num(params, "amount")
        if amount is not None:
            amt_cap = self.amount_cap(cat, num(params, "min_basket") or 0, profile)
            if amount > amt_cap:
                return False, f"{inr(amount)} off is over the {inr(amt_cap)} margin limit"
        return True, f"inside the {cap}% margin limit for {category_label(cat)}"

    def describe(self):
        lead, subject = self._parts()
        buf = self.p.get("buffer_pct", 0)
        margins: dict = self.p.get("margins", {})
        example = ""
        if margins:
            hi_cat = max(margins, key=margins.get)
            lo_cat = min(margins, key=margins.get)
            example = (
                f" ({category_label(hi_cat)} up to {self.cap_pct(hi_cat)}%, "
                f"{category_label(lo_cat)} up to {self.cap_pct(lo_cat)}%)"
            )
        whose = "" if subject == "customers" else f" for {subject}"
        return sentence(
            lead, f"discounts{whose} never go above the category margin minus {buf} points{example}."
        )


class DiscountCap(RuleSpec):
    """params: max_pct, max_amount, min_basket (discounts only), max_multiplier (points).
    Budget pacing shrinks max_pct and max_amount by context.pacing_factor."""

    type = "discount_cap"

    def caps(self, context: Context) -> dict:
        pf = min(1.0, max(0.0, context.pacing_factor))
        out = {}
        for key in ("max_pct", "max_amount"):
            if key in self.p:
                out[key] = math.floor(self.p[key] * pf)
        for key in ("min_basket", "max_multiplier"):
            if key in self.p:
                out[key] = self.p[key]
        return out

    def limits(self, profile, context):
        return self.caps(context)

    def constrain(self, cand, offer, profile, context):
        c = self.caps(context)
        paced = " (budget pacing)" if context.pacing_factor < 1 else ""
        who = self.rule.id
        if cand.type in DISCOUNT_TYPES:
            if "max_pct" in c:
                cand = narrow(cand, "pct", f"capped at {c['max_pct']}% by {who}{paced}", hi=c["max_pct"])
            if cand is not None and "max_amount" in c:
                cap = c["max_amount"]
                cand = narrow(cand, "amount", f"flat discount capped at {inr(cap)} by {who}{paced}", hi=cap)
            if cand is not None and "min_basket" in c:
                note = f"basket must be at least {inr(c['min_basket'])} ({who})"
                cand = narrow(cand, "min_basket", note, lo=c["min_basket"])
        elif cand.type == "bonus_points" and "max_multiplier" in c:
            note = f"points capped at {c['max_multiplier']}× by {who}"
            cand = narrow(cand, "multiplier", note, hi=c["max_multiplier"])
        return cand

    def _check(self, profile, context, offer, params, message):
        if offer is None:
            return True, "no offer to check"
        c = self.caps(context)
        if offer.type in DISCOUNT_TYPES:
            pct, amount = num(params, "pct"), num(params, "amount")
            basket = num(params, "min_basket") or 0
            if pct is not None and "max_pct" in c and pct > c["max_pct"]:
                return False, f"{pct:g}% off is over the {c['max_pct']}% cap"
            if amount is not None and "max_amount" in c and amount > c["max_amount"]:
                return False, f"{inr(amount)} off is over the {inr(c['max_amount'])} cap"
            if "min_basket" in c and basket < c["min_basket"]:
                return False, f"minimum basket {inr(basket)} is below the required {inr(c['min_basket'])}"
        elif offer.type == "bonus_points":
            mult = num(params, "multiplier")
            if mult is not None and "max_multiplier" in c and mult > c["max_multiplier"]:
                return False, f"{mult:g}× points is over the {c['max_multiplier']}× cap"
        return True, "inside the discount caps"

    def describe(self):
        lead, subject = self._parts()
        parts = []
        if "max_pct" in self.p:
            parts.append(f"{self.p['max_pct']}% off")
        if "max_amount" in self.p:
            parts.append(f"{inr(self.p['max_amount'])} off")
        if "max_multiplier" in self.p:
            parts.append(f"{self.p['max_multiplier']}× points")
        both = ", ".join(parts[:-1]) + " and " + parts[-1] if len(parts) > 1 else "".join(parts)
        text = f"{subject} can get " + (f"at most {both}" if parts else "discounts")
        if "min_basket" in self.p:
            text += f", only on baskets above {inr(self.p['min_basket'])}"
        return sentence(lead, text + ".")


class FrequencyCap(RuleSpec):
    """params: max_7d, min_gap_h."""

    type = "frequency_cap"
    scope = "customer"

    def limits(self, profile, context):
        out = {}
        if "max_7d" in self.p:
            out["max_offers_7d"] = self.p["max_7d"]
        if "min_gap_h" in self.p:
            out["min_gap_h"] = self.p["min_gap_h"]
        return out

    def constrain(self, cand, offer, profile, context):
        return cand if self._check(profile, context, None, {}, None)[0] else None

    def _check(self, profile, context, offer, params, message):
        max_7d = self.p.get("max_7d")
        if max_7d is not None and profile.offers_7d >= max_7d:
            return False, f"already got {profile.offers_7d} offers in the last 7 days (limit {max_7d})"
        gap = self.p.get("min_gap_h")
        if gap is not None and profile.last_offer_at is not None:
            since_h = (context.now - profile.last_offer_at).total_seconds() / 3600
            if since_h < gap:
                return False, f"last offer was {fmt_hours(max(since_h, 0))} ago (needs {fmt_hours(gap)})"
        return True, "within the frequency cap"

    def describe(self):
        lead, subject = self._parts()
        max_7d, gap = self.p.get("max_7d"), self.p.get("min_gap_h")
        if max_7d is not None and gap is not None:
            rest = f"{subject} can get at most {max_7d} offers every 7 days, at least {fmt_hours(gap)} apart."
        elif max_7d is not None:
            rest = f"{subject} can get at most {max_7d} offers every 7 days."
        else:
            rest = f"{subject} can get at most one offer every {fmt_hours(gap or 0)}."
        return sentence(lead, rest)


class QuietHours(RuleSpec):
    """params: start "21:00", end "09:00" (IST). Sends inside the window are queued by the harness."""

    type = "quiet_hours"
    scope = "customer"

    def _window(self) -> tuple[time, time]:
        return time.fromisoformat(self.p.get("start", "21:00")), time.fromisoformat(
            self.p.get("end", "09:00")
        )

    def is_quiet(self, now: datetime) -> bool:
        start, end = self._window()
        t = now.astimezone(IST).time()
        return (start <= t or t < end) if start > end else (start <= t < end)

    def _check(self, profile, context, offer, params, message):
        if self.is_quiet(context.now):
            at, end = context.now.astimezone(IST), self.p.get("end", "09:00")
            return False, f"{at:%H:%M} IST is inside quiet hours; queue until {end}"
        return True, "outside quiet hours"

    def describe(self):
        start, end = self.p.get("start", "21:00"), self.p.get("end", "09:00")
        return f"No messages between {start} and {end} IST; anything due then waits until {end}."


class Budget(RuleSpec):
    """params: daily_cap (₹, read by get_context), use_festival_pool (bool)."""

    type = "budget"

    def _left(self, context: Context) -> tuple[int, str]:
        left, what = context.budget_left_today, "today's budget"
        pool = context.budget_left_festival
        if self.p.get("use_festival_pool") and pool is not None and pool < left:
            left, what = context.budget_left_festival, "the festival budget pool"
        return left, what

    def limits(self, profile, context):
        return {"max_cost": self._left(context)[0]}

    def constrain(self, cand, offer, profile, context):
        left, _ = self._left(context)
        cost, _ = estimate_candidate(profile, cand)
        return cand if cost <= left else None

    def _check(self, profile, context, offer, params, message):
        left, what = self._left(context)
        if offer is None:
            return (left > 0, f"{inr(left)} left in {what}")
        cost, _ = estimate_offer(profile, offer.type, params, offer_category(offer, params, profile))
        if cost > left:
            return False, f"expected cost {inr(cost)} is more than the {inr(left)} left in {what}"
        return True, f"expected cost {inr(cost)}; {inr(left)} left in {what}"

    def describe(self):
        lead, _ = self._parts()
        if self.p.get("use_festival_pool"):
            return sentence(
                lead, "offers are paid from the festival's own budget pool and stop when it runs out."
            )
        cap = self.p.get("daily_cap")
        rest = f"spend at most {inr(cap)} a day on offers" if cap else "never spend more than the budget left"
        return sentence(lead, rest + "; discount caps shrink once 80% of it is used.")


class Eligibility(RuleSpec):
    """params: offer_types (whitelist), min_uplift, categories (whitelist), hero_only (discounts only on the
    active festival's hero categories)."""

    type = "eligibility"

    def limits(self, profile, context):
        out = {}
        if "offer_types" in self.p:
            out["allowed_offer_types"] = sorted(self.p["offer_types"])
        if "min_uplift" in self.p:
            out["min_uplift"] = self.p["min_uplift"]
        if "categories" in self.p:
            out["allowed_categories"] = sorted(self.p["categories"])
        return out

    def _verdict(
        self, offer_type: OfferType, category: str | None, profile: CustomerProfile, context: Context
    ) -> tuple[bool, str]:
        types = self.p.get("offer_types")
        if types is not None and offer_type not in types:
            return False, f"{OFFER_LABELS.get(offer_type, offer_type)} is not allowed here"
        min_uplift = self.p.get("min_uplift")
        if min_uplift is not None:
            uplift = ports.uplift_predict(profile, offer_type)
            if not uplift > min_uplift:
                return False, f"predicted uplift {uplift:.2f} is not above {min_uplift:.2f}"
        cats = self.p.get("categories")
        if cats is not None and category not in cats:
            return False, f"{category_label(category)} is not an allowed category"
        heroes = context.hero_categories
        if self.p.get("hero_only") and offer_type in DISCOUNT_TYPES and heroes and category not in heroes:
            return False, f"discounts only on hero categories, not {category_label(category)}"
        return True, "eligible"

    def constrain(self, cand, offer, profile, context):
        return cand if self._verdict(cand.type, cand.category, profile, context)[0] else None

    def _check(self, profile, context, offer, params, message):
        if offer is None:
            return True, "no offer to check"
        return self._verdict(offer.type, offer_category(offer, params, profile), profile, context)

    def describe(self):
        lead, subject = self._parts()
        bits = []
        if "offer_types" in self.p:
            bits.append(f"can only get {offer_labels(self.p['offer_types'])}")
        if "min_uplift" in self.p:
            lift = self.p["min_uplift"] * 100
            bits.append(f"only when the offer lifts their chance to buy by more than {lift:g} points")
        if "categories" in self.p:
            bits.append(f"only on {join_words([category_label(c) for c in self.p['categories']])}")
        if self.p.get("hero_only"):
            bits.append("can get discounts only on the festival's hero categories")
        return sentence(lead, f"{subject} " + ", and ".join(bits or ["are eligible"]) + ".")


class Exclusion(RuleSpec):
    """params: offer_types (list or "all"), categories (banned), use_suppressed (skip "Not for me"
    categories), within_purchase_h (the ban only holds this many hours after a purchase)."""

    type = "exclusion"

    @property
    def blocks_all(self) -> bool:
        return self.p.get("offer_types") == "all"

    def _after_purchase(self) -> str:
        h = self.p.get("within_purchase_h")
        return f" within {fmt_hours(h)} of a purchase" if h is not None else ""

    def _active(self, profile: CustomerProfile) -> bool:
        h = self.p.get("within_purchase_h")
        return h is None or profile.recency_days * 24 < h

    def limits(self, profile, context):
        if not self._active(profile):
            return {}
        if self.blocks_all:
            return {"blocked": True}
        out = {}
        if isinstance(self.p.get("offer_types"), list):
            out["banned_offer_types"] = sorted(self.p["offer_types"])
        if self.p.get("categories"):
            out["banned_categories"] = sorted(self.p["categories"])
        if self.p.get("use_suppressed") and profile.suppressed_categories:
            out["banned_categories"] = sorted(
                set(out.get("banned_categories", [])) | set(profile.suppressed_categories)
            )
        return out

    def _verdict(
        self, offer_type: str | None, category: str | None, profile: CustomerProfile
    ) -> tuple[bool, str]:
        if not self._active(profile):
            return True, "not active (no recent purchase)"
        if self.blocks_all:
            return False, "no proactive offers for this customer" + self._after_purchase()
        if offer_type is None:
            return True, "no offer to check"
        types = self.p.get("offer_types") or []
        if offer_type in types:
            why = (
                f" within {fmt_hours(self.p['within_purchase_h'])} of a purchase"
                if "within_purchase_h" in self.p
                else ""
            )
            return False, f"{OFFER_LABELS.get(offer_type, offer_type)} is excluded{why}"
        if category and category in (self.p.get("categories") or []):
            return False, f"{category_label(category)} is excluded"
        if self.p.get("use_suppressed") and category in profile.suppressed_categories:
            return False, f"customer said “Not for me” to {category_label(category)}"
        return True, "not excluded"

    def constrain(self, cand, offer, profile, context):
        return cand if self._verdict(cand.type, cand.category, profile)[0] else None

    def _check(self, profile, context, offer, params, message):
        if offer is None:
            return self._verdict(None, None, profile)
        return self._verdict(offer.type, offer_category(offer, params, profile), profile)

    def describe(self):
        lead, subject = self._parts()
        if self.blocks_all:
            return sentence(lead, f"{subject} must not get any proactive offers{self._after_purchase()}.")
        bits = []
        if isinstance(self.p.get("offer_types"), list):
            what = offer_labels(self.p["offer_types"])
            if "within_purchase_h" in self.p:
                what += f" within {fmt_hours(self.p['within_purchase_h'])} of a purchase"
            bits.append(f"{subject} can't get {what}")
        if self.p.get("categories"):
            cats = join_words([category_label(c) for c in self.p["categories"]])
            bits.append(f"{subject} can't get offers on {cats}")
        if self.p.get("use_suppressed"):
            bits.append("no offers on a category the customer tapped “Not for me” on, while it is suppressed")
        return sentence(lead, "; ".join(bits or [f"{subject} are not excluded"]) + ".")


class Stacking(RuleSpec):
    """params: max_active (coupons a customer may hold at once; the profile tracks one)."""

    type = "stacking"
    scope = "customer"

    def limits(self, profile, context):
        return {"max_active_coupons": self.p.get("max_active", 1)}

    def constrain(self, cand, offer, profile, context):
        return cand if self._check(profile, context, None, {}, None)[0] else None

    def _check(self, profile, context, offer, params, message):
        if profile.active_coupon and self.p.get("max_active", 1) <= 1:
            return False, f"already holds an active coupon ({profile.active_coupon})"
        return True, "no active coupon"

    def describe(self):
        n = self.p.get("max_active", 1)
        lead, subject = self._parts()
        coupons = "one active coupon" if n == 1 else f"{n} active coupons"
        return sentence(lead, f"{subject} can hold only {coupons} at a time.")


class EscalationLadder(RuleSpec):
    """params: steps [{"after_h": 0.5, "offer_types": [...], "max_pct": 5?}], timed from open_cart.since.
    Offer types not on the ladder are left to other rules."""

    type = "escalation_ladder"

    def _steps(self) -> list[dict]:
        return sorted(self.p.get("steps", []), key=lambda s: s.get("after_h", 0))

    def _ladder_types(self) -> set[str]:
        return {t for s in self._steps() for t in s.get("offer_types", [])}

    @staticmethod
    def cart_age_h(profile: CustomerProfile, context: Context) -> float:
        since = (profile.open_cart or {}).get("since")
        if isinstance(since, str):
            try:
                since = datetime.fromisoformat(since)
            except ValueError:
                return 0.0
        if not isinstance(since, datetime):
            return 0.0
        if since.tzinfo is None:
            since = since.replace(tzinfo=IST)
        return max(0.0, (context.now - since).total_seconds() / 3600)

    def _unlocked(self, offer_type: str, age_h: float) -> tuple[list[dict], float | None]:
        steps = [s for s in self._steps() if offer_type in s.get("offer_types", [])]
        unlocked = [s for s in steps if age_h >= s.get("after_h", 0)]
        first = steps[0].get("after_h", 0) if steps else None
        return unlocked, first

    @staticmethod
    def _pct_cap(unlocked: list[dict]) -> float | None:
        caps = [s.get("max_pct") for s in unlocked]
        return None if any(c is None for c in caps) else max(caps)

    def constrain(self, cand, offer, profile, context):
        if cand.type not in self._ladder_types():
            return cand
        unlocked, _ = self._unlocked(cand.type, self.cart_age_h(profile, context))
        if not unlocked:
            return None
        cap = self._pct_cap(unlocked)
        if cap is None:
            return cand
        return narrow(cand, "pct", f"capped at {cap:g}% by the cart ladder", hi=cap)

    def _check(self, profile, context, offer, params, message):
        if offer is None or offer.type not in self._ladder_types():
            return True, "not on the ladder"
        age = self.cart_age_h(profile, context)
        unlocked, first = self._unlocked(offer.type, age)
        label = OFFER_LABELS.get(offer.type, offer.type)
        if not unlocked:
            return False, f"{label} unlocks after {fmt_hours(first or 0)}; the cart is {fmt_hours(age)} old"
        cap = self._pct_cap(unlocked)
        pct = num(params, "pct")
        if cap is not None and pct is not None and pct > cap:
            return False, f"{pct:g}% off is above the ladder's {cap:g}% at this step"
        return True, f"step unlocked (cart {fmt_hours(age)} old)"

    def describe(self):
        lead, subject = self._parts()
        steps = []
        for s in self._steps():
            what = offer_labels(s.get("offer_types", []))
            if "max_pct" in s:
                what = (
                    f"up to {s['max_pct']}% off"
                    if s.get("offer_types") == ["pct_off"]
                    else f"{what} (≤ {s['max_pct']}%)"
                )
            steps.append(f"{what} once the cart is {fmt_hours(s.get('after_h', 0))} old")
        return sentence(lead, f"{subject} move up a ladder: " + ", then ".join(steps) + ".")


class MessageRule(RuleSpec):
    """params: max_len, banned_phrases, competitors, check_facts (default on): every %, ×, ₹ amount and number
    must match the final params, the expiry date must be the real one, and a festival greeting may appear
    only as the exact greeting the harness put in context (it does so only for opted-in customers)."""

    type = "message"
    scope = "message"

    def limits(self, profile, context):
        return {"max_message_len": self.p["max_len"]} if "max_len" in self.p else {}

    def _check(self, profile, context, offer, params, message):
        if message is None:
            return True, "no message to check"
        max_len = self.p.get("max_len")
        if max_len is not None and len(message) > max_len:
            return False, f"message is {len(message)} characters (limit {max_len})"
        low = message.lower()
        for phrase in self.p.get("banned_phrases", []):
            if phrase.lower() in low:
                return False, f"uses the banned phrase “{phrase}”"
        for name in self.p.get("competitors", []):
            if re.search(rf"\b{re.escape(name.lower())}\b", low):
                return False, f"names a competitor ({name})"
        if self.p.get("check_facts", True):
            problem = greeting_problem(message, context) or (
                facts_problem(message, profile, context, offer, params) if offer is not None else None
            )
            if problem:
                return False, problem
        return True, "message is clean and its facts match the offer"

    def describe(self):
        bits = []
        if "max_len" in self.p:
            bits.append(f"stay under {self.p['max_len']} characters")
        if self.p.get("banned_phrases"):
            bits.append("never say " + join_words([f"“{b}”" for b in self.p["banned_phrases"]]))
        if self.p.get("competitors"):
            bits.append("never name competitors")
        if self.p.get("check_facts", True):
            bits.append(
                "quote only the offer's real value and expiry date, and use a festival greeting only for "
                "customers who opted in"
            )
        return "Messages " + ", ".join(bits or ["are checked"]) + "."


_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_DATE = re.compile(rf"\b(\d{{1,2}})\s?({'|'.join(_MONTHS)})[a-z]*\b", re.I)
_CODE = re.compile(r"\b(?=[A-Z0-9]*\d)(?=[A-Z0-9]*[A-Z])[A-Z0-9]{6,}\b")
_PCT = re.compile(r"(\d+(?:\.\d+)?)\s?%")
_MULT = re.compile(r"(\d+(?:\.\d+)?)\s?(?:×|x\b)")  # "×" is not a word char, so no \b after it
_RUPEES = re.compile(r"(?:₹|rs\.?\s?|inr\s?)\s?(\d[\d,]*)", re.I)
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def offer_expiry(send_at: datetime, ctx: Context) -> datetime:
    """When a coupon sent at `send_at` expires: in 2 days at 23:59, or sooner if a festival delivery cutoff
    comes first (an offer that can't arrive in time shouldn't outlive the cutoff)."""
    local = send_at.astimezone(IST)
    expires = datetime.combine(local.date() + timedelta(days=EXPIRY_DAYS), time(23, 59), IST)
    cutoff = ctx.delivery_cutoff
    if cutoff and ctx.festival_phase in {"build_up", "last_minute"} and cutoff > local.date():
        expires = min(expires, datetime.combine(cutoff, time(23, 59), IST))
    return expires


def _num(text: str) -> float:
    return float(text.replace(",", ""))


def greeting_problem(message: str, context: Context) -> str | None:
    low = message.lower()
    for fest in ports.festivals():
        g = fest.greeting
        if g and g.lower() in low and g != context.greeting:
            return f"uses the greeting “{g}” without the customer's opt-in for it"
    if context.greeting and context.greeting.lower() in low and context.greeting not in message:
        return f"changes the festival greeting; it must read exactly “{context.greeting}”"
    return None


def facts_problem(
    message: str, profile: CustomerProfile, context: Context, offer: Offer, params: dict
) -> str | None:
    text = _CODE.sub(" ", message)
    item = (profile.open_cart or {}).get("item")
    if item:
        text = text.replace(str(item), " ")
    if context.greeting:
        text = text.replace(context.greeting, " ")

    expiry = offer_expiry(context.now, context)
    dates = [(int(d), m[:3].title()) for d, m in _DATE.findall(text)]
    for day, month in dates:
        if (day, month) != (expiry.day, f"{expiry:%b}"):
            return f"says the offer ends {day} {month}, but it ends {expiry:%d %b}"
    if offer.type not in NO_COUPON_TYPES and not dates:
        return f"must state the expiry date ({expiry:%d %b})"
    text = _DATE.sub(" ", text)

    pct = num(params, "pct")
    for found in _PCT.findall(text):
        if pct is None or _num(found) != pct:
            actual = "not a % discount" if pct is None else f"{pct:g}% off"
            return f"mentions {found}% but the offer is {actual}"
    text = _PCT.sub(" ", text)
    mult = num(params, "multiplier")
    for found in _MULT.findall(text):
        if mult is None or _num(found) != mult:
            actual = "no points multiplier" if mult is None else f"{mult:g}×"
            return f"mentions {found}× but the offer gives {actual}"
    text = _MULT.sub(" ", text)

    cart_value = (profile.open_cart or {}).get("value")
    money = {v for v in (num(params, "amount"), num(params, "min_basket"), cart_value) if v}
    for found in _RUPEES.findall(text):
        if _num(found) not in money:
            return f"mentions ₹{found}, which is not part of this offer"
    text = _RUPEES.sub(" ", text)
    offer_numbers = {v for v in (pct, mult, num(params, "amount")) if v is not None}
    other = money | offer_numbers | {profile.points_balance, profile.points_expiring}
    for found in _NUMBER.findall(text):
        if _num(found) not in other:
            return f"mentions the number {found}, which doesn't come from the offer"
    return None


class FestivalRestriction(RuleSpec):
    """params: restricted_terms, use_festival_list (also apply the active festival's restricted_promos)."""

    type = "festival_restriction"
    scope = "message"

    def _terms(self, context: Context) -> list[str]:
        terms = list(self.p.get("restricted_terms", []))
        if self.p.get("use_festival_list", True) and context.festival:
            for fest in ports.festivals():
                if fest.id == context.festival:
                    terms += fest.restricted_promos
        return terms

    def _check(self, profile, context, offer, params, message):
        if message is None:
            return True, "no message to check"
        low = message.lower()
        for term in self._terms(context):
            if re.search(rf"\b{re.escape(term.lower())}\b", low):
                return False, f"promotes “{term}”, which is restricted during this festival"
        return True, "no restricted promotions"

    def describe(self):
        lead, _ = self._parts()
        terms = self.p.get("restricted_terms", [])
        example = f" (e.g. {join_words(terms[:3])})" if terms else ""
        return sentence(lead, f"messages never promote items restricted for that festival{example}.")


RULE_TYPES: dict[str, type[RuleSpec]] = {
    cls.type: cls
    for cls in (
        MarginGuard,
        DiscountCap,
        FrequencyCap,
        QuietHours,
        Budget,
        Eligibility,
        Exclusion,
        Stacking,
        EscalationLadder,
        MessageRule,
        FestivalRestriction,
    )
}


def spec_for(rule: Rule) -> RuleSpec:
    return RULE_TYPES[rule.type](rule)
