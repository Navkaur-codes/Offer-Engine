"""Decision log: filtered list, full detail, and a live SSE stream for the Overview feed."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app import decision_store
from app.api.deps import not_found
from app.config import now
from app.contracts import Decision

router = APIRouter(prefix="/api/decisions", tags=["decisions"])

STREAM_POLL_SECONDS = 2.0
KEEPALIVE_SECONDS = 20.0


@router.get("")
def list_decisions(
    status: str | None = None,
    decided_by: str | None = None,
    policy: str | None = None,
    trigger: str | None = None,
    customer_id: str | None = None,
    q: str | None = None,
    festival: str | None = None,
    limit: int = 50,
    cursor: datetime | None = None,
) -> dict:
    limit = max(1, min(limit, 200))
    rows = decision_store.query(
        status=status,
        decided_by=decided_by,
        policy=policy,
        trigger=trigger,
        customer_id=customer_id,
        q=q,
        festival=festival,
        before=cursor,
        limit=limit + 1,
    )
    page, more = rows[:limit], len(rows) > limit
    return {"items": decision_store.light(page), "next": page[-1].ts.isoformat() if more else None}


@router.get("/stream")
async def stream(request: Request) -> StreamingResponse:
    async def events() -> AsyncIterator[str]:
        last = now()
        idle = 0.0
        yield ": connected\n\n"
        while not await request.is_disconnected():
            fresh = await asyncio.to_thread(decision_store.query, after=last, limit=50)
            for d in reversed(fresh):  # oldest first, so the feed reads in order
                payload = json.dumps(decision_store.light([d])[0].model_dump(mode="json"))
                yield f"event: decision\ndata: {payload}\n\n"
                last = max(last, d.ts)
            idle = 0.0 if fresh else idle + STREAM_POLL_SECONDS
            if idle >= KEEPALIVE_SECONDS:
                yield ": keepalive\n\n"
                idle = 0.0
            await asyncio.sleep(STREAM_POLL_SECONDS)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{decision_id}")
def get_decision(decision_id: str) -> Decision:
    d = decision_store.get(decision_id)
    if d is None:
        raise not_found("Decision")
    return d
