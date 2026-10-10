"""Integration tests for Realtime Voice WebSocket endpoint."""

import time
from fastapi.testclient import TestClient
from tests.security_helpers import auth_headers

from orchestrator.main import app, stt_adapter

client = TestClient(app, headers=auth_headers("ws-user", "user"))


def test_realtime_websocket_connection() -> None:
    session_id = "ws-test-session-1"

    # Set canned speech turn for this session
    stt_adapter.set_canned_turn(
        session_id,
        [("Hello Hina", True)],
    )

    token = client.headers["Authorization"].split(" ", 1)[1]
    with client.websocket_connect(
        f"/v1/realtime/ws?session_id={session_id}&user_id=ws-user&access_token={token}"
    ) as ws:
        # First message sent on session connect
        first_evt = ws.receive_json()
        assert first_evt["event_type"] == "SESSION_STARTED"
        assert first_evt["session_id"] == session_id

        # Send simulated audio frame
        ws.send_bytes(b"audio-frame-pcm")

        # Expect SPEECH_STARTED and TRANSCRIPT_FINAL events
        events_received = []
        for _ in range(3):
            try:
                evt = ws.receive_json()
                events_received.append(evt["event_type"])
            except Exception:
                break

        assert "SPEECH_STARTED" in events_received or "TRANSCRIPT_FINAL" in events_received
