"""Tests for MobileIntentValidator, DeviceManager, DeviceAgent, and confirmation gates."""

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from orchestrator.agents.device import DeviceAgent
from orchestrator.core.errors import (
    ConfirmationRequiredError,
    InvalidSchemaError,
    PolicyDeniedError,
)
from orchestrator.core.models import IntentType, MobileIntent
from orchestrator.devices.manager import DeviceManager
from orchestrator.devices.validator import MobileIntentValidator
from orchestrator.providers.mock_llm import MockLLMProvider


def test_intent_validator_valid_and_replay() -> None:
    validator = MobileIntentValidator()
    now = datetime.now(timezone.utc)
    intent = MobileIntent(
        device_id=str(uuid4()),
        intent_type=IntentType.OPEN_APP,
        payload={"target": "com.spotify.music"},
        issued_at=now,
        expires_at=now + timedelta(seconds=60),
        nonce="validnonce1234567890abcdef",
    )

    # 1. First validation succeeds
    validator.validate_intent(intent)

    # 2. Replay attack: same nonce should fail immediately
    with pytest.raises(PolicyDeniedError, match="Replay attack detected"):
        validator.validate_intent(intent)


def test_intent_validator_expired() -> None:
    validator = MobileIntentValidator()
    now = datetime.now(timezone.utc)
    expired_intent = MobileIntent(
        device_id=str(uuid4()),
        intent_type=IntentType.OPEN_APP,
        payload={"target": "com.example.app"},
        issued_at=now - timedelta(seconds=120),
        expires_at=now - timedelta(seconds=10),  # Already expired
        nonce="validnonce9876543210fedcba",
    )

    with pytest.raises(PolicyDeniedError, match="expired"):
        validator.validate_intent(expired_intent)


def test_device_manager_flow() -> None:
    async def _run() -> None:
        manager = DeviceManager()
        device_id = str(uuid4())
        user_id = "user-device-test"

        # 1. Register device
        dev_info = manager.register_device(device_id, user_id, "Test Phone")
        assert dev_info.is_revoked is False
        assert manager.is_device_authorized(device_id) is True

        now = datetime.now(timezone.utc)

        # 2. Low-risk intent (OPEN_APP) executes directly
        open_intent = MobileIntent(
            device_id=device_id,
            intent_type=IntentType.OPEN_APP,
            payload={"target": "camera"},
            issued_at=now,
            expires_at=now + timedelta(seconds=60),
            nonce="nonce_open_app_1234567890",
        )
        res = await manager.execute_intent(open_intent, user_id=user_id)
        assert res["status"] == "success"

        # 3. High-risk intent (SEND_SMS) requires confirmation
        sms_intent = MobileIntent(
            device_id=device_id,
            intent_type=IntentType.SEND_SMS,
            payload={"target": "+15551234567", "body": "Test message"},
            issued_at=now,
            expires_at=now + timedelta(seconds=60),
            nonce="nonce_send_sms_0987654321",
            confirmation_required=True,
        )

        with pytest.raises(ConfirmationRequiredError) as exc_info:
            await manager.execute_intent(sms_intent, user_id=user_id)

        challenge_token = exc_info.value.details["challenge_token"]
        assert challenge_token.startswith("confirm-")

        # 4. User approves with challenge token
        confirmed = manager.confirm_action(sms_intent.intent_id, challenge_token)
        assert confirmed is True

        # 5. Re-executing with approved token succeeds (with fresh transaction nonce)
        sms_intent.confirmation_token = challenge_token
        sms_intent.nonce = "nonce_send_sms_confirmed_123456789"
        sms_res = await manager.execute_intent(sms_intent, user_id=user_id)
        assert sms_res["status"] == "success"

        # 6. Revoke device
        manager.revoke_device(device_id)
        assert manager.is_device_authorized(device_id) is False

        # 7. Revoked device rejected
        open_intent.nonce = "nonce_open_app_revoked_test_123"
        with pytest.raises(PolicyDeniedError, match="revoked"):
            await manager.execute_intent(open_intent, user_id=user_id)

        # 8. Audit trail
        audit = manager.get_audit_trail(device_id)
        assert len(audit) >= 3

    asyncio.run(_run())


def test_device_agent_generates_typed_intent() -> None:
    llm = MockLLMProvider()
    agent = DeviceAgent(llm_provider=llm)
    device_id = str(uuid4())

    # SMS command
    sms_intent = agent.create_intent("Send SMS to Alice saying I arrived", device_id=device_id)
    assert sms_intent.intent_type == IntentType.SEND_SMS
    assert sms_intent.confirmation_required is True
    assert len(sms_intent.nonce) >= 16

    # Open app command
    app_intent = agent.create_intent("Open app Spotify", device_id=device_id)
    assert app_intent.intent_type == IntentType.OPEN_APP
    assert app_intent.confirmation_required is False
    assert app_intent.payload["target"] == "spotify"
