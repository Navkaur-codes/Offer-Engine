"""Scheduler status and manual runs (admins use it to demo proactive triggers without waiting)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.deps import not_found, require_admin
from app.scheduler import runner

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])


@router.get("")
def status(request: Request) -> dict:
    sched = getattr(request.app.state, "scheduler", None)
    jobs = (
        {j.id: j.next_run_time.isoformat() if j.next_run_time else None for j in sched.get_jobs()}
        if sched
        else {}
    )
    return {"running": sched is not None, "next_runs": jobs}


@router.post("/run/{job}", dependencies=[Depends(require_admin)])
async def run(job: str) -> dict:
    if job not in runner.SCHEDULE:
        raise not_found(f"Job {job}")
    return await runner.run_job(job)
