"""Unit tests for core models, serialization, and validation."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from orchestrator.core.models import (
    APIResponse,
    CriticCheckResult,
    IntentType,
    MemoryCandidate,
    MemoryEntityType,
    MemoryOperation,
    MobileIntent,
    RiskLevel,
    RouteType,
    SandboxExecuteRequest,
    SandboxExecutionResult,
    SupervisorInput,
    SupervisorOutput,
)


def test_supervisor_input_valid() -> None:
    data = {
        "session_id": str(uuid4()),
        "user_id": "usr-123",
        "text": "What is my current project?",
        "trace_id": str(uuid4()),
    }
    inp = SupervisorInput(**data)
    assert inp.session_id == data["session_id"]
    assert inp.text == "What is my current project?"


def test_supervisor_input_forbid_extra() -> None:
    with pytest.raises(ValidationError):
        SupervisorInput(
            session_id="s1",
            user_id="u1",
            text="hello",
            unknown_field="injected",  # type: ignore[call-arg]
        )


def test_supervisor_output_confidence_bounds() -> None:
    out = SupervisorOutput(
        route=RouteType.CONVERSATION,
        confidence=0.95,
        requires_confirmation=False,
    )
    assert out.route == RouteType.CONVERSATION
    assert out.confidence == 0.95

    with pytest.raises(ValidationError):
        SupervisorOutput(
            route=RouteType.CONVERSATION,
            confidence=1.5,  # Exceeds 1.0
            requires_confirmation=False,
        )


def test_mobile_intent_schema() -> None:
    now = datetime.now(timezone.utc)
    intent = MobileIntent(
        device_id=str(uuid4()),
        intent_type=IntentType.OPEN_APP,
        payload={"target": "com.example.app"},
        issued_at=now,
        expires_at=now + timedelta(seconds=60),
        nonce="1234567890abcdef1234",
    )
    assert intent.intent_type == IntentType.OPEN_APP
    assert intent.payload["target"] == "com.example.app"

    # Nonce too short
    with pytest.raises(ValidationError):
        MobileIntent(
            device_id=str(uuid4()),
            intent_type=IntentType.OPEN_APP,
            payload={},
            issued_at=now,
            expires_at=now + timedelta(seconds=60),
            nonce="short",
        )


def test_memory_candidate() -> None:
    candidate = MemoryCandidate(
        entity_type=MemoryEntityType.PROJECT,
        subject="User",
        predicate="WORKS_ON",
        object="HINA",
        confidence=0.99,
        source_turn_id=str(uuid4()),
        operation=MemoryOperation.CREATE,
    )
    assert candidate.object == "HINA"
    assert candidate.operation == MemoryOperation.CREATE


def test_sandbox_models() -> None:
    req = SandboxExecuteRequest(code="print(1 + 1)", timeout_ms=3000)
    assert req.network == "disabled"
    assert req.timeout_ms == 3000

    res = SandboxExecutionResult(
        status="success",
        stdout="2\n",
        stderr="",
        exit_code=0,
        execution_time_ms=50,
    )
    assert res.status == "success"
    assert res.stdout == "2\n"


def test_api_response_envelope() -> None:
    resp: APIResponse[dict[str, str]] = APIResponse(data={"status": "ready"})
    assert resp.error is None
    assert resp.data == {"status": "ready"}
    assert resp.request_id is not None
