"""Device Agent translating natural language into typed, bounded mobile intents."""

import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from orchestrator.core.models import IntentType, MobileIntent
from orchestrator.providers.base import LLMProvider


class DeviceAgent:
    """Agent producing typed, schema-validated MobileIntents without direct OS calls."""

    def __init__(self, llm_provider: LLMProvider) -> None:
        self.llm_provider = llm_provider

    def create_intent(
        self,
        command_text: str,
        device_id: str,
        ttl_seconds: int = 60,
    ) -> MobileIntent:
        """Create a typed mobile intent with nonce, expiration, and risk classification."""
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl_seconds)
        nonce = secrets.token_hex(16)  # 32 characters
        lower = command_text.lower()

        # Rule-based intent classification
        if "sms" in lower or "text" in lower:
            # Extract target and message if possible
            target_match = re.search(r"(?:to)\s+([a-zA-Z0-9\+]+)", lower)
            target = target_match.group(1) if target_match else "unknown"
            return MobileIntent(
                intent_id=str(uuid4()),
                device_id=device_id,
                intent_type=IntentType.SEND_SMS,
                payload={"target": target, "body": command_text},
                issued_at=now,
                expires_at=expires_at,
                nonce=nonce,
                confirmation_required=True,
            )

        elif "call" in lower or "dial" in lower:
            target_match = re.search(r"(?:to|dial)\s+([a-zA-Z0-9\+]+)", lower)
            target = target_match.group(1) if target_match else "unknown"
            return MobileIntent(
                intent_id=str(uuid4()),
                device_id=device_id,
                intent_type=IntentType.MAKE_CALL,
                payload={"target": target},
                issued_at=now,
                expires_at=expires_at,
                nonce=nonce,
                confirmation_required=True,
            )

        elif "setting" in lower or "wifi" in lower or "bluetooth" in lower:
            setting_type = "wifi" if "wifi" in lower else "bluetooth" if "bluetooth" in lower else "general"
            return MobileIntent(
                intent_id=str(uuid4()),
                device_id=device_id,
                intent_type=IntentType.SYSTEM_SETTING,
                payload={"setting": setting_type, "action": "toggle"},
                issued_at=now,
                expires_at=expires_at,
                nonce=nonce,
                confirmation_required=True,
            )

        else:
            # Default to OPEN_APP
            app_match = re.search(r"(?:open|launch)\s+(?:app\s+)?([a-zA-Z0-9\-_]+)", lower)
            app_name = app_match.group(1) if app_match else "default"
            return MobileIntent(
                intent_id=str(uuid4()),
                device_id=device_id,
                intent_type=IntentType.OPEN_APP,
                payload={"target": app_name},
                issued_at=now,
                expires_at=expires_at,
                nonce=nonce,
                confirmation_required=False,
            )
