"""Base Tool protocol and interface per AGENTS.md contract."""

from abc import ABC, abstractmethod
from typing import Any
from orchestrator.core.models import RiskLevel


class Tool(ABC):
    """Abstract base class that all HINA tools must implement."""

    name: str
    description: str
    input_schema: dict[str, Any]
    risk_level: RiskLevel = RiskLevel.LOW
    requires_confirmation: bool = False

    @abstractmethod
    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute tool logic asynchronously with validated payload."""
        ...
