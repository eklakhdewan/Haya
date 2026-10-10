"""Abstract base interface for code execution sandboxes."""

from abc import ABC, abstractmethod

from orchestrator.core.models import SandboxExecutionResult


class SandboxAdapter(ABC):
    """Abstract interface for isolated microVM code execution environments."""

    @abstractmethod
    async def execute(
        self,
        code: str,
        timeout_ms: int = 5000,
        network: str = "disabled",
    ) -> SandboxExecutionResult:
        """Execute code in an isolated microVM sandbox."""
        ...
