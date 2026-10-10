"""Intent validation, JSON schema enforcement, and replay protection."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import jsonschema

from orchestrator.core.errors import InvalidSchemaError, PolicyDeniedError
from orchestrator.core.models import MobileIntent

SCHEMA_PATH = Path(__file__).parent.parent.parent / "config" / "schemas" / "mobile_intent.schema.json"


class MobileIntentValidator:
    """Validates mobile intents against JSON Schema, expiration, and replay attacks."""

    def __init__(self, schema_file: Path = SCHEMA_PATH) -> None:
        self.schema_file = schema_file
        self._schema: dict[str, Any] | None = None
        self._used_nonces: dict[str, tuple[str, datetime]] = {}  # nonce -> (intent_id, timestamp)
        self._completed_intent_ids: set[str] = set()

    def _load_schema(self) -> dict[str, Any]:
        if self._schema is None:
            if not self.schema_file.exists():
                raise FileNotFoundError(f"Schema file not found at {self.schema_file}")
            with open(self.schema_file, "r", encoding="utf-8") as f:
                self._schema = json.load(f)
        return self._schema

    def validate_schema(self, intent_dict: dict[str, Any]) -> None:
        """Validate raw dictionary against the official JSON Schema."""
        schema = self._load_schema()
        try:
            jsonschema.validate(instance=intent_dict, schema=schema)
        except jsonschema.ValidationError as e:
            raise InvalidSchemaError(f"Mobile intent failed schema validation: {e.message}")

    def mark_completed(self, intent_id: str) -> None:
        """Mark an intent as executed so it cannot be re-executed."""
        self._completed_intent_ids.add(intent_id)

    def validate_intent(self, intent: MobileIntent) -> None:
        """Comprehensive verification including schema, expiration, and replay protection."""
        now = datetime.now(timezone.utc)

        # 1. Check expiration
        if intent.expires_at <= now:
            raise PolicyDeniedError(
                f"Mobile intent '{intent.intent_id}' has expired (expires_at={intent.expires_at}, now={now})."
            )

        # 2. Check if intent was already executed
        if intent.intent_id in self._completed_intent_ids:
            raise PolicyDeniedError(
                f"Replay attack detected: intent '{intent.intent_id}' has already been executed."
            )

        # 3. Replay attack protection: check if nonce was already used
        if intent.nonce in self._used_nonces:
            raise PolicyDeniedError(
                f"Replay attack detected: nonce '{intent.nonce}' has already been processed."
            )

        # 4. JSON schema validation
        intent_dict = intent.model_dump(mode="json", exclude_none=True)
        self.validate_schema(intent_dict)

        # Record nonce
        self._used_nonces[intent.nonce] = (intent.intent_id, now)

        # Prune nonces older than 1 hour to prevent memory leaks
        self._prune_nonces(now)

    def _prune_nonces(self, now: datetime) -> None:
        cutoff = now.timestamp() - 3600
        expired_nonces = [n for n, (_, dt) in self._used_nonces.items() if dt.timestamp() < cutoff]
        for n in expired_nonces:
            del self._used_nonces[n]
