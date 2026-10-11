"""HTTP and WebSocket authentication boundary regression tests."""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

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
    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect("/v1/realtime/ws"):
            pass
    assert error.value.code == 4401


def test_websocket_rejects_user_identity_mismatch() -> None:
    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect(
            "/v1/realtime/ws?user_id=other-user",
            headers=auth_headers("owner-user", "user"),
        ):
            pass
    assert error.value.code == 4403
