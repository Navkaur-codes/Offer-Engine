"""FastAPI entrypoint: health, Telegram webhook, and (from Phase 2) the REST API in app.api."""

from __future__ import annotations

import hmac
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update

from app import ports
from app.config import now, settings
from app.contracts import CONTRACT_VERSION
from app.db import init_db

VERSION = "0.1.0"
WEBHOOK_PATH = "/telegram/webhook/{secret}"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)  # its INFO lines contain the bot token in the URL
log = logging.getLogger("app")


async def _start_bot(app: FastAPI) -> None:
    app.state.tg = None
    if not settings.telegram_bot_token:
        log.warning("TELEGRAM_BOT_TOKEN not set; bot disabled")
        return
    tg = ports.build_application()
    await tg.initialize()
    await tg.start()
    app.state.tg = tg
    if settings.public_base_url:
        url = settings.public_base_url.rstrip("/") + WEBHOOK_PATH.format(
            secret=settings.telegram_webhook_secret
        )
        await tg.bot.set_webhook(
            url, secret_token=settings.telegram_webhook_secret, allowed_updates=Update.ALL_TYPES
        )
        log.info("webhook registered")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    await _start_bot(app)
    yield
    if app.state.tg is not None:
        await app.state.tg.stop()
        await app.state.tg.shutdown()


app = FastAPI(title="Offer Engine", version=VERSION, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health(request: Request) -> dict:
    return {
        "ok": True,
        "version": VERSION,
        "contracts": CONTRACT_VERSION,
        "now": now().isoformat(),
        "bot": getattr(request.app.state, "tg", None) is not None,
        "ports": ports.status(),
    }


@app.post(WEBHOOK_PATH, include_in_schema=False)
async def telegram_webhook(secret: str, request: Request) -> dict:
    header = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    expected = settings.telegram_webhook_secret
    if not (hmac.compare_digest(secret, expected) and hmac.compare_digest(header, expected)):
        raise HTTPException(status_code=403)
    tg = getattr(request.app.state, "tg", None)
    if tg is None:
        raise HTTPException(status_code=503, detail="bot disabled")
    await tg.process_update(Update.de_json(await request.json(), tg.bot))
    return {"ok": True}
