"""The Customer Lab cast: 10 fixed synthetic customers voiced round-robin by 1–10 "Lab Shopper" bots.

Each Lab customer has a hand-written character sheet whose history is built so the real `assign_policy`
lands on the intended persona (VIP spend, deal-hunter coupon use, at-risk silence, …). `ensure_lab_customers`
is idempotent and cheap, and runs before every Lab round, because a re-seed wipes `C…` history.
Tokens never leave this module's memory: only bot usernames are stored (in `customers.attrs`).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import delete, func
from sqlmodel import Session, select

from app import db
from app.bot import store
from app.config import now, settings
from app.models import CustomerBotRow, CustomerRow, EventRow, OrderRow, PointsLedgerRow


@dataclass(frozen=True)
class Order:
    days_ago: int
    category: str
    discount_pct: int = 0
    returned: bool = False


@dataclass(frozen=True)
class LabCustomer:
    id: str
    name: str
    label: str  # what the group sees: "👤 Priya · Deal hunter"
    persona: str  # contracts.Persona
    response_type: str  # hidden ground truth; drives how the customer reacts to offers
    signup_days_ago: int
    orders: list[Order] = field(default_factory=list)
    views_90d: int = 4
    city: tuple[str, int] = ("Ludhiana", 2)
    festivals: tuple[str, ...] = ()
    favourite: str = "fashion"
    past_offers: tuple[int, ...] = ()  # days ago a past campaign offer arrived and was answered "Not for me"


def _orders(spec: list[tuple]) -> list[Order]:
    return [Order(*o) for o in spec]


LAB_CUSTOMERS: list[LabCustomer] = [
    LabCustomer(
        "C900001",
        "Arjun",
        "VIP",
        "loyal_vip",
        "sure_thing",
        540,
        _orders(
            [
                (4, "electronics"),
                (19, "electronics"),
                (33, "jewellery"),
                (58, "electronics"),
                (80, "fashion"),
                (115, "electronics"),
                (160, "jewellery"),
                (210, "electronics"),
                (270, "electronics"),
                (330, "fashion"),
            ]
        ),
        views_90d=14,
        city=("Bengaluru", 1),
        favourite="electronics",
    ),
    LabCustomer(
        "C900002",
        "Priya",
        "Deal hunter",
        "deal_hunter",
        "persuadable",
        400,
        _orders(
            [
                (12, "ethnic_wear", 10),
                (40, "beauty", 15),
                (71, "ethnic_wear", 10),
                (102, "fashion"),
                (150, "ethnic_wear", 15),
                (205, "beauty", 10),
            ]
        ),
        views_90d=22,
        city=("Jaipur", 2),
        favourite="ethnic_wear",
    ),
    LabCustomer(
        "C900003",
        "Gurpreet",
        "At-risk regular",
        "at_risk_regular",
        "persuadable",
        480,
        _orders(
            [(75, "home_decor"), (110, "kitchen"), (150, "home_decor"), (200, "home_decor"), (260, "kitchen")]
        ),
        views_90d=2,
        city=("Amritsar", 2),
        favourite="home_decor",
    ),
    LabCustomer(
        "C900004",
        "Simran",
        "New shopper",
        "new_user",
        "persuadable",
        6,
        _orders([(5, "beauty")]),
        views_90d=6,
        city=("Chandigarh", 2),
        favourite="beauty",
    ),
    LabCustomer(
        "C900005",
        "Rohan",
        "Cart abandoner",
        "cart_abandoner",
        "persuadable",
        300,
        _orders([(22, "fashion"), (65, "electronics"), (130, "fashion")]),
        views_90d=18,
        city=("Pune", 1),
        favourite="fashion",
    ),
    LabCustomer(
        "C900006",
        "Aisha",
        "Window shopper",
        "window_shopper",
        "lost_cause",
        220,
        [],
        views_90d=26,
        city=("Lucknow", 2),
        favourite="home_decor",
    ),
    LabCustomer(
        "C900007",
        "Vikram",
        "Frequent returner",
        "high_returner",
        "persuadable",
        350,
        _orders(
            [
                (9, "fashion", 0, True),
                (30, "fashion", 0, True),
                (55, "electronics"),
                (90, "fashion", 0, True),
                (140, "winter_wear", 0, True),
                (190, "fashion"),
            ]
        ),
        views_90d=12,
        city=("Delhi", 1),
        favourite="fashion",
    ),
    LabCustomer(
        "C900008",
        "Meera",
        "Sleeping dog",
        "loyal_vip",
        "sleeping_dog",
        720,
        # long-standing, regular, full-price buyer: the uplift model reads any promo as a net negative
        _orders(
            [
                (22, "gifting"),
                (38, "kitchen"),
                (55, "gifting"),
                (71, "kitchen"),
                (110, "kitchen"),
                (166, "gifting"),
                (210, "kitchen"),
                (250, "gifting"),
                (295, "kitchen"),
            ]
        ),
        views_90d=8,
        city=("Kochi", 2),
        favourite="kitchen",
        past_offers=(45, 120),  # said "Not for me" to two past campaigns: promos annoy her
    ),
    LabCustomer(
        "C900009",
        "Karan",
        "Dormant",
        "dormant",
        "lost_cause",
        700,
        _orders([(200, "electronics"), (260, "fashion"), (340, "electronics")]),
        views_90d=0,
        city=("Indore", 2),
        favourite="electronics",
    ),
    LabCustomer(
        "C900010",
        "Neha",
        "Festive gifter",
        "festive_gifter",
        "persuadable",
        420,
        _orders([(24, "gifting"), (358, "jewellery"), (362, "gifting"), (366, "home_decor")]),
        views_90d=9,
        city=("Ludhiana", 2),
        festivals=("diwali", "karwa_chauth"),
        favourite="gifting",
    ),
]
BY_ID = {c.id: c for c in LAB_CUSTOMERS}
POINTS_EXPIRY_DAYS = 180


def find(name_or_id: str) -> LabCustomer | None:
    key = name_or_id.strip().lower()
    return next((c for c in LAB_CUSTOMERS if key in (c.id.lower(), c.name.lower())), None)


def tokens() -> list[str]:
    """Lab Shopper tokens from CUSTOMER_BOT_TOKENS; extra keys (customer_id, persona) are ignored."""
    return [b["token"] for b in settings.customer_bots if isinstance(b, dict) and b.get("token")][:10]


def voice_index(customer: LabCustomer, n_bots: int) -> int:
    """Round-robin: customer i is voiced by bot i mod n (4 bots → 3/3/2/2 customers)."""
    return LAB_CUSTOMERS.index(customer) % n_bots


# ---------------------------------------------------------------- DB setup
def _history(c: LabCustomer, clock: datetime) -> tuple[list[dict], list[dict], list[dict]]:
    rng = random.Random(c.id)
    events: list[dict] = []
    orders: list[dict] = []
    ledger: list[dict] = []

    def event(typ: str, ts: datetime, category=None, item=None, value=None) -> None:
        events.append(
            dict(
                id=f"E{c.id}-L{len(events) + 1:05d}",
                customer_id=c.id,
                type=typ,
                ts=ts,
                category=category,
                item=item,
                value=value,
                meta={"src": "lab"},
            )
        )

    for i, o in enumerate(c.orders):
        pick = store.premium_product if c.response_type == "sure_thing" else store.pick_product
        item, value = pick(o.category, f"{c.id}{i}")
        ts = clock - timedelta(days=o.days_ago, hours=rng.randint(1, 10), minutes=rng.randint(0, 59))
        event("session", ts - timedelta(minutes=9))
        event("view", ts - timedelta(minutes=7), o.category, item, value)
        event("add_to_cart", ts - timedelta(minutes=5), o.category, item, value)
        event("purchase", ts, o.category, item, value)
        oid = f"O{c.id}-L{i + 1:04d}"
        orders.append(
            dict(
                id=oid,
                customer_id=c.id,
                ts=ts,
                category=o.category,
                items=1,
                value=value,
                discount=value * o.discount_pct // 100,
                payment_method="upi",
                returned=o.returned,
                coupon_code=f"SAVE{o.discount_pct}" if o.discount_pct else None,
            )
        )
        if o.returned:
            event("return", ts + timedelta(days=rng.randint(3, 8)), o.category, item, value)
        elif value >= 100:
            ledger.append(
                dict(
                    customer_id=c.id,
                    ts=ts,
                    delta=value // 100,
                    reason=f"lab:earn:{oid}",
                    expires_on=(ts + timedelta(days=POINTS_EXPIRY_DAYS)).date(),
                )
            )
    for v in range(c.views_90d):
        item, value = store.pick_product(c.favourite, f"{c.id}v{v}")
        ts = clock - timedelta(days=rng.randint(1, 85), hours=rng.randint(0, 12))
        event("view", ts, c.favourite, item, value)
    for days in c.past_offers:
        ts = clock - timedelta(days=days)
        event("offer_received", ts)
        event("offer_declined", ts + timedelta(hours=2))
    return events, orders, ledger


def _row(c: LabCustomer, clock: datetime, existing: CustomerRow | None) -> CustomerRow:
    row = existing or CustomerRow(
        id=c.id,
        first_name=c.name,
        city=c.city[0],
        city_tier=c.city[1],
        signup_date=clock.date(),
        channel="lab",
        device="mobile",
        preferred_payment="upi",
        persona=c.persona,
        response_type=c.response_type,
    )
    row.first_name, row.city, row.city_tier = c.name, c.city[0], c.city[1]
    row.signup_date = (clock - timedelta(days=c.signup_days_ago)).date()
    row.persona, row.response_type = c.persona, c.response_type
    row.is_lab_bot, row.is_holdout, row.opted_out, row.paused_until = True, False, False, None
    row.opt_in_festivals = list(c.festivals)
    row.suppressed = {}
    return row


def ensure_lab_customers(force: bool = False) -> int:
    """Creates or repairs the 10 Lab customers and their history. Returns how many were (re)built."""
    clock = now()
    with Session(db.engine) as s:
        broken = [c for c in LAB_CUSTOMERS if force or not _healthy(s, c)]
    if not broken:
        return 0
    # history is built before the write session: it reads products in sessions of its own
    histories = {c.id: _history(c, clock) for c in broken}
    with Session(db.engine) as s:
        for c in broken:
            events, orders, ledger = histories[c.id]
            row = _row(c, clock, s.get(CustomerRow, c.id))
            row.points_balance = sum(p["delta"] for p in ledger if p["expires_on"] > clock.date())
            row.attrs = {**(row.attrs or {}), "lab": True}
            s.add(row)
            s.flush()  # customer row before its history (foreign keys on Postgres)
            for model in (EventRow, OrderRow, PointsLedgerRow):
                s.execute(delete(model).where(model.customer_id == c.id))
            for model, rows in ((EventRow, events), (OrderRow, orders), (PointsLedgerRow, ledger)):
                if rows:
                    s.execute(model.__table__.insert(), rows)
        s.commit()
    return len(broken)


def _healthy(s: Session, c: LabCustomer) -> bool:
    row = s.get(CustomerRow, c.id)
    n_orders = s.exec(select(func.count()).select_from(OrderRow).where(OrderRow.customer_id == c.id)).one()
    n_declined = s.exec(
        select(func.count())
        .select_from(EventRow)
        .where(EventRow.customer_id == c.id, EventRow.type == "offer_declined")
    ).one()
    # comparing counts against the sheet repairs a re-seed and picks up sheet changes after a deploy
    return (
        row is not None and row.is_lab_bot and n_orders >= len(c.orders) and n_declined >= len(c.past_offers)
    )


def remember_voices(usernames: list[str]) -> None:
    """Stores which Lab Shopper voices whom (usernames only): one `customer_bots` row per Lab customer, which
    also tells the seed to keep that customer (CR-C1)."""
    if not usernames:
        return
    with Session(db.engine) as s:
        for c in LAB_CUSTOMERS:
            row = s.get(CustomerRow, c.id)
            if row is None:
                continue
            username = usernames[voice_index(c, len(usernames))]
            row.attrs = {**(row.attrs or {}), "lab_voice": username}
            s.add(row)
            voice = s.get(CustomerBotRow, c.id) or CustomerBotRow(
                customer_id=c.id, username=username, persona=c.persona
            )
            voice.username, voice.persona = username, c.persona
            s.add(voice)
        s.commit()
