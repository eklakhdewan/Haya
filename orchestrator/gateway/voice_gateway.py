"""Voice Gateway orchestrating streaming STT, turn detection, routing, and interruptible TTS."""

import asyncio
import time
from typing import Any
from uuid import uuid4

from orchestrator.agents.supervisor import Supervisor
from orchestrator.core.models import RouteType, SupervisorInput
from orchestrator.gateway.events import RealtimeEventType, SessionState
from orchestrator.gateway.session_manager import SessionRegistry, VoiceSession
from orchestrator.gateway.stt_adapter import STTAdapter
from orchestrator.gateway.tts_adapter import TTSAdapter
from orchestrator.memory.lifecycle import MemoryLifecycleManager
from orchestrator.observability import trace_manager
from orchestrator.providers.base import LLMProvider
from orchestrator.tools.registry import ToolRegistry


class VoiceGateway:
    """Coordinates the full real-time voice pipeline."""

    def __init__(
        self,
        stt_adapter: STTAdapter,
        tts_adapter: TTSAdapter,
        supervisor: Supervisor,
        llm_provider: LLMProvider,
        tool_registry: ToolRegistry,
        memory_lifecycle: MemoryLifecycleManager,
        session_registry: SessionRegistry | None = None,
    ) -> None:
        self.stt_adapter = stt_adapter
        self.tts_adapter = tts_adapter
        self.supervisor = supervisor
        self.llm_provider = llm_provider
        self.tool_registry = tool_registry
        self.memory_lifecycle = memory_lifecycle
        self.sessions = session_registry or SessionRegistry()

    async def handle_audio_chunk(
        self,
        session_id: str,
        user_id: str,
        chunk: bytes,
    ) -> VoiceSession:
        """Process incoming client audio chunk (e.g. 80ms PCM/Opus)."""
        session = self.sessions.get_or_create(session_id, user_id)

        is_speech, transcript_text, is_final = await self.stt_adapter.process_audio_chunk(
            session_id, chunk
        )

        if is_speech:
            # 1. Barge-In: If assistant was speaking, interrupt immediately!
            if session.state == SessionState.SPEAKING:
                session.interrupt()

            if session.state != SessionState.LISTENING:
                session.state = SessionState.LISTENING
                session.emit_event(RealtimeEventType.SPEECH_STARTED)

            # 2. Stream partial transcript
            if transcript_text and not is_final:
                session.emit_event(
                    RealtimeEventType.TRANSCRIPT_PARTIAL,
                    {"text": transcript_text},
                )

        # 3. Handle turn finalization
        if is_final and transcript_text:
            session.emit_event(
                RealtimeEventType.TRANSCRIPT_FINAL,
                {"text": transcript_text},
            )
            # Process turn asynchronously so audio receiving is non-blocking
            asyncio.create_task(self._process_final_turn(session, transcript_text))

        return session

    async def _process_final_turn(self, session: VoiceSession, user_text: str) -> None:
        """Execute agent routing, tool execution, and streaming TTS for a finalized turn."""
        session.state = SessionState.THINKING
        trace_id = session.current_trace_id or str(uuid4())
        session.current_trace_id = trace_id
        trace_manager.start_trace(session.session_id, operation="voice_turn", trace_id=trace_id)

        try:
            # Step 1: Supervisor routing
            t_route = time.perf_counter()
            sup_input = SupervisorInput(
                session_id=session.session_id,
                user_id=session.user_id,
                text=user_text,
                trace_id=trace_id,
            )
            route_decision = await self.supervisor.route(sup_input)
            dur_route = (time.perf_counter() - t_route) * 1000
            trace_manager.record_stage(
                trace_id,
                "intent_classification",
                dur_route,
                {"route": route_decision.route.value, "confidence": route_decision.confidence},
            )

            response_text = ""

            # Step 2: Handle routing
            t_exec = time.perf_counter()
            if route_decision.route == RouteType.TOOL:
                session.state = SessionState.EXECUTING
                session.emit_event(RealtimeEventType.TOOL_STARTED, {"tool": "calculator"})
                # Builtin tool execution demo
                try:
                    tool_out = await self.tool_registry.execute("calculator", {"expression": "2 + 2"})
                    session.emit_event(RealtimeEventType.TOOL_RESULT, tool_out)
                    response_text = f"The calculated result is {tool_out.get('result', 4)}."
                except Exception as e:
                    response_text = f"Tool execution failed: {e}"

            elif route_decision.route == RouteType.MEMORY:
                session.state = SessionState.EXECUTING
                items = await self.memory_lifecycle.query(session.user_id, user_text, top_k=1)
                if items:
                    response_text = f"I recall that {items[0].text}."
                else:
                    response_text = "I don't have any specific memories stored for that yet."

            else:
                # Conversation / Coder / Device fallback
                response_text = await self.llm_provider.generate_text(
                    prompt=user_text,
                    system_prompt="You are HINA, an autonomous voice companion. Answer succinctly.",
                )

            dur_exec = (time.perf_counter() - t_exec) * 1000
            trace_manager.record_stage(
                trace_id,
                "specialist_execution",
                dur_exec,
                {"route": route_decision.route.value},
            )

            # Step 3: Stream Assistant Text
            session.emit_event(
                RealtimeEventType.ASSISTANT_TEXT,
                {"text": response_text},
            )

            # Step 4: Stream Assistant Audio with Barge-in Token
            session.state = SessionState.SPEAKING
            session._active_tts_task = asyncio.current_task()

            t_tts = time.perf_counter()
            try:
                async for audio_chunk in self.tts_adapter.synthesize_stream(
                    response_text,
                    session.cancellation_token,
                ):
                    if session.cancellation_token.is_set():
                        break
                    session.audio_output_queue.put_nowait(audio_chunk)
                    session.emit_event(
                        RealtimeEventType.ASSISTANT_AUDIO,
                        {"chunk_size": len(audio_chunk)},
                    )
            finally:
                dur_tts = (time.perf_counter() - t_tts) * 1000
                trace_manager.record_stage(trace_id, "tts_synthesis", dur_tts)
                if not session.cancellation_token.is_set():
                    session.state = SessionState.IDLE
                trace_manager.finish_trace(trace_id, "success")
        except Exception as e:
            trace_manager.finish_trace(trace_id, "error", str(e))
            raise
