"""Decision → Telegram HTML card + inline buttons (CLAUDE.md §7 "Telegram messages").

Pure functions only: no DB, no network. Every dynamic string is HTML-escaped because names and LLM text
are untrusted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html import escape as _html_escape

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.contracts import Decision


def escape(text: str) -> str:
    return _html_escape(text, quote=False)  # Telegram HTML only needs & < > escaped


CATEGORY_LABELS = {
    "fashion": "Fashion",
    "ethnic_wear": "Ethnic wear",
    "electronics": "Electronics",
    "beauty": "Beauty",
    "home_decor": "Home decor",
    "kitchen": "Kitchen",
    "grocery": "Grocery",
    "jewellery": "Jewellery",
    "gifting": "Gifting",
    "winter_wear": "Winter wear",
}

FOOTER = "<i>Reply /why to see why you got this · /stop to opt out</i>"
OFFER_STATUSES = {"SENT", "DRY_RUN", "QUEUED"}


@dataclass(frozen=True)
class Card:
    text: str
    keyboard: InlineKeyboardMarkup | None = None


def inr(amount: int | float) -> str:
    """₹ with Indian digit grouping: ₹1,299 · ₹1,25,000."""
    n = round(amount)
    digits = str(abs(n))
    head, tail = digits[:-3], digits[-3:]
    if head:
        tail = re.sub(r"(\d)(?=(\d{2})+$)", r"\1,", head) + "," + tail
    return ("-₹" if n < 0 else "₹") + tail


def _offer_type_and_category(d: Decision) -> tuple[str | None, str | None]:
    for c in d.candidates:
        if c.offer_id == d.final_offer_id:
            return c.type, c.category
    return None, None


def offer_value(d: Decision) -> str:
    """Plain value line, e.g. "Free shipping on Fashion" or "10% off Ethnic wear above ₹999"."""
    otype, category = _offer_type_and_category(d)
    p = d.final_params
    label = CATEGORY_LABELS.get(category, category) if category else ""
    on = f" on {label}" if label else ""
    above = f" above {inr(p['min_basket'])}" if p.get("min_basket") else ""
    match otype:
        case "pct_off":
            return f"{p.get('pct', '?')}% off {label}".rstrip() + above
        case "flat_off":
            return f"{inr(p.get('amount', p.get('flat', 0)))} off{on}{above}"
        case "free_shipping":
            return f"Free shipping{on}{above}"
        case "free_express":
            return f"Free express delivery{on}{above}"
        case "bonus_points":
            return f"{p.get('multiplier', 2)}× reward points{above}"
        case "points_reminder":
            return "Your reward points are about to expire"
        case "early_access":
            return f"Early access to the sale{on}"
        case "cart_nudge":
            return "Your cart is saved for you"
        case "gift_card":
            return f"{inr(p.get('amount', 0))} gift card"
        case _:
            raw = (d.final_offer_id or "offer").removeprefix("OF_").replace("_", " ")
            return raw.capitalize()


def personal_lines(d: Decision, limit: int = 2) -> list[str]:
    """Up to two sentences of the message, skipping any that repeat the coupon (it gets its own line)."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", d.message or "") if s.strip()]
    if d.coupon_code:
        sentences = [s for s in sentences if d.coupon_code not in s]
    return sentences[:limit]


def offer_keyboard(decision_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Claim", callback_data=f"o:claim:{decision_id}"),
                InlineKeyboardButton("⏰ Remind me tonight", callback_data=f"o:remind:{decision_id}"),
            ],
            [
                InlineKeyboardButton("🙅 Not for me", callback_data=f"o:decline:{decision_id}"),
                InlineKeyboardButton("❓ Why this?", callback_data=f"o:why:{decision_id}"),
            ],
        ]
    )


def why_keyboard(decision_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("❓ Why?", callback_data=f"o:why:{decision_id}")]])


def _offer_card(d: Decision) -> Card:
    parts = []
    if d.status == "DRY_RUN":
        parts.append("🧪 <b>Dry run</b> · not sent to anyone")
    parts.append(f"<b>{escape(d.headline or offer_value(d))}</b>")
    parts.extend(escape(line) for line in personal_lines(d))
    value = f"🎟 {escape(offer_value(d))}"
    if d.expires_at:
        value += f" · till {d.expires_at:%d %b}"
    parts.append("")
    parts.append(value)
    if d.coupon_code:
        parts.append(f"Code: <code>{escape(d.coupon_code)}</code>")
    parts.append("")
    parts.append(FOOTER)
    keyboard = offer_keyboard(d.id) if d.status != "DRY_RUN" else None
    return Card("\n".join(parts), keyboard)


def _no_offer_card(d: Decision) -> Card:
    name = escape(d.profile_snapshot.first_name)
    if d.status == "HELD_OUT":  # never reveal the holdout group to the customer
        body = "Nothing to send you right now. We'll message you when something genuinely fits."
        return Card(f"<b>You're all set, {name}</b>\n{body}")
    text = (
        f"<b>No offer right now, {name}</b>\n"
        f"{escape(d.explanation.telegram_text)}\n\n"
        "<i>We only send offers when they genuinely help.</i>"
    )
    return Card(text, why_keyboard(d.id))


def _blocked_card(d: Decision) -> Card:
    text = (
        "<b>Holding off for now</b>\n"
        f"{escape(d.explanation.telegram_text)}\n\n"
        "<i>Our rules keep offers rare and respectful.</i>"
    )
    return Card(text, why_keyboard(d.id))


def render_decision(d: Decision) -> Card:
    if d.status in OFFER_STATUSES and d.final_offer_id:
        return _offer_card(d)
    if d.status == "BLOCKED":
        return _blocked_card(d)
    return _no_offer_card(d)


def render_why(d: Decision) -> str:
    e = d.explanation
    return f"<b>{escape(e.title)}</b>\n{escape(e.telegram_text)}\n\n<i>{escape(e.rules_line)}</i>"
