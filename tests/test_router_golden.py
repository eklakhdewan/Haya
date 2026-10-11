"""50 Golden Routing Tests for Supervisor Agent Core."""

import asyncio
import json
from pathlib import Path
from uuid import uuid4

import pytest

from orchestrator.agents.supervisor import Supervisor
from orchestrator.core.models import RouteType, SupervisorInput
from orchestrator.providers.mock_llm import MockLLMProvider

GOLDEN_FILE = Path(__file__).parent / "golden" / "router.jsonl"


def load_golden_cases() -> list[dict[str, object]]:
    cases = []
    with open(GOLDEN_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


@pytest.mark.parametrize("case", load_golden_cases())
def test_supervisor_golden_routing(case: dict[str, object]) -> None:
    async def _run() -> None:
        provider = MockLLMProvider()
        supervisor = Supervisor(llm_provider=provider, max_loops_per_turn=5)

        inp = SupervisorInput(
            session_id=str(uuid4()),
            user_id="test-user",
            text=str(case["text"]),
            trace_id=str(uuid4()),
        )

        output = await supervisor.route(inp)

        expected_route = RouteType(case["expected_route"])
        expected_conf = bool(case["expected_confirmation"])

        assert output.route == expected_route, (
            f"Failed on text: '{case['text']}'. Expected {expected_route}, got {output.route}"
        )
        if expected_conf:
            assert output.requires_confirmation is True, (
                f"Expected confirmation=True on text: '{case['text']}'"
            )

    asyncio.run(_run())


def test_supervisor_loop_capping() -> None:
    async def _run() -> None:
        provider = MockLLMProvider()
        supervisor = Supervisor(llm_provider=provider, max_loops_per_turn=3)
        session_id = "test-session-loop"

        for _i in range(3):
            inp = SupervisorInput(
                session_id=session_id,
                user_id="user-1",
                text="write a python script",
            )
            out = await supervisor.route(inp)
            assert out.route == RouteType.CODER

        # 4th call exceeds max_loops_per_turn=3
        inp_excess = SupervisorInput(
            session_id=session_id,
            user_id="user-1",
            text="write a python script",
        )
        out_capped = await supervisor.route(inp_excess)
        assert out_capped.route == RouteType.CONVERSATION
        assert "exceeded" in out_capped.rationale

    asyncio.run(_run())
