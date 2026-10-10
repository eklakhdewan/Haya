"""JWT authentication primitives for the HINA API.

Tokens are issued by a trusted identity component, not by public API endpoints.
Use short-lived HS256 tokens and rotate HINA_JWT_SECRET through deployment secrets.
"""
from __future__ import annotations

from typing import Any

import jwt
from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError

from orchestrator.core.config import get_settings

_bearer = HTTPBearer(auto_error=False)


def decode_access_token(token: str) -> dict[str, Any]:
    """Validate signature, issuer, audience, expiry, issued-at, and subject."""
    settings = get_settings()
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        )
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=401,
            detail={"code": "AUTH_REQUIRED", "message": "Invalid or expired bearer token."},
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject.strip() or len(subject) > 200:
        raise HTTPException(
            status_code=401,
            detail={"code": "AUTH_REQUIRED", "message": "Token subject is invalid."},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return claims


async def require_principal(
    credentials: HTTPAuthorizationCredentials | None = __import__(
        "fastapi.security", fromlist=["HTTPAuthorizationCredentials"]
    ).HTTPAuthorizationCredentials = None,
) -> dict[str, Any]:
    """FastAPI dependency returning validated claims from a Bearer token."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail={"code": "AUTH_REQUIRED", "message": "Bearer token required."},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decode_access_token(credentials.credentials)


def principal_from_request(request: Request) -> dict[str, Any]:
    """Read the already-verified principal attached by the HTTP auth middleware."""
    principal = getattr(request.state, "principal", None)
    if not principal:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return principal
