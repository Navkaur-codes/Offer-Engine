"""What each Lab customer does on their turn: an event to write plus the line their bot posts.

Festival-aware: when a festival is ≤ 21 days away, browsing personas drift to its hero categories.
Karan (dormant) deliberately writes nothing, so his silence keeps him dormant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app import ports
from app.bot import store
from app.bot.render import CATEGORY_LABELS, escape, inr
from app.contracts import Festival
from app.lab.registry import LabCustomer

FESTIVAL_WINDOW_DAYS = 21


@dataclass
class Activity:
    line: str  # HTML, already escaped
    events: list[dict] = field(default_factory=list)
    meta: dict = field(default_factory=dict)


def upcoming_festival(at: datetime) -> tuple[Festival, int] | None:
    soon = [(f, (f.date - at.date()).days) for f in ports.festivals()]
    soon = [(f, d) for f, d in soon if 0 <= d <= FESTIVAL_WINDOW_DAYS]
    return min(soon, key=lambda fd: fd[1]) if soon else None


def _category(c: LabCustomer, festival: tuple[Festival, int] | None, turn: int) -> str:
    if (
        festival
        and festival[0].hero_categories
        and c.persona in ("deal_hunter", "festive_gifter", "new_user", "window_shopper", "loyal_vip")
    ):
        heroes = festival[0].hero_categories
        return heroes[turn % len(heroes)]
    return c.favourite


def activity(c: LabCustomer, at: datetime, turn: int) -> Activity:
    festival = upcoming_festival(at)
    category = _category(c, festival, turn)
    item, value = store.pick_product(category, f"{c.id}{turn}")
    label = CATEGORY_LABELS.get(category, category).lower()
    name, thing = escape(c.name), f"{escape(item)} {inr(value)}"
    view = {"type": "view", "ts": at, "category": category, "item": item, "value": value}
    meta: dict = {"activity": c.persona, "category": category}
    if festival:
        meta.update(festival=festival[0].id, days_to_festival=festival[1])

    match c.persona:
        case "loyal_vip" if c.response_type == "sleeping_dog":
            line = f"🛍 {name} reorders the usual {label} basket, no fuss"
            events = [view, {"type": "session", "ts": at}]
        case "loyal_vip":
            line = f"👀 {name} is checking out the new {thing}"
            events = [{"type": "session", "ts": at}, view]
        case "deal_hunter":
            line = f"🔎 {name} is comparing prices on {thing} and two cheaper ones"
            events = [view, {**view, "ts": at + timedelta(seconds=40)}]
        case "at_risk_regular":
            line = f"📱 {name} opened the app for the first time in weeks, glanced at {thing}"
            events = [{"type": "session", "ts": at}, view]
        case "new_user":
            line = f"✨ {name} is exploring {label} for the first time: {thing}"
            events = [{"type": "session", "ts": at}, view]
        case "cart_abandoner":
            since = at - timedelta(minutes=45)
            line = f"🛒 {name} added {thing} to cart 45 min ago… and left"
            events = [
                {**view, "ts": since - timedelta(minutes=2)},
                {**view, "type": "add_to_cart", "ts": since},
            ]
            meta.update(item=item, value=value, minutes=45)
        case "window_shopper":
            line = f"👀 {name} scrolled through a handful of {label} items again, nothing in the cart"
            events = [
                view,
                {**view, "ts": at + timedelta(seconds=30)},
                {**view, "ts": at + timedelta(seconds=70)},
            ]
        case "high_returner":
            line = f"🛒 {name} added {thing} to cart (4th try-on order this season)"
            events = [view, {**view, "type": "add_to_cart", "ts": at + timedelta(seconds=50)}]
        case "dormant":
            line = f"💤 {name} hasn't opened the app in over 6 months"
            events = []
        case "festive_gifter":
            when = f" for {escape(festival[0].name)} ({festival[1]} days away)" if festival else ""
            line = f"🎁 {name} is browsing gifts{when}: {thing}"
            events = [{"type": "session", "ts": at}, view]
        case _:
            line = f"👀 {name} is browsing {thing}"
            events = [view]
    return Activity(line, events, meta)
