"""Tool registry for registering, discovering, and dispatching tool executions."""

from typing import Any

from orchestrator.core.errors import InvalidSchemaError
from orchestrator.tools.base import Tool


class ToolRegistry:
    """Central registry of executable agent tools."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool instance."""
        if tool.name in self._tools:
            raise ValueError(f"Tool with name '{tool.name}' is already registered.")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        """Retrieve a registered tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[dict[str, Any]]:
        """Return list of tool metadata schemas for LLM function calling."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
                "risk_level": t.risk_level.value,
                "requires_confirmation": t.requires_confirmation,
            }
            for t in self._tools.values()
        ]

    async def execute(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool with input schema validation."""
        tool = self.get(tool_name)
        if not tool:
            raise InvalidSchemaError(f"Tool '{tool_name}' not found in registry.")

        # Basic schema check for required fields if defined in input_schema
        required_fields = tool.input_schema.get("required", [])
        for field in required_fields:
            if field not in payload:
                raise InvalidSchemaError(
                    f"Missing required parameter '{field}' for tool '{tool_name}'"
                )

        return await tool.execute(payload)
