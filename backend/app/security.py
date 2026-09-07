"""API key check for the /api/v1 endpoints."""

from typing import Optional

from fastapi import Header, HTTPException, status

from app.config import settings


async def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    """Reject the request when the X-API-Key header does not match settings.api_key.

    Disabled when api_key is empty, which is the default for local dev.
    """
    if not settings.api_key:
        return
    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "X-API-Key"},
        )
