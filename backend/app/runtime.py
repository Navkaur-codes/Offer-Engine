"""Runtime switches stored in the `settings` table (owned by Main; read by the harness, bot and API)."""

from __future__ import annotations

from sqlmodel import Session

from app import db
from app.config import now, settings
from app.models import SettingRow

KILLSWITCH = "killswitch"


def get_setting(key: str, default: dict | None = None) -> dict:
    with Session(db.engine) as s:
        row = s.get(SettingRow, key)
        return dict(row.value) if row else dict(default or {})


def set_setting(key: str, value: dict) -> dict:
    with Session(db.engine) as s:
        row = s.get(SettingRow, key) or SettingRow(key=key, value={}, updated_at=now())
        row.value, row.updated_at = value, now()
        s.add(row)
        s.commit()
    return value


def killswitch_on() -> bool:
    """True = pause ALL sends. The harness pre-gate must block every decision while this is on."""
    return bool(get_setting(KILLSWITCH, {"on": False}).get("on"))


def set_killswitch(on: bool, by: str = "dashboard") -> dict:
    return set_setting(KILLSWITCH, {"on": on, "changed_at": now().isoformat(), "by": by})


LAB_GROUP = "lab_group"
QUIET_HOURS_EXEMPT = {"customer", "admin"}


def lab_group_chat_id() -> int | None:
    """The Customer Lab group: saved by `/lab here`, else the optional LAB_GROUP_CHAT_ID env override."""
    saved = get_setting(LAB_GROUP).get("chat_id")
    return int(saved) if saved is not None else settings.lab_group_chat_id


def set_lab_group(chat_id: int, title: str | None = None, by: str = "telegram") -> dict:
    return set_setting(
        LAB_GROUP, {"chat_id": chat_id, "title": title, "by": by, "changed_at": now().isoformat()}
    )


def quiet_hours_apply(trigger: str, trigger_meta: dict | None) -> bool:
    """Quiet hours hold back proactive sends only; replies to customer/admin actions and Lab rounds go out."""
    if trigger == "lab":
        return False
    return (trigger_meta or {}).get("initiated_by") not in QUIET_HOURS_EXEMPT
