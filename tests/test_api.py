"""API integration tests for orchestrator endpoints."""

from uuid import uuid4

from fastapi.testclient import TestClient

from orchestrator.main import app
from tests.security_helpers import auth_headers

client = TestClient(app, headers=auth_headers("test-user-1", "user"))


def test_api_route_endpoint() -> None:
    req = {
        "session_id": str(uuid4()),
        "user_id": "test-user-1",
        "text": "Calculate 15 * 8",
        "trace_id": str(uuid4()),
    }
    response = client.post("/v1/supervisor/route", json=req)
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["route"] == "tool"
    assert body["data"]["confidence"] > 0.8


def test_api_tools_endpoints() -> None:
    # 1. List tools
    list_resp = client.get("/v1/tools")
    assert list_resp.status_code == 200
    tools = list_resp.json()["data"]
    names = [t["name"] for t in tools]
    assert "calculator" in names
    assert "current_time" in names

    # 2. Execute calculator tool
    exec_resp = client.post(
        "/v1/tools/execute",
        json={"tool_name": "calculator", "payload": {"expression": "100 / 5"}},
    )
    assert exec_resp.status_code == 200
    assert exec_resp.json()["data"]["result"] == 20.0

    # 3. Execute tool with missing parameters
    bad_req = client.post(
        "/v1/tools/execute",
        json={"tool_name": "calculator", "payload": {}},
    )
    assert bad_req.status_code == 422
    assert bad_req.json()["detail"]["code"] == "INVALID_SCHEMA"
