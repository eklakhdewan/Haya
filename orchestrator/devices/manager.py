"""Device enrollment, ownership checks, approval binding, and action audit."""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from orchestrator.core.config import get_settings
from orchestrator.core.errors import ConfirmationRequiredError, PolicyDeniedError
from orchestrator.core.models import IntentType, MobileIntent, RiskLevel
from orchestrator.devices.validator import MobileIntentValidator


class DeviceInfo(BaseModel):
    device_id: str
    user_id: str
    name: str
    registered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_revoked: bool = False


class ActionAuditRecord(BaseModel):
    action_id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    device_id: str
    intent_type: str
    risk: str
    confirmation: str
    requested_at: str
    executed_at: str | None = None
    result: str
    details: dict[str, Any] = Field(default_factory=dict)


@dataclass
class PendingConfirmation:
    token_digest: str
    user_id: str
    device_id: str
    intent_fingerprint: str
    expires_at: datetime
    confirmed: bool = False


class DeviceManager:
    """In-memory device manager; persistent storage is a separate production requirement."""

    def __init__(self, validator: MobileIntentValidator | None = None) -> None:
        self.validator = validator or MobileIntentValidator()
        self._devices: dict[str, DeviceInfo] = {}
        self._pending_confirmations: dict[str, PendingConfirmation] = {}
        self._audit_log: list[ActionAuditRecord] = []

    def register_device(self, device_id: str, user_id: str, name: str = "Android Device") -> DeviceInfo:
        if not device_id.strip() or not user_id.strip():
            raise PolicyDeniedError("device_id and authenticated user_id are required.")
        existing = self._devices.get(device_id)
        if existing and existing.user_id != user_id:
            raise PolicyDeniedError("Device ID is already owned by another user.")
        if existing and not existing.is_revoked:
            existing.name = name
            return existing
        device = DeviceInfo(device_id=device_id, user_id=user_id, name=name)
        self._devices[device_id] = device
        return device

    def revoke_device(self, device_id: str, user_id: str | None = None) -> bool:
        device = self._devices.get(device_id)
        if not device:
            return False
        if user_id is not None and device.user_id != user_id:
            raise PolicyDeniedError("Cannot revoke a device owned by another user.")
        device.is_revoked = True
        for intent_id, pending in list(self._pending_confirmations.items()):
            if pending.device_id == device_id:
                self._pending_confirmations.pop(intent_id, None)
        return True

    def owns_device(self, device_id: str, user_id: str) -> bool:
        """Return ownership independent of revocation state, for audit access."""
        device = self._devices.get(device_id)
        return device is not None and device.user_id == user_id

    def is_device_authorized(self, device_id: str, user_id: str | None = None) -> bool:
        device = self._devices.get(device_id)
        if not device or device.is_revoked:
            return False
        return user_id is None or device.user_id == user_id

    def get_risk_level(self, intent_type: IntentType) -> RiskLevel:
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

    def _issue_confirmation(self, intent: MobileIntent, user_id: str, fingerprint: str) -> str:
        token = secrets.token_urlsafe(32)
        ttl = get_settings().action_confirmation_ttl_seconds
        self._pending_confirmations[intent.intent_id] = PendingConfirmation(
            token_digest=hashlib.sha256(token.encode("utf-8")).hexdigest(),
            user_id=user_id,
            device_id=intent.device_id,
            intent_fingerprint=fingerprint,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=max(1, ttl)),
        )
        return token

    def confirm_action(self, intent_id: str, token: str, user_id: str | None = None) -> bool:
        pending = self._pending_confirmations.get(intent_id)
        now = datetime.now(timezone.utc)
        if not pending:
            return False
        if now >= pending.expires_at:
            self._pending_confirmations.pop(intent_id, None)
            return False
        if user_id is not None and pending.user_id != user_id:
            return False
        supplied_digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        if not hmac.compare_digest(pending.token_digest, supplied_digest):
            return False
        if pending.confirmed:
            return False
        pending.confirmed = True
        return True

    async def execute_intent(self, intent: MobileIntent, user_id: str = "default-user") -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        requested_at = now.isoformat()
        risk_level = self.get_risk_level(intent.intent_type)
        device = self._devices.get(intent.device_id)

        if not device or device.is_revoked or device.user_id != user_id:
            self._audit_log.append(ActionAuditRecord(
                user_id=user_id, device_id=intent.device_id, intent_type=intent.intent_type.value,
                risk=risk_level.value, confirmation="denied", requested_at=requested_at,
                result="rejected", details={"reason": "Device is not authorized for this user."},
            ))
            raise PolicyDeniedError("Device is not authorized for this authenticated user.")

        fingerprint = self._fingerprint(intent)
        # Confirmation policy is server-owned: all MEDIUM and HIGH actions require approval.
        requires_confirmation = risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH)
        pending = self._pending_confirmations.get(intent.intent_id)
        resumed_approved_action = False

        # An approval may resume only the exact previously validated intent, for the same
        # user and device, before both the intent and approval expire.
        if pending:
            if now >= pending.expires_at:
                self._pending_confirmations.pop(intent.intent_id, None)
                raise PolicyDeniedError("Action confirmation has expired; submit the action again.")
            if (
                pending.user_id != user_id
                or pending.device_id != intent.device_id
                or not hmac.compare_digest(pending.intent_fingerprint, fingerprint)
            ):
                raise PolicyDeniedError("Approved intent does not match the pending action.")
            if not pending.confirmed:
                raise ConfirmationRequiredError(
                    "This action is awaiting explicit confirmation.",
                    details={"intent_id": intent.intent_id},
                )
            if intent.expires_at <= now:
                self._pending_confirmations.pop(intent.intent_id, None)
                raise PolicyDeniedError("Approved intent has expired.")
            resumed_approved_action = True
        else:
            self.validator.validate_intent(intent)

        if requires_confirmation and not resumed_approved_action:
            challenge_token = self._issue_confirmation(intent, user_id, fingerprint)
            self._audit_log.append(ActionAuditRecord(
                user_id=user_id, device_id=intent.device_id, intent_type=intent.intent_type.value,
                risk=risk_level.value, confirmation="pending", requested_at=requested_at,
                result="requires_confirmation",
                details={"intent_fingerprint": fingerprint},
            ))
            raise ConfirmationRequiredError(
                f"Action '{intent.intent_type.value}' is high-risk and requires confirmation.",
                details={"challenge_token": challenge_token, "intent_id": intent.intent_id},
            )

        # Consume approval atomically from this in-memory manager before returning success.
        self._pending_confirmations.pop(intent.intent_id, None)
        executed_at = datetime.now(timezone.utc).isoformat()
        audit = ActionAuditRecord(
            user_id=user_id, device_id=intent.device_id, intent_type=intent.intent_type.value,
            risk=risk_level.value, confirmation="approved" if requires_confirmation else "not_required",
            requested_at=requested_at, executed_at=executed_at, result="success",
            details={"intent_fingerprint": fingerprint},
        )
        self._audit_log.append(audit)
        self.validator.mark_completed(intent.intent_id)
        return {
            "status": "success", "action_id": audit.action_id, "intent_id": intent.intent_id,
            "executed_at": executed_at, "payload": intent.payload,
        }

    def get_audit_trail(
        self, device_id: str | None = None, user_id: str | None = None
    ) -> list[ActionAuditRecord]:
        return [
            record for record in self._audit_log
            if (device_id is None or record.device_id == device_id)
            and (user_id is None or record.user_id == user_id)
        ]
