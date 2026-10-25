"""Uplift: T-learner per offer-type family, trained on the simulated past campaigns (with 10% control).

For each family a treated model learns P(buy within the campaign window | offer) and a pooled control model
learns P(buy | no offer); uplift = the difference. Features come from `build_profile` at the moment the
campaign was sent, so training and serving use exactly the same numbers.

Models are shallow GradientBoostingClassifiers exported as plain trees into `uplift_model.py` (only .py
files ship in the Docker image, and no pickle / scikit-learn version is needed to score).
Retrain with `python -m app.scoring.uplift` (seeds a temporary 5,000-customer DB, ~2 min).
"""

from __future__ import annotations

import math
from collections import OrderedDict
from collections.abc import Sequence
from pathlib import Path
from pprint import pformat

from app.contracts import CustomerProfile, OfferType

MODEL_PATH = Path(__file__).with_name("uplift_model.py")
FEATURES = [
    "log_recency",
    "orders_90d",
    "log_orders_total",
    "log_aov",
    "log_ltv",
    "churn_risk",
    "discount_usage",
    "return_rate",
    "price_sensitivity",
    "log_tenure",
    "log_inactive",
    "log_views_90d",
    "city_tier",
    "log_offers_received",
    "decline_share",
]
# Families with their own models; every other offer type borrows a family at a fixed strength. Shipping has
# only one small past test (Lohri, Punjab only: ~780 treated / ~700 control), too noisy for its own model,
# so it borrows the discount family at 60% (a ₹60 perk moves people less than 10–15% off).
FAMILY: dict[str, tuple[str, float]] = {
    "pct_off": ("discount", 1.0),
    "flat_off": ("discount", 1.0),
    "bundle": ("discount", 0.8),
    "gift_card": ("discount", 0.8),
    "birthday": ("discount", 0.8),
    "free_shipping": ("discount", 0.6),
    "free_express": ("discount", 0.65),
    "cart_nudge": ("discount", 0.25),
    "bonus_points": ("points", 1.0),
    "points_reminder": ("points", 0.5),
    "early_access": ("points", 0.4),
}
TRAIN_FAMILY = {
    "pct_off": "discount",
    "flat_off": "discount",
    "free_shipping": "shipping",
    "bonus_points": "points",
}
MODELLED_FAMILIES = ("discount", "points")


def features(p: CustomerProfile) -> list[float]:
    r = p.rfm
    return [
        math.log1p(p.recency_days),
        float(p.orders_90d),
        math.log1p(r.get("orders_total", 0)),
        math.log1p(p.aov),
        math.log1p(max(p.ltv, 0)),
        p.churn_risk,
        p.discount_usage_rate,
        p.return_rate,
        p.price_sensitivity,
        math.log1p(r.get("tenure_days", 0)),
        math.log1p(r.get("days_since_active", 0)),
        math.log1p(r.get("views_90d", 0)),
        float(p.city_tier),
        math.log1p(r.get("offers_received", 0)),
        r.get("offers_declined", 0) / max(r.get("offers_received", 0), 1),
    ]


# ------------------------------------------------------------------ scoring exported trees
def _tree_value(tree: dict, x: Sequence[float]) -> float:
    node = 0
    feat, thr, left, right, value = tree["f"], tree["t"], tree["l"], tree["r"], tree["v"]
    while left[node] != -1:
        node = left[node] if x[feat[node]] <= thr[node] else right[node]
    return value[node]


def _proba(model: dict, x: Sequence[float]) -> float:
    raw = model["init"] + model["lr"] * sum(_tree_value(t, x) for t in model["trees"])
    return 1 / (1 + math.exp(-raw))


def _load() -> dict | None:
    try:
        from app.scoring.uplift_model import MODEL
    except ImportError:
        return None
    return MODEL


_MODEL = _load()
_cache: OrderedDict[tuple, dict[str, tuple[float, float]]] = OrderedDict()


def family_probabilities(profile: CustomerProfile) -> dict[str, tuple[float, float]]:
    """{family: (P(buy | offer), P(buy | no offer))}. Cached per feature vector (rules ask many times)."""
    x = features(profile)
    key = tuple(round(v, 6) for v in x)
    hit = _cache.get(key)
    if hit is not None:
        return hit
    if _MODEL is None:
        return {}
    out = {}
    for fam, m in _MODEL["families"].items():
        p_c = _proba(m["control"], x)
        out[fam] = (p_c + m["calibration"] * (_proba(m["treated"], x) - p_c), p_c)
    _cache[key] = out
    if len(_cache) > 4096:
        _cache.popitem(last=False)
    return out


def predict(profile: CustomerProfile, offer_type: OfferType) -> float:
    """P(buy | offer) − P(buy | no offer) for this offer type."""
    fam, scale = FAMILY.get(offer_type, ("discount", 0.5))
    probs = family_probabilities(profile)
    if fam not in probs:
        return profile.uplift.get(offer_type, 0.0)
    p_t, p_c = probs[fam]
    return round((p_t - p_c) * scale, 4)


