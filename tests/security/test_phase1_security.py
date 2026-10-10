"""Regression tests for Phase 1 authentication, ownership, approval, and sandbox gates."""
import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from orchestrator.core.errors import ConfirmationRequiredError, PolicyDeniedError, ProviderUnavailableError
from orchestrator.core.models import IntentType, MobileIntent
from orchestrator.devices.manager import DeviceManager
from orchestrator.main import app
from orchestrator.sandbox.e2b_adapter import E2BSandboxAdapter
from tests.security_helpers import auth_headers


def make_intent(device_id: str, kind: IntentType = IntentType.OPEN_APP) -> MobileIntent:
    now = datetime.now(timezone.utc)
    payload = {"target": "calculator"}
    if kind == IntentType.SEND_SMS:
        payload = {"target": "+15550001111", "body": "Approved message"}
    return MobileIntent(
        device_id=device_id,
        intent_type=kind,
        payload=payload,
        issued_at=now,
        expires_at=now + timedelta(seconds=60),
        nonce=f"nonce-{uuid4().hex}-security",
        confirmation_required=kind == IntentType.SEND_SMS,
    )


def test_http_routes_require_valid_bearer_token() -> None:
    unauthenticated = TestClient(app)
    assert unauthenticated.get("/v1/tools").status_code == 401
    assert unauthenticated.get("/v1/health").status_code == 200

    ordinary_user = TestClient(app, headers=auth_headers("alice", "user"))
    assert ordinary_user.get("/dashboard").status_code == 403
    assert ordinary_user.get("/v1/traces").status_code == 403

    admin = TestClient(app, headers=auth_headers("admin-user", "admin"))
    assert admin.get("/dashboard").status_code == 200


def test_device_ownership_prevents_cross_user_actions() -> None:
    async def run() -> None:
        manager = DeviceManager()
        device_id = str(uuid4())
        manager.register_device(device_id, "alice")
        with pytest.raises(PolicyDeniedError, match="authenticated user"):
            await manager.execute_intent(make_intent(device_id), user_id="bob")
        with pytest.raises(PolicyDeniedError, match="another user"):
            manager.revoke_device(device_id, user_id="bob")

    asyncio.run(run())


def test_confirmation_is_bound_to_exact_intent_and_user() -> None:
    async def run() -> None:
        manager = DeviceManager()
        device_id = str(uuid4())
        manager.register_device(device_id, "alice")
        intent = make_intent(device_id, IntentType.SEND_SMS)

        with pytest.raises(ConfirmationRequiredError) as challenge:
            await manager.execute_intent(intent, user_id="alice")
        token = challenge.value.details["challenge_token"]

        assert manager.confirm_action(intent.intent_id, token, user_id="bob") is False
        assert manager.confirm_action(intent.intent_id, "incorrect-token", user_id="alice") is False
        assert manager.confirm_action(intent.intent_id, token, user_id="alice") is True
        assert manager.confirm_action(intent.intent_id, token, user_id="alice") is False

        modified = intent.model_copy(update={"payload": {"target": "+19990000000", "body": "Changed"}})
        with pytest.raises(PolicyDeniedError, match="does not match"):
            await manager.execute_intent(modified, user_id="alice")

        result = await manager.execute_intent(intent, user_id="alice")
        assert result["status"] == "success"
        with pytest.raises(PolicyDeniedError, match="Replay attack"):
            await manager.execute_intent(intent, user_id="alice")

    asyncio.run(run())



def test_expired_confirmation_challenge_can_be_renewed_for_same_valid_intent() -> None:
    async def run() -> None:
        manager = DeviceManager()
        device_id = str(uuid4())
        manager.register_device(device_id, "alice")
        intent = make_intent(device_id, IntentType.SYSTEM_SETTING)

        with pytest.raises(ConfirmationRequiredError) as first_challenge:
            await manager.execute_intent(intent, user_id="alice")
        old_token = first_challenge.value.details["challenge_token"]

        # Simulate TTL expiry without expiring or mutating the original intent.
        manager._pending_confirmations[intent.intent_id].expires_at = (
            datetime.now(timezone.utc) - timedelta(seconds=1)
        )
        with pytest.raises(ConfirmationRequiredError) as renewed_challenge:
            await manager.execute_intent(intent, user_id="alice")
        new_token = renewed_challenge.value.details["challenge_token"]

        assert new_token != old_token
        assert manager.confirm_action(intent.intent_id, old_token, user_id="alice") is False
        assert manager.confirm_action(intent.intent_id, new_token, user_id="bob") is False
        assert manager.confirm_action(intent.intent_id, new_token, user_id="alice") is True

        result = await manager.execute_intent(intent, user_id="alice")
        assert result["status"] == "success"
        with pytest.raises(PolicyDeniedError, match="Replay attack"):
            await manager.execute_intent(intent, user_id="alice")

    asyncio.run(run())


def test_medium_risk_requires_server_side_confirmation_even_if_client_flag_is_false() -> None:
    async def run() -> None:
        manager = DeviceManager()
        device_id = str(uuid4())
        manager.register_device(device_id, "alice")
        now = datetime.now(timezone.utc)
        intent = MobileIntent(
            device_id=device_id,
            intent_type=IntentType.SYSTEM_SETTING,
            payload={"setting": "wifi", "action": "toggle"},
            issued_at=now,
            expires_at=now + timedelta(seconds=60),
            nonce=f"setting-{uuid4().hex}-nonce",
            confirmation_required=False,
        )
        with pytest.raises(ConfirmationRequiredError) as challenge:
            await manager.execute_intent(intent, user_id="alice")
        token = challenge.value.details["challenge_token"]
        assert manager.confirm_action(intent.intent_id, token, user_id="alice")
        result = await manager.execute_intent(intent, user_id="alice")
        assert result["status"] == "success"

    asyncio.run(run())

def test_sandbox_fails_closed_without_isolated_provider() -> None:
    async def run() -> None:
        adapter = E2BSandboxAdapter(api_key="")
        with pytest.raises(ProviderUnavailableError, match="will not fall back"):
            await adapter.execute("print(1)", timeout_ms=1000, network="disabled")
        with pytest.raises(PolicyDeniedError, match="Network-enabled"):
            await E2BSandboxAdapter(api_key="configured-test-key").execute(
                "print(1)", timeout_ms=1000, network="enabled"
            )

    asyncio.run(run())
