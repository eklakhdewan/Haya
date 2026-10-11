"""Deterministic Mock LLM Provider for offline testing and golden benchmark evaluation."""

import re
from typing import TypeVar

from pydantic import BaseModel

from orchestrator.core.models import RouteType, SupervisorOutput
from orchestrator.providers.base import LLMMessage, LLMProvider

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class MockLLMProvider(LLMProvider):
    """Mock provider supporting regex matching, scripted responses, and deterministic fallbacks."""

    def __init__(self) -> None:
        self._text_responses: dict[str, str] = {}
        self._pattern_routes: list[tuple[re.Pattern[str], RouteType, float, bool]] = [
            # Memory patterns
            (
                re.compile(
                    r"\b(remember|store|save|forget|recall|what did I say about|"\n                    r"preference|prefer|favorite|my dog|project milestones|dietary)\b",
                    re.I,
                ),
                RouteType.MEMORY,
                0.95,
                False,
            ),
            # Coder patterns
            (
                re.compile(
                    r"\b(write a python script|code|function|debug|execute code|"\n                    r"run this program|python)\b",
                    re.I,
                ),
                RouteType.CODER,
                0.98,
                False,
            ),
            # Device patterns
            (
                re.compile(
                    r"\b(send sms|text message|make a call|call|open app|wifi|"\n                    r"bluetooth|setting|device)\b",
                    re.I,
                ),
                RouteType.DEVICE,
                0.97,
                True,
            ),
            # Tool patterns
            (
                re.compile(
                    r"\b(calculate|current time|what time|check.*time|search web|"\n                    r"weather|convert)\b",
                    re.I,
                ),
                RouteType.TOOL,
                0.92,
                False,
            ),
            # Default conversation
            (re.compile(r".*", re.I), RouteType.CONVERSATION, 0.85, False),
        ]

    def register_text_response(self, prompt_substring: str, response: str) -> None:
        self._text_responses[prompt_substring.lower()] = response

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.2,
    ) -> str:
        for sub, resp in self._text_responses.items():
            if sub in prompt.lower():
                return resp
        return f"Mock response to: {prompt}"

    async def generate_structured(
        self,
        messages: list[LLMMessage],
        response_schema: type[SchemaT],
        system_prompt: str | None = None,
        temperature: float = 0.1,
    ) -> SchemaT:
        last_message = messages[-1].content if messages else ""

        # Specialized handling for SupervisorOutput
        if response_schema == SupervisorOutput or issubclass(response_schema, SupervisorOutput):
            for pattern, route, conf, conf_req in self._pattern_routes:
                if pattern.search(last_message):
                    return response_schema(
                        route=route,
                        confidence=conf,
                        requires_confirmation=conf_req,
                        rationale=f"Mock rule match on pattern '{pattern.pattern}'",
                    )

        # Generic default initialization if possible
        try:
            return response_schema.model_validate({})
        except Exception:
            raise NotImplementedError(
                f"MockLLMProvider requires pre-registered handler for schema: {response_schema.__name__}"
            )