def predict_all(profile: CustomerProfile) -> dict[str, float]:
    return {t: predict(profile, t) for t in FAMILY}


def p_buy(profile: CustomerProfile, offer_type: OfferType) -> tuple[float, float]:
    """(P(buy | offer), P(buy | no offer)) for the cost side of the impact estimate."""
    fam, scale = FAMILY.get(offer_type, ("discount", 0.5))
    probs = family_probabilities(profile)
    if fam not in probs:
        return 0.1 + max(profile.uplift.get(offer_type, 0.0), 0), 0.1
    p_t, p_c = probs[fam]
    return p_c + (p_t - p_c) * scale, p_c


def qini() -> list[dict] | None:
    return _MODEL["qini"] if _MODEL else None


# ------------------------------------------------------------------ training
def _export(clf, n_features: int) -> dict:
    p1 = float(clf.init_.class_prior_[1])
    trees = []
    for est in clf.estimators_[:, 0]:
        t = est.tree_
        trees.append(
            {
                "f": [int(v) for v in t.feature],
                "t": [round(float(v), 6) for v in t.threshold],
                "l": [int(v) for v in t.children_left],
                "r": [int(v) for v in t.children_right],
                "v": [round(float(v), 6) for v in t.value[:, 0, 0]],
            }
        )
    return {
        "init": math.log(p1 / (1 - p1)),
        "lr": clf.learning_rate,
        "trees": trees,
        "n_features": n_features,
    }


def _qini_points(uplift, treated, converted, n_points: int = 20) -> tuple[list[dict], float]:
    import numpy as np

    order = np.argsort(-uplift)
    t, y = treated[order], converted[order]
    nt, nc = np.cumsum(t), np.cumsum(~t)
    yt, yc = np.cumsum(y & t), np.cumsum(y & ~t)
    q = yt - np.where(nc > 0, yc * nt / np.maximum(nc, 1), 0)
    n, total = len(q), float(q[-1])
    pts = []
    for i in range(n_points + 1):
        k = max(int(round(i / n_points * n)) - 1, 0) if i else None
        frac = i / n_points
        value = 0.0 if k is None else float(q[k]) / n
        pts.append(
            {"targeted": round(frac, 3), "model": round(value, 5), "random": round(frac * total / n, 5)}
        )
    area_model = float(np.trapezoid([p["model"] for p in pts], dx=1 / n_points))
    area_random = float(total / n / 2)
    return pts, round(area_model - area_random, 5)


def _calibration_slope(uplift, treated, converted, bins: int = 5) -> float:
    """Tree ensembles shrink uplift toward the average. Scale predictions so that, on held-out customers,
    each quintile's mean prediction matches its observed treated − control conversion gap."""
    import numpy as np

    edges = np.quantile(uplift, np.linspace(0, 1, bins + 1)[1:-1])
    which = np.searchsorted(edges, uplift)
    pred, obs, w = [], [], []
    for b in range(bins):
        m = which == b
        t, c = m & treated, m & ~treated
        if t.sum() < 20 or c.sum() < 20:
            continue
        pred.append(uplift[m].mean())
        obs.append(converted[t].mean() - converted[c].mean())
        w.append(m.sum())
    pred, obs, w = np.array(pred), np.array(obs), np.array(w)
    if not len(pred) or not (w * pred * pred).sum():
        return 1.0
    slope = float((w * pred * obs).sum() / (w * pred * pred).sum())
    return round(min(max(slope, 1.0), 3.0), 3)


def training_rows(engine, *, untargeted_per_campaign: int = 1200, seed: int = 0):
    """X, family, treated, converted, campaign_id, hidden response_type: campaign_history rows plus a sample
    of eligible-but-untargeted customers per campaign (family "none", control only)."""
    import random
    from datetime import datetime, time, timedelta

    from sqlmodel import Session, select

    from app import db
    from app.config import IST
    from app.data.generator import CAMPAIGNS
    from app.models import CampaignHistoryRow, CustomerRow, EventRow
    from app.scoring import profile as prof

    db.engine = engine
    prof.reset_cache()
    with Session(engine) as s:
        rows = s.exec(select(CampaignHistoryRow)).all()
        customers = s.exec(
            select(CustomerRow.id, CustomerRow.response_type, CustomerRow.signup_date, CustomerRow.attrs)
        ).all()
        purchases = s.exec(select(EventRow.customer_id, EventRow.ts).where(EventRow.type == "purchase")).all()
    hidden = {c[0]: c[1] for c in customers}
    bought: dict[str, list] = {}
    for cid, ts in purchases:
        bought.setdefault(cid, []).append(prof._aware(ts))

    X, fam, treated, conv, camp, resp = [], [], [], [], [], []

    def add(cid: str, sent_at, family: str, is_treated: bool, converted: bool, campaign: str) -> None:
        p = prof.build_profile(cid, sent_at - timedelta(minutes=1))
        X.append(features(p))
        fam.append(family)
        treated.append(is_treated)
        conv.append(converted)
        camp.append(campaign)
        resp.append(hidden[cid])

    for r in rows:
        add(
            r.customer_id,
            prof._aware(r.sent_at),
            TRAIN_FAMILY[r.offer_type],
            not r.is_control,
            r.converted,
            r.campaign_id,
        )

    # Targets were drawn at random from the eligible customers, so eligible-but-untargeted customers are
    # a second, much larger randomised "no offer" group for the control model.
    rng = random.Random(seed)
    targeted = {(r.campaign_id, r.customer_id) for r in rows}
    sent = {r.campaign_id: prof._aware(r.sent_at) for r in rows}
    for camp_def in CAMPAIGNS:
        if camp_def.id not in sent:
            continue
        start = sent[camp_def.id]
        window_end = datetime.combine(camp_def.start + timedelta(days=camp_def.days), time(0), IST)
        window_start = datetime.combine(camp_def.start, time(0), IST)
        pool = [
            c[0]
            for c in customers
            if c[0].startswith("C")
            and (camp_def.id, c[0]) not in targeted
            and c[2] <= camp_def.start
            and (camp_def.region is None or (c[3] or {}).get("state") == camp_def.region)
        ]
        for cid in rng.sample(pool, min(len(pool), untargeted_per_campaign)):
            converted = any(window_start <= t < window_end for t in bought.get(cid, ()))
            add(cid, start, "none", False, converted, camp_def.id)
    return X, fam, treated, conv, camp, resp


