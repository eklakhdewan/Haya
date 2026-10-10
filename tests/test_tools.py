"""Tests for Tool abstraction, Registry, and built-in tools."""

import asyncio
import pytest

from orchestrator.core.errors import InvalidSchemaError
from orchestrator.tools.builtin import CalculatorTool, TimeTool
from orchestrator.tools.registry import ToolRegistry


def test_calculator_tool_eval() -> None:
    async def _run() -> None:
        calc = CalculatorTool()
        res1 = await calc.execute({"expression": "2 + 2"})
        assert res1["result"] == 4

        res2 = await calc.execute({"expression": "(10 * 5) - (20 / 4)"})
        assert res2["result"] == 45.0

        res3 = await calc.execute({"expression": "2 ** 8"})
        assert res3["result"] == 256

        # Division by zero
        res4 = await calc.execute({"expression": "10 / 0"})
        assert res4["error"] == "Division by zero in calculation"
        assert res4["result"] is None

        # Invalid syntax
        with pytest.raises(InvalidSchemaError):
            await calc.execute({"expression": "invalid syntax +++"})

    asyncio.run(_run())


def test_time_tool() -> None:
    async def _run() -> None:
        time_tool = TimeTool()
        res = await time_tool.execute({})
        assert "utc_date" in res
        assert "utc_time" in res
        assert "timestamp" in res
        assert "iso" in res

    asyncio.run(_run())


def test_tool_registry() -> None:
    async def _run() -> None:
        registry = ToolRegistry()
        calc = CalculatorTool()
        time_tool = TimeTool()

        registry.register(calc)
        registry.register(time_tool)

        # Duplicate register should raise ValueError
        with pytest.raises(ValueError):
            registry.register(calc)

        # List tools
        tools_meta = registry.list_tools()
        names = [t["name"] for t in tools_meta]
        assert "calculator" in names
        assert "current_time" in names

        # Execute through registry
        calc_out = await registry.execute("calculator", {"expression": "100 / 4"})
        assert calc_out["result"] == 25.0

        # Non-existent tool
        with pytest.raises(InvalidSchemaError):
            await registry.execute("unknown_tool", {})

        # Missing required parameter
        with pytest.raises(InvalidSchemaError):
            await registry.execute("calculator", {})

    asyncio.run(_run())
