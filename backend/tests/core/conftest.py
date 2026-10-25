from __future__ import annotations

import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def _no_real_llm(monkeypatch):
    """Unit tests never reach Groq, even when a key sits in the worktree .env (live runs are scripts)."""
    monkeypatch.setattr(settings, "groq_api_key", "")
    monkeypatch.setattr(settings, "force_llm_fail", False)
