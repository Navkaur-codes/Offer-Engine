"""B3: budget guard, Groq client seams, read-only tools, tool loop, top-5 batch rule (no API calls)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import httpx
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine

from app import db, ports, runtime
from app.agent import budget, groq_client, harness, tools
from app.agent.harness import decide, decide_batch, parse_output
from app.agent.llm import LLMRateLimited, LLMResponse, LLMTimeout, MockLLM
from app.config import IST, settings
from app.rules.engine import effective_policy, load_rules, screen_offers
from app.rules.offers import DEFAULT_OFFERS
from tests.core.helpers import NOW, make_context, make_profile


@pytest.fixture(autouse=True)
def memory_db(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    import app.models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(settings, "llm_daily_tokens_agent", 1000)
    monkeypatch.setattr(settings, "llm_daily_tokens_fast", 5000)
    yield engine


# ---------------------------------------------------------------- budget guard
def test_budget_modes_switch_at_80_and_100_percent():
    assert budget.mode(NOW) == "70b"
    budget.record("agent", 799, NOW)
    assert budget.mode(NOW) == "70b"
    budget.record("agent", 1, NOW)
    assert budget.mode(NOW) == "8b"  # 80% of the 70B budget
    budget.record("fast", 5000, NOW)
    assert budget.mode(NOW) == "70b"  # 8B spent, 70B still has 20% left
    budget.record("agent", 200, NOW)
    assert budget.mode(NOW) == "rules"
    status = budget.status(NOW)
    assert status["mode"] == "rules"
    assert status["agent"] == {"used": 1000, "limit": 1000, "model": settings.groq_model_agent}


def test_budget_resets_at_ist_midnight():
    late = datetime(2026, 10, 24, 23, 59, tzinfo=IST)
    budget.record("agent", 1000, late)
    budget.record("fast", 5000, late)
    assert budget.mode(late) == "rules"
    assert budget.mode(late + timedelta(minutes=2)) == "70b"  # 00:01 IST is a new day
    assert budget.usage(late + timedelta(minutes=2)) == {"agent": 0, "fast": 0}


def test_exhausted_budget_sends_decisions_to_the_rules(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "test-key-not-real")
    budget.record("agent", 1000, NOW)
    budget.record("fast", 5000, NOW)
    d = decide("C000001", "cart_abandoned", {}, now=NOW)
    assert d.decided_by == "RULES_FALLBACK" and budget.EXHAUSTED_REASON in d.fallback_reason


def test_8b_mode_uses_the_fast_model_and_charges_its_budget(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "test-key-not-real")
    used_models = []

    class FakeGroq(MockLLM):
        def __init__(self, model):
            super().__init__("good")
            used_models.append(model)

    monkeypatch.setattr(groq_client, "GroqClient", FakeGroq)
    budget.record("agent", 850, NOW)
    d = decide("C000001", "cart_abandoned", {}, now=NOW)
    assert used_models == [settings.groq_model_fast]
    assert d.decided_by == "AGENT"
    assert budget.usage(NOW)["fast"] == d.llm_tokens > 0


# ---------------------------------------------------------------- tools
def _toolbox(cid: str = "C000002") -> tools.ToolBox:
    p, ctx = make_profile(cid), make_context()
    rules = load_rules()
    cands, _ = screen_offers(p, ctx, DEFAULT_OFFERS, rules=rules)
    return tools.ToolBox(p, ctx, effective_policy(p, ctx, rules=rules), cands, rules, DEFAULT_OFFERS, None)


def test_tools_are_read_only_and_never_expose_the_hidden_truth():
    box = _toolbox()
    outputs = [box.run(t["function"]["name"], "{}") for t in tools.TOOL_SCHEMAS]
    assert all("response_type" not in o and "persuadable" not in o for o in outputs)
    assert json.loads(box.run("get_profile", "{}"))["policy"] == "deal_hunter"
    assert json.loads(box.run("drop_table", "{}"))["error"].startswith("unknown tool")
    assert "error" in json.loads(box.run("get_profile", "not json"))


def test_check_offer_is_allowed_once():
    box = _toolbox()
    args = json.dumps({"offer_id": "OF_PCT_CAT", "params": {"pct": 50, "min_basket": 999}})
    first = json.loads(box.run("check_offer", args))
    assert first["ok"] is False and first["violations"]
    assert "already used" in json.loads(box.run("check_offer", args))["error"]


class ScriptedLLM:
    """Asks for tools `tool_rounds` times, then answers like MockLLM('good')."""

    name = "scripted"

    def __init__(self, tool_rounds: int, tool: str = "check_offer"):
        self.tool_rounds, self.tool, self.calls, self.offered = tool_rounds, tool, 0, []
        self.inner = MockLLM("good")

    def chat(self, messages, tools_offered, timeout):
        self.calls += 1
        self.offered.append(tools_offered is not None)
        if self.calls <= self.tool_rounds and tools_offered:
            args = json.dumps({"offer_id": "OF_FREE_SHIP", "params": {"min_basket": 0}})
            return LLMResponse(
                "", tokens=100, tool_calls=[{"id": f"t{self.calls}", "name": self.tool, "arguments": args}]
            )
        return self.inner.chat(messages, None, timeout)


def test_agent_may_check_once_then_answers():
    llm = ScriptedLLM(tool_rounds=1)
    d = decide("C000001", "cart_abandoned", {}, now=NOW, llm=llm)
    assert d.decided_by == "AGENT" and llm.calls == 2
    assert [t.name for t in d.agent_trace][:3] == ["llm", "check_offer", "llm"]


def test_tool_steps_are_capped_and_the_last_step_must_answer():
    llm = ScriptedLLM(tool_rounds=99, tool="get_context")
    d = decide("C000001", "cart_abandoned", {}, now=NOW, llm=llm)
    assert llm.calls == harness.MAX_TOOL_STEPS + 1
    assert llm.offered[-1] is False  # no tools offered on the final step
    assert d.decided_by == "AGENT"


def test_parse_output_tolerates_a_fence():
    raw = (
        MockLLM("good")
        .chat([{"role": "user", "content": '<facts>{"candidates": []}</facts>'}], None, 1)
        .content
    )
    assert parse_output(f"```json\n{raw}\n```").decision == "NO_OFFER"
    with pytest.raises(ValueError):
        parse_output("no json here")


# ---------------------------------------------------------------- groq client (no network)
def _client_raising(exc: Exception) -> groq_client.GroqClient:
    client = groq_client.GroqClient("llama-3.3-70b-versatile", api_key="test-key-not-real")

    class Completions:
        def create(self, **kwargs):
            raise exc

    client._client = type("C", (), {"chat": type("Ch", (), {"completions": Completions()})()})()
    return client


def test_groq_errors_map_to_fallback_reasons(monkeypatch):
    import groq

    monkeypatch.setattr(groq_client, "_BUCKETS", {})
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    rate = groq.RateLimitError("429", response=httpx.Response(429, request=request), body=None)
    with pytest.raises(LLMRateLimited):
        _client_raising(rate).chat([{"role": "user", "content": "hi"}], None, 20)
    with pytest.raises(LLMTimeout):
        _client_raising(groq.APITimeoutError(request=request)).chat(
            [{"role": "user", "content": "hi"}], None, 20
        )


def test_token_bucket_refuses_instead_of_waiting():
    bucket = groq_client.TokenBucket(rpm=2, tpm=1000)
    assert bucket.take(400) and bucket.take(400)
    assert not bucket.take(10)  # out of requests: the harness falls back at once


# ---------------------------------------------------------------- batch rule
def test_batch_sends_only_the_top_5_to_the_agent(monkeypatch):
    calls = []

    def fake_pick(now):
        llm = MockLLM("good")
        calls.append(llm)
        return llm, "agent", None

    monkeypatch.setattr(harness, "pick_llm", fake_pick)
    items = [(f"C00000{i % 5 + 1}", "campaign", {}) for i in range(8)]
    out = decide_batch(items, dry_run=True, now=NOW)
    assert len(out) == 8 and len(calls) <= 5
    assert sum("batch rule" in (d.fallback_reason or "") for d in out) >= 3


def test_kill_switch_still_wins_without_any_llm_call(monkeypatch):
    runtime.set_killswitch(True)
    llm = MockLLM("good")
    d = decide("C000001", "cart_abandoned", {"initiated_by": "customer"}, now=NOW, llm=llm)
    assert d.status == "BLOCKED" and llm.calls == 0
    assert ports.decide is not None


def test_answer_wrapped_as_a_json_tool_call_is_salvaged():
    answer = {"decision": "NO_OFFER", "reasoning": {"why_customer": "x", "why_offer": "y"}, "confidence": 0.5}
    body = {
        "error": {
            "code": "tool_use_failed",
            "failed_generation": json.dumps({"name": "json", "arguments": answer}),
        }
    }
    assert parse_output(groq_client.salvage_answer(body)).decision == "NO_OFFER"
    assert groq_client.salvage_answer({"error": {"code": "invalid_api_key"}}) is None
    assert (
        groq_client.salvage_answer({"error": {"code": "tool_use_failed", "failed_generation": "{oops"}})
        is None
    )
