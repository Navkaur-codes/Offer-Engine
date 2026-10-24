"""Churn risk: logistic regression on recency, purchase-frequency trend, session decline and return rate.

Label: no purchase in the 60 days after a snapshot date, read from the simulation. Snapshots are taken at
60, 120 and 180 days before the end of the simulated year; the split is by customer.

The fitted scaler + coefficients are written to `churn_model.py` (plain Python, not a pickle): the Docker
build only packages .py files, and scoring stays independent of the scikit-learn version.
Retrain with `python -m app.scoring.churn`.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import datetime, time
from pathlib import Path
from pprint import pformat

import numpy as np

from app.config import IST

DAY = 86400.0
HORIZON_DAYS = 60
FEATURES = [
    "log_recency",
    "orders_90d",
    "freq_trend",
    "session_trend",
    "return_rate",
    "log_tenure",
    "log_aov",
]
MODEL_PATH = Path(__file__).with_name("churn_model.py")


def features(
    purchase_ts: Sequence[float],
    purchase_values: Sequence[float],
    session_ts: Sequence[float],
    returns: int,
    signup_ts: float,
    now_ts: float,
) -> list[float]:
    """Feature vector from epoch-second timestamps up to `now_ts`. Shared by training and build_profile."""
    p = np.asarray(purchase_ts, dtype=float)
    s = np.asarray(session_ts, dtype=float)
    age = (now_ts - p) / DAY
    sage = (now_ts - s) / DAY
    tenure = max((now_ts - signup_ts) / DAY, 1.0)
    recency = float(age.min()) if len(p) else tenure
    orders_90 = int((age <= 90).sum())
    orders_prev = int(((age > 90) & (age <= 180)).sum())
    sess_30 = int((sage <= 30).sum())
    sess_prev = int(((sage > 30) & (sage <= 90)).sum())
    aov = float(np.mean(purchase_values)) if len(purchase_values) else 0.0
    return [
        math.log1p(max(recency, 0.0)),
        float(orders_90),
        float(orders_90 - orders_prev),
        math.log1p(sess_30) - math.log1p(sess_prev / 2),
        returns / len(p) if len(p) else 0.0,
        math.log1p(tenure),
        math.log1p(aov),
    ]


def _load() -> dict | None:
    try:
        from app.scoring.churn_model import MODEL
    except ImportError:
        return None
    return MODEL


_MODEL = _load()


def predict(x: Sequence[float]) -> float:
    """P(no purchase in the next 60 days)."""
    if _MODEL is None:  # untrained checkout: a transparent recency-only fallback
        return 1 / (1 + math.exp(-(x[0] - math.log1p(45)) * 2.0))
    z = sum(
        c * (v - m) / s for c, v, m, s in zip(_MODEL["coef"], x, _MODEL["mean"], _MODEL["scale"], strict=True)
    )
    return 1 / (1 + math.exp(-(z + _MODEL["intercept"])))


# ------------------------------------------------------------------ training
def training_set(data) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(X, y, customer index) from a generator.SimData, at three snapshot dates."""
    ev = data.events
    end_ts = ev["ts_s"].max()
    signup_ts = np.array(
        [datetime.combine(d, time(0), IST).timestamp() for d in data.customers["signup_date"]]
    )
    by_type = {
        t: g.groupby("c") for t, g in ev[ev["type"].isin(["purchase", "session", "return"])].groupby("type")
    }
    purchases = {c: (g["ts_s"].to_numpy(), g["value"].to_numpy(float)) for c, g in by_type["purchase"]}
    sessions = {c: g["ts_s"].to_numpy() for c, g in by_type["session"]}
    returns = {c: g["ts_s"].to_numpy() for c, g in by_type["return"]}

    X, y, who = [], [], []
    for days_back in (60, 120, 180):
        cut = end_ts - days_back * DAY
        for c, (pts, pval) in purchases.items():
            before = pts <= cut
            if not before.any() or signup_ts[c] > cut:
                continue
            sess = sessions.get(c, np.empty(0))
            ret = returns.get(c, np.empty(0))
            X.append(
                features(
                    pts[before], pval[before], sess[sess <= cut], int((ret <= cut).sum()), signup_ts[c], cut
                )
            )
            y.append(not ((pts > cut) & (pts <= cut + HORIZON_DAYS * DAY)).any())
            who.append(c)
    return np.array(X), np.array(y, dtype=int), np.array(who)


def train(data, seed: int = 0) -> dict:
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.preprocessing import StandardScaler

    X, y, who = training_set(data)
    rng = np.random.default_rng(seed)
    customers = np.unique(who)
    test_customers = set(rng.choice(customers, len(customers) // 4, replace=False))
    test = np.array([c in test_customers for c in who])

    scaler = StandardScaler().fit(X[~test])
    clf = LogisticRegression(max_iter=1000).fit(scaler.transform(X[~test]), y[~test])
    auc = roc_auc_score(y[test], clf.predict_proba(scaler.transform(X[test]))[:, 1])
    return {
        "features": FEATURES,
        "mean": [round(float(v), 6) for v in scaler.mean_],
        "scale": [round(float(v), 6) for v in scaler.scale_],
        "coef": [round(float(v), 6) for v in clf.coef_[0]],
        "intercept": round(float(clf.intercept_[0]), 6),
        "auc": round(float(auc), 4),
        "n_train": int((~test).sum()),
        "n_test": int(test.sum()),
        "churn_rate": round(float(y.mean()), 4),
    }


def save(model: dict, path: Path = MODEL_PATH) -> None:
    path.write_text(
        '"""Generated by `python -m app.scoring.churn`; do not edit by hand."""\n\n'
        f"MODEL = {pformat(model, width=100, sort_dicts=False)}\n",
        encoding="utf-8",
    )


def main() -> None:
    from app.data.generator import DEFAULT_END, SIM_START, generate

    data = generate(5000, 42, SIM_START, DEFAULT_END)
    model = train(data)
    save(model)
    print(
        f"churn model: AUC {model['auc']} on {model['n_test']} held-out snapshots "
        f"(train {model['n_train']}, churn rate {model['churn_rate']}) -> {MODEL_PATH.name}"
    )
    for name, coef in zip(FEATURES, model["coef"], strict=True):
        print(f"  {name:>14}: {coef:+.3f}")


if __name__ == "__main__":
    main()
