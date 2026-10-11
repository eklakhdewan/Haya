"""Fail-closed behavior tests for the external sandbox adapter."""

import pytest

from orchestrator.core.errors import PolicyDeniedError, ProviderUnavailableError
from orchestrator.sandbox.e2b_adapter import E2BSandboxAdapter


@pytest.mark.asyncio
async def test_e2b_missing_credentials_fails_closed() -> None:
    adapter = E2BSandboxAdapter(api_key="")
    with pytest.raises(ProviderUnavailableError, match="will not fall back"):
        await adapter.execute("print(1 + 1)", timeout_ms=3000, network="disabled")


@pytest.mark.asyncio
async def test_e2b_rejects_network_enabled_execution_before_provider_call() -> None:
    adapter = E2BSandboxAdapter(api_key="test-key")
    with pytest.raises(PolicyDeniedError, match="Network-enabled"):
        await adapter.execute("print(1 + 1)", timeout_ms=3000, network="enabled")


@pytest.mark.asyncio
async def test_e2b_invalid_timeout_is_rejected() -> None:
    adapter = E2BSandboxAdapter(api_key="test-key")
    with pytest.raises(PolicyDeniedError, match="timeout"):
        await adapter.execute("print(1 + 1)", timeout_ms=100, network="disabled")
