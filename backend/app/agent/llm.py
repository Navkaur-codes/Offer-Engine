"""The LLM seam. The harness only talks to an `LLMClient`; Phase 3 adds Groq behind the same protocol.

`MockLLM` plays scripted behaviours so the harness can be tested (and demoed) without any API calls.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Literal, Protocol


class LLMError(Exception):
    """Any failure that sends the harness straight to the rules fallback."""


class LLMTimeout(LLMError):
    pass


class LLMRateLimited(LLMError):
    pass


@dataclass
class LLMResponse:
    content: str
    tokens: int = 0
    tool_calls: list[dict] = field(default_factory=list)


class LLMClient(Protocol):
    name: str

    def chat(self, messages: list[dict], tools: list[dict] | None, timeout: float) -> LLMResponse: ...


Behaviour = Literal[
    "good", "no_offer", "over_limit", "fix_on_retry", "invalid_json", "timeout", "rate_limited", "injected"
]


def _payload(messages: list[dict]) -> dict:
    """The harness puts the decision facts as JSON inside <facts> in the first user turn."""
    first_user = next(m["content"] for m in messages if m["role"] == "user")
    match = re.search(r"<facts>(.*?)</facts>", first_user, re.S)
    return json.loads(match.group(1)) if match else {}


class MockLLM:
    """Scripted stand-in for the agent. Picks the top candidate like a sensible model would, then
    misbehaves on purpose according to `behaviour`."""

    name = "mock"

    def __init__(self, behaviour: Behaviour = "good"):
        self.behaviour = behaviour
        self.calls = 0

    def chat(self, messages: list[dict], tools: list[dict] | None, timeout: float) -> LLMResponse:
        self.calls += 1
        if self.behaviour == "timeout":
            raise LLMTimeout(f"no answer within {timeout:g} s")
        if self.behaviour == "rate_limited":
            raise LLMRateLimited("429 Too Many Requests")
        if self.behaviour == "invalid_json":
            return LLMResponse("Sure! Here is the best offer for this customer: 10% off", tokens=40)

        facts = _payload(messages)
        cands = facts.get("candidates", [])
        if self.behaviour == "no_offer" or not cands:
            return LLMResponse(json.dumps(self._output(None, {}, "No offer needed.", facts)), tokens=300)

        cand = cands[0]
        params = {k: r.get("min", 0) for k, r in cand["allowed_params"].items()}
        greedy = self.behaviour in {"over_limit", "injected"} or (
            self.behaviour == "fix_on_retry" and self.calls == 1
        )
        if greedy:
            pct_cand = next((c for c in cands if "pct" in c["allowed_params"]), cand)
            cand, params = pct_cand, {"pct": 90 if self.behaviour == "injected" else 50, "min_basket": 0}
        first_user = next(m["content"] for m in messages if m["role"] == "user")
        typed = re.search(r'<customer_text field="first_name">(.*?)</customer_text>', first_user, re.S)
        name = typed.group(1) if typed else "there"
        value = f"{params['pct']}% off" if "pct" in params else cand["type"].replace("_", " ")
        message = (
            f"Hi {name}! {value.capitalize()} just for you till {facts.get('expiry', 'soon')}. Code {{CODE}}."
        )
        return LLMResponse(json.dumps(self._output(cand, params, message, facts)), tokens=900)

    @staticmethod
    def _output(cand: dict | None, params: dict, message: str, facts: dict) -> dict:
        policy = facts.get("customer", {}).get("policy", "?")
        return {
            "decision": "SEND" if cand else "NO_OFFER",
            "offer_id": cand["offer_id"] if cand else None,
            "params": params,
            "send_at": "now",
            "headline": "A little something for you" if cand else "",
            "message": message if cand else "",
            "reasoning": {
                "why_customer": f"Policy {policy}, trigger {facts.get('trigger')}.",
                "why_offer": "Top expected incremental profit among allowed offers." if cand else message,
                "alternatives_rejected": [
                    {"offer_id": c["offer_id"], "reason": "lower expected incremental profit"}
                    for c in facts.get("candidates", [])[1:3]
                ],
                "key_signals": [f"trigger {facts.get('trigger')}"],
                "expected_impact_inr": cand["est_incremental_profit"] if cand else 0,
            },
            "confidence": 0.7,
        }
