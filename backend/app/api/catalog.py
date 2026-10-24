"""Offer catalogue and festival calendar (editable by marketers)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from app import db, ports, stubs
from app.api.deps import not_found, require_admin
from app.contracts import Festival, Offer
from app.models import FestivalRow, OfferRow

router = APIRouter(prefix="/api", tags=["catalog"])


class OfferPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    param_schema: dict | None = None
    enabled: bool | None = None


class FestivalPatch(BaseModel):
    date: str | None = None
    hero_categories: list[str] | None = None
    budget: int | None = None
    strategy: dict | None = None
    greeting: str | None = None


def ensure_catalogue() -> int:
    """Store the default catalogue once so marketers can edit it; never overwrites edits."""
    added = 0
    with Session(db.engine) as s:
        for offer in stubs.CATALOGUE:
            if s.get(OfferRow, offer.id) is None:
                s.add(OfferRow(**offer.model_dump()))
                added += 1
        s.commit()
    return added


@router.get("/offers")
def list_offers() -> list[Offer]:
    with Session(db.engine) as s:
        rows = s.exec(select(OfferRow).order_by(OfferRow.id)).all()
    return [Offer.model_validate(r.model_dump()) for r in rows] or list(stubs.CATALOGUE)


@router.patch("/offers/{offer_id}", dependencies=[Depends(require_admin)])
def patch_offer(offer_id: str, body: OfferPatch) -> Offer:
    with Session(db.engine) as s:
        row = s.get(OfferRow, offer_id)
        if row is None:
            raise not_found("Offer")
        for k, v in body.model_dump(exclude_none=True).items():
            setattr(row, k, v)
        s.add(row)
        s.commit()
        s.refresh(row)
        return Offer.model_validate(row.model_dump())


@router.get("/festivals")
def list_festivals() -> list[Festival]:
    with Session(db.engine) as s:
        rows = s.exec(select(FestivalRow).order_by(FestivalRow.date)).all()
    return [Festival.model_validate(r.payload) for r in rows] or sorted(
        ports.festivals(), key=lambda f: f.date
    )


@router.patch("/festivals/{festival_id}", dependencies=[Depends(require_admin)])
def patch_festival(festival_id: str, body: FestivalPatch) -> Festival:
    with Session(db.engine) as s:
        row = s.get(FestivalRow, festival_id)
        if row is None:
            raise not_found("Festival")
        fest = Festival.model_validate(row.payload).model_copy(update=body.model_dump(exclude_none=True))
        fest = Festival.model_validate(fest.model_dump())  # re-validate edited values
        row.payload, row.date = fest.model_dump(mode="json"), fest.date
        s.add(row)
        s.commit()
        return fest
