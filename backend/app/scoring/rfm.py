"""RFM: recency / frequency / monetary quintiles (1–5) mapped to named marketing segments.

Cut-points are quintiles over customers who bought in the last 365 days (`cutpoints()`), so the
scores stay relative to the current customer base. `DEFAULT_CUTPOINTS` (seed 42, 5,000 customers)
is the fallback when the DB has no orders yet.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

SEGMENTS = ["Champions", "Loyal", "Potential", "At Risk", "Hibernating", "New", "Lost"]


@dataclass(frozen=True)
class Cutpoints:
    recency: tuple[float, ...]  # days, ascending; lower recency → higher R
    frequency: tuple[float, ...]  # orders in 365 days, ascending
    monetary: tuple[float, ...]  # ₹ in 365 days, ascending


DEFAULT_CUTPOINTS = Cutpoints(
    recency=(14.0, 51.0, 116.0, 219.0),
    frequency=(1.0, 2.0, 3.0, 6.0),
    monetary=(1299.0, 3098.0, 7374.0, 19651.0),
)


def cutpoints(recency: Sequence[float], frequency: Sequence[float], monetary: Sequence[float]) -> Cutpoints:
    """Quintile edges from the buyer population; falls back to defaults for tiny populations."""
    if len(recency) < 25:
        return DEFAULT_CUTPOINTS
    q = [20, 40, 60, 80]
    return Cutpoints(
        tuple(float(x) for x in np.percentile(recency, q)),
        tuple(float(x) for x in np.percentile(frequency, q)),
        tuple(float(x) for x in np.percentile(monetary, q)),
    )


def _bucket(value: float, edges: Sequence[float]) -> int:
    """1 + number of edges strictly below `value` → 1..5."""
    return 1 + sum(value > e for e in edges)


def score(
    recency_days: int | None, orders_365d: int, spend_365d: int, cp: Cutpoints = DEFAULT_CUTPOINTS
) -> dict:
    if orders_365d == 0 or recency_days is None:
        return {"r": 1, "f": 1, "m": 1}
    return {
        "r": 6 - _bucket(recency_days, cp.recency),
        "f": _bucket(orders_365d, cp.frequency),
        "m": _bucket(spend_365d, cp.monetary),
    }


def segment(r: int, f: int, m: int, *, orders_total: int, tenure_days: int, days_since_active: int) -> str:
    if orders_total <= 1 and tenure_days < 30:
        return "New"
    if orders_total == 0:
        return "Potential" if days_since_active < 30 else "Lost"
    if r >= 4 and f >= 4 and m >= 4:
        return "Champions"
    if r >= 3 and f >= 4:
        return "Loyal"
    if r <= 2 and f >= 3:
        return "At Risk"
    if r == 1:
        return "Lost"
    if r == 2:
        return "Hibernating"
    return "Potential"
