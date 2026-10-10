"""Coder Agent implementing the 7-step autonomous development and repair flow."""

from dataclasses import dataclass
from orchestrator.core.models import SandboxExecutionResult
from orchestrator.providers.base import LLMMessage, LLMProvider
from orchestrator.sandbox.base import SandboxAdapter
from orchestrator.sandbox.static_checker import StaticSecurityChecker

CODER_SYSTEM_PROMPT = """You are the Coder Agent for HINA.
Your job is to generate Python code to fulfill user programming tasks.

Rules:
1. Output ONLY runnable, clean Python code. Do not wrap in conversational chit-chat.
2. If code blocks are needed, format inside standard ```python ... ``` fences.
3. NEVER write code attempting to access host credentials, files outside sandbox, or unauthorized network resources.
"""

REPAIR_PROMPT_TEMPLATE = """The previous Python code failed execution in the isolated sandbox.
Execution status: {status}
Exit code: {exit_code}
Stderr / Errors:
{stderr}

Previous code:
```python
{code}
```

Please analyze the error and output repaired Python code that resolves the issue.
Output ONLY the repaired Python code.
"""


@dataclass
class CoderRunResult:
    task: str
    final_code: str
    execution_result: SandboxExecutionResult
    repairs_attempted: int
    success: bool


class CoderAgent:
    """Autonomous Coder Agent with static security verification and up to 2x repair attempts."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        sandbox: SandboxAdapter,
        max_repairs: int = 2,
    ) -> None:
        self.llm_provider = llm_provider
        self.sandbox = sandbox
        self.max_repairs = max_repairs

    def _extract_code(self, raw_text: str) -> str:
        """Extract code from markdown code fences if present."""
        if "```python" in raw_text:
            parts = raw_text.split("```python")
            return parts[1].split("```")[0].strip()
        elif "```" in raw_text:
            parts = raw_text.split("```")
            return parts[1].split("```")[0].strip()
        return raw_text.strip()

    async def run(
        self,
        task_description: str,
        timeout_ms: int = 5000,
        network: str = "disabled",
    ) -> CoderRunResult:
        # Step 1: Understand task and generate initial code
        prompt = f"Task: {task_description}\nWrite Python code to solve this task."
        raw_output = await self.llm_provider.generate_text(
            prompt=prompt,
            system_prompt=CODER_SYSTEM_PROMPT,
            temperature=0.1,
        )
        current_code = self._extract_code(raw_output)

        repairs_attempted = 0

        # Step 2-6: Execution and repair loop
        while True:
            # Step 3: Static policy check
            static_check = StaticSecurityChecker.check(current_code, network=network)
            if not static_check.passed:
                exec_result = SandboxExecutionResult(
                    status="error",
                    stdout="",
                    stderr="Static security check failed:\n" + "\n".join(static_check.violations),
                    exit_code=1,
                    execution_time_ms=0,
                )
            else:
                # Step 4: Execute in sandbox
                exec_result = await self.sandbox.execute(
                    code=current_code,
                    timeout_ms=timeout_ms,
                    network=network,
                )

            # Step 5: Inspect stdout/stderr and exit_code
            if exec_result.status == "success" and exec_result.exit_code == 0:
                # Execution succeeded
                return CoderRunResult(
                    task=task_description,
                    final_code=current_code,
                    execution_result=exec_result,
                    repairs_attempted=repairs_attempted,
                    success=True,
                )

            # Check if repair budget is exhausted
            if repairs_attempted >= self.max_repairs:
                return CoderRunResult(
                    task=task_description,
                    final_code=current_code,
                    execution_result=exec_result,
                    repairs_attempted=repairs_attempted,
                    success=False,
                )

            # Step 6: Trigger repair attempt
            repairs_attempted += 1
            repair_prompt = REPAIR_PROMPT_TEMPLATE.format(
                status=exec_result.status,
                exit_code=exec_result.exit_code,
                stderr=exec_result.stderr,
                code=current_code,
            )

            repair_output = await self.llm_provider.generate_text(
                prompt=repair_prompt,
                system_prompt=CODER_SYSTEM_PROMPT,
                temperature=0.1,
            )
            current_code = self._extract_code(repair_output)
