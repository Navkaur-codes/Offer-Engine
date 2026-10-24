"""Plain-English sentence for a rule, regenerated from its current params (the dashboard shows this)."""

from __future__ import annotations

from app.contracts import Rule
from app.rules.rule_types import spec_for


def describe(rule: Rule) -> str:
    return spec_for(rule).describe()
