"""E2B isolated microVM sandbox adapter."""

import os
from uuid import uuid4

from orchestrator.core.errors import ProviderUnavailableError
from orchestrator.core.models import SandboxExecutionResult
from orchestrator.sandbox.base import SandboxAdapter
from orchestrator.sandbox.static_checker import StaticSecurityChecker


class E2BSandboxAdapter(SandboxAdapter):
    """Adapter executing code inside an external, isolated E2B microVM sandbox."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("E2B_API_KEY", "")

    async def execute(
        self,
        code: str,
        timeout_ms: int = 5000,
        network: str = "disabled",
    ) -> SandboxExecutionResult:
        # Pre-flight static policy check
        check = StaticSecurityChecker.check(code, network=network)
        if not check.passed:
            return SandboxExecutionResult(
                execution_id=str(uuid4()),
                status="error",
                stdout="",
                stderr="\n".join(check.violations),
                exit_code=1,
                execution_time_ms=5,
            )

        if not self.api_key:
            raise ProviderUnavailableError(
                "E2B_API_KEY is not configured. Configure E2B_API_KEY or use MockSandboxAdapter."
            )

        try:
            from e2b_code_interpreter import Sandbox  # type: ignore[import-not-found]

            # Convert ms to seconds for E2B timeout
            timeout_s = max(1, timeout_ms // 1000)

            with Sandbox(api_key=self.api_key, timeout=timeout_s) as sandbox:
                execution = sandbox.run_code(code)
                stdout_text = "\n".join([str(log) for log in execution.logs.stdout])
                stderr_text = "\n".join([str(log) for log in execution.logs.stderr])

                if execution.error:
                    stderr_text += f"\n{execution.error.name}: {execution.error.value}"

                return SandboxExecutionResult(
                    execution_id=str(uuid4()),
                    status="error" if execution.error else "success",
                    stdout=stdout_text,
                    stderr=stderr_text,
                    exit_code=1 if execution.error else 0,
                    execution_time_ms=timeout_ms // 2,
                )
        except ImportError:
            raise ProviderUnavailableError(
                "e2b-code-interpreter is not installed. Install via pip install e2b-code-interpreter."
            )
        except Exception as e:
            return SandboxExecutionResult(
                execution_id=str(uuid4()),
                status="error",
                stdout="",
                stderr=f"E2B microVM error: {e}",
                exit_code=1,
                execution_time_ms=0,
            )
