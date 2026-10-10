"""Built-in deterministic tools for Hina: Calculator and Time."""

import ast
import operator
from datetime import datetime, timezone
from collections.abc import Callable
from typing import Any, TypeAlias

from orchestrator.core.errors import InvalidSchemaError
from orchestrator.core.models import RiskLevel
from orchestrator.tools.base import Tool


NumericOperator: TypeAlias = Callable[[float | int, float | int], float | int]
UnaryOperator: TypeAlias = Callable[[float | int], float | int]


class CalculatorTool(Tool):
    """Safely evaluates basic arithmetic expressions using AST parsing without eval()."""

    name = "calculator"
    description = "Evaluates basic mathematical expressions (+, -, *, /, **, %)."
    risk_level = RiskLevel.LOW
    requires_confirmation = False
    input_schema = {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "Mathematical expression (e.g. '2 + 2' or '(15 * 3) / 2')",
            }
        },
        "required": ["expression"],
    }

    _BINARY_OPERATORS: dict[type[ast.operator], NumericOperator] = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.Mod: operator.mod,
    }
    _UNARY_OPERATORS: dict[type[ast.unaryop], UnaryOperator] = {
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    def _eval_node(self, node: ast.AST) -> float | int:
        if isinstance(node, ast.Expression):
            return self._eval_node(node.body)
        elif isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        elif isinstance(node, ast.BinOp):
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            op_type = type(node.op)
            if op_type in self._BINARY_OPERATORS:
                if op_type == ast.Div and right == 0:
                    raise ZeroDivisionError("Division by zero in calculation")
                return self._BINARY_OPERATORS[op_type](left, right)
            raise ValueError(f"Unsupported binary operator: {op_type.__name__}")
        elif isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand)
            op_type = type(node.op)
            if op_type in self._UNARY_OPERATORS:
                return self._UNARY_OPERATORS[op_type](operand)
            raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
        raise ValueError(f"Unsupported expression node: {type(node).__name__}")

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        expr = str(payload.get("expression", "")).strip()
        if not expr:
            raise InvalidSchemaError("Expression cannot be empty")

        try:
            tree = ast.parse(expr, mode="eval")
            result = self._eval_node(tree)
            return {"expression": expr, "result": result}
        except ZeroDivisionError as e:
            return {"expression": expr, "error": str(e), "result": None}
        except Exception as e:
            raise InvalidSchemaError(f"Failed to calculate expression: {e}")


class TimeTool(Tool):
    """Provides current UTC time and formatted timestamps."""

    name = "current_time"
    description = "Provides the current UTC date, time, and timestamp."
    risk_level = RiskLevel.LOW
    requires_confirmation = False
    input_schema = {
        "type": "object",
        "properties": {},
    }

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        return {
            "iso": now.isoformat(),
            "timestamp": now.timestamp(),
            "utc_date": now.strftime("%Y-%m-%d"),
            "utc_time": now.strftime("%H:%M:%S UTC"),
        }
