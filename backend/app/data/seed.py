"""Seed the DB with the synthetic world: `python -m app.data.seed --customers 5000 --seed 42`.

Re-runnable: it replaces only synthetic data (customer ids starting with "C") and leaves real Telegram
users ("TG…"), decisions and rules alone. Customers the Customer Lab bots point at are updated in place.
"""

from __future__ import annotations

import argparse
import logging
import time
from collections.abc import Iterable
from datetime import date, timedelta

import pandas as pd
from sqlalchemy import delete, insert, select
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel

from app import config
from app.data.festivals import FESTIVALS
from app.data.generator import DEFAULT_END, SIM_START, SimData, generate
from app.models import (
    CampaignHistoryRow,
    CustomerBotRow,
    CustomerRow,
    EventRow,
    FestivalRow,
    OrderRow,
    PointsLedgerRow,
    ProductRow,
)

log = logging.getLogger(__name__)
CHUNK = 5000
SYNTHETIC = "C%"


def default_end() -> date:
    """Simulate up to yesterday (IST), so recency looks live on demo day."""
    return max(DEFAULT_END, config.now().date() - timedelta(days=1))


def run(
    n_customers: int = 5000, seed: int = 42, *, end: date | None = None, engine: Engine | None = None
) -> None:
    from app.db import engine as default_engine

    engine = engine or default_engine
    t0 = time.perf_counter()
    data = generate(n_customers, seed, SIM_START, end or default_end())
    t1 = time.perf_counter()
    import app.models  # noqa: F401  (registers tables)

    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        _clear(s)
        _write(s, data)
        s.commit()
    log.info(
        "seeded %d customers, %d events, %d orders (generate %.1fs, write %.1fs)",
        len(data.customers),
        len(data.events),
        len(data.orders),
        t1 - t0,
        time.perf_counter() - t1,
    )


def _clear(s: Session) -> None:
    for table in (EventRow, OrderRow, PointsLedgerRow, CampaignHistoryRow):
        s.execute(delete(table).where(table.customer_id.like(SYNTHETIC)))
    kept = set(s.scalars(select(CustomerBotRow.customer_id)))
    s.execute(delete(CustomerRow).where(CustomerRow.id.like(SYNTHETIC), CustomerRow.id.not_in(kept)))
    s.execute(delete(ProductRow))
    s.execute(delete(FestivalRow))


def _bulk(s: Session, model: type[SQLModel], rows: Iterable[dict]) -> None:
    batch: list[dict] = []
    for row in rows:
        batch.append(row)
        if len(batch) == CHUNK:
            s.execute(insert(model.__table__), batch)
            batch = []
    if batch:
        s.execute(insert(model.__table__), batch)


def _none(v):
    return None if v is None or (isinstance(v, float) and pd.isna(v)) else v


def _write(s: Session, d: SimData) -> None:
    _bulk(s, ProductRow, d.products.to_dict("records"))
    _bulk(
        s,
        FestivalRow,
        ({"id": f.id, "date": f.date, "payload": f.model_dump(mode="json")} for f in FESTIVALS),
    )

    existing = set(s.scalars(select(CustomerRow.id).where(CustomerRow.id.like(SYNTHETIC))))
    new_rows = []
    for r in d.customers.itertuples(index=False):
        row = dict(
            id=r.id,
            first_name=r.first_name,
            age=_none(r.age),
            gender=_none(r.gender),
            city=r.city,
            city_tier=int(r.city_tier),
            signup_date=r.signup_date,
            channel=r.channel,
            device=r.device,
            preferred_payment=r.preferred_payment,
            persona=r.persona,
            response_type=r.response_type,
            telegram_chat_id=None,
            is_lab_bot=False,
            opt_in_festivals=list(r.opt_in_festivals),
            opted_out=False,
            paused_until=None,
            is_holdout=bool(r.is_holdout),
            points_balance=int(r.points_balance),
            tier=r.tier,
            suppressed={},
            attrs={
                "state": r.state,
                "churn_date": r.churn_date.isoformat() if r.churn_date else None,
                "heavy_returner": bool(r.heavy_returner),
            },
        )
        if r.id in existing:  # a Lab bot plays this customer: keep the row, refresh its content
            s.merge(CustomerRow(**{k: v for k, v in row.items() if k != "is_lab_bot"}))
        else:
            new_rows.append(row)
    _bulk(s, CustomerRow, new_rows)

    o = d.orders
    _bulk(
        s,
        OrderRow,
        (
            dict(
                id=i,
                customer_id=c,
                ts=ts.to_pydatetime(),
                category=cat,
                items=int(q),
                value=int(v),
                discount=int(dc),
                coupon_code=cc,
                payment_method=pm,
                returned=bool(rt),
            )
            for i, c, ts, cat, q, v, dc, cc, pm, rt in zip(
                o["id"],
                o["customer_id"],
                o["ts"],
                o["category"],
                o["items"],
                o["value"],
                o["discount"],
                o["coupon_code"],
                o["payment_method"],
                o["returned"],
                strict=True,
            )
        ),
    )

    e = d.events
    _bulk(
        s,
        EventRow,
        (
            dict(
                id=i,
                customer_id=c,
                type=t,
                ts=ts.to_pydatetime(),
                category=cat,
                item=item,
                value=None if v is None else int(v),
                meta=_meta(sid, oid, camp),
            )
            for i, c, t, ts, cat, item, v, sid, oid, camp in zip(
                e["id"],
                e["customer_id"],
                e["type"],
                e["ts"],
                e["category"],
                e["item"],
                e["value"],
                e["sid"],
                e["order_id"],
                e["campaign"],
                strict=True,
            )
        ),
    )

    ids = d.customers["id"].to_numpy()
    p = d.points
    _bulk(
        s,
        PointsLedgerRow,
        (
            dict(
                customer_id=ids[c],
                ts=pd.Timestamp(ts).to_pydatetime(),
                delta=int(dl),
                reason=rs,
                expires_on=ex,
            )
            for c, ts, dl, rs, ex in zip(
                p["c"], p["ts"], p["delta"], p["reason"], p["expires_on"], strict=True
            )
        ),
    )
    _bulk(s, CampaignHistoryRow, d.campaigns.to_dict("records"))


def _meta(sid, order_id, campaign) -> dict:
    meta = {}
    if sid is not None:
        meta["sid"] = int(sid)
    if order_id is not None:
        meta["order_id"] = order_id
    if campaign is not None:
        meta["campaign"] = campaign
    return meta


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate and load the synthetic offer-engine dataset.")
    parser.add_argument("--customers", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--end", type=date.fromisoformat, default=None, help="last simulated day (YYYY-MM-DD)"
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    run(args.customers, args.seed, end=args.end)


if __name__ == "__main__":
    main()
