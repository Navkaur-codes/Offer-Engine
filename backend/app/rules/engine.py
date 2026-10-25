"""The rules engine. The pre-gate, the agent's check_offer tool and the final validator all call `evaluate()`,
so they can never disagree (CLAUDE.md §2.3).

Layers run Global → Festival → Persona → Individual. Every applicable rule is checked on its own, so a lower
layer can only add limits; `effective_policy()` also reports (and ignores) any attempt to loosen one.
"""

from __future__ import annotations

import hashlib
import json
import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from app.contracts import (
    Context,
    CustomerProfile,
    EffectivePolicy,
    Offer,
    OfferCandidate,
    Rule,
    RuleCheck,
    ValidationResult,
)
from app.rules.rule_types import (
    CATEGORIES,
    VALUE_KEYS,
    RuleSpec,
    estimate_candidate,
    num,
    offer_category,
    spec_for,
)
from app.rules.seed_rules import SEED_RULES

log = logging.getLogger(__name__)

LAYER_ORDER = {"global": 0, "festival": 1, "persona": 2, "individual": 3}
CATALOGUE_RULE_ID = "CATALOGUE"
EXTRA_PARAM_KEYS = {"category", "min_basket"}  # accepted on any offer


# ---------------------------------------------------------------- sources: DB first, seed/fixtures fallback
def load_rules() -> list[Rule]:
    from app.db import engine as db_engine
    from app.models import RuleRow

    try:
        with Session(db_engine) as s:
            rows = s.exec(select(RuleRow)).all()
    except SQLAlchemyError:
        log.debug("rules table not readable; using seed rules")
        return list(SEED_RULES)
    return [Rule.model_validate(r.model_dump()) for r in rows] or list(SEED_RULES)


def load_catalogue() -> list[Offer]:
    """Same source as the harness (offers table, else the default catalogue), so every caller of evaluate()
    judges an offer id against the same catalogue."""
    from app.rules.offers import load_offers

    return load_offers()


# ---------------------------------------------------------------- layers
def applicable_specs(profile: CustomerProfile, context: Context, rules: list[Rule]) -> list[RuleSpec]:
    active = sorted((r for r in rules if r.enabled), key=lambda r: (LAYER_ORDER[r.layer], r.priority, r.id))
    return [spec for spec in map(spec_for, active) if spec.applies(profile, context)]


def _combine(key: str, cur, new) -> tuple[object, bool]:
    """Tightest of two limit values, and whether `new` tried to loosen `cur`."""
    if key.startswith("max_"):
        return min(cur, new), new > cur
    if key.startswith("min_"):
        return max(cur, new), new < cur
    if key.startswith("allowed_"):
        return sorted(set(cur) & set(new)), bool(set(new) - set(cur))
    if key.startswith("banned_"):
        return sorted(set(cur) | set(new)), False
    if key == "blocked":
        return cur or new, False
    return cur, new != cur


def merge_limits(specs: list[RuleSpec], profile: CustomerProfile, context: Context) -> tuple[dict, list[str]]:
    merged: dict = {}
    first_layer: dict[str, int] = {}
    ignored: list[str] = []
    for spec in specs:
        layer = LAYER_ORDER[spec.rule.layer]
        for key, value in spec.limits(profile, context).items():
            if key not in merged:
                merged[key], first_layer[key] = value, layer
                continue
            merged[key], loosened = _combine(key, merged[key], value)
            if loosened and layer > first_layer[key]:
                log.warning(
                    "rule %s (%s) tried to loosen %s to %r; tighter value %r kept",
                    spec.rule.id,
                    spec.rule.layer,
                    key,
                    value,
                    merged[key],
                )
                ignored.append(
                    f"{spec.rule.id} ({spec.rule.layer} layer) asked for a looser {key.replace('_', ' ')}; "
                    "the tighter limit above it still applies."
                )
    return merged, ignored


def _version_hash(profile: CustomerProfile, context: Context, specs: list[RuleSpec]) -> str:
    payload = [profile.policy, round(context.pacing_factor, 3)] + [
        [s.rule.id, s.rule.version, s.rule.params] for s in specs
    ]
    return hashlib.sha1(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:12]


def effective_policy(
    profile: CustomerProfile, context: Context, *, rules: list[Rule] | None = None
) -> EffectivePolicy:
    specs = applicable_specs(profile, context, load_rules() if rules is None else rules)
    limits, ignored = merge_limits(specs, profile, context)
    summary = [s.describe() for s in specs]
    if context.pacing_factor < 1:
        summary.append(
            f"Budget pacing is on: discount caps are cut to {context.pacing_factor:.0%} of normal "
            "because most of today's budget is used."
        )
    summary += ignored
    return EffectivePolicy(
        customer_id=profile.customer_id,
        policy=profile.policy,
        festival=context.festival,
        rules=[s.rule.model_copy(update={"description": s.describe()}) for s in specs],
        limits=limits,
        summary=summary,
        version_hash=_version_hash(profile, context, specs),
    )


# ---------------------------------------------------------------- candidates
def _seed_candidate(offer: Offer, profile: CustomerProfile) -> OfferCandidate:
    return OfferCandidate(
        offer_id=offer.id,
        type=offer.type,
        category=offer_category(offer, {}, profile),
        allowed_params=json.loads(json.dumps(offer.param_schema)),
        est_cost=0,
        est_incremental_profit=0,
    )


