"""Device manager handling enrollment, authorization, confirmation gates, and action audit."""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
from pydantic import BaseModel, Field

from orchestrator.core.errors import (
    ConfirmationRequiredError,
    DeviceOfflineError,
    PolicyDeniedError,
)
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
    confirmation: str  # "approved", "denied", "not_required"
    requested_at: str
    executed_at: str | None = None
    result: str  # "success", "rejected", "failed"
    details: dict[str, Any] = Field(default_factory=dict)


class DeviceManager:
    """Central device manager for mobile client authentication and action enforcement."""

    def __init__(self, validator: MobileIntentValidator | None = None) -> None:
        self.validator = validator or MobileIntentValidator()
        self._devices: dict[str, DeviceInfo] = {}
        # intent_id -> confirmation_token
        self._pending_confirmations: dict[str, str] = {}
        self._confirmed_intents: set[str] = set()
        self._audit_log: list[ActionAuditRecord] = []

    def register_device(self, device_id: str, user_id: str, name: str = "Android Device") -> DeviceInfo:
        device = DeviceInfo(device_id=device_id, user_id=user_id, name=name)
        self._devices[device_id] = device
        return device

    def revoke_device(self, device_id: str) -> bool:
        if device_id in self._devices:
            self._devices[device_id].is_revoked = True
            return True
        return False

    def is_device_authorized(self, device_id: str) -> bool:
        device = self._devices.get(device_id)
        if not device or device.is_revoked:
            return False
        return True

    def get_risk_level(self, intent_type: IntentType) -> RiskLevel:
        if intent_type in [IntentType.SEND_SMS, IntentType.MAKE_CALL]:
            return RiskLevel.HIGH
        elif intent_type == IntentType.SYSTEM_SETTING:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def issue_confirmation_token(self, intent_id: str) -> str:
        token = f"confirm-{uuid4().hex[:16]}"
        self._pending_confirmations[intent_id] = token
        return token

    def confirm_action(self, intent_id: str, token: str) -> bool:
        expected = self._pending_confirmations.get(intent_id)
        if expected and expected == token:
            del self._pending_confirmations[intent_id]
            self._confirmed_intents.add(intent_id)
            return True
        return False

    async def execute_intent(self, intent: MobileIntent, user_id: str = "default-user") -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        requested_at = now.isoformat()

        # 1. Device enrollment check
        if not self.is_device_authorized(intent.device_id):
            audit = ActionAuditRecord(
                user_id=user_id,
                device_id=intent.device_id,
                intent_type=intent.intent_type.value,
                risk=self.get_risk_level(intent.intent_type).value,
                confirmation="denied",
                requested_at=requested_at,
                result="rejected",
                details={"reason": "Device is not registered or has been revoked."},
            )
            self._audit_log.append(audit)
            raise PolicyDeniedError(f"Device '{intent.device_id}' is not authorized or has been revoked.")

        # 2. Schema, expiration, and replay protection
        self.validator.validate_intent(intent)

        # 3. Risk-based Confirmation Policy Check
        risk_level = self.get_risk_level(intent.intent_type)
        if risk_level == RiskLevel.HIGH:
            # Requires explicit confirmation token or prior approval
            token_valid = (
                intent.intent_id in self._confirmed_intents
                or (
                    intent.confirmation_token
                    and self._pending_confirmations.get(intent.intent_id) == intent.confirmation_token
                )
            )

            if not token_valid:
                # Generate new challenge token for the user to approve
                challenge_token = self.issue_confirmation_token(intent.intent_id)
                audit = ActionAuditRecord(
                    user_id=user_id,
                    device_id=intent.device_id,
                    intent_type=intent.intent_type.value,
                    risk=risk_level.value,
                    confirmation="pending",
                    requested_at=requested_at,
                    result="requires_confirmation",
                    details={"challenge_token": challenge_token},
                )
                self._audit_log.append(audit)
                raise ConfirmationRequiredError(
                    f"Action '{intent.intent_type.value}' is high-risk and requires confirmation.",
                    details={"challenge_token": challenge_token, "intent_id": intent.intent_id},
                )

        # Cleanup confirmed state for this execution
        self._confirmed_intents.discard(intent.intent_id)
        self._pending_confirmations.pop(intent.intent_id, None)

        # 4. Dispatch and record success in audit log
        executed_at = datetime.now(timezone.utc).isoformat()
        audit = ActionAuditRecord(
            user_id=user_id,
            device_id=intent.device_id,
            intent_type=intent.intent_type.value,
            risk=risk_level.value,
            confirmation="approved" if risk_level == RiskLevel.HIGH else "not_required",
            requested_at=requested_at,
            executed_at=executed_at,
            result="success",
            details=intent.payload,
        )
        self._audit_log.append(audit)
        self.validator.mark_completed(intent.intent_id)

        return {
            "status": "success",
            "action_id": audit.action_id,
            "intent_id": intent.intent_id,
            "executed_at": executed_at,
            "payload": intent.payload,
        }

    def get_audit_trail(self, device_id: str | None = None) -> list[ActionAuditRecord]:
        if device_id:
            return [r for r in self._audit_log if r.device_id == device_id]
        return list(self._audit_log)
