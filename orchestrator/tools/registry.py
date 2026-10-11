"""Tool registry for registering, discovering, and dispatching tool executions."""

from typing import Any

from jsonschema import SchemaError, ValidationError, validate

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
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
                "risk_level": tool.risk_level.value,
                "requires_confirmation": tool.requires_confirmation,
            }
            for tool in self._tools.values()
        ]

    async def execute(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Validate a complete JSON Schema before invoking a tool."""
        tool = self.get(tool_name)
        if tool is None:
            raise InvalidSchemaError(f"Tool '{tool_name}' not found in registry.")
        try:
            validate(instance=payload, schema=tool.input_schema)
        except (ValidationError, SchemaError) as exc:
            reason = exc.message if isinstance(exc, ValidationError) else "invalid tool schema"
            raise InvalidSchemaError(f"Invalid payload for tool '{tool_name}': {reason}") from exc
        result = await tool.execute(payload)
        if not isinstance(result, dict):
            raise InvalidSchemaError(f"Tool '{tool_name}' returned an invalid result type.")
        return result
