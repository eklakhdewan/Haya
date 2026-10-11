"""Live PostgreSQL tests for persistent device authorization.

These tests are skipped unless DATABASE_URL points to a dedicated disposable test DB.
CI provisions an isolated PostgreSQL service and applies the real Alembic migration first.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete

from orchestrator.core.database import create_database_runtime
from orchestrator.core.errors import ConfirmationRequiredError, PolicyDeniedError
from orchestrator.core.models import IntentType, MobileIntent
from orchestrator.devices.persistence_models import (
    ActionAuditRecordModel,
    CompletedIntentRecord,
    DeviceRecord,
    PendingConfirmationRecord,
    UsedNonceRecord,
)
from orchestrator.devices.persistent_manager import PersistentDeviceManager

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="DATABASE_URL must point to a dedicated disposable PostgreSQL test database",
)


@pytest_asyncio.fixture
async def persistent_manager() -> AsyncIterator[PersistentDeviceManager]:
    runtime = create_database_runtime(DATABASE_URL)
    assert runtime is not None
    manager = PersistentDeviceManager(runtime)
    try:
        # The CI database is disposable. Keep tests independent while exercising
        # the actual schema created by Alembic, not metadata.create_all().
        async with runtime.sessions() as session, session.begin():
            for model in (
                ActionAuditRecordModel,
                CompletedIntentRecord,
                UsedNonceRecord,
                PendingConfirmationRecord,
                DeviceRecord,
            ):
                await session.execute(delete(model))
        yield manager
    finally:
        await runtime.dispose()


def make_intent(
    device_id: str,
    *,
    intent_type: IntentType = IntentType.OPEN_APP,
    intent_id: str | None = None,
    nonce: str | None = None,
) -> MobileIntent:
    now = datetime.now(UTC)
    return MobileIntent(
        intent_id=intent_id or str(uuid4()),
        device_id=device_id,
        intent_type=intent_type,
        payload={"app": "com.example.test"},
        issued_at=now,
        expires_at=now + timedelta(minutes=5),
        nonce=nonce or uuid4().hex + uuid4().hex,
    )


@pytest.mark.asyncio
async def test_device_ownership_and_revocation_survive_manager_restart(
    persistent_manager: PersistentDeviceManager,
) -> None:
    device_id = f"device-{uuid4()}"
    user_id = f"user-{uuid4()}"
    await persistent_manager.register_device(device_id, user_id, "Test device")

    # A new manager instance simulates an application process restart.
    restarted = PersistentDeviceManager(persistent_manager.runtime)
    assert await restarted.is_device_authorized(device_id, user_id)
    assert await restarted.revoke_device(device_id, user_id=user_id)
    assert not await persistent_manager.is_device_authorized(device_id, user_id)


@pytest.mark.asyncio
async def test_high_risk_confirmation_is_single_use(
    persistent_manager: PersistentDeviceManager,
) -> None:
    device_id = f"device-{uuid4()}"
    user_id = f"user-{uuid4()}"
    await persistent_manager.register_device(device_id, user_id)
    intent = make_intent(device_id, intent_type=IntentType.SEND_SMS)

    with pytest.raises(ConfirmationRequiredError) as challenge:
        await persistent_manager.execute_intent(intent, user_id=user_id)
    token = challenge.value.details["challenge_token"]

    assert await persistent_manager.confirm_action(intent.intent_id, token, user_id=user_id)
    result = await persistent_manager.execute_intent(intent, user_id=user_id)
    assert result["status"] == "success"

    with pytest.raises(PolicyDeniedError, match="Replay attack"):
        await persistent_manager.execute_intent(intent, user_id=user_id)


@pytest.mark.asyncio
async def test_nonce_cannot_be_reused_for_a_different_intent(
    persistent_manager: PersistentDeviceManager,
) -> None:
    device_id = f"device-{uuid4()}"
    user_id = f"user-{uuid4()}"
    await persistent_manager.register_device(device_id, user_id)
    nonce = uuid4().hex + uuid4().hex

    first = make_intent(device_id, nonce=nonce)
    await persistent_manager.execute_intent(first, user_id=user_id)
    second = make_intent(device_id, nonce=nonce)

    with pytest.raises(PolicyDeniedError, match="nonce or intent"):
        await persistent_manager.execute_intent(second, user_id=user_id)


@pytest.mark.asyncio
async def test_concurrent_replay_only_allows_one_completion(
    persistent_manager: PersistentDeviceManager,
) -> None:
    device_id = f"device-{uuid4()}"
    user_id = f"user-{uuid4()}"
    await persistent_manager.register_device(device_id, user_id)
    intent = make_intent(device_id)

    async def attempt() -> str:
        try:
            await persistent_manager.execute_intent(intent, user_id=user_id)
            return "success"
        except PolicyDeniedError:
            return "denied"

    outcomes = await asyncio.gather(attempt(), attempt())
    assert outcomes.count("success") == 1
    assert outcomes.count("denied") == 1


@pytest.mark.asyncio
async def test_concurrent_registration_cannot_claim_device_for_two_users(
    persistent_manager: PersistentDeviceManager,
) -> None:
    device_id = f"device-{uuid4()}"
    users = [f"user-{uuid4()}", f"user-{uuid4()}"]
    outcomes = await asyncio.gather(
        *(persistent_manager.register_device(device_id, user_id) for user_id in users),
        return_exceptions=True,
    )

    assert sum(not isinstance(item, BaseException) for item in outcomes) == 1
    denied = [item for item in outcomes if isinstance(item, PolicyDeniedError)]
    assert len(denied) == 1
    assert await persistent_manager.is_device_authorized(
        device_id, user_id=users[0]
    ) != await persistent_manager.is_device_authorized(device_id, user_id=users[1])
