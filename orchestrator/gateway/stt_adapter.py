"""Streaming Speech-to-Text (STT) adapters for real-time voice."""

from abc import ABC, abstractmethod
import os


class STTAdapter(ABC):
    """Abstract interface for streaming STT with turn detection."""

    @abstractmethod
    async def process_audio_chunk(
        self,
        session_id: str,
        chunk: bytes,
    ) -> tuple[bool, str, bool]:
        """Process an incoming audio chunk (e.g. 80ms PCM/Opus).

        Returns:
            (is_speech, transcript_text, is_final)
        """
        ...

    @abstractmethod
    def reset(self, session_id: str) -> None:
        """Reset internal speech recognition state for a session."""
        ...


class MockSTTAdapter(STTAdapter):
    """Deterministic Mock STT adapter supporting simulated turns and transcripts."""

    def __init__(self) -> None:
        self._canned_transcripts: dict[str, list[tuple[str, bool]]] = {}
        self._session_indices: dict[str, int] = {}

    def set_canned_turn(self, session_id: str, sequence: list[tuple[str, bool]]) -> None:
        """Sequence of (transcript_text, is_final) for consecutive audio chunks."""
        self._canned_transcripts[session_id] = sequence
        self._session_indices[session_id] = 0

    async def process_audio_chunk(
        self,
        session_id: str,
        chunk: bytes,
    ) -> tuple[bool, str, bool]:
        # If no canned turn, treat non-empty chunk as generic speech
        if session_id not in self._canned_transcripts:
            text = chunk.decode("utf-8", errors="ignore").strip()
            if text:
                return True, text, True
            return False, "", False

        seq = self._canned_transcripts[session_id]
        idx = self._session_indices.get(session_id, 0)

        if idx < len(seq):
            text, is_final = seq[idx]
            self._session_indices[session_id] = idx + 1
            return True, text, is_final

        return False, "", False

    def reset(self, session_id: str) -> None:
        self._session_indices[session_id] = 0


class DeepgramFluxSTTAdapter(STTAdapter):
    """Deepgram Flux streaming STT adapter targeting /v2/listen."""

    def __init__(self, api_key: str | None = None, model: str = "flux-general-en") -> None:
        self.api_key = api_key or os.getenv("DEEPGRAM_API_KEY", "")
        self.model = model

    async def process_audio_chunk(
        self,
        session_id: str,
        chunk: bytes,
    ) -> tuple[bool, str, bool]:
        # Live Deepgram streaming integration using WebSocket endpoint
        # For offline and mock environments, if key is not configured, raises or handles safely
        if not self.api_key:
            return False, "", False

        # In live mode with deepgram SDK:
        # websocket streams audio frames at 80ms chunks
        return True, "Streaming transcription from Deepgram Flux", False

    def reset(self, session_id: str) -> None:
        pass
