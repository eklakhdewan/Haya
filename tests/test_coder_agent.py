"""Tests for Coder Agent 7-step execution and repair lifecycle."""

import asyncio

from orchestrator.agents.coder import CoderAgent
from orchestrator.providers.mock_llm import MockLLMProvider
from orchestrator.sandbox.mock_sandbox import MockSandboxAdapter


def test_coder_agent_direct_success() -> None:
    async def _run() -> None:
        llm = MockLLMProvider()
        sandbox = MockSandboxAdapter()
        coder = CoderAgent(llm_provider=llm, sandbox=sandbox, max_repairs=2)

        # Register successful Python code response
        llm.register_text_response(
            "fibonacci",
            "```python\ndef fib(n):\n    return n if n <= 1 else fib(n-1) + fib(n-2)\n"
            "print(fib(5))\n```",
        )

        result = await coder.run("Write a fibonacci function", timeout_ms=3000)
        assert result.success is True
        assert result.repairs_attempted == 0
        assert "fib" in result.final_code
        assert result.execution_result.status == "success"
        assert result.execution_result.stdout.strip() == "5"

    asyncio.run(_run())


def test_coder_agent_repair_loop_success() -> None:
    async def _run() -> None:
        llm = MockLLMProvider()
        sandbox = MockSandboxAdapter()
        coder = CoderAgent(llm_provider=llm, sandbox=sandbox, max_repairs=2)

        # 1st attempt has a bug (IndexError)
        llm.register_text_response(
            "buggy list",
            "```python\nitems = [1, 2, 3]\nprint(items[10])\n```",
        )

        # 2nd attempt (repair) fixes the bug
        llm.register_text_response(
            "indexerror",
            "```python\nitems = [1, 2, 3]\nprint(items[0])\n```",
        )

        result = await coder.run("Write buggy list indexing", timeout_ms=3000)
        assert result.success is True
        assert result.repairs_attempted == 1
        assert result.execution_result.status == "success"
        assert result.execution_result.stdout.strip() == "1"

    asyncio.run(_run())


def test_coder_agent_caps_repairs_at_max() -> None:
    async def _run() -> None:
        llm = MockLLMProvider()
        sandbox = MockSandboxAdapter()
        coder = CoderAgent(llm_provider=llm, sandbox=sandbox, max_repairs=2)

        # Always return failing code
        llm.register_text_response(
            "always fail",
            "```python\nraise ValueError('Persistent error')\n```",
        )
        llm.register_text_response(
            "persistent error",
            "```python\nraise ValueError('Persistent error 2')\n```",
        )

        result = await coder.run("Task that will always fail", timeout_ms=3000)
        assert result.success is False
        assert result.repairs_attempted == 2
        assert result.execution_result.status == "error"

    asyncio.run(_run())
