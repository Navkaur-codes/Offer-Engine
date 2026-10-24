"""Rules & policies: list, edit (versioned), preview impact, history, revert."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app import db, ports
from app.api.deps import not_found, require_admin
from app.config import now
from app.contracts import Rule
from app.models import RuleRow, RuleVersionRow

router = APIRouter(prefix="/api/rules", tags=["rules"])

DEFAULT_DAILY_CAP = 50_000


class RulePatch(BaseModel):
    params: dict | None = None
    enabled: bool | None = None
    priority: int | None = None


class PreviewIn(BaseModel):
    rule: Rule


def _to_rule(row: RuleRow) -> Rule:
    return Rule.model_validate(row.model_dump())


def all_rules() -> list[Rule]:
    with Session(db.engine) as s:
        return [_to_rule(r) for r in s.exec(select(RuleRow)).all()]


def daily_cap() -> int:
    """The global budget rule's `daily_cap` (₹); marketers change it in the Rules page."""
    for rule in all_rules():
        if rule.layer == "global" and rule.type == "budget" and rule.enabled and "daily_cap" in rule.params:
            return int(rule.params["daily_cap"])
    return DEFAULT_DAILY_CAP


def _snapshot(s: Session, row: RuleRow) -> None:
    s.add(
        RuleVersionRow(
            rule_id=row.id,
            version=row.version,
            snapshot=_to_rule(row).model_dump(mode="json"),
            created_at=now(),
        )
    )


def _apply(s: Session, row: RuleRow, changes: dict, by: str) -> Rule:
    _snapshot(s, row)
    for k, v in changes.items():
        setattr(row, k, v)
    row.version += 1
    row.updated_by, row.updated_at = by, now()
    row.description = ports.describe_rule(_to_rule(row))
    s.add(row)
    s.commit()
    s.refresh(row)
    return _to_rule(row)


@router.get("")
def list_rules(layer: str | None = None) -> list[Rule]:
    rules = all_rules()
    order = {"global": 0, "festival": 1, "persona": 2, "individual": 3}
    rules = [r for r in rules if not layer or r.layer == layer]
    return sorted(rules, key=lambda r: (order.get(r.layer, 9), r.priority, r.id))


@router.patch("/{rule_id}", dependencies=[Depends(require_admin)])
def patch_rule(rule_id: str, body: RulePatch) -> Rule:
    changes = body.model_dump(exclude_none=True)
    if not changes:
        raise HTTPException(status_code=422, detail="Nothing to change")
    with Session(db.engine) as s:
        row = s.get(RuleRow, rule_id)
        if row is None:
            raise not_found("Rule")
        if "params" in changes:
            changes["params"] = {**row.params, **changes["params"]}
        return _apply(s, row, changes, "dashboard")


@router.post("/preview")
def preview(body: PreviewIn) -> dict:
    return ports.rule_impact(body.rule)


@router.get("/{rule_id}/versions")
def versions(rule_id: str) -> list[Rule]:
    with Session(db.engine) as s:
        row = s.get(RuleRow, rule_id)
        if row is None:
            raise not_found("Rule")
        old = s.exec(
            select(RuleVersionRow)
            .where(RuleVersionRow.rule_id == rule_id)
            .order_by(RuleVersionRow.version.desc())
        ).all()
        return [_to_rule(row)] + [Rule.model_validate(v.snapshot) for v in old]


@router.post("/{rule_id}/revert/{version}", dependencies=[Depends(require_admin)])
def revert(rule_id: str, version: int) -> Rule:
    with Session(db.engine) as s:
        row = s.get(RuleRow, rule_id)
        if row is None:
            raise not_found("Rule")
        snap = s.exec(
            select(RuleVersionRow).where(RuleVersionRow.rule_id == rule_id, RuleVersionRow.version == version)
        ).first()
        if snap is None:
            raise not_found(f"Version {version}")
        old = Rule.model_validate(snap.snapshot)
        return _apply(
            s,
            row,
            {"params": old.params, "enabled": old.enabled, "priority": old.priority},
            f"revert to v{version}",
        )
