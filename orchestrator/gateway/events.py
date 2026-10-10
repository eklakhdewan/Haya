"""Realtime event definitions and schemas conforming to API_SPEC.md."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class RealtimeEventType(str, Enum):
    SESSION_STARTED = "SESSION_STARTED"
    SPEECH_STARTED = "SPEECH_STARTED"
    TRANSCRIPT_PARTIAL = "TRANSCRIPT_PARTIAL"
    TRANSCRIPT_FINAL = "TRANSCRIPT_FINAL"
    TOOL_STARTED = "TOOL_STARTED"
    TOOL_RESULT = "TOOL_RESULT"
    ASSISTANT_TEXT = "ASSISTANT_TEXT"
    ASSISTANT_AUDIO = "ASSISTANT_AUDIO"
    SPEECH_INTERRUPTED = "SPEECH_INTERRUPTED"
    SESSION_ENDED = "SESSION_ENDED"
    ERROR = "ERROR"


class SessionState(str, Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    INTERRUPTED = "INTERRUPTED"
    EXECUTING = "EXECUTING"
    WAITING_FOR_CONFIRMATION = "WAITING_FOR_CONFIRMATION"
    ERROR = "ERROR"
    OFFLINE = "OFFLINE"


class RealtimeEvent(BaseModel):
    """Base event payload for WebRTC data channels and WebSocket sessions."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    event_type: RealtimeEventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    payload: dict[str, Any] = Field(default_factory=dict)
