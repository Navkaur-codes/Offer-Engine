"""Realism + experiment stats from a seeded DB (the dashboard's Realism and Experiments pages)."""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta

import pytest
from sqlmodel import Session

from app import db, ports
from app.config import IST
from app.data.generator import DEFAULT_END
from app.data.seed import run
from app.models import DecisionRow, EventRow
from app.scoring import experiments, realism

START, END = date(2025, 10, 1), DEFAULT_END


@pytest.fixture(scope="module")
def engine(tmp_path_factory):
    eng = db.make_engine(f"sqlite:///{tmp_path_factory.mktemp('stats') / 's.db'}")
    run(1500, 3, end=DEFAULT_END, engine=eng)  # production Neon size
    return eng


@pytest.fixture(autouse=True)
def use_engine(engine, monkeypatch):
    monkeypatch.setattr(db, "engine", engine)
    realism.reset_cache()
    experiments.reset_cache()


def test_realism_reports_every_benchmark_with_a_source():
    r = realism.compute()
    assert set(r.benchmarks) == {
        "pareto_top20_share",
        "cart_abandon_rate",
        "view_to_purchase",
        "fashion_return_rate",
        "evening_session_share",
        "diwali_week_ratio",
    }
    for key, b in r.benchmarks.items():
        assert b["min"] < b["max"] and b["source"], key
    assert sum(b["ok"] for b in r.benchmarks.values()) >= 5  # a 1,500-customer world is a little noisy
    assert r.funnel["view"] > r.funnel["session"] > r.funnel["add_to_cart"] > r.funnel["purchase"] > 0
    assert 0.6 < r.cart_abandon_rate < 0.8
    assert r.aov_by_category["electronics"] > r.aov_by_category["grocery"]
    assert len(r.seasonality_daily) > 300 and r.retention_cohorts


def test_stats_are_cached_and_fast():
    realism.compute()
    experiments.compute(START, END)
    t = time.perf_counter()
    realism.compute()
    experiments.compute(START, END)
    assert time.perf_counter() - t < 0.05


def test_experiments_show_incremental_value():
    e = experiments.compute(START, END)
    assert e.treatment["n"] > 5 * e.control["n"] > 0
    assert e.treatment["conv_rate"] > e.control["conv_rate"]
    assert e.incremental_revenue > 0 and e.margin_saved_sure_things > 0
    assert e.qini and e.qini[-1]["targeted"] == 1
    policies = {r["policy"]: r for r in e.uplift_by_policy}
    assert "at_risk" in policies and policies["at_risk"]["uplift"] > 0
    assert {r["type"] for r in e.roi_by_offer_type} >= {"pct_off", "flat_off"}
    diwali = next(f for f in e.festival_vs_baseline if f["id"] == "diwali_2025")
    assert diwali["lift"] > 1.5


def test_experiments_count_live_decisions_against_the_holdout(engine):
    now = datetime(2026, 10, 25, 12, 0, tzinfo=IST)
    with Session(engine) as s:
        for i, (status, buys) in enumerate([("SENT", True)] * 25 + [("HELD_OUT", False)] * 6):
            cid = f"C{i + 1:06d}"
            s.add(
                DecisionRow(
                    id=f"DTEST{i}",
                    ts=now,
                    customer_id=cid,
                    policy="cart_abandoner",
                    trigger="lab",
                    decided_by="RULES_FALLBACK",
                    status=status,
                    final_offer_id="OF_NUDGE",
                    is_holdout=status == "HELD_OUT",
                )
            )
            if buys:
                s.add(
                    EventRow(
                        id=f"ETEST{i}",
                        customer_id=cid,
                        type="purchase",
                        ts=now + timedelta(hours=3),
                        category="fashion",
                        item="Cotton Kurta",
                        value=1450,
                    )
                )
        s.commit()
    e = experiments.compute(date(2026, 10, 25), date(2026, 10, 25))
    assert e.treatment["n"] == 25 and e.control["n"] == 6
    assert e.treatment["conv_rate"] == 1.0 and e.control["conv_rate"] == 0.0


