"""Integration tests for Android Device Bridge API endpoints."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from orchestrator.main import app
from tests.security_helpers import auth_headers

client = TestClient(app, headers=auth_headers("user-api-device", "user"))


def test_api_device_lifecycle() -> None:
    device_id = str(uuid4())
    user_id = "user-api-device"

    # 1. Register device
    reg_resp = client.post(
        "/v1/device/register",
        json={"device_id": device_id, "user_id": user_id, "name": "Pixel 9"},
    )
    assert reg_resp.status_code == 200
    assert reg_resp.json()["data"]["device_id"] == device_id

    now = datetime.now(UTC)

    # 2. Execute low-risk action (OPEN_APP)
    open_intent = {
        "intent_id": str(uuid4()),
        "device_id": device_id,
        "intent_type": "OPEN_APP",
        "payload": {"target": "maps"},
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=60)).isoformat(),
        "nonce": "api_test_nonce_1234567890",
        "confirmation_required": False,
    }
    action_resp = client.post("/v1/device/actions", json=open_intent)
    assert action_resp.status_code == 200
    assert action_resp.json()["data"]["status"] == "success"

    # 3. Execute high-risk action (SEND_SMS) without confirmation
    sms_intent_id = str(uuid4())
    sms_intent = {
        "intent_id": sms_intent_id,
        "device_id": device_id,
        "intent_type": "SEND_SMS",
        "payload": {"target": "+15550001111", "body": "Meeting in 5 min"},
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=60)).isoformat(),
        "nonce": "api_test_nonce_9876543210",
        "confirmation_required": True,
    }
    sms_resp = client.post("/v1/device/actions", json=sms_intent)
    assert sms_resp.status_code == 403
    err_detail = sms_resp.json()["detail"]
    assert err_detail["code"] == "CONFIRMATION_REQUIRED"
    challenge_token = err_detail["details"]["challenge_token"]

    # 4. Confirm action via /v1/device/confirm
    confirm_resp = client.post(
        "/v1/device/confirm",
        json={"intent_id": sms_intent_id, "confirmation_token": challenge_token},
    )
    assert confirm_resp.status_code == 200
    assert confirm_resp.json()["data"]["confirmed"] is True

    # 5. Check action audit trail
    audit_resp = client.get(f"/v1/device/audit?device_id={device_id}")
    assert audit_resp.status_code == 200
    audit_records = audit_resp.json()["data"]
    assert len(audit_records) >= 2

    # 6. Revoke device
    revoke_resp = client.post("/v1/device/revoke", json={"device_id": device_id})
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["data"]["revoked"] is True
