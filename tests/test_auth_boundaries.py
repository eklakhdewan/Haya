"""HTTP and WebSocket authentication boundary regression tests."""

import time
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from orchestrator.core.config import get_settings
from orchestrator.main import app
from tests.security_helpers import auth_headers

client = TestClient(app)


def test_health_is_the_only_anonymous_http_endpoint() -> None:
    assert client.get("/v1/health").status_code == 200
    assert client.get("/").status_code == 401
    assert client.get("/v1/traces").status_code == 401


def test_regular_user_cannot_access_admin_control_plane() -> None:
    user_client = TestClient(app, headers=auth_headers("regular-user", "user"))
    assert user_client.get("/dashboard").status_code == 403
    assert user_client.get("/v1/traces").status_code == 403
    assert user_client.get("/v1/traces/example-trace").status_code == 403


def test_supervisor_route_rejects_cross_user_identity() -> None:
    user_client = TestClient(app, headers=auth_headers("owner-user", "user"))
    response = user_client.post(
        "/v1/supervisor/route",
        json={
            "session_id": "auth-test-session",
            "user_id": "other-user",
            "text": "hello",
        },
    )
    assert response.status_code == 403


def test_websocket_rejects_missing_authentication() -> None:
    with pytest.raises(WebSocketDisconnect) as error, client.websocket_connect("/v1/realtime/ws"):
        pass
    assert error.value.code == 4401


def test_websocket_rejects_user_identity_mismatch() -> None:
    with (
        pytest.raises(WebSocketDisconnect) as error,
        client.websocket_connect(
            "/v1/realtime/ws?user_id=other-user",
            headers=auth_headers("owner-user", "user"),
        ),
    ):
        pass
    assert error.value.code == 4403


def _token_with_claims(**overrides: Any) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {
        "sub": "auth-test-user",
        "role": "user",
        "iss": get_settings().jwt_issuer,
        "aud": get_settings().jwt_audience,
        "iat": now,
        "exp": now + 300,
    }
    claims.update(overrides)
    return jwt.encode(claims, get_settings().jwt_secret, algorithm="HS256")


@pytest.mark.parametrize(
    "claims",
    [
        {"iss": "untrusted-issuer"},
        {"aud": "other-audience"},
        {"exp": int(time.time()) - 10},
        {"sub": ""},
        {"iat": int(time.time()) + 600},
    ],
)
def test_http_rejects_invalid_jwt_claims(claims: dict[str, Any]) -> None:
    headers = {"Authorization": f"Bearer {_token_with_claims(**claims)}"}
    response = TestClient(app, headers=headers).get("/v1/tools")
    assert response.status_code == 401