def train(rows, seed: int = 0) -> dict:
    import numpy as np
    from sklearn.ensemble import GradientBoostingClassifier

    X, fam, treated, conv, camp, resp = (np.array(v) for v in rows)
    rng = np.random.default_rng(seed)
    test = rng.random(len(X)) < 0.3

    def fit(mask):
        clf = GradientBoostingClassifier(
            n_estimators=300,
            max_depth=3,
            learning_rate=0.05,
            min_samples_leaf=30,
            subsample=0.8,
            random_state=seed,
        )
        return clf.fit(X[mask], conv[mask])

    families, report = {}, {}
    for f in MODELLED_FAMILIES:
        # the control arm comes from the same campaigns (same season, same eligibility) as the treated arm
        same_campaigns = np.isin(camp, np.unique(camp[fam == f]))
        arm_t, arm_c = treated & (fam == f), ~treated & same_campaigns
        m_t, m_c = fit(arm_t & ~test), fit(arm_c & ~test)
        u = m_t.predict_proba(X)[:, 1] - m_c.predict_proba(X)[:, 1]
        held = (arm_t | arm_c) & test
        slope = _calibration_slope(u[held], treated[held], conv[held])
        u = u * slope
        qini_pts, qini_gain = _qini_points(u[held], treated[held], conv[held])
        truth = {
            str(r): round(float(conv[arm_t & (resp == r)].mean() - conv[arm_c & (resp == r)].mean()), 4)
            for r in np.unique(resp)
        }
        predicted = {str(r): round(float(u[held & (resp == r)].mean()), 4) for r in np.unique(resp)}
        families[f] = {
            "treated": _export(m_t, X.shape[1]),
            "control": _export(m_c, X.shape[1]),
            "calibration": slope,
        }
        report[f] = {
            "calibration_slope": slope,
            "qini": qini_pts,
            "qini_gain_over_random": qini_gain,
            "n_treated": int(arm_t.sum()),
            "n_control": int(arm_c.sum()),
            "mean_uplift_by_response_type": predicted,
            "observed_uplift_by_response_type": truth,
        }
        # the exported trees must reproduce scikit-learn exactly
        probe = X[:50]
        exported = np.array([_proba(families[f]["treated"], row) for row in probe])
        assert np.allclose(exported, m_t.predict_proba(probe)[:, 1], atol=1e-4)

    return {
        "features": FEATURES,
        "families": families,
        "report": report,
        "qini": report["discount"]["qini"],
        "n_rows": int(len(X)),
    }


def save(model: dict, path: Path = MODEL_PATH) -> None:
    path.write_text(
        '"""Generated by `python -m app.scoring.uplift`; do not edit by hand."""\n\n'
        "# fmt: off\n"
        f"MODEL = {pformat(model, width=110, sort_dicts=False, compact=True)}\n",
        encoding="utf-8",
    )


def main() -> None:
    import tempfile

    from app.data.generator import DEFAULT_END
    from app.data.seed import run
    from app.db import make_engine

    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(f"sqlite:///{Path(tmp) / 'train.db'}")
        run(5000, 42, end=DEFAULT_END, engine=engine)
        model = train(training_rows(engine))
        engine.dispose()
    save(model)
    print(f"uplift model: {model['n_rows']} training rows -> {MODEL_PATH.name}")
    for fam, r in model["report"].items():
        print(
            f"  {fam}: treated {r['n_treated']}, control {r['n_control']}, "
            f"Qini gain over random {r['qini_gain_over_random']}"
        )
        print(f"    predicted by hidden type: {r['mean_uplift_by_response_type']}")
        print(f"    observed by hidden type:  {r['observed_uplift_by_response_type']}")


if __name__ == "__main__":
    main()