def test_empty_range_is_safe():
    e = experiments.compute(date(2020, 1, 1), date(2020, 1, 2))
    assert e.treatment["n"] == 0 and e.incremental_revenue == 0


def test_ports_are_real():
    ports.reset_cache()
    status = ports.status()
    assert status["realism_compute"] == "real" and status["experiments_compute"] == "real"


# ------------------------------------------------------------ GATE-4: headline consistent with breakdown
def _rows(
    stratum: str, offer: str, n_t: int, conv_t: float, n_c: int, conv_c: float, basket: int, cost: int = 0
):
    rows = []
    for i in range(n_t):
        buys = i < round(n_t * conv_t)
        rows.append((stratum, f"T{stratum}{i}", True, buys, basket if buys else 0, cost, offer, "default"))
    for i in range(n_c):
        buys = i < round(n_c * conv_c)
        rows.append((stratum, f"C{stratum}{i}", False, buys, basket if buys else 0, 0, offer, "default"))
    return rows


def _frame(rows):
    import pandas as pd

    return pd.DataFrame(rows, columns=experiments._COLUMNS)


def test_headline_is_per_campaign_not_pooled():
    """Simpson's paradox: each campaign lifts conversion by 5 points, but the cheap-season campaign has far
    more treated customers, so pooling all treated vs all control would make the offers look harmful."""
    import pandas as pd

    df = _frame(
        _rows("festive", "pct_off", 100, 0.30, 100, 0.25, 4000, cost=20)
        + _rows("monsoon", "flat_off", 900, 0.10, 20, 0.05, 1000, cost=5)
    )
    pooled = df[df["treated"]]["revenue"].mean() - df[~df["treated"]]["revenue"].mean()
    assert pooled < 0  # the trap the old headline fell into
    e = experiments._stats(
        df, pd.DataFrame(columns=["ts", "category", "value"]), date(2025, 1, 1), date(2025, 12, 31)
    )
    assert e.incremental_revenue == round(0.05 * 100 * 4000 + 0.05 * 900 * 1000)
    assert e.incremental_revenue > 0
    assert abs(e.incremental_profit - sum(r["incremental_profit"] for r in e.roi_by_offer_type)) <= len(
        e.roi_by_offer_type
    )
    assert abs(e.incremental_revenue - sum(r["incremental_revenue"] for r in e.roi_by_offer_type)) <= len(
        e.roi_by_offer_type
    )
    costs = {r["type"]: r["cost"] for r in e.roi_by_offer_type}
    assert costs == {"pct_off": 100 * 20, "flat_off": 900 * 5}  # each treated customer's coupon counted once


def test_strata_without_enough_control_are_not_guessed():
    import pandas as pd

    df = _frame(_rows("live", "cart_nudge", 50, 0.5, 3, 0.0, 1500))
    e = experiments._stats(
        df, pd.DataFrame(columns=["ts", "category", "value"]), date(2025, 1, 1), date(2025, 12, 31)
    )
    assert e.incremental_revenue == 0 and e.roi_by_offer_type == []
    assert e.treatment["measured_n"] == 0 and e.treatment["unmeasured_n"] == 50


def test_one_big_order_in_a_small_control_does_not_flip_the_result():
    import pandas as pd

    rows = _rows("holi", "bonus_points", 300, 0.07, 26, 0.04, 1200)
    rows[300] = ("holi", "Choli0", False, True, 18999, 0, "bonus_points", "default")  # a gold coin in control
    e = experiments._stats(
        _frame(rows), pd.DataFrame(columns=["ts", "category", "value"]), date(2025, 1, 1), date(2025, 12, 31)
    )
    assert e.incremental_revenue > 0


def test_seeded_headline_matches_its_breakdown():
    e = experiments.compute(START, END)
    assert e.treatment["measured_n"] > 0
    rows = e.roi_by_offer_type
    assert abs(e.incremental_revenue - sum(r["incremental_revenue"] for r in rows)) <= len(rows)
    assert abs(e.incremental_profit - sum(r["incremental_profit"] for r in rows)) <= len(rows)
