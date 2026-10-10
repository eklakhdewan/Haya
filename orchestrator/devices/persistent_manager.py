"""PostgreSQL-backed device manager with transactional replay and approval controls."""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from orchestrator.core.config import get_settings
from orchestrator.core.database import DatabaseRuntime
from orchestrator.core.errors import ConfirmationRequiredError, PolicyDeniedError
from orchestrator.core.models import IntentType, MobileIntent, RiskLevel
from orchestrator.devices.manager import ActionAuditRecord, DeviceInfo
from orchestrator.devices.persistence_models import (
    ActionAuditRecordModel,
    CompletedIntentRecord,
    DeviceRecord,
    PendingConfirmationRecord,
    UsedNonceRecord,
)
from orchestrator.devices.validator import MobileIntentValidator


class PersistentDeviceManager:
    """Persistent alternative to DeviceManager for multi-worker deployments.

    Each state-changing operation owns a database transaction. Unique constraints
    on nonce and completed-intent identifiers provide cross-worker replay protection.
    """

    def __init__(
        self,
        runtime: DatabaseRuntime,
        validator: MobileIntentValidator | None = None,
    ) -> None:
        self.runtime = runtime
        self.validator = validator or MobileIntentValidator()

    @staticmethod
    def get_risk_level(intent_type: IntentType) -> RiskLevel:
        if intent_type in (IntentType.SEND_SMS, IntentType.MAKE_CALL):
            return RiskLevel.HIGH
        if intent_type == IntentType.SYSTEM_SETTING:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    @staticmethod
    def _fingerprint(intent: MobileIntent) -> str:
        payload = intent.model_dump(mode="json", exclude={"confirmation_token"})
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _device_info(record: DeviceRecord) -> DeviceInfo:
        return DeviceInfo(
            device_id=record.device_id,
            user_id=record.user_id,
            name=record.name,
            registered_at=record.registered_at,
            is_revoked=record.is_revoked,
        )

    @staticmethod
    def _audit_model(record: ActionAuditRecord) -> ActionAuditRecordModel:
        def parse_timestamp(value: str | None) -> datetime | None:
            if value is None:
                return None
            parsed = datetime.fromisoformat(value)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

        return ActionAuditRecordModel(
            action_id=record.action_id,
            user_id=record.user_id,
            device_id=record.device_id,
            intent_type=record.intent_type,
            risk=record.risk,
            confirmation=record.confirmation,
            requested_at=parse_timestamp(record.requested_at),
            executed_at=parse_timestamp(record.executed_at),
            result=record.result,
            details=record.details,
        )

    @staticmethod
    def _audit_record(row: ActionAuditRecordModel) -> ActionAuditRecord:
        def iso(value: datetime | None) -> str | None:
            if value is None:
                return None
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.isoformat()

        return ActionAuditRecord(
            action_id=row.action_id,
            user_id=row.user_id,
            device_id=row.device_id,
            intent_type=row.intent_type,
            risk=row.risk,
            confirmation=row.confirmation,
            requested_at=iso(row.requested_at) or "",
            executed_at=iso(row.executed_at),
            result=row.result,
            details=row.details,
        )

    async def register_device(
        self, device_id: str, user_id: str, name: str = "Android Device"
    ) -> DeviceInfo:
        if not device_id.strip() or not user_id.strip():
            raise PolicyDeniedError("device_id and authenticated user_id are required.")
        now = datetime.now(timezone.utc)
        async with self.runtime.sessions() as session, session.begin():
            record = await session.scalar(
                select(DeviceRecord).where(DeviceRecord.device_id == device_id).with_for_update()
            )
            if record and record.user_id != user_id:
                raise PolicyDeniedError("Device ID is already owned by another user.")
            if record and not record.is_revoked:
                record.name = name
                return self._device_info(record)
            if record:
                record.name = name
                record.registered_at = now
                record.is_revoked = False
                record.revoked_at = None
                await session.execute(
                    delete(PendingConfirmationRecord).where(
                        PendingConfirmationRecord.device_id == device_id
                    )
                )
            else:
                record = DeviceRecord(
                    device_id=device_id,
                    user_id=user_id,
                    name=name,
                    registered_at=now,
                    is_revoked=False,
                )
                session.add(record)
            await session.flush()
            return self._device_info(record)

    async def revoke_device(self, device_id: str, user_id: str | None = None) -> bool:
        now = datetime.now(timezone.utc)
        async with self.runtime.sessions() as session, session.begin():
            record = await session.scalar(
                select(DeviceRecord).where(DeviceRecord.device_id == device_id).with_for_update()
            )
            if record is None:
                return False
            if user_id is not None and record.user_id != user_id:
                raise PolicyDeniedError("Cannot revoke a device owned by another user.")
            record.is_revoked = True
            record.revoked_at = now
            await session.execute(
                delete(PendingConfirmationRecord).where(
                    PendingConfirmationRecord.device_id == device_id
                )
            )
            return True

    async def owns_device(self, device_id: str, user_id: str) -> bool:
        async with self.runtime.sessions() as session:
            record = await session.scalar(
                select(DeviceRecord.device_id).where(
                    DeviceRecord.device_id == device_id,
                    DeviceRecord.user_id == user_id,
                )
            )
            return record is not None

    async def is_device_authorized(self, device_id: str, user_id: str | None = None) -> bool:
        conditions = [DeviceRecord.device_id == device_id, DeviceRecord.is_revoked.is_(False)]
        if user_id is not None:
            conditions.append(DeviceRecord.user_id == user_id)
        async with self.runtime.sessions() as session:
            record = await session.scalar(select(DeviceRecord.device_id).where(*conditions))
            return record is not None

    async def confirm_action(
        self, intent_id: str, token: str, user_id: str | None = None
    ) -> bool:
        now = datetime.now(timezone.utc)
        supplied_digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        async with self.runtime.sessions() as session, session.begin():
            pending = await session.scalar(
                select(PendingConfirmationRecord)
                .where(PendingConfirmationRecord.intent_id == intent_id)
                .with_for_update()
            )
            if pending is None or now >= pending.expires_at:
                if pending is not None:
                    await session.delete(pending)
                return False
            if user_id is not None and pending.user_id != user_id:
                return False
            if not hmac.compare_digest(pending.token_digest, supplied_digest) or pending.confirmed:
                return False
            pending.confirmed = True
            return True

    async def execute_intent(
        self, intent: MobileIntent, user_id: str = "default-user"
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        requested_at = now.isoformat()
        risk_level = self.get_risk_level(intent.intent_type)
        fingerprint = self._fingerprint(intent)
        requires_confirmation = risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH)
        token: str | None = None
        denied_message: str | None = None
        result: dict[str, Any] | None = None

        try:
            async with self.runtime.sessions() as session, session.begin():
                device = await session.scalar(
                    select(DeviceRecord)
                    .where(DeviceRecord.device_id == intent.device_id)
                    .with_for_update()
                )
                if device is None or device.is_revoked or device.user_id != user_id:
                    session.add(self._audit_model(ActionAuditRecord(
                        user_id=user_id,
                        device_id=intent.device_id,
                        intent_type=intent.intent_type.value,
                        risk=risk_level.value,
                        confirmation="denied",
                        requested_at=requested_at,
                        result="rejected",
                        details={"reason": "Device is not authorized for this user."},
                    )))
                    denied_message = "Device is not authorized for this authenticated user."
                else:
                    pending = await session.scalar(
                        select(PendingConfirmationRecord)
                        .where(PendingConfirmationRecord.intent_id == intent.intent_id)
                        .with_for_update()
                    )
                    renewing = False
                    resumed = False

                    if pending and now >= pending.expires_at:
                        if (
                            pending.user_id != user_id
                            or pending.device_id != intent.device_id
                            or not hmac.compare_digest(pending.intent_fingerprint, fingerprint)
                        ):
                            denied_message = (
                                "Expired challenge does not match this user, device, or intent."
                            )
                        elif intent.expires_at <= now:
                            await session.delete(pending)
                            denied_message = "Action intent has expired; a new valid intent is required."
                        else:
                            await session.delete(pending)
                            await session.flush()
                            pending = None
                            renewing = True

                    if denied_message is None and pending is not None:
                        if (
                            pending.user_id != user_id
                            or pending.device_id != intent.device_id
                            or not hmac.compare_digest(pending.intent_fingerprint, fingerprint)
                        ):
                            denied_message = "Approved intent does not match the pending action."
                        elif not pending.confirmed:
                            denied_message = "This action is awaiting explicit confirmation."
                        elif intent.expires_at <= now:
                            await session.delete(pending)
                            denied_message = "Approved intent has expired."
                        else:
                            resumed = True

                    if denied_message is None and pending is None and not renewing:
                        if intent.expires_at <= now:
                            denied_message = f"Mobile intent '{intent.intent_id}' has expired."
                        else:
                            if await session.get(CompletedIntentRecord, intent.intent_id):
                                denied_message = (
                                    f"Replay attack detected: intent '{intent.intent_id}' "
                                    "has already been executed."
                                )
                            else:
                                self.validator.validate_schema(
                                    intent.model_dump(mode="json", exclude_none=True)
                                )
                                session.add(UsedNonceRecord(
                                    nonce=intent.nonce,
                                    intent_id=intent.intent_id,
                                    used_at=now,
                                ))
                                await session.flush()

                    if denied_message is None and requires_confirmation and not resumed:
                        token = secrets.token_urlsafe(32)
                        ttl = max(1, get_settings().action_confirmation_ttl_seconds)
                        session.add(PendingConfirmationRecord(
                            intent_id=intent.intent_id,
                            token_digest=hashlib.sha256(token.encode("utf-8")).hexdigest(),
                            user_id=user_id,
                            device_id=intent.device_id,
                            intent_fingerprint=fingerprint,
                            expires_at=now + timedelta(seconds=ttl),
                            confirmed=False,
                            created_at=now,
                        ))
                        session.add(self._audit_model(ActionAuditRecord(
                            user_id=user_id,
                            device_id=intent.device_id,
                            intent_type=intent.intent_type.value,
                            risk=risk_level.value,
                            confirmation="pending",
                            requested_at=requested_at,
                            result="requires_confirmation",
                            details={"intent_fingerprint": fingerprint},
                        )))
                    elif denied_message is None:
                        if pending is not None:
                            await session.delete(pending)
                        session.add(CompletedIntentRecord(
                            intent_id=intent.intent_id,
                            device_id=intent.device_id,
                            user_id=user_id,
                            completed_at=now,
                        ))
                        executed_at = datetime.now(timezone.utc).isoformat()
                        audit = ActionAuditRecord(
                            user_id=user_id,
                            device_id=intent.device_id,
                            intent_type=intent.intent_type.value,
                            risk=risk_level.value,
                            confirmation="approved" if requires_confirmation else "not_required",
                            requested_at=requested_at,
                            executed_at=executed_at,
                            result="success",
                            details={"intent_fingerprint": fingerprint},
                        )
                        session.add(self._audit_model(audit))
                        result = {
                            "status": "success",
                            "action_id": audit.action_id,
                            "intent_id": intent.intent_id,
                            "executed_at": executed_at,
                            "payload": intent.payload,
                        }
        except IntegrityError as exc:
            raise PolicyDeniedError(
                "Replay attack detected: nonce or intent has already been processed."
            ) from exc

        if denied_message is not None:
            if denied_message == "This action is awaiting explicit confirmation.":
                raise ConfirmationRequiredError(
                    denied_message, details={"intent_id": intent.intent_id}
                )
            raise PolicyDeniedError(denied_message)
        if token is not None:
            raise ConfirmationRequiredError(
                f"Action '{intent.intent_type.value}' is high-risk and requires confirmation.",
                details={"challenge_token": token, "intent_id": intent.intent_id},
            )
        if result is None:
            raise PolicyDeniedError("Intent could not be completed.")
        return result

    async def get_audit_trail(
        self, device_id: str | None = None, user_id: str | None = None
    ) -> list[ActionAuditRecord]:
        conditions = []
        if device_id is not None:
            conditions.append(ActionAuditRecordModel.device_id == device_id)
        if user_id is not None:
            conditions.append(ActionAuditRecordModel.user_id == user_id)
        async with self.runtime.sessions() as session:
            rows = (
                await session.scalars(
                    select(ActionAuditRecordModel)
                    .where(*conditions)
                    .order_by(ActionAuditRecordModel.requested_at.asc())
                )
            ).all()
            return [self._audit_record(row) for row in rows]
