"""Shared test helpers for authenticated API integration tests."""

import time

import jwt

from orchestrator.core.config import get_settings


def auth_headers(subject: str, role: str = "user") -> dict[str, str]:
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": subject,
            "role": role,
            "iss": get_settings().jwt_issuer,
            "aud": get_settings().jwt_audience,
            "iat": now,
            "exp": now + 300,
        },
        get_settings().jwt_secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}
