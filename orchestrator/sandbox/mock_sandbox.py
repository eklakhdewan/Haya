"""Deterministic mock sandbox for offline tests.

This adapter interprets a restricted Python subset. It is not a secure
general-purpose execution environment; use the isolated E2B adapter for
real code execution.
"""

import ast
import operator
import time
from typing import Any
from uuid import uuid4

from orchestrator.core.models import SandboxExecutionResult
from orchestrator.sandbox.base import SandboxAdapter
from orchestrator.sandbox.static_checker import StaticSecurityChecker

_BINARY_OPERATORS: dict[type[ast.operator], Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_COMPARE_OPERATORS: dict[type[ast.cmpop], Any] = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}


class _ReturnSignal(Exception):
    def __init__(self, value: Any) -> None:
        self.value = value


class _MockInterpreter:
    """Interpreter for a small, explicitly supported Python subset."""

    MAX_STEPS = 10_000
    MAX_CALL_DEPTH = 50

    def __init__(self) -> None:
        self.output: list[str] = []
        self.functions: dict[str, ast.FunctionDef] = {}
        self.steps = 0
        self.depth = 0

    def _step(self) -> None:
        self.steps += 1
        if self.steps > self.MAX_STEPS:
            raise TimeoutError("Mock execution step limit exceeded")

    def run(self, source: str) -> str:
        tree = ast.parse(source, mode="exec")

        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                self.functions[node.name] = node

        environment: dict[str, Any] = {}
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef):
                self._statement(node, environment)

        return "".join(self.output)

    def _statement(self, node: ast.stmt, env: dict[str, Any]) -> None:
        self._step()

        if isinstance(node, ast.Assign):
            value = self._expression(node.value, env)
            for target in node.targets:
                if not isinstance(target, ast.Name):
                    raise ValueError("Only simple variable assignments are supported")
                env[target.id] = value
            return

        if isinstance(node, ast.Expr):
            self._expression(node.value, env)
            return

        if isinstance(node, ast.If):
            branch = node.body if self._expression(node.test, env) else node.orelse
            for statement in branch:
                self._statement(statement, env)
            return

        if isinstance(node, ast.Return):
            raise _ReturnSignal(self._expression(node.value, env) if node.value else None)

        if isinstance(node, ast.Raise):
            if not isinstance(node.exc, ast.Call):
                raise ValueError("Only explicit exception constructors are supported")
            if not isinstance(node.exc.func, ast.Name):
                raise ValueError("Unsupported exception constructor")
            message = str(self._expression(node.exc.args[0], env)) if node.exc.args else ""
            if node.exc.func.id == "ValueError":
                raise ValueError(message)
            if node.exc.func.id == "TypeError":
                raise TypeError(message)
            raise ValueError("Unsupported exception type")

        if isinstance(node, ast.Pass):
            return

        raise ValueError(f"Unsupported statement: {type(node).__name__}")

    def _expression(self, node: ast.expr, env: dict[str, Any]) -> Any:
        self._step()

        if isinstance(node, ast.Constant):
            if isinstance(node.value, (str, int, float, bool, type(None))):
                return node.value
            raise ValueError("Unsupported constant")

        if isinstance(node, ast.Name):
            if node.id in env:
                return env[node.id]
            if node.id in {"ValueError", "TypeError"}:
                return node.id
            raise NameError(f"Name '{node.id}' is not defined")

        if isinstance(node, ast.List):
            return [self._expression(item, env) for item in node.elts]

        if isinstance(node, ast.Tuple):
            return tuple(self._expression(item, env) for item in node.elts)

        if isinstance(node, ast.Subscript):
            container = self._expression(node.value, env)
            index = self._expression(node.slice, env)
            return container[index]

        if isinstance(node, ast.BinOp):
            operation = _BINARY_OPERATORS.get(type(node.op))
            if operation is None:
                raise ValueError("Unsupported arithmetic operator")
            left = self._expression(node.left, env)
            right = self._expression(node.right, env)
            if isinstance(node.op, ast.Pow) and abs(right) > 100:
                raise ValueError("Exponent exceeds mock execution limit")
            result = operation(left, right)
            if isinstance(result, (int, float)) and abs(result) > 10**100:
                raise ValueError("Numeric result exceeds mock execution limit")
            return result

        if isinstance(node, ast.UnaryOp):
            value = self._expression(node.operand, env)
            if isinstance(node.op, ast.USub):
                return -value
            if isinstance(node.op, ast.UAdd):
                return +value
            if isinstance(node.op, ast.Not):
                return not value
            raise ValueError("Unsupported unary operator")

        if isinstance(node, ast.Compare):
            left = self._expression(node.left, env)
            for operation_node, comparator in zip(node.ops, node.comparators, strict=True):
                operation = _COMPARE_OPERATORS.get(type(operation_node))
                if operation is None:
                    raise ValueError("Unsupported comparison")
                right = self._expression(comparator, env)
                if not operation(left, right):
                    return False
                left = right
            return True

        if isinstance(node, ast.IfExp):
            branch = node.body if self._expression(node.test, env) else node.orelse
            return self._expression(branch, env)

        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("Only direct function calls are supported")

            name = node.func.id
            args = [self._expression(arg, env) for arg in node.args]

            if name == "print":
                self.output.append(" ".join(map(str, args)) + "\n")
                return None

            if name == "range":
                if len(args) > 3 or not all(type(arg) is int for arg in args):
                    raise ValueError("Unsupported range arguments")
                result = range(*args)
                if len(result) > 1000:
                    raise ValueError("Range exceeds mock execution limit")
                return result

            builtins: dict[str, Any] = {
                "len": len,
                "int": int,
                "float": float,
                "str": str,
                "bool": bool,
                "list": list,
                "tuple": tuple,
                "sum": sum,
                "min": min,
                "max": max,
                "abs": abs,
                "round": round,
            }
            if name in builtins:
                return builtins[name](*args)

            function = self.functions.get(name)
            if function is None:
                raise NameError(f"Function '{name}' is not defined")

            if self.depth >= self.MAX_CALL_DEPTH:
                raise RecursionError("Mock function call depth exceeded")

            parameters = [arg.arg for arg in function.args.args]
            if len(args) != len(parameters):
                raise TypeError(f"{name} received the wrong number of arguments")

            local_env = dict(zip(parameters, args, strict=True))
            self.depth += 1
            try:
                for statement in function.body:
                    self._statement(statement, local_env)
            except _ReturnSignal as signal:
                return signal.value
            finally:
                self.depth -= 1
            return None

        raise ValueError(f"Unsupported expression: {type(node).__name__}")


