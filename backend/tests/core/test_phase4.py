"""Phase 4: the daily digest and the rule-impact preview (no API calls)."""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app import db, ports, runtime
from app.agent import digest
from app.agent.harness import decide
from app.agent.llm import LLMError, LLMResponse, MockLLM
from app.models import CustomerRow
from app.rules import preview
from app.rules.seed_rules import SEED_RULES
from tests.core.helpers import NOW, make_profile

DAY = NOW.date()


@pytest.fixture(autouse=True)
def memory_db(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    import app.models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db, "engine", engine)
    preview._cache.update(at=0.0, day=None, profiles=[])
    yield engine


def _a_day_of_decisions() -> None:
    for i, cid in enumerate(["C000001", "C000002", "C000004", "C000005", "C000003"]):
        decide(
            cid,
            "browse_interest",
            {"initiated_by": "customer"},
            now=NOW + timedelta(minutes=i),
            llm=MockLLM("good"),
        )
    runtime.set_killswitch(True)
    decide("C000001", "browse_interest", {}, now=NOW + timedelta(minutes=10))
    runtime.set_killswitch(False)


# ---------------------------------------------------------------- digest
def test_empty_day_digest_is_five_honest_lines():
    lines = digest.daily(date(2026, 10, 1)).splitlines()
    assert len(lines) == 5 and lines[0].startswith("01 Oct: 0 decisions")
    assert "no offers went out" in lines[2]


def test_digest_counts_come_from_the_log():
    _a_day_of_decisions()
    s = digest.stats(DAY)
    assert s["total"] == 6 and s["status"].get("SENT", 0) >= 4 and s["status"].get("BLOCKED", 0) >= 1
    lines = digest.daily(DAY).splitlines()
    assert len(lines) == 5
    assert lines[0].startswith(f"{DAY:%d %b}: 6 decisions")
    assert "Top blocks:" in lines[1] and "the kill switch" in lines[1]
    assert lines[4].startswith("Suggestion")


class DigestLLM:
    name = "digest-mock"

    def __init__(self, lines=None, error=None):
        self.lines, self.error = lines, error

    def chat(self, messages, tools, timeout):
        if self.error:
            raise self.error
        return LLMResponse(json.dumps({"lines": self.lines}), tokens=321)


def test_llm_rewrite_is_used_when_it_sticks_to_the_facts():
    _a_day_of_decisions()
    lines = [f"{w}: 6 decisions today." for w in ("Totals", "Spend", "Segments", "Festival", "Suggestion")]
    assert digest.daily(DAY, llm=DigestLLM(lines)).splitlines() == lines


@pytest.mark.parametrize(
    "llm",
    [
        DigestLLM(["6 decisions, 93% claimed."] * 5),  # invented 93
        DigestLLM(["only one line"]),
        DigestLLM(error=LLMError("429")),
    ],
    ids=["invented-number", "wrong-shape", "llm-error"],
)
def test_digest_falls_back_to_the_template(llm):
    _a_day_of_decisions()
    assert digest.daily(DAY, llm=llm) == "\n".join(digest.template(digest.stats(DAY)))


# ---------------------------------------------------------------- rule impact preview
def _deal_hunters(n: int = 6):
    return [
        make_profile("C000002", aov=1199 + 100 * i).model_copy(update={"customer_id": f"C1000{i:02d}"})
        for i in range(n)
    ]


def test_tightening_a_cap_shows_who_changes_and_the_budget_effect():
    cap = next(r for r in SEED_RULES if r.id == "P_DEAL_CAP")
    zero = cap.model_copy(update={"params": {"max_pct": 0, "min_basket": 999}, "version": cap.version + 1})
    res = preview.impact(zero, profiles=_deal_hunters(), now=NOW)
    assert res["sample_size"] == 6
    assert res["customers_affected"] >= 1 and res["budget_delta"] <= 0
    ex = res["examples"][0]
    assert ex["customer_id"].startswith("C1000") and ex["before"] != ex["after"]


def test_an_unchanged_rule_affects_nobody():
    cap = next(r for r in SEED_RULES if r.id == "P_DEAL_CAP")
    res = preview.impact(cap, profiles=_deal_hunters(), now=NOW)
    assert res == {"customers_affected": 0, "budget_delta": 0, "examples": [], "sample_size": 6}


def test_switching_off_a_blocking_rule_is_visible():
    dogs = [
        make_profile("C000002", policy="sleeping_dog").model_copy(update={"customer_id": f"C2000{i:02d}"})
        for i in range(3)
    ]
    rule = next(r for r in SEED_RULES if r.id == "P_SLEEPING_DOG").model_copy(update={"enabled": False})
    res = preview.impact(rule, profiles=dogs, now=NOW)
    assert res["customers_affected"] == 3
    assert all(e["before"] == "not allowed" and e["after"].startswith("up to") for e in res["examples"])


def test_sample_comes_from_synthetic_customers_only(memory_db):
    with Session(memory_db) as s:
        for i in range(8):
            s.add(
                CustomerRow(
                    id=f"C30000{i}",
                    first_name="T",
                    city="Pune",
                    city_tier=1,
                    signup_date=date(2025, 1, 1),
                    channel="organic",
                    device="android",
                    preferred_payment="upi",
                    persona="deal_hunter",
                    response_type="persuadable",
                    is_lab_bot=i == 0,
                )
            )
        s.commit()
    profiles = preview.sample_profiles(NOW, size=5)
    assert len(profiles) == 5 and "C300000" not in {p.customer_id for p in profiles}
    assert preview.sample_profiles(NOW, size=5) is profiles  # cached
    assert ports.build_profile is not None


def test_cap_10_to_8_shows_a_saving_and_names_the_offer():
    cap = next(r for r in SEED_RULES if r.id == "P_DEAL_CAP")
    eight = cap.model_copy(update={"params": {"max_pct": 8, "min_basket": 999}})
    res = preview.impact(eight, profiles=_deal_hunters(), now=NOW)
    assert res["customers_affected"] == 6 and res["budget_delta"] < 0
    ex = res["examples"][0]
    assert ex["offer"] == "% off a category"
    assert ex["before"].startswith("up to 10% off") and ex["after"].startswith("up to 8% off")


def test_suggestion_is_plain_english_without_codes():
    s = {
        "total": 8,
        "status": {"SENT": 2, "NO_OFFER": 6},
        "decided_by": {"RULES_FALLBACK": 8},
        "top_blocks": [("NO_CANDIDATES", 6)],
    }
    line = digest._suggestion(s)
    assert (
        line
        == "Suggestion: 6 of 8 decisions found no allowed offer; review the persona caps on the Rules page."
    )
    assert not digest._CODE.search(line)
    s["top_blocks"] = [("G_FREQ", 6)]
    assert "the frequency cap" in digest._suggestion(s) and "G_FREQ" not in digest._suggestion(s)


def test_a_rewrite_that_shows_an_internal_code_is_rejected():
    _a_day_of_decisions()
    lines = ["6 decisions today, NO_CANDIDATES held some."] * 5
    assert digest.daily(DAY, llm=DigestLLM(lines)) == "\n".join(digest.template(digest.stats(DAY)))
