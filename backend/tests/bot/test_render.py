"""Render snapshots: stub Decision fixture → expected Telegram HTML.

Regenerate after an intended copy change with: UPDATE_SNAPSHOTS=1 python -m pytest tests/bot/test_render.py
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path

import pytest

from app import stubs
from app.bot.render import FOOTER, inr, offer_value, render_decision, render_why
from app.config import IST

SNAPSHOTS = Path(__file__).parent / "snapshots"
NOW = datetime(2026, 10, 23, 19, 42, tzinfo=IST)

CASES = {
    "sent_cart_abandoner": ("C000001", "welcome", {}),
    "sent_deal_hunter": ("C000002", "welcome", {}),
    "sent_at_risk": ("C000004", "inactivity", {}),
    "no_offer_vip": ("C000003", "welcome", {}),
    "blocked_manual": ("C000001", "manual", {}),
}


def _decision(name: str, **kw):
    cid, trigger, meta = CASES[name]
    return stubs.decide(cid, trigger, meta, now=NOW, **kw)


def _snapshot(name: str, text: str) -> None:
    path = SNAPSHOTS / f"{name}.html"
    if os.environ.get("UPDATE_SNAPSHOTS") or not path.exists():
        SNAPSHOTS.mkdir(exist_ok=True)
        path.write_text(text, encoding="utf-8")
    assert text == path.read_text(encoding="utf-8")


def _visible(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")


@pytest.mark.parametrize("name", list(CASES))
def test_render_snapshot(name):
    _snapshot(name, render_decision(_decision(name)).text)


def test_offer_card_shape():
    card = render_decision(_decision("sent_cart_abandoner"))
    assert card.text.startswith("<b>Your Cotton Kurta is waiting, shipping's on us</b>")
    assert "🎟 Free shipping on Fashion · till 26 Oct" in card.text
    assert re.search(r"Code: <code>SHIP[A-Z0-9]+</code>", card.text)
    assert card.text.endswith(FOOTER)
    labels = [b.text for row in card.keyboard.inline_keyboard for b in row]
    assert labels == ["✅ Claim", "⏰ Remind me tonight", "🙅 Not for me", "❓ Why this?"]
    for row in card.keyboard.inline_keyboard:
        for b in row:
            assert len(b.callback_data.encode()) <= 64  # Telegram limit


@pytest.mark.parametrize("name", [n for n in CASES if n.startswith("sent")])
def test_offer_body_within_280_chars(name):
    body = render_decision(_decision(name)).text.removesuffix(FOOTER)
    assert len(_visible(body).strip()) <= 280


def test_coupon_not_repeated_in_personal_lines():
    d = _decision("sent_cart_abandoner")
    assert render_decision(d).text.count(d.coupon_code) == 1


def test_no_offer_and_blocked_have_only_why_button():
    for name in ("no_offer_vip", "blocked_manual"):
        card = render_decision(_decision(name))
        assert "<code>" not in card.text
        assert [b.text for row in card.keyboard.inline_keyboard for b in row] == ["❓ Why?"]


def test_held_out_never_mentions_holdout():
    d = _decision("sent_cart_abandoner").model_copy(
        update={"status": "HELD_OUT", "decided_by": "HOLDOUT", "final_offer_id": None}
    )
    card = render_decision(d)
    assert "hold" not in card.text.lower() and card.keyboard is None


def test_dry_run_has_banner_and_no_buttons():
    card = render_decision(_decision("sent_deal_hunter", dry_run=True))
    assert card.text.startswith("🧪 <b>Dry run</b>") and card.keyboard is None


def test_untrusted_text_is_escaped():
    d = _decision("sent_cart_abandoner")
    d = d.model_copy(update={"headline": "<script>x</script>", "message": "Hi <b>Bob</b> & co."})
    text = render_decision(d).text
    assert "<script>" not in text and "&lt;script&gt;" in text and "&amp; co." in text


def test_offer_values():
    assert offer_value(_decision("sent_deal_hunter")) == "10% off Ethnic wear above ₹999"
    assert offer_value(_decision("sent_at_risk")) == "15% off Home decor above ₹1,499"


def test_inr_indian_grouping():
    assert [inr(x) for x in (0, 999, 1299, 125000, 10000000)] == [
        "₹0",
        "₹999",
        "₹1,299",
        "₹1,25,000",
        "₹1,00,00,000",
    ]


def test_why_text():
    d = _decision("sent_cart_abandoner")
    assert d.explanation.telegram_text in render_why(d)
