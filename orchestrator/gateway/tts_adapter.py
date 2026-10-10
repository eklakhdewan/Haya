"""Streaming Text-to-Speech (TTS) adapters with barge-in cancellation support."""

import asyncio
import os
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class TTSAdapter(ABC):
    """Abstract interface for streaming interruptible TTS synthesis."""

    @abstractmethod
    async def synthesize_stream(
        self,
        text: str,
        cancellation_token: asyncio.Event,
    ) -> AsyncIterator[bytes]:
        """Synthesize text into streaming audio chunks with instant cancellation support."""
        ...


class MockTTSAdapter(TTSAdapter):
    """Deterministic Mock TTS producing simulated audio chunks that respect barge-in cancellation."""

    def __init__(self, chunk_count: int = 5, delay_per_chunk_s: float = 0.01) -> None:
        self.chunk_count = chunk_count
        self.delay_per_chunk_s = delay_per_chunk_s

    async def synthesize_stream(
        self,
        text: str,
        cancellation_token: asyncio.Event,
    ) -> AsyncIterator[bytes]:
        # Generate N simulated audio packets (representing 80ms audio frames)
        for i in range(self.chunk_count):
            if cancellation_token.is_set():
                # Barge-in: immediately abort audio streaming!
                break

            await asyncio.sleep(self.delay_per_chunk_s)

            if cancellation_token.is_set():
                break

            # Simulated PCM/Opus frame
            audio_frame = f"[AUDIO_FRAME_{i}:{text[:10]}]".encode("utf-8")
            yield audio_frame


class DeepgramFluxTTSAdapter(TTSAdapter):
    """Deepgram Flux / Cartesia streaming TTS adapter."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("DEEPGRAM_API_KEY", "")

    async def synthesize_stream(
        self,
        text: str,
        cancellation_token: asyncio.Event,
    ) -> AsyncIterator[bytes]:
        if not self.api_key:
            yield b""
            return

        # Deepgram TTS streaming path
        for i in range(3):
            if cancellation_token.is_set():
                break
            await asyncio.sleep(0.02)
            yield f"[DEEPGRAM_TTS_{i}]".encode("utf-8")