def screen_offers(
    profile: CustomerProfile, context: Context, catalogue: list[Offer], *, rules: list[Rule] | None = None
) -> tuple[list[OfferCandidate], list[dict]]:
    """(candidates sorted by expected incremental profit, rejected [{"offer_id","rule_id","reason"}])."""
    specs = applicable_specs(profile, context, load_rules() if rules is None else rules)
    kept: list[OfferCandidate] = []
    rejected: list[dict] = []
    for offer in catalogue:
        if not offer.enabled:
            continue
        cand: OfferCandidate | None = _seed_candidate(offer, profile)
        for spec in specs:
            cand = spec.constrain(cand, offer, profile, context)
            if cand is None:
                rejected.append({"offer_id": offer.id, "rule_id": spec.rule.id, "reason": spec.describe()})
                break
        if cand is not None:
            cost, profit = estimate_candidate(profile, cand)
            kept.append(cand.model_copy(update={"est_cost": cost, "est_incremental_profit": profit}))
    kept.sort(key=lambda c: (-c.est_incremental_profit, c.est_cost, c.offer_id))
    return kept, rejected


def allowed_offers(
    profile: CustomerProfile, context: Context, catalogue: list[Offer], *, rules: list[Rule] | None = None
) -> list[OfferCandidate]:
    return screen_offers(profile, context, catalogue, rules=rules)[0]


# ---------------------------------------------------------------- evaluate
def _catalogue_check(offer_id: str, offer: Offer | None, params: dict) -> RuleCheck:
    def result(passed: bool, detail: str) -> RuleCheck:
        return RuleCheck(
            rule_id=CATALOGUE_RULE_ID,
            description="The offer must be in the catalogue, switched on, and use only its own settings.",
            passed=passed,
            severity="hard",
            detail=detail,
        )

    if offer is None:
        return result(False, f"unknown offer {offer_id!r}")
    if not offer.enabled:
        return result(False, f"offer {offer_id} is switched off")
    if not isinstance(params, dict):
        return result(False, "params must be an object")
    schema = offer.param_schema
    for key, value in params.items():
        if key == "category":
            if value not in CATEGORIES or (offer.categories and value not in offer.categories):
                return result(False, f"category {value!r} is not valid for {offer_id}")
        elif key not in schema and key not in EXTRA_PARAM_KEYS:
            return result(False, f"{offer_id} has no setting {key!r}")
    for key in set(schema) | {"min_basket"}:
        rng = schema.get(key, {})
        if key not in params:
            if key in VALUE_KEYS:
                return result(False, f"{key} is required for {offer_id}")
            value = 0 if key == "min_basket" else None
            if value is None:
                continue
        else:
            value = num(params, key)
            if value is None:
                return result(False, f"{key} must be a number")
        if value < 0:
            return result(False, f"{key} cannot be negative")
        lo, hi = rng.get("min"), rng.get("max")
        if lo is not None and value < lo:
            return result(False, f"{key}={value:g} is below the catalogue minimum {lo}")
        if hi is not None and value > hi:
            return result(False, f"{key}={value:g} is above the catalogue maximum {hi}")
    return result(True, "valid catalogue offer and settings")


def _clamp(params: dict, allowed: dict) -> dict:
    out = {"category": params["category"]} if "category" in params else {}
    for key, rng in allowed.items():
        lo, hi = rng.get("min"), rng.get("max")
        v = num(params, key)
        if v is None:
            v = lo if lo is not None else hi
        if v is None:
            continue
        if lo is not None:
            v = max(v, lo)
        if hi is not None:
            v = min(v, hi)
        out[key] = int(v) if float(v).is_integer() else v
    return out


def _run_checks(
    profile: CustomerProfile,
    context: Context,
    offer_id: str | None,
    params: dict,
    message: str | None,
    specs: list[RuleSpec],
    catalogue: list[Offer],
) -> tuple[list[RuleCheck], Offer | None]:
    checks: list[RuleCheck] = []
    offer = None
    if offer_id is not None:
        offer = next((o for o in catalogue if o.id == offer_id), None)
        cat_check = _catalogue_check(offer_id, offer, params)
        checks.append(cat_check)
        if not cat_check.passed:
            offer = None  # rule checks below then judge only the customer and the message
    safe_params = params if isinstance(params, dict) else {}
    checks += [s.check(profile, context, offer, safe_params, message) for s in specs]
    return checks, offer


def evaluate(
    profile: CustomerProfile,
    context: Context,
    offer_id: str | None,
    params: dict,
    message: str | None = None,
    *,
    rules: list[Rule] | None = None,
    catalogue: list[Offer] | None = None,
) -> ValidationResult:
    """Check one decision against every applicable rule.

    `offer_id=None` checks only whether this customer may be contacted now (the pre-gate).
    `violations` lists every failed check; `ok` is False if any of them is hard.
    `adjusted_params` is a compliant version of `params` when clamping the numbers alone would fix it.
    """
    rules = load_rules() if rules is None else rules
    catalogue = load_catalogue() if catalogue is None and offer_id is not None else (catalogue or [])
    specs = applicable_specs(profile, context, rules)
    checks, offer = _run_checks(profile, context, offer_id, params, message, specs, catalogue)
    violations = [c for c in checks if not c.passed]
    ok = not any(c.severity == "hard" for c in violations)

    adjusted = None
    known_offer = next((o for o in catalogue if o.id == offer_id), None) if offer_id else None
    if not ok and known_offer is not None and known_offer.enabled and isinstance(params, dict):
        cand: OfferCandidate | None = _seed_candidate(known_offer, profile)
        for spec in specs:
            cand = spec.constrain(cand, known_offer, profile, context)
            if cand is None:
                break
        if cand is not None:
            trial = _clamp(params, cand.allowed_params)
            trial_checks, _ = _run_checks(profile, context, offer_id, trial, None, specs, catalogue)
            if all(c.passed or c.severity == "soft" for c in trial_checks):
                adjusted = trial
    return ValidationResult(ok=ok, checks=checks, violations=violations, adjusted_params=adjusted)
