"""Day-by-day behaviour simulation: customers, sessions, funnels, orders, returns, points, campaigns.

Everything is seeded (numpy + Faker en_IN), so `generate(n, seed)` is reproducible. Each simulated day:
  expected sessions = persona rate × customer spread × season × weekday × payday × festival lift
                      × (campaign effect by hidden response type) × (0.03 once churned)
  each session: views → add_to_cart → checkout_started → purchase, category drawn from the
  customer's affinity × festival hero lift, order value lognormal per category, then matched to a real
  catalogue product. Churn is a per-persona hazard (scripted for dormant / at-risk personas).

Past campaigns run inside the same loop with a random 10% control group, so their outcomes come from
the same behaviour model; that is the uplift model's training data.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

import numpy as np
import pandas as pd
from faker import Faker

from app.config import IST
from app.contracts import Category, OfferType
from app.data.catalog import CATEGORIES, PRODUCTS
from app.data.festivals import FESTIVALS, OPT_IN_KEYS, Lift, lifts, phase_on
from app.data.personas import (
    PERSONAS,
    RESPONSE_BASELINE,
    RESPONSE_COUPON_MULT,
    RESPONSE_DECLINE_P,
    response_effect,
)

SIM_START = date(2025, 10, 1)
DEFAULT_END = date(2026, 10, 23)

CATS: list[Category] = list(CATEGORIES)
PERSONA_NAMES = list(PERSONAS)
RESPONSES = ["persuadable", "sure_thing", "lost_cause", "sleeping_dog"]

# (city, tier, state, weight). Punjab ≈ 45% of customers, the rest spread across India.
CITIES: list[tuple[str, int, str, float]] = [
    ("Ludhiana", 2, "Punjab", 0.090),
    ("Amritsar", 2, "Punjab", 0.070),
    ("Jalandhar", 2, "Punjab", 0.060),
    ("Patiala", 2, "Punjab", 0.045),
    ("Mohali", 2, "Punjab", 0.045),
    ("Bathinda", 3, "Punjab", 0.030),
    ("Hoshiarpur", 3, "Punjab", 0.020),
    ("Pathankot", 3, "Punjab", 0.015),
    ("Moga", 3, "Punjab", 0.015),
    ("Firozpur", 3, "Punjab", 0.015),
    ("Kapurthala", 3, "Punjab", 0.015),
    ("Sangrur", 3, "Punjab", 0.015),
    ("Barnala", 3, "Punjab", 0.015),
    ("Delhi", 1, "Delhi", 0.090),
    ("Chandigarh", 2, "Chandigarh", 0.050),
    ("Mumbai", 1, "Maharashtra", 0.050),
    ("Bengaluru", 1, "Karnataka", 0.045),
    ("Gurugram", 1, "Haryana", 0.035),
    ("Hyderabad", 1, "Telangana", 0.030),
    ("Pune", 1, "Maharashtra", 0.025),
    ("Jaipur", 2, "Rajasthan", 0.030),
    ("Lucknow", 2, "Uttar Pradesh", 0.030),
    ("Panipat", 3, "Haryana", 0.020),
    ("Karnal", 3, "Haryana", 0.020),
    ("Dehradun", 3, "Uttarakhand", 0.020),
    ("Jammu", 3, "Jammu & Kashmir", 0.020),
    ("Kolkata", 1, "West Bengal", 0.025),
    ("Chennai", 1, "Tamil Nadu", 0.020),
    ("Shimla", 3, "Himachal Pradesh", 0.010),
]

# Session start hour-of-day weights (IST): quiet nights, lunch bump, evening peak 20:00–23:00.
HOUR_WEIGHTS = np.array(
    [
        1.5,
        0.8,
        0.4,
        0.3,
        0.3,
        0.4,
        0.8,
        1.5,
        2.5,
        3.0,
        3.2,
        3.5,
        4.0,
        4.2,
        3.6,
        3.3,
        3.4,
        3.8,
        4.5,
        5.5,
        7.0,
        7.8,
        7.5,
        4.5,
    ]
)
WEEKDAY = np.array([0.95, 0.95, 0.97, 0.98, 1.02, 1.10, 1.12])  # Mon..Sun
MONTH = {
    1: 0.95,
    2: 0.92,
    3: 0.97,
    4: 0.90,
    5: 0.90,
    6: 0.88,
    7: 0.86,
    8: 0.92,
    9: 0.97,
    10: 1.05,
    11: 1.05,
    12: 1.02,
}
WINTER_WEAR_BY_MONTH = {
    1: 3.2,
    2: 1.6,
    3: 0.5,
    4: 0.2,
    5: 0.1,
    6: 0.1,
    7: 0.1,
    8: 0.15,
    9: 0.3,
    10: 0.9,
    11: 2.5,
    12: 3.2,
}
CHANNELS = (
    ["organic", "google_ads", "instagram", "whatsapp_referral", "affiliate", "youtube"],
    [0.30, 0.22, 0.20, 0.13, 0.08, 0.07],
)
POINTS_EXPIRY_DAYS = 180
CHURNED_ACTIVITY = 0.03


@dataclass(frozen=True)
class Campaign:
    id: str
    name: str
    start: date
    days: int
    offer_type: OfferType
    params: dict
    strength: float  # 0..1, how strong the incentive is (feeds personas.response_effect)
    share: float  # share of eligible customers targeted
    coupon: str
    region: str | None = None


CAMPAIGNS: list[Campaign] = [
    Campaign(
        "diwali_2025",
        "Diwali 2025: 15% off hero categories",
        date(2025, 10, 13),
        8,
        "pct_off",
        {"pct": 15, "min_basket": 999},
        1.0,
        0.50,
        "DIWALI15",
    ),
    Campaign(
        "black_friday_2025",
        "Black Friday: ₹300 off ₹1,999",
        date(2025, 11, 25),
        6,
        "flat_off",
        {"flat": 300, "min_basket": 1999},
        0.8,
        0.35,
        "BF300",
    ),
    Campaign(
        "lohri_2026",
        "Lohri: free shipping (Punjab)",
        date(2026, 1, 9),
        5,
        "free_shipping",
        {"min_basket": 0},
        0.6,
        0.60,
        "LOHRISHIP",
        region="Punjab",
    ),
    Campaign(
        "holi_2026",
        "Holi: double points",
        date(2026, 2, 26),
        7,
        "bonus_points",
        {"multiplier": 2},
        0.35,
        0.30,
        "HOLI2X",
    ),
    Campaign(
        "summer_sale_2026",
        "Summer sale: 10% off",
        date(2026, 5, 22),
        7,
        "pct_off",
        {"pct": 10, "min_basket": 799},
        0.75,
        0.40,
        "SUMMER10",
    ),
    Campaign(
        "independence_day_2026",
        "Independence Day: ₹200 off ₹1,499",
        date(2026, 8, 12),
        5,
        "flat_off",
        {"flat": 200, "min_basket": 1499},
        0.7,
        0.35,
        "AZADI200",
    ),
]
CONTROL_SHARE = 0.10


@dataclass
class SimData:
    customers: pd.DataFrame
    products: pd.DataFrame
    events: pd.DataFrame
    orders: pd.DataFrame
    points: pd.DataFrame
    campaigns: pd.DataFrame
    start: date
    end: date


# ------------------------------------------------------------------ calendar
def _strongest_lift(day: date) -> tuple[Lift, str | None]:
    best, best_id = Lift(), None
    for f in FESTIVALS:
        phase = phase_on(f, day)
        if phase is None:
            continue
        lift = lifts(f)[phase]
        if best_id is None or lift.visit > best.visit:
            best, best_id = lift, f.id
    return best, best_id


def _day_factors(days: list[date]) -> dict[str, np.ndarray]:
    T = len(days)
    visit, conv, aov = np.ones(T), np.ones(T), np.ones(T)
    fest_visit, fest_conv, fest_aov = np.ones(T), np.ones(T), np.ones(T)
    catmult = np.ones((T, len(CATS)))
    for t, d in enumerate(days):
        lift, _ = _strongest_lift(d)
        fest_visit[t], fest_conv[t], fest_aov[t] = lift.visit, lift.conversion, lift.aov
        for c, m in lift.categories.items():
            catmult[t, CATS.index(c)] *= m
        catmult[t, CATS.index("winter_wear")] *= WINTER_WEAR_BY_MONTH[d.month]
        payday = d.day <= 5
        month_end = (d + timedelta(days=2)).month != d.month
        visit[t] = MONTH[d.month] * WEEKDAY[d.weekday()] * (1.12 if payday else 1.05 if month_end else 1.0)
        conv[t] = 1.08 if payday else 1.0
    return dict(
        visit=visit,
        conv=conv,
        aov=aov,
        fest_visit=fest_visit,
        fest_conv=fest_conv,
        fest_aov=fest_aov,
        catmult=catmult,
    )


# ------------------------------------------------------------------ customers
def _customers(n: int, rng: np.random.Generator, fake: Faker, T: int, factors: dict) -> pd.DataFrame:
    shares = np.array([PERSONAS[p].share for p in PERSONA_NAMES])
    persona_idx = rng.choice(len(PERSONA_NAMES), n, p=shares)
    personas = np.array(PERSONA_NAMES)[persona_idx]

    response = np.empty(n, dtype=object)
    for i, p in enumerate(PERSONA_NAMES):
        mask = persona_idx == i
        mix = PERSONAS[p].response_mix
        response[mask] = rng.choice(list(mix), mask.sum(), p=list(mix.values()))

    # signup day relative to SIM_START (negative = customer before the simulated year)
    signup_weights = (1 + 0.6 * np.arange(T) / T) * factors["fest_visit"] ** 1.5
    signup_weights /= signup_weights.sum()
    pre_existing = rng.random(n) < 0.55
    signup_t = np.where(pre_existing, -rng.integers(1, 730, n), rng.choice(T, n, p=signup_weights))
    is_new = personas == "new_user"
    signup_t[is_new] = rng.integers(T - 60, T, is_new.sum())
    scripted = np.isin(personas, ["dormant", "at_risk_regular"])
    old_enough = rng.random(n) < 0.8
    signup_t[scripted] = np.where(
        old_enough[scripted], -rng.integers(30, 730, scripted.sum()), rng.integers(0, T - 200, scripted.sum())
    )
    active_from = np.maximum(signup_t, 0)

    hazard = np.array([PERSONAS[p].churn_hazard for p in personas])
    never = T + 10_000
    churn_t = np.where(hazard > 0, active_from + rng.geometric(np.where(hazard > 0, hazard, 1.0)), never)
    churn_t = np.where(churn_t >= T, never, churn_t)
    at_risk = personas == "at_risk_regular"
    churn_t[at_risk] = T - rng.integers(45, 111, at_risk.sum())
    dormant = personas == "dormant"
    churn_t[dormant] = np.minimum(active_from[dormant] + rng.integers(20, 150, dormant.sum()), T - 150)

    city_w = np.array([c[3] for c in CITIES])
    city_idx = rng.choice(len(CITIES), n, p=city_w / city_w.sum())
    tiers = np.array([CITIES[i][1] for i in city_idx])

    genders = rng.choice(["F", "M"], n, p=[0.52, 0.48])
    names = [fake.first_name_female() if g == "F" else fake.first_name_male() for g in genders]
    gender = np.where(rng.random(n) < 0.04, None, genders)  # messy: some never told us

    age_mean = np.array([PERSONAS[p].age_mean for p in personas])
    age_sd = np.array([PERSONAS[p].age_sd for p in personas])
    age = np.clip(rng.normal(age_mean, age_sd), 18, 72).round().astype(int).astype(object)
    age[rng.random(n) < 0.03] = None  # messy: ~3% missing age

    payment = np.empty(n, dtype=object)
    for tier, p in {1: [0.62, 0.13, 0.25], 2: [0.62, 0.23, 0.15], 3: [0.55, 0.37, 0.08]}.items():
        mask = tiers == tier
        payment[mask] = rng.choice(["upi", "cod", "card"], mask.sum(), p=p)

    opted = rng.random(n) < 0.6
    opt_ins = [
        sorted(k for k in OPT_IN_KEYS if rng.random() < 0.35) or [str(rng.choice(OPT_IN_KEYS))] if o else []
        for o in opted
    ]

    heavy_returner = (personas == "high_returner") | (rng.random(n) < 0.01)
    visit_mult = rng.lognormal(-0.5 * 0.85**2, 0.85, n)

    affinity = np.zeros((n, len(CATS)))
    for i, p in enumerate(PERSONA_NAMES):
        mask = persona_idx == i
        base = np.array([PERSONAS[p].category_weights()[c] for c in CATS])
        affinity[mask] = rng.dirichlet(base * 25, mask.sum())

    sim_start = SIM_START
    return pd.DataFrame(
        {
            "id": [f"C{i + 1:06d}" for i in range(n)],
            "first_name": names,
            "age": age,
            "gender": gender,
            "city": [CITIES[i][0] for i in city_idx],
            "state": [CITIES[i][2] for i in city_idx],
            "city_tier": tiers,
            "signup_date": [sim_start + timedelta(days=int(s)) for s in signup_t],
            "channel": rng.choice(CHANNELS[0], n, p=CHANNELS[1]),
            "device": rng.choice(["android", "ios", "web"], n, p=[0.72, 0.10, 0.18]),
            "preferred_payment": payment,
            "persona": personas,
            "response_type": response,
            "opt_in_festivals": opt_ins,
            "is_holdout": rng.random(n) < 0.10,
            "heavy_returner": heavy_returner,
            "visit_mult": visit_mult,
            "signup_t": signup_t,
            "active_from": active_from,
            "churn_t": churn_t,
            "affinity": list(affinity),
        }
    )


# ------------------------------------------------------------------ the simulation
def generate(
    n_customers: int = 5000, seed: int = 42, start: date = SIM_START, end: date = DEFAULT_END
) -> SimData:
    if start != SIM_START:
        raise ValueError("the festival lifts and campaigns are calibrated for SIM_START")
    rng = np.random.default_rng(seed)
    fake = Faker("en_IN")
    fake.seed_instance(seed)

    days = [start + timedelta(days=t) for t in range(_days(start, end))]
    T = len(days)
    f = _day_factors(days)
    cust = _customers(n_customers, rng, fake, T, f)
    n = len(cust)

    personas = cust["persona"].to_numpy()
    spec = [PERSONAS[p] for p in personas]
    rate = np.array([s.visit_rate for s in spec]) * cust["visit_mult"].to_numpy()
    p_cart = np.array([s.p_cart for s in spec])
    p_chk = np.array([s.p_checkout for s in spec])
    p_pur = np.array([s.p_purchase for s in spec])
    aov_mult = np.array([s.aov_mult for s in spec])
    disc_use = np.clip(
        np.array([s.discount_usage for s in spec])
        * np.array([RESPONSE_COUPON_MULT[r] for r in cust["response_type"]]),
        0,
        0.95,
    )
    ret_mult = np.array([s.return_mult for s in spec]) * np.where(
        cust["heavy_returner"].to_numpy() & (personas != "high_returner"), 3.0, 1.0
    )
    fest_sens = np.array([s.festival_sensitivity for s in spec])
    resp = cust["response_type"].to_numpy()
    base_visit = np.array([RESPONSE_BASELINE[r][0] for r in resp])
    base_conv = np.array([RESPONSE_BASELINE[r][1] for r in resp])
    affinity = np.vstack(cust["affinity"].to_numpy())
    active_from = cust["active_from"].to_numpy()
    churn_t = cust["churn_t"].to_numpy().copy()
    pref_pay = cust["preferred_payment"].to_numpy()

    prod_price = np.array([p.price for p in PRODUCTS])
    prod_cat = np.array([CATS.index(p.category) for p in PRODUCTS])
    cat_products = [np.where(prod_cat == c)[0] for c in range(len(CATS))]
    cat_sorted = [idx[np.argsort(prod_price[idx])] for idx in cat_products]
    cat_median = np.array([CATEGORIES[c].aov_median for c in CATS])
    cat_sigma = np.array([CATEGORIES[c].aov_sigma for c in CATS])
    cat_ret = np.array([CATEGORIES[c].return_rate for c in CATS])
    cat_ship = np.array([CATEGORIES[c].shipping_cost for c in CATS])
    hour_p = HOUR_WEIGHTS / HOUR_WEIGHTS.sum()
    day0 = int(datetime.combine(start, time(0), IST).timestamp())

    camp_state = _setup_campaigns(cust, rng, T, churn_t)
    sess_parts: list[dict[str, np.ndarray]] = []
    sid_next = 0

    for t in range(T):
        live = active_from <= t
        if not live.any():
            continue
        churned = t >= churn_t
        lam = (
            rate
            * base_visit
            * f["visit"][t]
            * (1 + fest_sens * (f["fest_visit"][t] - 1))
            * np.where(churned, CHURNED_ACTIVITY, 1.0)
            * np.where(t - active_from < 14, 1.6, 1.0)
        )
        conv = base_conv * f["conv"][t] * (1 + fest_sens * (f["fest_conv"][t] - 1))
        offer = np.full(n, -1)
        for k, cs in enumerate(camp_state):
            if cs["t0"] <= t < cs["t1"]:
                lam = lam * cs["visit"]
                conv = conv * cs["conv"]
                offer[cs["treated"]] = k
        lam = np.where(live, lam, 0.0)
        n_sess = rng.poisson(lam)
        if n_sess.sum() == 0:
            continue
        c = np.repeat(np.arange(n), n_sess)
        m = len(c)
        sid = np.arange(sid_next, sid_next + m)
        sid_next += m

        ts = day0 + t * 86400 + rng.choice(24, m, p=hour_p) * 3600 + rng.integers(0, 3600, m)
        w = affinity[c] * f["catmult"][t]
        cat = (w.cumsum(1) > rng.random(m)[:, None] * w.sum(1)[:, None]).argmax(1)
        n_views = 1 + rng.poisson(1.8, m)
        cart = rng.random(m) < np.clip(p_cart[c] * conv[c], 0, 0.95)
        chk = cart & (rng.random(m) < p_chk[c] * 0.92)
        pur = chk & (rng.random(m) < p_pur[c])

        target = np.exp(
            np.log(cat_median[cat] * aov_mult[c] * f["fest_aov"][t]) + cat_sigma[cat] * rng.standard_normal(m)
        )
        prod, qty = _match_products(target, cat, cat_sorted, prod_price, rng)
        value = prod_price[prod] * qty

        sess_parts.append(
            dict(
                c=c,
                sid=sid,
                ts=ts,
                cat=cat,
                n_views=n_views,
                cart=cart,
                chk=chk,
                pur=pur,
                prod=prod,
                qty=qty,
                value=value,
                offer=offer[c],
            )
        )
        bought = c[pur]
        if len(bought):
            for cs in camp_state:
                if cs["t0"] <= t < cs["t1"]:
                    np.add.at(cs["revenue"], bought, value[pur])
                    cs["converted"][bought] = True

    sess = {k: np.concatenate([p[k] for p in sess_parts]) for k in sess_parts[0]}
    orders = _orders(sess, rng, cat_ret, cat_ship, ret_mult, disc_use, pref_pay, camp_state, day0, T)
    orders["customer_id"] = cust["id"].to_numpy()[orders["c"].to_numpy()]
    events = _events(sess, orders, camp_state, cust, rng, day0, T)
    points, balance, tier = _points(orders, n, end)
    campaigns = _campaign_rows(camp_state, cust)

    cust["points_balance"] = balance
    cust["tier"] = tier
    cust["churn_date"] = [start + timedelta(days=int(x)) if x < T else None for x in churn_t]
    cust["category_affinity"] = [dict(zip(CATS, np.round(a, 3).tolist(), strict=True)) for a in affinity]

    products = pd.DataFrame([p.__dict__ for p in PRODUCTS])
    return SimData(cust, products, events, orders, points, campaigns, start, end)


def _days(start: date, end: date) -> int:
    return (end - start).days + 1


def _match_products(
    target: np.ndarray,
    cat: np.ndarray,
    cat_sorted: list[np.ndarray],
    price: np.ndarray,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """Pick the catalogue product whose price best explains a lognormal order value, plus a quantity."""
    prod = np.empty(len(target), dtype=int)
    for k, idx in enumerate(cat_sorted):
        mask = cat == k
        if not mask.any():
            continue
        prices = price[idx]
        # choose among the products priced at or below the target, so big baskets become qty > 1
        pos = np.searchsorted(prices, target[mask], side="right") - 1
        pos = np.where(pos < 0, 0, pos)
        jitter = rng.integers(-1, 2, mask.sum())
        prod[mask] = idx[np.clip(pos + jitter, 0, len(idx) - 1)]
    qty = np.clip(np.round(target / price[prod]), 1, 4).astype(int)
    return prod, qty


# ------------------------------------------------------------------ campaigns
def _setup_campaigns(cust: pd.DataFrame, rng: np.random.Generator, T: int, churn_t: np.ndarray) -> list[dict]:
    n = len(cust)
    resp = cust["response_type"].to_numpy()
    active_from = cust["active_from"].to_numpy()
    states = cust["state"].to_numpy()
    out = []
    for camp in CAMPAIGNS:
        t0 = (camp.start - SIM_START).days
        if t0 + camp.days > T:
            continue
        eligible = active_from <= t0
        if camp.region:
            eligible &= states == camp.region
        targeted = eligible & (rng.random(n) < camp.share)
        control = targeted & (rng.random(n) < CONTROL_SHARE)
        treated = targeted & ~control
        visit, conv = np.ones(n), np.ones(n)
        for r in RESPONSES:
            mask = treated & (resp == r)
            v, cv, churn_p = response_effect(r, camp.strength)
            visit[mask], conv[mask] = v, cv
            quits = mask & (rng.random(n) < churn_p)
            churn_t[quits] = np.minimum(churn_t[quits], t0 + 1)
        out.append(
            dict(
                campaign=camp,
                t0=t0,
                t1=t0 + camp.days,
                targeted=targeted,
                control=control,
                treated=treated,
                visit=visit,
                conv=conv,
                converted=np.zeros(n, dtype=bool),
                revenue=np.zeros(n, dtype=np.int64),
            )
        )
    return out


def _campaign_rows(camp_state: list[dict], cust: pd.DataFrame) -> pd.DataFrame:
    rows = []
    ids = cust["id"].to_numpy()
    for cs in camp_state:
        camp: Campaign = cs["campaign"]
        sent_at = datetime.combine(camp.start, time(11, 0), IST)
        for i in np.where(cs["targeted"])[0]:
            rows.append(
                dict(
                    campaign_id=camp.id,
                    customer_id=ids[i],
                    sent_at=sent_at,
                    offer_type=camp.offer_type,
                    params=dict(camp.params),
                    is_control=bool(cs["control"][i]),
                    converted=bool(cs["converted"][i]),
                    revenue=int(cs["revenue"][i]),
                )
            )
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ orders, events, points
def _orders(sess, rng, cat_ret, cat_ship, ret_mult, disc_use, pref_pay, camp_state, day0, T):
    p = sess["pur"]
    c, cat, value, offer = sess["c"][p], sess["cat"][p], sess["value"][p], sess["offer"][p]
    ts = sess["ts"][p] + sess["n_views"][p] * 90 + 420
    m = len(c)

    discount = np.zeros(m, dtype=np.int64)
    coupon = np.full(m, None, dtype=object)
    natural = rng.random(m) < disc_use[c]
    pct = rng.choice([5, 10, 15], m, p=[0.3, 0.5, 0.2])
    discount[natural] = (value[natural] * pct[natural] / 100).astype(np.int64)
    coupon[natural] = np.array([f"SAVE{x}" for x in pct])[natural]

    bonus = np.ones(m, dtype=int)
    for k, cs in enumerate(camp_state):
        camp: Campaign = cs["campaign"]
        mine = offer == k
        if camp.offer_type == "pct_off":
            ok = mine & (value >= camp.params["min_basket"])
            discount[ok] = (value[ok] * camp.params["pct"] / 100).astype(np.int64)
        elif camp.offer_type == "flat_off":
            ok = mine & (value >= camp.params["min_basket"])
            discount[ok] = camp.params["flat"]
        elif camp.offer_type == "free_shipping":
            ok = mine.copy()
            discount[ok] = cat_ship[cat[ok]]
        else:  # bonus_points: no ₹ off, points multiplier instead
            ok = mine.copy()
            discount[ok] = 0
            bonus[ok] = camp.params["multiplier"]
        coupon[ok] = camp.coupon

    payment = np.where(rng.random(m) < 0.75, pref_pay[c], rng.choice(["upi", "cod", "card"], m))
    # COD orders get returned/refused more often: a well-known Indian e-commerce pattern
    ret_p = np.clip(cat_ret[cat] * ret_mult[c] * np.where(payment == "cod", 1.25, 1.0), 0, 0.85)
    return_ts = ts + rng.integers(3, 13, m) * 86400 + rng.integers(0, 86400, m)
    end_ts = day0 + T * 86400
    returned = (rng.random(m) < ret_p) & (return_ts < end_ts)

    keep = ts < end_ts  # a late-night session can finish checkout after the last simulated day
    order = np.argsort(np.where(keep, ts, np.iinfo(np.int64).max), kind="stable")[: keep.sum()]
    df = (
        pd.DataFrame(
            {
                "c": c,
                "ts_s": ts,
                "category": np.array(CATS)[cat],
                "items": sess["qty"][p],
                "value": value,
                "discount": discount,
                "coupon_code": coupon,
                "payment_method": payment,
                "returned": returned,
                "return_ts_s": return_ts,
                "product": sess["prod"][p],
                "sid": sess["sid"][p],
                "bonus": bonus,
                "offer": offer,
            }
        )
        .iloc[order]
        .reset_index(drop=True)
    )
    df.insert(0, "id", [f"O{i + 1:07d}" for i in range(len(df))])
    df["ts"] = pd.to_datetime(df["ts_s"], unit="s", utc=True).dt.tz_convert(IST)
    return df


def _events(sess, orders, camp_state, cust, rng, day0, T) -> pd.DataFrame:
    names = np.array([p.name for p in PRODUCTS], dtype=object)
    prices = np.array([p.price for p in PRODUCTS])
    cats = np.array(CATS, dtype=object)
    n_prod_cat = len(PRODUCTS) // len(CATS)
    end_ts = day0 + T * 86400
    parts: list[pd.DataFrame] = []

    def add(c, typ, ts, cat=None, prod=None, value=None, sid=None, order_id=None, campaign=None):
        k = len(c)
        parts.append(
            pd.DataFrame(
                {
                    "c": c,
                    "type": typ,
                    "ts_s": ts,
                    "category": cats[cat] if cat is not None else np.full(k, None, dtype=object),
                    "item": names[prod] if prod is not None else np.full(k, None, dtype=object),
                    "value": value if value is not None else np.full(k, None, dtype=object),
                    "sid": sid if sid is not None else np.full(k, None, dtype=object),
                    "order_id": order_id if order_id is not None else np.full(k, None, dtype=object),
                    "campaign": campaign if campaign is not None else np.full(k, None, dtype=object),
                }
            )
        )

    c, sid, ts, cat = sess["c"], sess["sid"], sess["ts"], sess["cat"]
    add(c, "session", ts, sid=sid)
    dup = rng.random(len(c)) < 0.008  # messy: double-fired session beacons
    add(c[dup], "session", ts[dup] + rng.integers(0, 3, dup.sum()), sid=sid[dup])

    nv = sess["n_views"]
    vi = np.repeat(np.arange(len(c)), nv)
    within = _within_session_offsets(rng.integers(20, 180, len(vi)), nv)
    vprod = cat[vi] * n_prod_cat + rng.integers(0, n_prod_cat, len(vi))
    last = np.cumsum(nv) - 1
    vprod[last[sess["cart"]]] = sess["prod"][sess["cart"]]  # the last product viewed is the one carted
    add(c[vi], "view", ts[vi] + within, cat=cat[vi], prod=vprod, value=prices[vprod], sid=sid[vi])

    t_cart = ts + within[last] + 60
    cart = sess["cart"]
    add(
        c[cart],
        "add_to_cart",
        t_cart[cart],
        cat=cat[cart],
        prod=sess["prod"][cart],
        value=sess["value"][cart],
        sid=sid[cart],
    )
    wish = ~cart & (rng.random(len(c)) < 0.04)
    add(c[wish], "wishlist", t_cart[wish], cat=cat[wish], prod=vprod[last[wish]], sid=sid[wish])
    chk = sess["chk"]
    add(
        c[chk],
        "checkout_started",
        t_cart[chk] + 180,
        cat=cat[chk],
        prod=sess["prod"][chk],
        value=sess["value"][chk],
        sid=sid[chk],
    )

    o = orders
    cat_o = np.array([CATS.index(x) for x in o["category"]])
    add(
        o["c"].to_numpy(),
        "purchase",
        o["ts_s"].to_numpy(),
        cat=cat_o,
        prod=o["product"].to_numpy(),
        value=o["value"].to_numpy(),
        sid=o["sid"].to_numpy(),
        order_id=o["id"].to_numpy(),
    )
    r = o["returned"].to_numpy()
    add(
        o["c"].to_numpy()[r],
        "return",
        o["return_ts_s"].to_numpy()[r],
        cat=cat_o[r],
        prod=o["product"].to_numpy()[r],
        value=o["value"].to_numpy()[r],
        order_id=o["id"].to_numpy()[r],
    )

    for k, cs in enumerate(camp_state):
        camp: Campaign = cs["campaign"]
        treated = np.where(cs["treated"])[0]
        sent = int(datetime.combine(camp.start, time(11, 0), IST).timestamp()) + rng.integers(
            0, 7200, len(treated)
        )
        cid = np.full(len(treated), camp.id, dtype=object)
        add(treated, "offer_received", sent, campaign=cid)
        used = o[(o["offer"] == k) & (o["coupon_code"] == camp.coupon)].drop_duplicates("c")
        add(
            used["c"].to_numpy(),
            "offer_claimed",
            used["ts_s"].to_numpy() - 30,
            campaign=np.full(len(used), camp.id, dtype=object),
        )
        resp = cust["response_type"].to_numpy()[treated]
        no = rng.random(len(treated)) < np.array([RESPONSE_DECLINE_P[r] for r in resp])
        add(treated[no], "offer_declined", sent[no] + rng.integers(300, 7200, no.sum()), campaign=cid[no])

    ev = pd.concat(parts, ignore_index=True)
    ev = ev[ev["ts_s"] < end_ts].sort_values("ts_s", kind="stable").reset_index(drop=True)
    ev.insert(0, "id", [f"E{i + 1:08d}" for i in range(len(ev))])
    ev["customer_id"] = cust["id"].to_numpy()[ev["c"].to_numpy()]
    ev["ts"] = pd.to_datetime(ev["ts_s"], unit="s", utc=True).dt.tz_convert(IST)
    return ev


def _within_session_offsets(gaps: np.ndarray, counts: np.ndarray) -> np.ndarray:
    """Cumulative seconds since session start for each view, restarting at every session."""
    total = np.cumsum(gaps)
    starts = np.r_[0, np.cumsum(counts)[:-1]]
    before = np.r_[0, total][starts]
    return total - np.repeat(before, counts)


def _points(orders: pd.DataFrame, n: int, end: date) -> tuple[pd.DataFrame, np.ndarray, list[str]]:
    """1 point per ₹100 on kept orders (× campaign multiplier), expiring after 180 days."""
    kept = orders[~orders["returned"]]
    ts = pd.to_datetime(kept["ts_s"], unit="s", utc=True).dt.tz_convert(IST)
    earn = pd.DataFrame(
        {
            "c": kept["c"].to_numpy(),
            "ts": ts.to_numpy(),
            "delta": (kept["value"].to_numpy() // 100 * kept["bonus"].to_numpy()).astype(int),
            "reason": "earn:" + kept["id"],
            "expires_on": (ts.dt.date + timedelta(days=POINTS_EXPIRY_DAYS)).to_numpy(),
        }
    )
    earn = earn[earn["delta"] > 0]
    gone = earn[earn["expires_on"] <= end]
    expiry = pd.DataFrame(
        {
            "c": gone["c"].to_numpy(),
            "ts": [datetime.combine(d, time(0, 5), IST) for d in gone["expires_on"]],
            "delta": -gone["delta"].to_numpy(),
            "reason": "expiry",
            "expires_on": None,
        }
    )
    ledger = pd.concat([earn, expiry], ignore_index=True)
    balance = np.zeros(n, dtype=int)
    np.add.at(balance, ledger["c"].to_numpy(), ledger["delta"].to_numpy())

    since = int(datetime.combine(end - timedelta(days=365), time(0), IST).timestamp())
    spend = np.zeros(n, dtype=np.int64)
    recent = orders[(orders["ts_s"] >= since) & ~orders["returned"]]
    np.add.at(spend, recent["c"].to_numpy(), recent["value"].to_numpy())
    tier = np.select(
        [spend >= 75000, spend >= 30000, spend >= 10000], ["Platinum", "Gold", "Silver"], "Bronze"
    )
    return ledger, balance, tier.tolist()
