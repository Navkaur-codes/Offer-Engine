"""Offer card image (CLAUDE.md §7): graphite header, signal-orange value, amber expiry chip, mono coupon.

Only facts already in the Decision are drawn (offer type + params, category, expiry, code, first name).
Rendered in memory; callers fall back to the text card on any error, so this must never be load-bearing.
"""

from __future__ import annotations

from functools import cache
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.bot.render import CATEGORY_LABELS, _offer_type_and_category, inr, short_name
from app.contracts import Decision

ASSETS = Path(__file__).parent / "assets"
W, H, SCALE = 1080, 600, 2  # drawn at 2× a 540×300 design for crisp phone screens
BG, SURFACE, INK, MUTED, LINE = "#FAFAFA", "#FFFFFF", "#0A0A0B", "#71717A", "#E7E7EA"
RAIL, SIGNAL, AMBER, ON_RAIL = "#0B0B0D", "#FF4F00", "#F5A524", "#A1A1AA"
RADIUS = 8 * SCALE
EXT_CHARS = frozenset("₹")  # not in Geist's latin subset; drawn from latin-ext


@cache
def _font(file: str, size: int, weight: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        font = ImageFont.truetype(str(ASSETS / file), size)
        font.set_variation_by_axes([weight])
        return font
    except OSError:  # font missing: Pillow's own font keeps the card readable
        return ImageFont.load_default(size)


def _fonts(size: int, weight: int = 400, mono: bool = False):
    if mono:
        f = _font("GeistMono-latin.woff2", size, weight)
        return f, f
    return _font("Geist-latin.woff2", size, weight), _font("Geist-latin-ext.woff2", size, weight)


def _runs(text: str, size: int, weight: int, mono: bool):
    main, ext = _fonts(size, weight, mono)
    run, use_ext = "", False
    for ch in text:
        wants_ext = ch in EXT_CHARS
        if run and wants_ext != use_ext:
            yield run, ext if use_ext else main
            run = ""
        run, use_ext = run + ch, wants_ext
    if run:
        yield run, ext if use_ext else main


def text_width(text: str, size: int, weight: int = 400, mono: bool = False) -> int:
    return int(sum(f.getlength(r) for r, f in _runs(text, size, weight, mono)))


def draw_text(draw: ImageDraw.ImageDraw, xy, text: str, size: int, fill: str, weight=400, mono=False) -> None:
    x, y = xy
    for run, font in _runs(text, size, weight, mono):
        draw.text((x, y), run, font=font, fill=fill)
        x += font.getlength(run)


def fit_size(text: str, max_width: int, start: int, smallest: int, weight: int) -> int:
    size = start
    while size > smallest and text_width(text, size, weight) > max_width:
        size -= 4
    return size


def headline_value(d: Decision) -> str:
    """The big orange line: exactly the offer's own numbers, nothing invented."""
    otype, _ = _offer_type_and_category(d)
    p = d.final_params
    match otype:
        case "pct_off":
            return f"{p.get('pct', '?')}% OFF"
        case "flat_off":
            return f"{inr(p.get('amount', p.get('flat', 0)))} OFF"
        case "free_shipping":
            return "FREE SHIPPING"
        case "free_express":
            return "FREE EXPRESS"
        case "bonus_points":
            return f"{p.get('multiplier', 2)}× POINTS"
        case "early_access":
            return "EARLY ACCESS"
        case "points_reminder":
            return "POINTS EXPIRING"
        case "cart_nudge":
            return "CART SAVED"
        case "gift_card":
            return f"{inr(p.get('amount', 0))} GIFT CARD"
        case _:
            return (d.final_offer_id or "OFFER").removeprefix("OF_").replace("_", " ").upper()


def detail_line(d: Decision) -> str:
    otype, category = _offer_type_and_category(d)
    parts = []
    if category or d.final_params.get("category"):
        cat = category or d.final_params["category"]
        parts.append(f"on {CATEGORY_LABELS.get(cat, cat)}")
    if d.final_params.get("min_basket"):
        parts.append(f"above {inr(d.final_params['min_basket'])}")
    if not parts:
        parts.append("on your next order" if otype != "early_access" else "before everyone else")
    return " · ".join(parts)


def render_card(d: Decision) -> bytes:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    m = 12 * SCALE
    card = (m, m, W - m, H - m)
    draw.rounded_rectangle(card, RADIUS, fill=SURFACE, outline=LINE, width=SCALE)

    header_h = 56 * SCALE
    draw.rounded_rectangle((m, m, W - m, m + header_h), RADIUS, fill=RAIL)
    draw.rectangle((m, m + header_h - RADIUS, W - m, m + header_h), fill=RAIL)  # square the band's bottom
    pad = 28 * SCALE
    draw_text(draw, (m + pad, m + 17 * SCALE), "HOLDOUT", 20 * SCALE, "#FFFFFF", weight=600)
    who = f"for {short_name(d.profile_snapshot.first_name, 16)}"
    size = 16 * SCALE
    draw_text(draw, (W - m - pad - text_width(who, size), m + 20 * SCALE), who, size, ON_RAIL)

    inner = W - 2 * (m + pad)
    value = headline_value(d)
    vsize = fit_size(value, inner, 60 * SCALE, 30 * SCALE, 600)
    top = m + header_h + 26 * SCALE
    draw_text(draw, (m + pad, top), value, vsize, SIGNAL, weight=600)
    draw_text(draw, (m + pad, top + vsize + 18 * SCALE), detail_line(d), 18 * SCALE, INK)

    row_y = H - m - pad - 40 * SCALE
    if d.coupon_code:
        csize = 20 * SCALE
        code_w = text_width(d.coupon_code, csize, 500, mono=True)
        box = (m + pad, row_y, m + pad + code_w + 28 * SCALE, row_y + 40 * SCALE)
        draw.rounded_rectangle(box, 6 * SCALE, fill=BG, outline=LINE, width=SCALE)
        draw_text(
            draw, (box[0] + 14 * SCALE, row_y + 8 * SCALE), d.coupon_code, csize, INK, weight=500, mono=True
        )
    if d.expires_at:
        chip = f"till {d.expires_at:%d %b}"
        size = 16 * SCALE
        chip_w = text_width(chip, size, 600) + 28 * SCALE
        x1 = W - m - pad
        draw.rounded_rectangle(
            (x1 - chip_w, row_y + 4 * SCALE, x1, row_y + 36 * SCALE), 16 * SCALE, fill=AMBER
        )
        draw_text(draw, (x1 - chip_w + 14 * SCALE, row_y + 10 * SCALE), chip, size, INK, weight=600)

    out = BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()