class MockSandboxAdapter(SandboxAdapter):
    """Deterministic test adapter; not a real isolation boundary."""

    def __init__(self) -> None:
        self._forced_responses: dict[str, SandboxExecutionResult] = {}
        self._simulate_timeout = False

    def force_response(self, code_substring: str, result: SandboxExecutionResult) -> None:
        """Register a canned result for testing repair and error handling."""
        self._forced_responses[code_substring] = result

    def set_simulate_timeout(self, timeout: bool) -> None:
        self._simulate_timeout = timeout

    async def execute(
        self,
        code: str,
        timeout_ms: int = 5000,
        network: str = "disabled",
    ) -> SandboxExecutionResult:
        execution_id = str(uuid4())
        check = StaticSecurityChecker.check(code, network=network)

        if not check.passed:
            return SandboxExecutionResult(
                execution_id=execution_id,
                status="error",
                stdout="",
                stderr="\n".join(check.violations),
                exit_code=1,
                execution_time_ms=10,
            )

        if self._simulate_timeout:
            return SandboxExecutionResult(
                execution_id=execution_id,
                status="timeout",
                stdout="",
                stderr=f"Execution timed out after {timeout_ms} ms",
                exit_code=124,
                execution_time_ms=timeout_ms,
            )

        for substring, result in self._forced_responses.items():
            if substring in code:
                return result

        started = time.monotonic()
        interpreter = _MockInterpreter()

        try:
            stdout = interpreter.run(code)
            elapsed_ms = max(1, int((time.monotonic() - started) * 1000))
            return SandboxExecutionResult(
                execution_id=execution_id,
                status="success",
                stdout=stdout,
                stderr="",
                exit_code=0,
                execution_time_ms=elapsed_ms,
            )
        except Exception as exc:
            elapsed_ms = max(1, int((time.monotonic() - started) * 1000))
            return SandboxExecutionResult(
                execution_id=execution_id,
                status="error",
                stdout="".join(interpreter.output),
                stderr=f"{type(exc).__name__}: {exc}",
                exit_code=1,
                execution_time_ms=elapsed_ms,
            )
