"""E2B isolated microVM sandbox adapter; fails closed when isolation is unavailable."""
import math
import os
import time
from uuid import uuid4

from orchestrator.core.errors import PolicyDeniedError, ProviderUnavailableError
from orchestrator.core.models import SandboxExecutionResult
from orchestrator.sandbox.base import SandboxAdapter
from orchestrator.sandbox.static_checker import StaticSecurityChecker


class E2BSandboxAdapter(SandboxAdapter):
    """Execute untrusted code only in an external E2B microVM."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("E2B_API_KEY", "")

    async def execute(
        self,
        code: str,
        timeout_ms: int = 5000,
        network: str = "disabled",
    ) -> SandboxExecutionResult:
        started = time.monotonic()
        if not 500 <= timeout_ms <= 60_000:
            raise PolicyDeniedError("Sandbox timeout must be between 500 and 60000 milliseconds.")
        # Egress is denied until a real provider-level network policy is implemented.
        # AST checks are defense-in-depth only, never a sandbox boundary.
        if network != "disabled":
            raise PolicyDeniedError("Network-enabled sandbox execution is disabled by security policy.")

        check = StaticSecurityChecker.check(code, network="disabled")
        if not check.passed:
            return SandboxExecutionResult(
                execution_id=str(uuid4()),
                status="error",
                stdout="",
                stderr="\n".join(check.violations),
                exit_code=1,
                execution_time_ms=max(0, int((time.monotonic() - started) * 1000)),
            )

        if not self.api_key:
            raise ProviderUnavailableError(
                "Isolated execution is unavailable: configure E2B_API_KEY. "
                "The API will not fall back to in-process execution."
            )

        try:
            from e2b_code_interpreter import Sandbox  # type: ignore[import-not-found]

            timeout_s = max(1, math.ceil(timeout_ms / 1000))
            with Sandbox(api_key=self.api_key, timeout=timeout_s) as sandbox:
                execution = sandbox.run_code(code)
                stdout_text = "\n".join(str(log) for log in execution.logs.stdout)
                stderr_text = "\n".join(str(log) for log in execution.logs.stderr)
                if execution.error:
                    stderr_text += f"\n{execution.error.name}: {execution.error.value}"

                return SandboxExecutionResult(
                    execution_id=str(uuid4()),
                    status="error" if execution.error else "success",
                    stdout=stdout_text,
                    stderr=stderr_text,
                    exit_code=1 if execution.error else 0,
                    execution_time_ms=max(0, int((time.monotonic() - started) * 1000)),
                )
        except ImportError as exc:
            raise ProviderUnavailableError(
                "Isolated execution is unavailable: install e2b-code-interpreter."
            ) from exc
        except Exception as exc:
            error_type = type(exc).__name__
            is_timeout = "timeout" in error_type.lower() or "timed out" in str(exc).lower()
            return SandboxExecutionResult(
                execution_id=str(uuid4()),
                status="timeout" if is_timeout else "error",
                stdout="",
                stderr="Sandbox execution timed out." if is_timeout else f"Sandbox provider failed ({error_type}).",
                exit_code=124 if is_timeout else 1,
                execution_time_ms=max(0, int((time.monotonic() - started) * 1000)),
            )
