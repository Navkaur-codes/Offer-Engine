from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine

import app.models  # noqa: F401  (registers tables)
from app import db
from app.bot import sender


@pytest.fixture(autouse=True)
def memory_db(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db, "engine", engine)
    sender._RECENT.clear()
    yield engine


class FakeChat:
    """Stands in for update + context: records every reply/edit/send as (kind, text, keyboard)."""

    def __init__(self, user_id: int = 55512345, first_name: str = "Navpreet"):
        self.sent: list[tuple[str, str, object]] = []
        self.user_data: dict = {}
        self.user = SimpleNamespace(id=user_id, first_name=first_name)
        self.chat = SimpleNamespace(id=user_id)
        self._message_id = 100
        self.bot = SimpleNamespace(send_message=AsyncMock(side_effect=self._record("send", skip_chat=True)))

    def _record(self, kind: str, skip_chat: bool = False):
        async def record(*args, **kwargs):
            text = args[1] if skip_chat else (args[0] if args else kwargs.get("text"))
            self.sent.append((kind, text, kwargs.get("reply_markup")))
            self._message_id += 1
            return SimpleNamespace(message_id=self._message_id)

        return record

    def message_update(self, text: str = "/start"):
        message = SimpleNamespace(text=text, reply_text=AsyncMock(side_effect=self._record("reply")))
        return SimpleNamespace(
            update_id=1, effective_user=self.user, effective_chat=self.chat, effective_message=message,
            callback_query=None,
        )

    def button_update(self, data: str):
        query = SimpleNamespace(
            data=data,
            answer=AsyncMock(),
            edit_message_text=AsyncMock(side_effect=self._record("edit")),
            edit_message_reply_markup=AsyncMock(side_effect=self._record_markup),
        )
        message = SimpleNamespace(reply_text=AsyncMock(side_effect=self._record("reply")))
        return SimpleNamespace(
            update_id=2, effective_user=self.user, effective_chat=self.chat, effective_message=message,
            callback_query=query,
        )

    async def _record_markup(self, markup=None, **kwargs):
        self.sent.append(("markup", None, markup))

    def context(self, args: list[str] | None = None):
        return SimpleNamespace(
            user_data=self.user_data, bot=self.bot, args=args or [], job_queue=MagicMock(), error=None
        )

    @property
    def last_text(self) -> str:
        return next(t for _, t, _ in reversed(self.sent) if t is not None)


@pytest.fixture
def chat() -> FakeChat:
    return FakeChat()
