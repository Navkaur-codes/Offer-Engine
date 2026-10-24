"""Shared API dependencies."""

from __future__ import annotations

import hmac

from fastapi import Header, HTTPException

from app.config import settings


def require_admin(x_admin_passcode: str = Header(default="")) -> str:
    """Writes need the dashboard passcode; reads stay public so judges can browse."""
    expected = settings.admin_passcode
    if not expected:
        raise HTTPException(status_code=503, detail="ADMIN_PASSCODE is not configured on the server")
    if not hmac.compare_digest(x_admin_passcode, expected):
        raise HTTPException(status_code=401, detail="Wrong admin passcode")
    return "admin"


def not_found(what: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"{what} not found")
