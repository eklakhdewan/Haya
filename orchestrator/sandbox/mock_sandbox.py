"""Mock sandbox adapter for offline testing without cloud microVM dependencies."""

import io
from contextlib import redirect_stderr, redirect_stdout
from uuid import uuid4

from orchestrator.core.models import SandboxExecutionResult
from orchestrator.sandbox.base import SandboxAdapter
from orchestrator.sandbox.static_checker import StaticSecurityChecker


class MockSandboxAdapter(SandboxAdapter):
    """Deterministic, isolated test sandbox that simulates microVM execution."""

    def __init__(self) -> None:
        self._forced_responses: dict[str, SandboxExecutionResult] = {}
        self._simulate_timeout: bool = False

    def force_response(self, code_substring: str, result: SandboxExecutionResult) -> None:
        """Register a canned execution result for testing repair loops and error handling."""
        self._forced_responses[code_substring] = result

    def set_simulate_timeout(self, timeout: bool) -> None:
        self._simulate_timeout = timeout

    async def execute(
        self,
        code: str,
        timeout_ms: int = 5000,
        network: str = "disabled",
    ) -> SandboxExecutionResult:
        # Check static policy first
        check_result = StaticSecurityChecker.check(code, network=network)
        if not check_result.passed:
            return SandboxExecutionResult(
                execution_id=str(uuid4()),
                status="error",
                stdout="",
                stderr="\n".join(check_result.violations),
                exit_code=1,
                execution_time_ms=10,
            )

        if self._simulate_timeout:
            return SandboxExecutionResult(
                execution_id=str(uuid4()),
                status="timeout",
                stdout="",
                stderr=f"Execution timed out after {timeout_ms} ms",
                exit_code=124,
                execution_time_ms=timeout_ms,
            )

        # Check for preset canned responses
        for sub, res in self._forced_responses.items():
            if sub in code:
                return res

        # Pure sandbox simulation: execute in an empty, sandboxed global namespace
        # with no __import__, no builtins that touch disk/network
        safe_builtins = {
            "print": print,
            "range": range,
            "len": len,
            "int": int,
            "float": float,
            "str": str,
            "bool": bool,
            "list": list,
            "dict": dict,
            "set": set,
            "tuple": tuple,
            "sum": sum,
            "min": min,
            "max": max,
            "sorted": sorted,
            "abs": abs,
            "round": round,
            "enumerate": enumerate,
            "zip": zip,
            "Exception": Exception,
            "ValueError": ValueError,
            "TypeError": TypeError,
            "IndexError": IndexError,
            "KeyError": KeyError,
        }

        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        isolated_globals = {"__builtins__": safe_builtins}

        try:
            with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
                exec(code, isolated_globals)  # Safe execution with strictly stripped builtins

            return SandboxExecutionResult(
                execution_id=str(uuid4()),
                status="success",
                stdout=stdout_buf.getvalue(),
                stderr=stderr_buf.getvalue(),
                exit_code=0,
                execution_time_ms=35,
            )
        except Exception as e:
            return SandboxExecutionResult(
                execution_id=str(uuid4()),
                status="error",
                stdout=stdout_buf.getvalue(),
                stderr=f"{type(e).__name__}: {e}",
                exit_code=1,
                execution_time_ms=20,
            )
