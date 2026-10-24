"""The synthetic world must look like Indian e-commerce (judging criterion: data realism)."""

from __future__ import annotations

from datetime import date

import pytest

from app.data import stats
from app.data.generator import DEFAULT_END, SIM_START, generate
from app.data.personas import response_effect

DIWALI_2025 = date(2025, 10, 20)


@pytest.fixture(scope="module", params=[42, 7], ids=lambda s: f"seed{s}")
def world(request):
    return generate(5000, request.param, SIM_START, DEFAULT_END)


def _within(value: float, key: str) -> None:
    lo, hi = stats.BENCHMARKS[key]
    assert lo <= value <= hi, f"{key}={value:.3f} outside [{lo}, {hi}]"


def test_pareto_top20_share(world):
    _within(stats.pareto_top20_share(world.orders), "pareto_top20_share")


def test_cart_abandonment(world):
    _within(stats.cart_abandon_rate(world.events), "cart_abandon_rate")


def test_view_to_purchase(world):
    _within(stats.view_to_purchase(world.events), "view_to_purchase")


def test_fashion_return_rate(world):
    _within(stats.return_rate_by_category(world.orders)["fashion"], "fashion_return_rate")


def test_diwali_week_beats_normal_week(world):
    _within(stats.festival_week_ratio(world.orders, DIWALI_2025), "diwali_week_ratio")


def test_evening_session_share(world):
    _within(stats.evening_session_share(world.events), "evening_session_share")


def test_funnel_is_monotone(world):
    f = stats.funnel(world.events)
    assert f["view"] > f["session"] > f["add_to_cart"] > f["checkout_started"] > f["purchase"] > 0


def test_retention_decays(world):
    first = stats.retention_cohorts(world.orders)[0]
    assert first["m1"] > first["m6"] > 0


def test_category_economics_are_ordered(world):
    aov = stats.aov_by_category(world.orders)
    assert aov["electronics"] > aov["fashion"] > aov["grocery"]
    returns = stats.return_rate_by_category(world.orders)
    assert returns["fashion"] > returns["electronics"] > returns["grocery"]


def test_messy_data_is_present(world):
    c = world.customers
    assert 0.02 <= c["age"].isna().mean() <= 0.04
    sessions = world.events[world.events["type"] == "session"]
    assert sessions.duplicated(["customer_id", "sid"]).sum() > 0
    assert c["heavy_returner"].sum() > c["persona"].eq("high_returner").sum()


def test_punjab_heavy_city_mix(world):
    share = (world.customers["state"] == "Punjab").mean()
    assert 0.40 <= share <= 0.50
    assert set(world.customers["city_tier"]) == {1, 2, 3}


def test_holdout_is_ten_percent(world):
    assert 0.08 <= world.customers["is_holdout"].mean() <= 0.12


def test_campaigns_have_ten_percent_control(world):
    camp = world.campaigns
    assert camp["campaign_id"].nunique() >= 6
    assert "diwali_2025" in set(camp["campaign_id"])
    for _, grp in camp.groupby("campaign_id"):
        assert 0.06 <= grp["is_control"].mean() <= 0.14


def test_campaign_outcomes_follow_response_type(world):
    camp = world.campaigns.merge(
        world.customers[["id", "response_type"]], left_on="customer_id", right_on="id"
    )
    conv = camp.groupby(["response_type", "is_control"])["converted"].mean()
    uplift = {r: conv[(r, False)] - conv[(r, True)] for r in ("persuadable", "sure_thing", "sleeping_dog")}
    assert uplift["persuadable"] > 0.08
    assert abs(uplift["sure_thing"]) < 0.04
    # only ~80 sleeping dogs land in control, so assert the ordering here and the sign on the mechanism
    assert uplift["sleeping_dog"] < uplift["persuadable"] - 0.08
    visit, conv, churn = response_effect("sleeping_dog", 1.0)
    assert visit < 1 and conv < 1 and churn > 0


def test_points_and_tiers(world):
    c = world.customers
    assert (c["points_balance"] >= 0).all()
    assert set(c["tier"]) <= {"Bronze", "Silver", "Gold", "Platinum"}
    assert c["tier"].value_counts()["Bronze"] > c["tier"].value_counts().get("Platinum", 0)


def test_generation_is_deterministic():
    a, b = generate(300, 3), generate(300, 3)
    assert a.customers["first_name"].tolist() == b.customers["first_name"].tolist()
    assert a.orders["value"].tolist() == b.orders["value"].tolist()
