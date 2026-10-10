"""Integration tests for Developer Dashboard UI and OpenTelemetry trace retrieval."""

from uuid import uuid4
from fastapi.testclient import TestClient
from tests.security_helpers import auth_headers

from orchestrator.main import app

client = TestClient(app, headers=auth_headers("trace-user", "admin"))


def test_dashboard_ui_served() -> None:
    # Root endpoint serves dashboard
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert "HINA — Developer Control Plane & Dashboard" in res_root.text
    assert "Realtime Voice Session" in res_root.text

    # /dashboard serves the same
    res_dash = client.get("/dashboard")
    assert res_dash.status_code == 200
    assert "HINA — Developer Control Plane & Dashboard" in res_dash.text


def test_traces_lifecycle_and_api() -> None:
    trace_id = str(uuid4())
    session_id = f"trace-test-{uuid4()}"

    # 1. Trigger supervisor route to record a trace
    route_req = {
        "session_id": session_id,
        "user_id": "trace-user",
        "text": "Calculate 10 * 10",
        "trace_id": trace_id,
    }
    client.post("/v1/supervisor/route", json=route_req)

    # 2. Query /v1/traces
    traces_resp = client.get("/v1/traces")
    assert traces_resp.status_code == 200
    traces = traces_resp.json()["data"]
    assert len(traces) >= 1

    matching = next((t for t in traces if t["trace_id"] == trace_id), None)
    assert matching is not None
    assert matching["operation"] == "supervisor_route"
    assert matching["status"] == "success"
    assert len(matching["stages"]) >= 1
    assert matching["stages"][0]["stage"] == "intent_classification"

    # 3. Query specific trace by ID
    single_trace_resp = client.get(f"/v1/traces/{trace_id}")
    assert single_trace_resp.status_code == 200
    single_trace = single_trace_resp.json()["data"]
    assert single_trace["trace_id"] == trace_id
    assert single_trace["total_duration_ms"] >= 0


def test_voice_turn_trace_recorded() -> None:
    import asyncio
    from orchestrator.main import voice_gateway
    from orchestrator.observability import trace_manager

    session_id = f"voice-trace-{uuid4()}"
    trace_id = f"tid-{uuid4()}"
    session = voice_gateway.sessions.get_or_create(session_id, "user-vt")
    session.current_trace_id = trace_id

    async def _run() -> None:
        await voice_gateway._process_final_turn(session, "What is 2 + 2?")

    asyncio.run(_run())

    tr = trace_manager.get_trace(trace_id)
    assert tr is not None
    assert tr["operation"] == "voice_turn"
    stage_names = [s["stage"] for s in tr["stages"]]
    assert "intent_classification" in stage_names
    assert "specialist_execution" in stage_names
    assert "tts_synthesis" in stage_names

