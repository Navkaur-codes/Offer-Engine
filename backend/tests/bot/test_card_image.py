"""Offer card image: one render per offer type, long names, speed, and the never-break-delivery fallback."""

from __future__ import annotations

import time
from datetime import datetime
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from PIL import Image
from telegram.error import BadRequest, Forbidden

from app import stubs
from app.bot import card_image, sender
from app.config import IST

NOW = datetime(2026, 10, 26, 11, 0, tzinfo=IST)


def _offer(otype: str, params: dict, category: str | None = None, name: str = "Navpreet"):
    d = stubs.decide("C000001", "lab", now=NOW)
    cand = d.candidates[0].model_copy(update={"offer_id": "OF_TEST", "type": otype, "category": category})
    profile = d.profile_snapshot.model_copy(update={"first_name": name})
    return d.model_copy(
        update={
            "candidates": [cand],
            "final_offer_id": "OF_TEST",
            "final_params": params,
            "profile_snapshot": profile,
        }
    )


CASES = [
    ("pct_off", {"pct": 10, "min_basket": 999}, "ethnic_wear", "10% OFF", "on Ethnic wear · above ₹999"),
    ("flat_off", {"amount": 150, "min_basket": 1499}, None, "₹150 OFF", "above ₹1,499"),
    ("free_shipping", {"min_basket": 0}, "fashion", "FREE SHIPPING", "on Fashion"),
    ("bonus_points", {"multiplier": 2}, None, "2× POINTS", "on your next order"),
    ("early_access", {}, "electronics", "EARLY ACCESS", "on Electronics"),
]


@pytest.mark.parametrize(("otype", "params", "category", "value", "detail"), CASES)
def test_renders_every_offer_type(otype, params, category, value, detail):
    d = _offer(otype, params, category)
    assert card_image.headline_value(d) == value
    assert card_image.detail_line(d) == detail
    png = card_image.render_card(d)
    img = Image.open(BytesIO(png))
    assert img.format == "PNG" and img.size == (card_image.W, card_image.H)
    assert img.getpixel((card_image.W // 2, 40)) == (11, 11, 13)  # graphite header band


def test_value_uses_signal_orange():
    img = Image.open(BytesIO(card_image.render_card(_offer("free_shipping", {}, "fashion"))))
    assert (255, 79, 0) in {c for _, c in img.getcolors(1_000_000)}


def test_long_name_stays_inside_the_header():
    d = _offer("pct_off", {"pct": 15}, "beauty", name="Venkatanarasimharajuvaripeta Subrahmanyam")
    who = f"for {card_image.short_name(d.profile_snapshot.first_name, 16)}"
    assert who == "for Venkatanarasimh…"
    assert card_image.text_width(who, 16 * card_image.SCALE) < card_image.W // 2
    card_image.render_card(d)


def test_fast_enough():
    d = _offer("pct_off", {"pct": 10, "min_basket": 999}, "ethnic_wear")
    card_image.render_card(d)  # warm the font cache
    t = time.perf_counter()
    card_image.render_card(d)
    assert time.perf_counter() - t < 0.15


def _bot(photo_error: Exception | None = None):
    sent = []

    async def send_photo(chat_id, photo, caption, **kw):
        if photo_error:
            raise photo_error
        sent.append(("photo", caption, photo))
        return SimpleNamespace(message_id=1)

    async def send_message(chat_id, text, **kw):
        sent.append(("text", text, None))
        return SimpleNamespace(message_id=2)

    return SimpleNamespace(send_photo=send_photo, send_message=send_message, sent=sent)


async def test_sent_offer_goes_as_photo_with_card_caption():
    bot = _bot()
    d = _offer("free_shipping", {}, "fashion")
    await sender.send_decision(bot, 1, d)
    kind, caption, png = bot.sent[0]
    assert kind == "photo" and png.startswith(b"\x89PNG") and "<code>" in caption and len(caption) <= 1024


async def test_photo_failure_falls_back_to_text():
    bot = _bot(BadRequest("wrong file identifier"))
    await sender.send_decision(bot, 1, _offer("pct_off", {"pct": 10}, "beauty"))
    assert [k for k, *_ in bot.sent] == ["text"]


async def test_render_failure_falls_back_to_text(monkeypatch):
    def boom(d):
        raise ValueError("bad font")

    monkeypatch.setattr(card_image, "render_card", boom)
    bot = _bot()
    await sender.send_decision(bot, 1, _offer("pct_off", {"pct": 10}, "beauty"))
    assert [k for k, *_ in bot.sent] == ["text"]


async def test_blocked_customer_gets_no_text_retry(chat):
    from .test_handlers import _onboard

    await _onboard(chat)
    bot = _bot(Forbidden("bot was blocked by the user"))
    assert await sender.send_card(bot, chat.user.id, _offer("pct_off", {"pct": 10}), "hi") is None
    assert bot.sent == []


async def test_no_offer_and_blocked_stay_text():
    for d in (stubs.decide("C000003", "lab", now=NOW), stubs.decide("C000001", "manual", now=NOW)):
        bot = _bot()
        bot.send_photo = AsyncMock(side_effect=AssertionError("no image for non-offers"))
        await sender.send_decision(bot, 1, d)
        assert [k for k, *_ in bot.sent] == ["text"]
