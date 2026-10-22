from fastapi.testclient import TestClient

from app import main
from app.config import settings


def _client(monkeypatch) -> TestClient:
    monkeypatch.setattr(settings, "telegram_bot_token", "")
    monkeypatch.setattr(settings, "database_url", "sqlite://")
    return TestClient(main.app)


def test_health(monkeypatch):
    with _client(monkeypatch) as client:
        body = client.get("/health").json()
    assert body["ok"] is True and body["contracts"] == "v1" and body["bot"] is False
    assert "decide" in body["ports"]


def test_webhook_rejects_wrong_secret(monkeypatch):
    with _client(monkeypatch) as client:
        r = client.post(
            "/telegram/webhook/wrong", json={}, headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"}
        )
    assert r.status_code == 403


def test_webhook_needs_header_too(monkeypatch):
    secret = settings.telegram_webhook_secret
    with _client(monkeypatch) as client:
        r = client.post(f"/telegram/webhook/{secret}", json={})
    assert r.status_code == 403


def test_webhook_without_bot_is_503(monkeypatch):
    secret = settings.telegram_webhook_secret
    with _client(monkeypatch) as client:
        r = client.post(
            f"/telegram/webhook/{secret}", json={}, headers={"X-Telegram-Bot-Api-Secret-Token": secret}
        )
    assert r.status_code == 503
