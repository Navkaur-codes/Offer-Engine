"""Groq behind the LLMClient protocol. Never retries: a 429, a timeout or an empty bucket goes straight to the
rules fallback, so a busy free tier can never stall or silence the bot."""

from __future__ import annotations

import json
import logging
import threading
import time as timer

from app.agent.llm import LLMError, LLMRateLimited, LLMResponse, LLMTimeout
from app.config import settings

log = logging.getLogger(__name__)

TEMPERATURE = 0.3
MAX_OUTPUT_TOKENS = 700
REASONING_OUTPUT_TOKENS = 1_500  # gpt-oss thinks before it answers; the thinking counts as output
# Groq free tier per model (requests and tokens per minute); we stay a little under.
FREE_TIER = {
    "llama-3.3-70b-versatile": (28, 11_000),
    "llama-3.1-8b-instant": (28, 5_500),
    "openai/gpt-oss-120b": (28, 7_500),
    "openai/gpt-oss-20b": (28, 7_500),
}
DEFAULT_TIER = (25, 5_000)


def is_reasoning_model(model: str) -> bool:
    return model.startswith("openai/gpt-oss")


class TokenBucket:
    """Requests-per-minute and tokens-per-minute buckets, refilled continuously. `take` never blocks."""

    def __init__(self, rpm: int, tpm: int):
        self.cap = {"req": float(rpm), "tok": float(tpm)}
        self.level = dict(self.cap)
        self.stamp = timer.monotonic()
        self.lock = threading.Lock()

    def _refill(self) -> None:
        now = timer.monotonic()
        elapsed = now - self.stamp
        self.stamp = now
        for k in self.level:
            self.level[k] = min(self.cap[k], self.level[k] + self.cap[k] * elapsed / 60)

    def take(self, tokens: int) -> bool:
        with self.lock:
            self._refill()
            if self.level["req"] < 1 or self.level["tok"] < tokens:
                return False
            self.level["req"] -= 1
            self.level["tok"] -= tokens
            return True


_BUCKETS: dict[str, TokenBucket] = {}


def bucket_for(model: str) -> TokenBucket:
    if model not in _BUCKETS:
        _BUCKETS[model] = TokenBucket(*FREE_TIER.get(model, DEFAULT_TIER))
    return _BUCKETS[model]


def output_cap(model: str) -> int:
    return REASONING_OUTPUT_TOKENS if is_reasoning_model(model) else MAX_OUTPUT_TOKENS


def estimate_tokens(messages: list[dict], tools: list[dict] | None, model: str = "") -> int:
    chars = sum(len(str(m.get("content") or "")) for m in messages) + len(json.dumps(tools or []))
    return chars // 4 + output_cap(model)


def salvage_answer(body: object) -> str | None:
    """gpt-oss sometimes emits its final JSON as a call to a tool named "json" (Groq 400 tool_use_failed).
    Groq returns that generation; recover the answer from it instead of spending a second call."""
    error = body.get("error", body) if isinstance(body, dict) else None
    if not isinstance(error, dict) or error.get("code") != "tool_use_failed":
        return None
    try:
        generated = json.loads(error.get("failed_generation") or "")
    except json.JSONDecodeError:
        return None
    if isinstance(generated, dict) and isinstance(generated.get("arguments"), dict):
        generated = generated["arguments"]
    if isinstance(generated, dict) and "decision" in generated:
        return json.dumps(generated)
    return None


class GroqClient:
    def __init__(self, model: str, api_key: str | None = None):
        from groq import Groq

        self.name = model
        self.model = model
        self._client = Groq(api_key=api_key or settings.groq_api_key, max_retries=0)

    def chat(self, messages: list[dict], tools: list[dict] | None, timeout: float) -> LLMResponse:
        import groq

        if not bucket_for(self.model).take(estimate_tokens(messages, tools, self.model)):
            raise LLMRateLimited("local token bucket empty")
        kwargs: dict = dict(
            model=self.model,
            messages=messages,
            temperature=TEMPERATURE,
            max_tokens=output_cap(self.model),
            timeout=timeout,
        )
        if is_reasoning_model(self.model):
            kwargs["reasoning_effort"] = "low"
        if tools:
            kwargs.update(tools=tools, tool_choice="auto")
        else:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            resp = self._client.chat.completions.create(**kwargs)
        except groq.RateLimitError as exc:
            raise LLMRateLimited("Groq 429") from exc
        except groq.APITimeoutError as exc:
            raise LLMTimeout(f"Groq gave no answer within {timeout:g} s") from exc
        except groq.BadRequestError as exc:
            salvaged = salvage_answer(getattr(exc, "body", None))
            if salvaged is None:
                log.warning("Groq 400 for %s: %s", self.model, str(getattr(exc, "body", ""))[:300])
                raise LLMError("Groq error 400") from exc
            # the answer was generated, just wrapped as a call to a "json" tool: count it, don't pay twice
            return LLMResponse(content=salvaged, tokens=estimate_tokens(messages, tools, self.model))
        except groq.APIError as exc:
            status = getattr(exc, "status_code", "")
            log.warning("Groq %s error for %s: %s", status, self.model, str(getattr(exc, "body", ""))[:300])
            raise LLMError(f"Groq error {status}".strip()) from exc
        msg = resp.choices[0].message
        calls = [
            {"id": c.id, "name": c.function.name, "arguments": c.function.arguments}
            for c in (msg.tool_calls or [])
        ]
        tokens = resp.usage.total_tokens if resp.usage else 0
        return LLMResponse(content=msg.content or "", tokens=tokens, tool_calls=calls)
