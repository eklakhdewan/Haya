"""Typed domain models and schemas for the HINA orchestrator."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Generic, Literal, TypeVar
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


# Enums
class RouteType(str, Enum):
    CONVERSATION = "conversation"
    MEMORY = "memory"
    TOOL = "tool"
    CODER = "coder"
    DEVICE = "device"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class MemoryOperation(str, Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    IGNORE = "IGNORE"


class MemoryEntityType(str, Enum):
    PERSON = "Person"
    PREFERENCE = "Preference"
    PROJECT = "Project"
    EVENT = "Event"
    ORGANIZATION = "Organization"
    SKILL = "Skill"
    RELATIONSHIP = "Relationship"


class IntentType(str, Enum):
    SEND_SMS = "SEND_SMS"
    MAKE_CALL = "MAKE_CALL"
    OPEN_APP = "OPEN_APP"
    SYSTEM_SETTING = "SYSTEM_SETTING"


# Supervisor Contracts (from AGENTS.md)
class SupervisorInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(description="Unique conversation session identifier")
    user_id: str = Field(description="Unique authenticated user identifier")
    text: str = Field(description="User prompt or transcribed speech text")
    trace_id: str = Field(default_factory=lambda: str(uuid4()), description="Distributed trace identifier")


class SupervisorOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route: RouteType = Field(description="Selected target agent specialist")
    confidence: float = Field(ge=0.0, le=1.0, description="Routing confidence score")
    requires_confirmation: bool = Field(default=False, description="Whether routing or action requires user confirmation")
    rationale: str = Field(default="", description="Brief classifier reasoning")


# Memory Domain Models (from DATA_SPEC.md & AGENTS.md)
class MemoryCandidate(BaseModel):
    entity_type: MemoryEntityType
    subject: str
    predicate: str
    object: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_turn_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    operation: MemoryOperation = MemoryOperation.CREATE


class MemoryRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    kind: str = "fact"
    subject: str
    predicate: str
    object: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_turn_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: Literal["active", "deleted", "archived"] = "active"


class MemoryQueryRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=50)
    include_graph: bool = Field(default=True)


class MemoryQueryItem(BaseModel):
    memory_id: str
    text: str
    score: float
    source_turn_id: str


class MemoryQueryResponse(BaseModel):
    items: list[MemoryQueryItem] = Field(default_factory=list)


# Code Execution Sandbox Models (from DATA_SPEC.md & API_SPEC.md)
class SandboxExecuteRequest(BaseModel):
    language: Literal["python"] = "python"
    code: str
    timeout_ms: int = Field(default=5000, ge=500, le=60000)
    network: Literal["enabled", "disabled"] = "disabled"


class SandboxExecutionResult(BaseModel):
    execution_id: str = Field(default_factory=lambda: str(uuid4()))
    status: Literal["success", "error", "timeout"]
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    execution_time_ms: int = 0


# Mobile Device Intent Models (from mobile_intent.schema.json & DATA_SPEC.md)
class MobileIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent_id: str = Field(default_factory=lambda: str(uuid4()))
    device_id: str
    intent_type: IntentType
    payload: dict[str, Any]
    issued_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime
    nonce: str = Field(min_length=16)
    confirmation_required: bool = False
    confirmation_token: str | None = None


# Critic Verification Models (from AGENTS.md)
class CriticCheckResult(BaseModel):
    approved: bool
    groundedness_score: float = Field(ge=0.0, le=1.0)
    policy_compliant: bool
    reasons: list[str] = Field(default_factory=list)


# API Response Envelope (from API_SPEC.md)
DataT = TypeVar("DataT")


class APIResponse(BaseModel, Generic[DataT]):
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    data: DataT | None = None
    error: dict[str, Any] | None = None
