import pytest
from pydantic import ValidationError

from app.contracts import CONTRACT_VERSION, AgentOutput, AgentReasoning, Event


def test_contract_version():
    assert CONTRACT_VERSION == "v1.1"


def test_agent_output_rejects_long_message():
    reasoning = AgentReasoning(why_customer="x", why_offer="y")
    with pytest.raises(ValidationError):
        AgentOutput(decision="SEND", message="a" * 281, reasoning=reasoning, confidence=0.5)


def test_unknown_fields_are_forbidden():
    with pytest.raises(ValidationError):
        Event(id="E1", customer_id="C1", type="view", ts="2026-10-22T10:00:00+05:30", colour="red")


def test_enum_values_are_enforced():
    with pytest.raises(ValidationError):
        Event(id="E1", customer_id="C1", type="teleport", ts="2026-10-22T10:00:00+05:30")
