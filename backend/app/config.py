"""Settings from env + the single clock every module must use (`now()`)."""

from __future__ import annotations

import json
from datetime import date, datetime, time
from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict

IST = ZoneInfo("Asia/Kolkata")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    # telegram
    telegram_bot_token: str = ""
    telegram_webhook_secret: str = "dev-secret"
    customer_bot_tokens: str = "[]"  # JSON list: [{"token","customer_id","persona"}]
    lab_group_chat_id: int | None = None
    shadow_channel_id: int | None = None
    admin_telegram_ids: str = ""  # comma-separated

    # llm
    groq_api_key: str = ""
    groq_model_agent: str = "llama-3.3-70b-versatile"
    groq_model_fast: str = "llama-3.1-8b-instant"
    force_llm_fail: bool = False

    # app
    database_url: str = "sqlite:///./offer_engine.db"
    admin_passcode: str = ""
    public_base_url: str = ""  # e.g. https://offer-engine.onrender.com
    cors_origins: str = "http://localhost:5173"
    demo_time_override: str = ""  # "2026-11-06" or "2026-11-06T19:30"

    @property
    def admin_ids(self) -> set[int]:
        return {int(x) for x in self.admin_telegram_ids.split(",") if x.strip()}

    @property
    def customer_bots(self) -> list[dict]:
        return json.loads(self.customer_bot_tokens or "[]")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

# Runtime override (set by /lab date or the Playground); takes precedence over the env var.
_runtime_override: datetime | None = None


def _parse_override(raw: str) -> datetime:
    if len(raw) == 10:  # date only → keep the current wall-clock time on that day
        return datetime.combine(date.fromisoformat(raw), datetime.now(IST).time().replace(microsecond=0), IST)
    dt = datetime.fromisoformat(raw)
    return dt if dt.tzinfo else dt.replace(tzinfo=IST)


def set_time_override(value: datetime | date | str | None) -> None:
    global _runtime_override
    if value is None or value == "":
        _runtime_override = None
    elif isinstance(value, datetime):
        _runtime_override = value if value.tzinfo else value.replace(tzinfo=IST)
    elif isinstance(value, date):
        _runtime_override = datetime.combine(value, time(12, 0), IST)
    else:
        _runtime_override = _parse_override(value)


def time_override() -> datetime | None:
    if _runtime_override is not None:
        return _runtime_override
    return _parse_override(settings.demo_time_override) if settings.demo_time_override else None


def now() -> datetime:
    """Current time in IST, honouring demo time-travel. Never call datetime.now() elsewhere."""
    return time_override() or datetime.now(IST)
