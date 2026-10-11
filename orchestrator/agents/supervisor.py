"""Supervisor Agent responsible for intent routing, loop capping, and policy enforcement."""

from orchestrator.core.models import (
    RouteType,
    SupervisorInput,
    SupervisorOutput,
)
from orchestrator.providers.base import LLMMessage, LLMProvider

SUPERVISOR_SYSTEM_PROMPT = """You are the Supervisor Agent for HINA, an autonomous AI companion.
Your role is to classify user input into exactly one specialist route:
1. conversation: General open-domain chat, questions, greetings, explanations.
2. memory: Requests to remember, update, forget, or recall personal preferences, facts,\n   relationships, or projects.
3. tool: Requests requiring deterministic tools such as calculators, time checks, unit\n   conversions, or search.
4. coder: Requests to write, run, debug, or execute programming code or scripts.
5. device: Requests to interact with an Android phone (SMS, calls, app launches, or\n   system settings).

Safety & Confirmation Policy:
- High-risk device actions (SMS, calls, or critical settings changes) MUST set\n  requires_confirmation to true.
- Code execution tasks with external side effects require confirmation.
- Do NOT execute actions. Output only the route, confidence, and\n  confirmation requirement.
"""


class Supervisor:
    """Supervisor agent choosing specialists and capping iteration loops."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        max_loops_per_turn: int = 5,
    ) -> None:
        self.llm_provider = llm_provider
        self.max_loops_per_turn = max_loops_per_turn
        self._session_loop_counts: dict[str, int] = {}

    def get_loop_count(self, session_id: str) -> int:
        return self._session_loop_counts.get(session_id, 0)

    def increment_loop_count(self, session_id: str) -> int:
        count = self._session_loop_counts.get(session_id, 0) + 1
        self._session_loop_counts[session_id] = count
        return count

    def reset_loop_count(self, session_id: str) -> None:
        self._session_loop_counts[session_id] = 0

    async def route(self, input_data: SupervisorInput) -> SupervisorOutput:
        """Route user input to appropriate specialist while enforcing iteration policies."""
        # 1. Check iteration loops
        current_loops = self.increment_loop_count(input_data.session_id)
        if current_loops > self.max_loops_per_turn:
            return SupervisorOutput(
                route=RouteType.CONVERSATION,
                confidence=1.0,
                requires_confirmation=False,
                rationale=(
                    f"Max loop iterations ({self.max_loops_per_turn}) exceeded. "
                    "Capping loop and falling back to direct conversation."
                ),
            )

        # 2. Query LLM provider with structured schema
        messages = [
            LLMMessage(role="user", content=input_data.text),
        ]

        output = await self.llm_provider.generate_structured(
            messages=messages,
            response_schema=SupervisorOutput,
            system_prompt=SUPERVISOR_SYSTEM_PROMPT,
            temperature=0.0,
        )

        # 3. Policy override: Ensure device actions like SMS or calls always require confirmation
        lower_text = input_data.text.lower()
        if output.route == RouteType.DEVICE and any(
            k in lower_text for k in ["sms", "text", "call", "dial", "setting", "system"]
        ):
                output.requires_confirmation = True

        return output
