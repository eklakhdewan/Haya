"""Voice Session and Barge-In lifecycle management."""

import asyncio
from typing import Any
from uuid import uuid4

from orchestrator.gateway.events import (
    RealtimeEvent,
    RealtimeEventType,
    SessionState,
)


class VoiceSession:
    """Represents an active bidirectional real-time audio session."""

    def __init__(self, session_id: str, user_id: str) -> None:
        self.session_id = session_id
        self.user_id = user_id
        self.state: SessionState = SessionState.IDLE
        self.current_trace_id: str = str(uuid4())
        self.cancellation_token: asyncio.Event = asyncio.Event()
        self.event_queue: asyncio.Queue[RealtimeEvent] = asyncio.Queue()
        self.audio_output_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._active_tts_task: asyncio.Task[Any] | None = None

    def emit_event(self, event_type: RealtimeEventType, payload: dict[str, Any] | None = None) -> RealtimeEvent:
        event = RealtimeEvent(
            session_id=self.session_id,
            event_type=event_type,
            trace_id=self.current_trace_id,
            payload=payload or {},
        )
        self.event_queue.put_nowait(event)
        return event

    def interrupt(self) -> None:
        """Trigger instant barge-in interruption: cancel active TTS and audio playback."""
        if self.state == SessionState.SPEAKING or self._active_tts_task:
            self.cancellation_token.set()
            if self._active_tts_task and not self._active_tts_task.done():
                self._active_tts_task.cancel()
                self._active_tts_task = None

            # Clear buffered outgoing audio
            while not self.audio_output_queue.empty():
                try:
                    self.audio_output_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

            self.state = SessionState.INTERRUPTED
            self.emit_event(RealtimeEventType.SPEECH_INTERRUPTED, {"reason": "user_barge_in"})
            self.state = SessionState.LISTENING

    def reset_for_new_turn(self) -> None:
        self.current_trace_id = str(uuid4())
        self.cancellation_token = asyncio.Event()
        self.state = SessionState.LISTENING


class SessionRegistry:
    """Registry maintaining active voice sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, VoiceSession] = {}

    def get_or_create(self, session_id: str, user_id: str) -> VoiceSession:
        if session_id not in self._sessions:
            session = VoiceSession(session_id, user_id)
            session.emit_event(RealtimeEventType.SESSION_STARTED, {"user_id": user_id})
            self._sessions[session_id] = session
        return self._sessions[session_id]

    def remove(self, session_id: str) -> VoiceSession | None:
        session = self._sessions.pop(session_id, None)
        if session:
            session.interrupt()
            session.state = SessionState.OFFLINE
            session.emit_event(RealtimeEventType.SESSION_ENDED)
        return session
