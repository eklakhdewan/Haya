"""Tests for VoiceGateway streaming, turn detection, and barge-in interruption."""

import asyncio
from uuid import uuid4

from orchestrator.agents.supervisor import Supervisor
from orchestrator.gateway.events import RealtimeEventType, SessionState
from orchestrator.gateway.session_manager import SessionRegistry
from orchestrator.gateway.stt_adapter import MockSTTAdapter
from orchestrator.gateway.tts_adapter import MockTTSAdapter
from orchestrator.gateway.voice_gateway import VoiceGateway
from orchestrator.memory.lifecycle import MemoryLifecycleManager
from orchestrator.memory.mock_memory import InMemoryGraphStore, InMemoryVectorStore
from orchestrator.providers.mock_llm import MockLLMProvider
from orchestrator.tools.builtin import CalculatorTool, TimeTool
from orchestrator.tools.registry import ToolRegistry


def test_voice_turn_lifecycle() -> None:
    async def _run() -> None:
        stt = MockSTTAdapter()
        tts = MockTTSAdapter(chunk_count=3, delay_per_chunk_s=0.005)
        llm = MockLLMProvider()
        supervisor = Supervisor(llm_provider=llm)
        tools = ToolRegistry()
        tools.register(CalculatorTool())
        tools.register(TimeTool())
        memory = MemoryLifecycleManager(InMemoryVectorStore(), InMemoryGraphStore())

        gateway = VoiceGateway(
            stt_adapter=stt,
            tts_adapter=tts,
            supervisor=supervisor,
            llm_provider=llm,
            tool_registry=tools,
            memory_lifecycle=memory,
        )

        session_id = f"test-voice-{uuid4()}"
        user_id = "voice-user-1"

        # Program mock STT to emit partial then final turn
        stt.set_canned_turn(
            session_id,
            [
                ("What is 2", False),
                ("What is 2 + 2", True),
            ],
        )

        # 1. Chunk 1: Partial speech
        session = await gateway.handle_audio_chunk(session_id, user_id, b"chunk-1")
        assert session.state == SessionState.LISTENING

        # 2. Chunk 2: Finalized speech turn
        await gateway.handle_audio_chunk(session_id, user_id, b"chunk-2")

        # Allow background turn task to finish
        await asyncio.sleep(0.08)

        # Collect emitted events
        events = []
        while not session.event_queue.empty():
            events.append(session.event_queue.get_nowait())

        event_types = [e.event_type for e in events]
        assert RealtimeEventType.SESSION_STARTED in event_types
        assert RealtimeEventType.SPEECH_STARTED in event_types
        assert RealtimeEventType.TRANSCRIPT_PARTIAL in event_types
        assert RealtimeEventType.TRANSCRIPT_FINAL in event_types
        assert RealtimeEventType.ASSISTANT_TEXT in event_types
        assert RealtimeEventType.ASSISTANT_AUDIO in event_types

        # Verify outgoing audio frames
        assert not session.audio_output_queue.empty()

    asyncio.run(_run())


def test_barge_in_interruption() -> None:
    async def _run() -> None:
        stt = MockSTTAdapter()
        # Slow TTS to give time for interruption
        tts = MockTTSAdapter(chunk_count=10, delay_per_chunk_s=0.05)
        llm = MockLLMProvider()
        supervisor = Supervisor(llm_provider=llm)
        tools = ToolRegistry()
        memory = MemoryLifecycleManager(InMemoryVectorStore(), InMemoryGraphStore())

        gateway = VoiceGateway(
            stt_adapter=stt,
            tts_adapter=tts,
            supervisor=supervisor,
            llm_provider=llm,
            tool_registry=tools,
            memory_lifecycle=memory,
        )

        session_id = f"test-bargein-{uuid4()}"
        user_id = "voice-user-2"

        session = gateway.sessions.get_or_create(session_id, user_id)
        session.state = SessionState.SPEAKING

        # Simulated incoming speech while assistant is speaking
        session.interrupt()

        assert session.state == SessionState.LISTENING
        assert session.cancellation_token.is_set()

        events = []
        while not session.event_queue.empty():
            events.append(session.event_queue.get_nowait())

        event_types = [e.event_type for e in events]
        assert RealtimeEventType.SPEECH_INTERRUPTED in event_types

    asyncio.run(_run())
