"""Business festival calendar, Oct 2025 – Jan 2027 (seeded into the `festivals` table).

Date sources, checked 24 Oct 2026:
- 2026 Hindu festivals (Navratri begins 12 Oct, Dussehra 20 Oct, Karwa Chauth 29 Oct, Dhanteras 6 Nov,
  Diwali 8 Nov, Lohri 13 Jan, Makar Sankranti 14 Jan): SmartPuja "Hindu Festival Calendar 2026"
  https://www.smartpuja.com/blog/wp-content/uploads/2025/12/SmartPuja_Hindu_Festival_Calendar_2026.pdf.pdf
  (Karwa Chauth / Dhanteras / Diwali also match the central-government 2026 holiday list).
- Bhai Dooj 11 Nov 2026: publicholidays.in/bhai-dooj and calendarlabs.com (one outlier says 10 Nov).
- Guru Nanak Jayanti 24 Nov 2026: gazetted holiday list 2026, CAG Punjab
  https://cag.gov.in/ag2/punjab/en/page-ag2-punjab-holiday-list
- 2025 dates (Navratri 22 Sep, Dussehra 2 Oct, Karwa Chauth 10 Oct, Dhanteras 18 Oct, Diwali 20 Oct,
  Bhai Dooj 23 Oct, Gurpurab 5 Nov) are past and match the 2025 gazetted list.
- Lohri 2027: Punjab calendars give 13 Jan; one central RH list gives 14 Jan. We keep 13 Jan (eve of
  Maghi); re-check before January. Outside the judging window either way.

Greetings come from this table only, never from the LLM (CLAUDE.md §2.9). Every religious festival
`needs_opt_in`; commercial moments (Black Friday, Republic Day sale, wedding season) don't.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.contracts import Category, Festival, FestivalPhase

STANDARD_PHASES: dict[FestivalPhase, tuple[int, int]] = {
    "teaser": (-14, -8),
    "build_up": (-7, -2),
    "last_minute": (-1, 0),
    "post": (1, 10),
}
SHORT_PHASES: dict[FestivalPhase, tuple[int, int]] = {
    "teaser": (-7, -4),
    "build_up": (-3, -2),
    "last_minute": (-1, 0),
    "post": (1, 2),
}
STRATEGY: dict[FestivalPhase, str] = {
    "teaser": "Zero-cost only: early access for VIPs, wishlist reminders, points-boost announcements.",
    "build_up": "Hero-category offers, gift bundles, min-basket flat ₹ off, gift cards.",
    "last_minute": "Delivery-cutoff nudges; free express shipping beats a discount.",
    "post": "Cross-sell to festival buyers; no discounts for customers who already bought.",
}
NO_MEAT_ALCOHOL = ["meat", "chicken", "mutton", "fish", "egg", "alcohol", "beer", "wine", "liquor"]
PUNJAB = ["Punjab"]


def _f(
    fid: str,
    name: str,
    day: date,
    heroes: list[Category],
    budget: int,
    greeting: str | None,
    *,
    opt_in: bool = True,
    phases: dict[FestivalPhase, tuple[int, int]] = STANDARD_PHASES,
    restricted: list[str] | None = None,
    region: list[str] | None = None,
    delivery: dict[int, int] | None = None,
) -> Festival:
    return Festival(
        id=fid,
        name=name,
        date=day,
        region=region,
        phases=phases,
        hero_categories=heroes,
        greeting=greeting,
        needs_opt_in=opt_in,
        restricted_promos=restricted or [],
        budget=budget,
        strategy=STRATEGY,
        delivery_days_by_tier=delivery or {1: 2, 2: 3, 3: 5},
    )


_WEDDING_PHASES: dict[FestivalPhase, tuple[int, int]] = {
    "teaser": (-21, -8),
    "build_up": (-7, 30),
    "last_minute": (31, 60),
    "post": (61, 75),
}
_NAVRATRI_PHASES: dict[FestivalPhase, tuple[int, int]] = {
    "teaser": (-10, -4),
    "build_up": (-3, -1),
    "last_minute": (0, 8),
    "post": (9, 10),
}
_SALE_PHASES: dict[FestivalPhase, tuple[int, int]] = {
    "teaser": (-7, -3),
    "build_up": (-2, -1),
    "last_minute": (0, 3),
    "post": (4, 6),
}

FESTIVALS: list[Festival] = [
    # ------------------------------------------------------------ 2025 (history the generator replays)
    _f(
        "navratri_2025",
        "Navratri",
        date(2025, 9, 22),
        ["ethnic_wear", "jewellery", "beauty"],
        60000,
        "Happy Navratri",
        phases=_NAVRATRI_PHASES,
        restricted=NO_MEAT_ALCOHOL,
    ),
    _f(
        "dussehra_2025",
        "Dussehra",
        date(2025, 10, 2),
        ["fashion", "electronics", "home_decor"],
        50000,
        "Happy Dussehra",
        phases=SHORT_PHASES,
    ),
    _f(
        "karwa_chauth_2025",
        "Karwa Chauth",
        date(2025, 10, 10),
        ["ethnic_wear", "jewellery", "beauty", "gifting"],
        40000,
        "Happy Karwa Chauth",
        phases=SHORT_PHASES,
    ),
    _f(
        "dhanteras_2025",
        "Dhanteras",
        date(2025, 10, 18),
        ["jewellery", "kitchen", "electronics"],
        60000,
        "Happy Dhanteras",
        phases=SHORT_PHASES,
    ),
    _f(
        "diwali_2025",
        "Diwali / Bandi Chhor Divas",
        date(2025, 10, 20),
        ["home_decor", "gifting", "electronics", "fashion", "grocery"],
        150000,
        "Happy Diwali",
    ),
    _f(
        "bhai_dooj_2025",
        "Bhai Dooj",
        date(2025, 10, 23),
        ["gifting", "fashion", "beauty"],
        25000,
        "Happy Bhai Dooj",
        phases=SHORT_PHASES,
        delivery={1: 1, 2: 2, 3: 3},
    ),
    _f(
        "gurpurab_2025",
        "Gurpurab (Guru Nanak Jayanti)",
        date(2025, 11, 5),
        ["ethnic_wear", "home_decor"],
        20000,
        "Gurpurab diyan lakh lakh vadhaiyan",
        phases=SHORT_PHASES,
        restricted=NO_MEAT_ALCOHOL + ["tobacco"],
    ),
    _f(
        "wedding_season_2025",
        "Wedding season",
        date(2025, 11, 20),
        ["ethnic_wear", "jewellery", "gifting", "kitchen"],
        120000,
        None,
        opt_in=False,
        phases=_WEDDING_PHASES,
    ),
    _f(
        "black_friday_2025",
        "Black Friday sale",
        date(2025, 11, 28),
        ["electronics", "winter_wear", "fashion"],
        80000,
        None,
        opt_in=False,
        phases=_SALE_PHASES,
    ),
    _f(
        "christmas_2025",
        "Christmas",
        date(2025, 12, 25),
        ["gifting", "home_decor", "winter_wear"],
        40000,
        "Merry Christmas",
        phases=SHORT_PHASES,
    ),
    # ------------------------------------------------------------ Jan 2026
    _f(
        "lohri_2026",
        "Lohri",
        date(2026, 1, 13),
        ["winter_wear", "grocery", "gifting"],
        30000,
        "Happy Lohri",
        phases=SHORT_PHASES,
        region=PUNJAB,
    ),
    _f(
        "makar_sankranti_2026",
        "Makar Sankranti",
        date(2026, 1, 14),
        ["grocery", "gifting"],
        20000,
        "Happy Makar Sankranti",
        phases=SHORT_PHASES,
    ),
    _f(
        "republic_day_2026",
        "Republic Day sale",
        date(2026, 1, 26),
        ["electronics", "fashion", "home_decor"],
        60000,
        None,
        opt_in=False,
        phases=_SALE_PHASES,
    ),
    # ------------------------------------------------------------ Oct 2026 – Jan 2027 (live during judging)
    _f(
        "navratri_2026",
        "Navratri",
        date(2026, 10, 12),
        ["ethnic_wear", "jewellery", "beauty"],
        60000,
        "Happy Navratri",
        phases=_NAVRATRI_PHASES,
        restricted=NO_MEAT_ALCOHOL,
    ),
    _f(
        "dussehra_2026",
        "Dussehra",
        date(2026, 10, 20),
        ["fashion", "electronics", "home_decor"],
        50000,
        "Happy Dussehra",
        phases=SHORT_PHASES,
    ),
    _f(
        "karwa_chauth_2026",
        "Karwa Chauth",
        date(2026, 10, 29),
        ["ethnic_wear", "jewellery", "beauty", "gifting"],
        40000,
        "Happy Karwa Chauth",
    ),
    _f(
        "dhanteras_2026",
        "Dhanteras",
        date(2026, 11, 6),
        ["jewellery", "kitchen", "electronics"],
        60000,
        "Happy Dhanteras",
        phases=SHORT_PHASES,
    ),
    _f(
        "diwali_2026",
        "Diwali / Bandi Chhor Divas",
        date(2026, 11, 8),
        ["home_decor", "gifting", "electronics", "fashion", "grocery"],
        150000,
        "Happy Diwali",
    ),
    _f(
        "bhai_dooj_2026",
        "Bhai Dooj",
        date(2026, 11, 11),
        ["gifting", "fashion", "beauty"],
        25000,
        "Happy Bhai Dooj",
        phases=SHORT_PHASES,
        delivery={1: 1, 2: 2, 3: 3},
    ),
    _f(
        "gurpurab_2026",
        "Gurpurab (Guru Nanak Jayanti)",
        date(2026, 11, 24),
        ["ethnic_wear", "home_decor"],
        20000,
        "Gurpurab diyan lakh lakh vadhaiyan",
        phases=SHORT_PHASES,
        restricted=NO_MEAT_ALCOHOL + ["tobacco"],
    ),
    _f(
        "wedding_season_2026",
        "Wedding season",
        date(2026, 11, 20),
        ["ethnic_wear", "jewellery", "gifting", "kitchen"],
        120000,
        None,
        opt_in=False,
        phases=_WEDDING_PHASES,
    ),
    _f(
        "black_friday_2026",
        "Black Friday sale",
        date(2026, 11, 27),
        ["electronics", "winter_wear", "fashion"],
        80000,
        None,
        opt_in=False,
        phases=_SALE_PHASES,
    ),
    _f(
        "christmas_2026",
        "Christmas",
        date(2026, 12, 25),
        ["gifting", "home_decor", "winter_wear"],
        40000,
        "Merry Christmas",
        phases=SHORT_PHASES,
    ),
    _f(
        "lohri_2027",
        "Lohri",
        date(2027, 1, 13),
        ["winter_wear", "grocery", "gifting"],
        30000,
        "Happy Lohri",
        phases=SHORT_PHASES,
        region=PUNJAB,
    ),
    _f(
        "makar_sankranti_2027",
        "Makar Sankranti",
        date(2027, 1, 14),
        ["grocery", "gifting"],
        20000,
        "Happy Makar Sankranti",
        phases=SHORT_PHASES,
    ),
    _f(
        "republic_day_2027",
        "Republic Day sale",
        date(2027, 1, 26),
        ["electronics", "fashion", "home_decor"],
        60000,
        None,
        opt_in=False,
        phases=_SALE_PHASES,
    ),
]


def festival_key(festival_id: str) -> str:
    """'diwali_2026' → 'diwali'. Customers opt in to a festival *key*, so opt-ins survive the year change."""
    return festival_id.rsplit("_", 1)[0]


OPT_IN_KEYS: list[str] = sorted({festival_key(f.id) for f in FESTIVALS if f.needs_opt_in})


@dataclass(frozen=True)
class Lift:
    """Demand multipliers the generator applies on a festival day (1.0 = normal day)."""

    visit: float = 1.0
    conversion: float = 1.0
    aov: float = 1.0
    categories: dict[Category, float] = field(default_factory=dict)


_MAJOR: dict[FestivalPhase, tuple[float, float, float, float]] = {  # visit, conversion, aov, hero mult
    "teaser": (1.15, 1.05, 1.00, 1.3),
    "build_up": (1.35, 1.15, 1.08, 2.2),
    "last_minute": (1.55, 1.20, 1.10, 2.4),
    "post": (0.85, 0.90, 1.00, 1.2),
}
_MINOR: dict[FestivalPhase, tuple[float, float, float, float]] = {
    "teaser": (1.05, 1.00, 1.00, 1.2),
    "build_up": (1.20, 1.10, 1.05, 1.8),
    "last_minute": (1.30, 1.15, 1.05, 2.0),
    "post": (1.00, 1.00, 1.00, 1.1),
}
_SALE: dict[FestivalPhase, tuple[float, float, float, float]] = {
    "teaser": (1.05, 1.00, 1.00, 1.1),
    "build_up": (1.25, 1.10, 1.00, 1.5),
    "last_minute": (1.60, 1.30, 1.05, 2.0),
    "post": (1.05, 1.00, 1.00, 1.1),
}
_WEDDING: dict[FestivalPhase, tuple[float, float, float, float]] = {
    "teaser": (1.00, 1.00, 1.00, 1.2),
    "build_up": (1.08, 1.05, 1.10, 1.6),
    "last_minute": (1.05, 1.05, 1.10, 1.5),
    "post": (1.00, 1.00, 1.00, 1.1),
}
_SCALE_BY_KEY = {
    "diwali": _MAJOR,
    "dhanteras": _MAJOR,
    "navratri": _MINOR,
    "dussehra": _MINOR,
    "karwa_chauth": _MINOR,
    "bhai_dooj": _MINOR,
    "gurpurab": _MINOR,
    "christmas": _MINOR,
    "lohri": _MINOR,
    "makar_sankranti": _MINOR,
    "black_friday": _SALE,
    "republic_day": _SALE,
    "wedding_season": _WEDDING,
}


def lifts(festival: Festival) -> dict[FestivalPhase, Lift]:
    """Category lift multipliers per phase. Kept beside the Festival rows (the contract has no lift field)."""
    scale = _SCALE_BY_KEY[festival_key(festival.id)]
    return {
        phase: Lift(v, c, a, {cat: hero for cat in festival.hero_categories})
        for phase, (v, c, a, hero) in scale.items()
    }


def phase_on(festival: Festival, day: date) -> FestivalPhase | None:
    offset = (day - festival.date).days
    for phase, (lo, hi) in festival.phases.items():
        if lo <= offset <= hi:
            return phase
    return None
